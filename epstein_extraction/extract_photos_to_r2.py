#!/usr/bin/env python3
"""
Extract Real Photos from PDFs and Upload to Cloudflare R2

Iterates through PDF files in a dataset, extracts embedded images using PyMuPDF,
classifies each image using OpenCV heuristics to separate real photos from document
scans, and uploads photos directly to Cloudflare R2.

Usage:
    python extract_photos_to_r2.py --dataset DataSet_1 --dry-run
    python extract_photos_to_r2.py --dataset DataSet_1 --workers 4
    python extract_photos_to_r2.py --dataset DataSet_1 --resume-from EFTA00001000
"""

import argparse
import hashlib
import io
import multiprocessing
import os
import queue as queue_module
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import cv2
import fitz  # PyMuPDF
import numpy as np
from loguru import logger
from sqlalchemy import text

# Add parent dir so we can import config/models
sys.path.insert(0, str(Path(__file__).parent))
from config import SessionLocal

# ============================================
# CONFIGURATION
# ============================================

# R2 credentials (same as appsettings.json)
R2_ACCOUNT_ID = "f8370fa3403bc68c2a46a3ad87be970d"
R2_ACCESS_KEY_ID = "ae0a78c0037d7ac13df823d2e085777c"
R2_SECRET_ACCESS_KEY = "6aed78ea947b634aa80d78b3d7d976493c1926501eecd77e4faa0691bc85faa2"
R2_BUCKET_NAME = "epsteinfiles"

# Dataset paths - local directories containing PDF files
DATASET_PATHS = {
    "DataSet_1": Path(r"D:\Personal\Epstein\data\files\DataSet_1"),
    "DataSet_2": Path(r"D:\Personal\Epstein\data\files\DataSet_2"),
    "DataSet_3": Path(r"D:\Personal\Epstein\data\files\DataSet_3"),
    "DataSet_4": Path(r"D:\Personal\Epstein\data\files\DataSet_4"),
    "DataSet_5": Path(r"D:\Personal\Epstein\data\files\DataSet_5"),
    "DataSet_6": Path(r"D:\Personal\Epstein\data\files\DataSet_6"),
    "DataSet_7": Path(r"D:\Personal\Epstein\data\files\DataSet_7"),
    "DataSet_8": Path(r"D:\Personal\Epstein\data\files\DataSet_8"),
    "DataSet_9": Path(r"D:\Personal\Epstein\data\files\DataSet_9"),
    "DataSet_10": Path(r"D:\Personal\Epstein\data\files\DataSet_10"),
    "DataSet_11": Path(r"D:\Personal\Epstein\data\files\DataSet_11"),
    "DataSet_12": Path(r"D:\Personal\Epstein\data\files\DataSet_12"),
}

# Minimum image dimensions to consider (skip tiny icons/artifacts)
MIN_WIDTH = 50
MIN_HEIGHT = 50

# Document classifier threshold: score >= this means "document scan" (skip)
# 6 is more permissive than the original 5, avoiding false positives on B&W photos
DOCUMENT_SCORE_THRESHOLD = 6

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <level>{message}</level>",
)
logger.add(
    Path(__file__).parent.parent / "extraction_output" / "logs" / "extract_photos_{time:YYYY-MM-DD}.log",
    rotation="100 MB",
    retention="30 days",
    level="DEBUG",
)


# ============================================
# R2 CLIENT
# ============================================

def create_r2_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def upload_to_r2(s3_client, bucket: str, key: str, data: bytes, content_type: str) -> bool:
    """Upload bytes to R2. Returns True on success."""
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return True
    except Exception as e:
        logger.error(f"R2 upload failed for {key}: {e}")
        return False


# ============================================
# IMAGE CLASSIFICATION (OpenCV Heuristics)
# ============================================

MAX_CLASSIFY_DIM = 800  # Downscale images larger than this for classification


def calculate_metrics(image: np.ndarray) -> dict:
    """Calculate image metrics for document vs photo classification.

    Replicates logic from run_vision_analysis.py DocumentClassifier._calculate_metrics()
    but works on in-memory numpy arrays instead of file paths.
    """
    # Downscale large images to limit memory usage (classification doesn't need full res)
    h_orig, w_orig = image.shape[:2]
    if max(h_orig, w_orig) > MAX_CLASSIFY_DIM:
        scale = MAX_CLASSIFY_DIM / max(h_orig, w_orig)
        image = cv2.resize(image, (int(w_orig * scale), int(h_orig * scale)), interpolation=cv2.INTER_AREA)

    if len(image.shape) == 2:
        gray = image
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape
    # Use original dimensions for aspect ratio (more accurate)
    aspect_ratio_h, aspect_ratio_w = h_orig, w_orig

    # Aspect ratio (height / width) - documents are usually portrait
    aspect_ratio = aspect_ratio_h / aspect_ratio_w if aspect_ratio_w > 0 else 1

    # Color variance via saturation channel
    if len(image.shape) == 3 and image.shape[2] >= 3:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1]
        color_variance = float(np.std(saturation))
    else:
        color_variance = 0.0

    # White space ratio
    white_pixels = np.sum(gray > 240)
    white_ratio = float(white_pixels / (h * w))

    # Text-like region density
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
    dilated = cv2.dilate(binary, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    text_contours = 0
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw > ch * 2 and cw > 20:
            text_contours += 1

    text_density = text_contours / (h * w / 10000) if h * w > 0 else 0

    # Horizontal line density (forms, tables)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    line_density = float(np.sum(horizontal_lines > 0) / (h * w))

    return {
        "aspect_ratio": aspect_ratio,
        "color_variance": color_variance,
        "white_ratio": white_ratio,
        "text_density": text_density,
        "line_density": line_density,
    }


def is_document_scan(metrics: dict) -> tuple[bool, int]:
    """Score-based document detection. Returns (is_document, score).

    Replicates logic from run_vision_analysis.py DocumentClassifier._is_document().
    Score >= DOCUMENT_SCORE_THRESHOLD means it's a document scan.
    """
    score = 0

    # Documents tend to be portrait orientation (1.2-1.6 aspect ratio)
    if 1.2 < metrics["aspect_ratio"] < 1.6:
        score += 2
    elif metrics["aspect_ratio"] > 1.0:
        score += 1

    # Low color variance suggests document
    if metrics["color_variance"] < 30:
        score += 2
    elif metrics["color_variance"] < 50:
        score += 1

    # High white ratio suggests document
    if metrics["white_ratio"] > 0.6:
        score += 2
    elif metrics["white_ratio"] > 0.4:
        score += 1

    # Text density
    if metrics["text_density"] > 0.5:
        score += 2
    elif metrics["text_density"] > 0.2:
        score += 1

    # Line density (forms, tables)
    if metrics["line_density"] > 0.01:
        score += 1

    return score >= DOCUMENT_SCORE_THRESHOLD, score


# ============================================
# PDF IMAGE EXTRACTION
# ============================================

def decode_image(image_bytes: bytes, ext: str) -> Optional[np.ndarray]:
    """Decode raw image bytes into an OpenCV numpy array."""
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        logger.debug(f"Failed to decode image ({ext}): {e}")
        return None


def get_content_type(ext: str) -> str:
    """Map file extension to MIME content type."""
    mapping = {
        "png": "image/png",
        "jpeg": "image/jpeg",
        "jpg": "image/jpeg",
        "jp2": "image/jp2",
        "jxr": "image/jxr",
        "bmp": "image/bmp",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "ppm": "image/x-portable-pixmap",
    }
    return mapping.get(ext.lower(), "image/png")


def process_pdf(
    pdf_path: Path,
    dataset_name: str,
    dataset_base: Optional[Path],
    s3_client,
    db_session,
    dry_run: bool = False,
    seen_checksums: Optional[set] = None,
    checksums_lock: Optional[threading.Lock] = None,
    source_r2_key: Optional[str] = None,
) -> dict:
    """Extract embedded images from a single PDF, classify, and upload photos.

    source_r2_key: when set (R2 mode), the photo R2 key is derived from the
    source PDF's R2 key directory rather than the local relative path.

    Returns a stats dict: {photos_found, docs_skipped, errors, uploaded, skipped_small, skipped_dup}
    """
    stats = {
        "photos_found": 0,
        "docs_skipped": 0,
        "errors": 0,
        "uploaded": 0,
        "skipped_small": 0,
        "skipped_dup": 0,
        "skipped_grayscale_tiny": 0,
        "needs_ocr": False,  # True if any page lacks extractable text
    }

    if seen_checksums is None:
        seen_checksums = set()

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.error(f"Cannot open PDF {pdf_path.name}: {e}")
        stats["errors"] += 1
        return stats

    # Determine the directory prefix for photo R2 keys.
    # R2 mode: derive from the source PDF's known R2 key (authoritative).
    # Local mode: derive from the PDF's path relative to the dataset base.
    if source_r2_key:
        # e.g. "DataSet_10/0001/EFTA01262782.pdf" -> "DataSet_10/0001"
        photo_r2_dir = str(Path(source_r2_key).parent).replace("\\", "/")
    else:
        try:
            rel_path = pdf_path.relative_to(dataset_base)
        except ValueError:
            rel_path = Path(pdf_path.name)
        rel_dir = str(rel_path.parent).replace("\\", "/")
        photo_r2_dir = dataset_name if rel_dir == "." else f"{dataset_name}/{rel_dir}"

    # EFTA number from filename (e.g. EFTA00000002.pdf -> EFTA00000002)
    efta_stem = pdf_path.stem  # e.g. "EFTA00000002"

    # Look up source document_id for this EFTA
    source_doc_id = None
    try:
        result = db_session.execute(
            text("SELECT document_id FROM documents WHERE efta_number = :efta"),
            {"efta": efta_stem},
        ).fetchone()
        if result:
            source_doc_id = result[0]
    except Exception as e:
        logger.debug(f"Could not look up document_id for {efta_stem}: {e}")
        try:
            db_session.rollback()
        except Exception:
            pass

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # OCR detection: if the page has no/minimal extractable text it's
            # a scanned image and will need OCR.  We only flip needs_ocr once.
            if not stats["needs_ocr"]:
                try:
                    page_text = page.get_text().strip()
                    if len(page_text) < 50:
                        stats["needs_ocr"] = True
                except Exception:
                    pass  # don't let text-check errors stop extraction

            image_list = page.get_images(full=True)

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]

                try:
                    base_image = doc.extract_image(xref)
                except Exception as e:
                    logger.debug(f"  Cannot extract xref {xref} from {pdf_path.name} p{page_num + 1}: {e}")
                    stats["errors"] += 1
                    continue

                if not base_image:
                    continue

                img_bytes = base_image["image"]
                img_ext = base_image.get("ext", "png")
                img_width = base_image.get("width", 0)
                img_height = base_image.get("height", 0)

                # Skip tiny images (icons, artifacts, line separators)
                if img_width < MIN_WIDTH or img_height < MIN_HEIGHT:
                    stats["skipped_small"] += 1
                    continue

                # Decode for classification
                cv_image = decode_image(img_bytes, img_ext)
                if cv_image is None:
                    stats["errors"] += 1
                    continue

                # SHA-256 checksum for dedup within this run
                checksum = hashlib.sha256(img_bytes).hexdigest()

                # Thread-safe dedup check
                if checksums_lock:
                    with checksums_lock:
                        if checksum in seen_checksums:
                            stats["skipped_dup"] += 1
                            continue
                        seen_checksums.add(checksum)
                else:
                    if checksum in seen_checksums:
                        stats["skipped_dup"] += 1
                        continue
                    seen_checksums.add(checksum)

                # Look up existing DB record (we may update it)
                existing_media_id = None
                try:
                    existing_row = db_session.execute(
                        text("SELECT media_file_id FROM media_files WHERE checksum = :cs LIMIT 1"),
                        {"cs": checksum},
                    ).fetchone()
                    if existing_row:
                        existing_media_id = existing_row[0]
                except Exception:
                    try:
                        db_session.rollback()
                    except Exception:
                        pass

                # Classify: document scan or real photo?
                metrics = calculate_metrics(cv_image)
                is_doc, doc_score = is_document_scan(metrics)

                if is_doc:
                    stats["docs_skipped"] += 1
                    continue

                # It's a photo! Build the R2 key using the pre-computed directory.
                # e.g. DataSet_10/0001/EFTA01262782_p1_img1.png
                r2_key = f"{photo_r2_dir}/{efta_stem}_p{page_num + 1}_img{img_idx + 1}.{img_ext}"

                content_type = get_content_type(img_ext)
                file_size = len(img_bytes)

                stats["photos_found"] += 1

                if dry_run:
                    existing_tag = " (exists in DB)" if existing_media_id else " (NEW)"
                    logger.info(
                        f"  [DRY-RUN] Would upload: {r2_key} "
                        f"({img_width}x{img_height}, score={doc_score}, "
                        f"color_var={metrics['color_variance']:.1f}, "
                        f"white={metrics['white_ratio']:.2f}){existing_tag}"
                    )
                    continue

                # Upload to R2
                if upload_to_r2(s3_client, R2_BUCKET_NAME, r2_key, img_bytes, content_type):
                    stats["uploaded"] += 1

                    # Upsert media_files record
                    try:
                        file_name = f"{efta_stem}_p{page_num + 1}_img{img_idx + 1}.{img_ext}"
                        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

                        if existing_media_id:
                            # Update ALL records with this checksum (handles duplicates)
                            db_session.execute(
                                text("""
                                    UPDATE media_files
                                    SET file_path = :file_path,
                                        is_likely_photo = true,
                                        updated_at = :now
                                    WHERE checksum = :checksum
                                """),
                                {
                                    "file_path": r2_key,
                                    "now": now_str,
                                    "checksum": checksum,
                                },
                            )
                        else:
                            # Insert new record
                            db_session.execute(
                                text("""
                                    INSERT INTO media_files (
                                        file_path, file_name, media_type, file_format,
                                        file_size_bytes, checksum, width_pixels, height_pixels,
                                        source_document_id, is_likely_photo, created_at, updated_at
                                    ) VALUES (
                                        :file_path, :file_name, 'image', :file_format,
                                        :file_size, :checksum, :width, :height,
                                        :source_doc_id, true, :now, :now
                                    )
                                """),
                                {
                                    "file_path": r2_key,
                                    "file_name": file_name,
                                    "file_format": img_ext,
                                    "file_size": file_size,
                                    "checksum": checksum,
                                    "width": img_width,
                                    "height": img_height,
                                    "source_doc_id": source_doc_id,
                                    "now": now_str,
                                },
                            )
                        db_session.commit()
                    except Exception as e:
                        logger.error(f"  DB insert failed for {r2_key}: {e}")
                        db_session.rollback()
                else:
                    stats["errors"] += 1

    except Exception as e:
        logger.error(f"Error processing {pdf_path.name}: {e}")
        stats["errors"] += 1
        # Ensure session is clean for next use
        try:
            db_session.rollback()
        except Exception:
            pass
    finally:
        doc.close()

    return stats


# ============================================
# MAIN PROCESSING LOOP
# ============================================

def _stamp_checked(db_session, efta_stem: str, needs_ocr: bool = False):
    """Write photos_checked_at and ocr_status for an EFTA. Silently skips on error.

    ocr_status values:
      'pending'     — at least one page has no extractable text (scanned, needs OCR)
      'not_needed'  — all pages have extractable text (already searchable)
    """
    ocr_status = "pending" if needs_ocr else "not_needed"
    try:
        db_session.execute(
            text(
                "UPDATE documents "
                "SET photos_checked_at = NOW(), ocr_status = :ocr_status "
                "WHERE efta_number = :efta AND photos_checked_at IS NULL"
            ),
            {"efta": efta_stem, "ocr_status": ocr_status},
        )
        db_session.commit()
    except Exception as e:
        logger.debug(f"Could not stamp {efta_stem}: {e}")
        try:
            db_session.rollback()
        except Exception:
            pass


def _worker_main(task_queue, result_queue, dataset_name, dataset_path_str, dry_run,
                 source="local", temp_dir_str=None):
    """Child process: processes PDFs one at a time via queues.

    Runs in a separate process so PyMuPDF segfaults don't kill the main process.

    Local mode: task items are local path strings.
    R2 mode:    task items are (efta, r2_key) tuples; PDF is downloaded to temp_dir.
    """
    dataset_path = Path(dataset_path_str) if dataset_path_str else None
    temp_dir = Path(temp_dir_str) if temp_dir_str else None
    s3_client = create_r2_client()  # needed for both upload (always) and download (R2 mode)
    if dry_run and source == "local":
        s3_client = None
    db_session = SessionLocal()
    seen_checksums: set = set()

    while True:
        try:
            item = task_queue.get(timeout=10)
        except queue_module.Empty:
            continue

        if item is None:  # shutdown sentinel
            db_session.close()
            return

        # Unpack item depending on mode
        if source == "r2":
            efta, r2_key = item
            pdf_path = None
        else:
            pdf_path = Path(item)
            efta = pdf_path.stem
            r2_key = None

        temp_path = None
        try:
            if source == "r2":
                # Download from R2 to temp file
                temp_path = temp_dir / f"{efta}.pdf"
                if not dry_run:
                    s3_client.download_file(R2_BUCKET_NAME, r2_key, str(temp_path))
                pdf_path = temp_path

            stats = process_pdf(
                pdf_path, dataset_name, dataset_path,
                s3_client, db_session, dry_run, seen_checksums,
                source_r2_key=r2_key,
            )
            if not dry_run:
                _stamp_checked(db_session, efta, needs_ocr=stats.get("needs_ocr", False))
            result_queue.put(('ok', stats))
        except Exception as e:
            logger.error(f"Worker error on {efta}: {e}")
            try:
                db_session.rollback()
            except Exception:
                pass
            result_queue.put(('error', {
                'photos_found': 0, 'docs_skipped': 0, 'uploaded': 0,
                'errors': 1, 'skipped_small': 0, 'skipped_dup': 0,
            }))
        finally:
            # Always clean up temp file
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass


def find_pdfs(dataset_path: Path) -> list[Path]:
    """Find all PDF files in a dataset directory, sorted by name."""
    pdfs = sorted(
        p for p in dataset_path.rglob("*.pdf")
        if not any(part.startswith('.') for part in p.parts)
    )
    logger.info(f"Found {len(pdfs)} PDF files in {dataset_path}")
    return pdfs


def get_unprocessed_r2_pdfs(
    dataset_name: str,
    db_session,
    limit: Optional[int] = None,
    resume_from: Optional[str] = None,
) -> list[tuple[str, str]]:
    """Query DB for (efta_number, r2_key) pairs that have not been photo-checked.

    Only returns rows where r2_key IS NOT NULL — never assumes file location.
    Results are ordered by efta_number for deterministic processing.
    """
    query = """
        SELECT efta_number, r2_key
        FROM documents
        WHERE photos_checked_at IS NULL
          AND r2_key IS NOT NULL
          AND r2_key LIKE :prefix
        ORDER BY efta_number
    """
    params: dict = {"prefix": f"{dataset_name}/%"}
    rows = db_session.execute(text(query), params).fetchall()
    results = [(r[0], r[1]) for r in rows]

    if resume_from:
        resume_upper = resume_from.upper()
        for i, (efta, _) in enumerate(results):
            if efta.upper() >= resume_upper:
                results = results[i:]
                logger.info(f"Resuming from {resume_from}, skipped {i} entries")
                break

    if limit:
        results = results[:limit]

    logger.info(f"R2 work queue: {len(results)} unprocessed PDFs for {dataset_name}")
    return results


def download_from_r2(s3_client, r2_key: str, temp_dir: Path) -> Path:
    """Download a PDF from R2 to temp_dir. Returns the local temp path."""
    stem = Path(r2_key).stem
    dest = temp_dir / f"{stem}.pdf"
    s3_client.download_file(R2_BUCKET_NAME, r2_key, str(dest))
    return dest


def process_dataset(
    dataset_name: str,
    dry_run: bool = False,
    workers: int = 1,
    resume_from: Optional[str] = None,
    limit: Optional[int] = None,
    efta_list: Optional[set] = None,
    source: str = "local",
    temp_dir: Optional[Path] = None,
):
    """Process all PDFs in a dataset.

    source="local": reads from local filesystem (original behaviour).
    source="r2":    queries DB for r2_key, downloads each PDF on demand.
                    temp_dir is used for temporary PDF downloads.
    """
    dataset_path: Optional[Path] = None

    if source == "local":
        if dataset_name not in DATASET_PATHS:
            logger.error(f"Unknown dataset: {dataset_name}. Known: {list(DATASET_PATHS.keys())}")
            return
        dataset_path = DATASET_PATHS[dataset_name]
        if not dataset_path.exists():
            logger.error(f"Dataset path does not exist: {dataset_path}")
            return
        pdfs = find_pdfs(dataset_path)
        if not pdfs:
            logger.warning("No PDFs found.")
            return
        # Filter / resume / limit for local mode
        if efta_list:
            before = len(pdfs)
            pdfs = [p for p in pdfs if p.stem.upper() in efta_list]
            logger.info(f"EFTA filter: {before} -> {len(pdfs)} PDFs")
        if resume_from:
            resume_from_upper = resume_from.upper()
            for i, pdf in enumerate(pdfs):
                if resume_from_upper in pdf.stem.upper():
                    pdfs = pdfs[i:]
                    logger.info(f"Resuming from {resume_from}, skipped {i} PDFs")
                    break
        if limit:
            pdfs = pdfs[:limit]
            logger.info(f"Limited to {limit} PDFs")
        work_items = pdfs  # list[Path]

    else:  # source == "r2"
        # Set up temp directory for PDF downloads
        if temp_dir is None:
            temp_dir = Path(tempfile.gettempdir()) / "epstein_photo_extraction"
        temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"R2 mode: temp dir = {temp_dir}")

        db_init = SessionLocal()
        try:
            r2_work = get_unprocessed_r2_pdfs(dataset_name, db_init, limit, resume_from)
        finally:
            db_init.close()

        if not r2_work:
            logger.info(f"No unprocessed R2 PDFs found for {dataset_name} — all done or r2_key not yet populated.")
            return
        work_items = r2_work  # list[tuple[efta, r2_key]]

    # R2 client always needed (uploads in both modes; downloads in R2 mode)
    s3_client = create_r2_client()
    logger.info("R2 client initialized")

    # Shared state
    seen_checksums: set[str] = set()
    total_stats = {
        "pdfs_processed": 0,
        "photos_found": 0,
        "docs_skipped": 0,
        "uploaded": 0,
        "errors": 0,
        "skipped_small": 0,
        "skipped_dup": 0,
    }

    start_time = time.time()
    logger.info(f"Processing {len(work_items)} PDFs from {dataset_name} "
                f"(source={source}, dry_run={dry_run}, workers={workers})")

    if workers <= 1:
        # Sequential processing via crash-isolated child process.
        # PyMuPDF can segfault on corrupt PDFs; running it in a child process
        # means a segfault kills only the child, not the whole run.
        task_queue = multiprocessing.Queue()
        result_queue = multiprocessing.Queue()

        def start_worker():
            p = multiprocessing.Process(
                target=_worker_main,
                args=(task_queue, result_queue, dataset_name,
                      str(dataset_path) if dataset_path else "", dry_run),
                kwargs={"source": source, "temp_dir_str": str(temp_dir) if temp_dir else None},
                daemon=True,
            )
            p.start()
            return p

        worker = start_worker()
        current_item = None

        for i, item in enumerate(work_items):
            # Restart worker if it died (segfault from previous PDF)
            if not worker.is_alive():
                logger.warning(f"Worker died (exit {worker.exitcode}), restarting for {item_label(item)}")
                # Clean up any orphaned temp file from the crashed worker
                if source == "r2" and current_item is not None:
                    orphan = temp_dir / f"{current_item[0]}.pdf"
                    if orphan.exists():
                        orphan.unlink(missing_ok=True)
                worker = start_worker()

            current_item = item
            # Local mode: send path string; R2 mode: send (efta, r2_key) tuple
            task_queue.put(str(item) if source == "local" else item)

            # Wait for result; if worker crashes during processing, detect via timeout
            try:
                status, stats = result_queue.get(timeout=300)
            except queue_module.Empty:
                if not worker.is_alive():
                    logger.error(f"Worker segfaulted on {item_label(item)} (exit {worker.exitcode}), skipping")
                    worker = start_worker()
                    stats = {'photos_found': 0, 'docs_skipped': 0, 'uploaded': 0,
                             'errors': 1, 'skipped_small': 0, 'skipped_dup': 0}
                else:
                    logger.warning(f"Timeout waiting for result from {item_label(item)}, skipping")
                    stats = {'photos_found': 0, 'docs_skipped': 0, 'uploaded': 0,
                             'errors': 1, 'skipped_small': 0, 'skipped_dup': 0}

            # Accumulate stats
            total_stats["pdfs_processed"] += 1
            for key in ["photos_found", "docs_skipped", "uploaded", "errors", "skipped_small", "skipped_dup"]:
                total_stats[key] += stats.get(key, 0)

            # Progress log every 50 PDFs
            if (i + 1) % 50 == 0 or (i + 1) == len(work_items):
                elapsed = time.time() - start_time
                rate = total_stats["pdfs_processed"] / elapsed if elapsed > 0 else 0
                logger.info(
                    f"Progress: {i + 1}/{len(work_items)} PDFs "
                    f"({rate:.1f}/s) | "
                    f"photos={total_stats['photos_found']} "
                    f"uploaded={total_stats['uploaded']} "
                    f"docs_skipped={total_stats['docs_skipped']} "
                    f"dups={total_stats['skipped_dup']} "
                    f"errors={total_stats['errors']}"
                )

        # Shut down worker gracefully
        task_queue.put(None)
        worker.join(timeout=10)
        if worker.is_alive():
            worker.terminate()
    else:
        # Parallel processing with thread pool
        # Each worker gets its own DB session; shared set guarded by lock
        checksums_lock = threading.Lock()

        def worker_fn(item) -> dict:
            """item is a Path (local mode) or (efta, r2_key) tuple (R2 mode)."""
            session = SessionLocal()
            temp_path = None
            try:
                if source == "r2":
                    efta, r2_key = item
                    temp_path = temp_dir / f"{efta}_{threading.get_ident()}.pdf"
                    if not dry_run:
                        s3_client.download_file(R2_BUCKET_NAME, r2_key, str(temp_path))
                    pdf_path = temp_path
                else:
                    pdf_path = item
                    efta = pdf_path.stem
                    r2_key = None

                stats = process_pdf(
                    pdf_path, dataset_name, dataset_path,
                    s3_client, session, dry_run, seen_checksums,
                    checksums_lock, source_r2_key=r2_key,
                )
                if not dry_run:
                    _stamp_checked(session, efta, needs_ocr=stats.get("needs_ocr", False))
                return stats
            finally:
                session.close()
                if temp_path and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(worker_fn, item): item for item in work_items}

            for i, future in enumerate(as_completed(futures)):
                item = futures[future]
                try:
                    stats = future.result()
                    total_stats["pdfs_processed"] += 1
                    for key in ["photos_found", "docs_skipped", "uploaded", "errors", "skipped_small", "skipped_dup"]:
                        total_stats[key] += stats.get(key, 0)
                except Exception as e:
                    logger.error(f"Worker error for {item_label(item)}: {e}")
                    total_stats["errors"] += 1

                if (i + 1) % 50 == 0 or (i + 1) == len(work_items):
                    elapsed = time.time() - start_time
                    rate = total_stats["pdfs_processed"] / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Progress: {total_stats['pdfs_processed']}/{len(work_items)} PDFs "
                        f"({rate:.1f}/s) | "
                        f"photos={total_stats['photos_found']} "
                        f"uploaded={total_stats['uploaded']} "
                        f"docs_skipped={total_stats['docs_skipped']} "
                        f"dups={total_stats['skipped_dup']} "
                        f"errors={total_stats['errors']}"
                    )

    # Final summary
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"DONE — {dataset_name} processing complete in {elapsed:.0f}s")
    logger.info(f"  PDFs processed:    {total_stats['pdfs_processed']}")
    logger.info(f"  Photos found:      {total_stats['photos_found']}")
    logger.info(f"  Uploaded to R2:    {total_stats['uploaded']}")
    logger.info(f"  Document scans:    {total_stats['docs_skipped']}")
    logger.info(f"  Duplicates:        {total_stats['skipped_dup']}")
    logger.info(f"  Too small:         {total_stats['skipped_small']}")
    logger.info(f"  Errors:            {total_stats['errors']}")
    logger.info("=" * 60)


# ============================================
# ENTRY POINT
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description="Extract real photos from PDFs and upload to Cloudflare R2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would be extracted (no uploads)
  python extract_photos_to_r2.py --dataset DataSet_1 --dry-run

  # Process all PDFs in DataSet_1
  python extract_photos_to_r2.py --dataset DataSet_1

  # Resume from a specific EFTA number
  python extract_photos_to_r2.py --dataset DataSet_1 --resume-from EFTA00001000

  # Process first 100 PDFs with 4 workers
  python extract_photos_to_r2.py --dataset DataSet_1 --limit 100 --workers 4
""",
    )

    parser.add_argument(
        "--dataset",
        default="DataSet_1",
        choices=list(DATASET_PATHS.keys()),
        help="Which dataset to process (default: DataSet_1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview mode: classify images but don't upload or update DB",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1, sequential)",
    )
    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="Resume processing from a specific EFTA number (e.g. EFTA00001000)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit to N PDFs (for testing)",
    )
    parser.add_argument(
        "--efta-list",
        type=str,
        default=None,
        help="Path to a text file with one EFTA number per line; only those PDFs will be processed (local mode only)",
    )
    parser.add_argument(
        "--source",
        choices=["local", "r2"],
        default="local",
        help="Source of PDFs: 'local' reads from local filesystem (default), "
             "'r2' downloads each PDF from R2 on demand using r2_key from the database",
    )
    parser.add_argument(
        "--temp-dir",
        type=str,
        default=None,
        help="Directory for temporary PDF downloads in R2 mode (default: system temp). "
             "Needs ~(workers × avg PDF size) free space.",
    )

    args = parser.parse_args()

    efta_list = None
    if args.efta_list:
        if args.source == "r2":
            logger.warning("--efta-list is ignored in R2 mode")
        else:
            with open(args.efta_list) as f:
                efta_list = {line.strip().upper() for line in f if line.strip()}
            logger.info(f"Loaded {len(efta_list)} EFTAs from {args.efta_list}")

    process_dataset(
        dataset_name=args.dataset,
        dry_run=args.dry_run,
        workers=args.workers,
        resume_from=args.resume_from,
        limit=args.limit,
        efta_list=efta_list,
        source=args.source,
        temp_dir=Path(args.temp_dir) if args.temp_dir else None,
    )


if __name__ == "__main__":
    main()

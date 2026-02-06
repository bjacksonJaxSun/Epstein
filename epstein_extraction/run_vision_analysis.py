#!/usr/bin/env python3
"""
Vision Analysis Script for Epstein Document Images

This script analyzes images to:
1. Detect and cluster faces (for later identification)
2. Analyze scenes and locations
3. Extract text via OCR
4. Tag objects and categorize images

Usage:
    python run_vision_analysis.py --help
    python run_vision_analysis.py --faces-only --batch-size 100
    python run_vision_analysis.py --full-analysis --provider openai
"""

import argparse
import base64
import hashlib
import json
import os
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{function}</cyan> - <level>{message}</level>")

# Database path
DB_PATH = Path(__file__).parent.parent / "extraction_output" / "epstein_documents.db"


@dataclass
class FaceCluster:
    cluster_id: int
    face_encodings: list
    media_file_ids: list
    representative_image_id: Optional[int] = None
    person_name: Optional[str] = None


def ensure_tables_exist(conn: sqlite3.Connection, max_retries: int = 5):
    """Create tables for vision analysis results."""
    import time

    for attempt in range(max_retries):
        try:
            cur = conn.cursor()
            _create_tables(cur)
            conn.commit()
            logger.info("Vision analysis tables ready")
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                logger.warning(f"Database locked, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                raise


def _create_tables(cur):
    """Internal function to create tables."""
    # Face detections table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS face_detections (
            face_id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_file_id INTEGER NOT NULL,
            face_index INTEGER NOT NULL,
            bounding_box TEXT,
            face_encoding BLOB,
            cluster_id INTEGER,
            confidence REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_file_id) REFERENCES media_files(media_file_id),
            UNIQUE(media_file_id, face_index)
        )
    """)

    # Face clusters table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS face_clusters (
            cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER,
            person_name TEXT,
            face_count INTEGER DEFAULT 0,
            representative_face_id INTEGER,
            centroid_encoding BLOB,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES people(person_id)
        )
    """)

    # Scene analysis table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scene_analysis (
            analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_file_id INTEGER NOT NULL UNIQUE,
            scene_type TEXT,
            scene_description TEXT,
            detected_objects TEXT,
            detected_text TEXT,
            location_hints TEXT,
            date_hints TEXT,
            is_document INTEGER DEFAULT 0,
            is_photo INTEGER DEFAULT 0,
            confidence REAL,
            provider TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_file_id) REFERENCES media_files(media_file_id)
        )
    """)

    # Location clusters table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS location_clusters (
            cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT,
            location_type TEXT,
            description TEXT,
            media_count INTEGER DEFAULT 0,
            representative_media_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Media to location cluster mapping
    cur.execute("""
        CREATE TABLE IF NOT EXISTS media_location_clusters (
            media_file_id INTEGER NOT NULL,
            cluster_id INTEGER NOT NULL,
            confidence REAL,
            PRIMARY KEY (media_file_id, cluster_id),
            FOREIGN KEY (media_file_id) REFERENCES media_files(media_file_id),
            FOREIGN KEY (cluster_id) REFERENCES location_clusters(cluster_id)
        )
    """)


def get_unprocessed_media(conn: sqlite3.Connection, analysis_type: str, limit: int = 100) -> list:
    """Get media files that haven't been analyzed yet."""
    cur = conn.cursor()

    if analysis_type == "faces":
        cur.execute("""
            SELECT m.media_file_id, m.file_path
            FROM media_files m
            LEFT JOIN face_detections f ON m.media_file_id = f.media_file_id
            WHERE m.media_type = 'image'
            AND f.face_id IS NULL
            AND m.file_path IS NOT NULL
            LIMIT ?
        """, (limit,))
    elif analysis_type == "scenes":
        cur.execute("""
            SELECT m.media_file_id, m.file_path
            FROM media_files m
            LEFT JOIN scene_analysis s ON m.media_file_id = s.media_file_id
            WHERE m.media_type = 'image'
            AND s.analysis_id IS NULL
            AND m.file_path IS NOT NULL
            LIMIT ?
        """, (limit,))
    else:
        cur.execute("""
            SELECT m.media_file_id, m.file_path
            FROM media_files m
            WHERE m.media_type = 'image'
            AND m.file_path IS NOT NULL
            LIMIT ?
        """, (limit,))

    return cur.fetchall()


class FaceAnalyzer:
    """Handles face detection using OpenCV's built-in cascade classifier and clustering."""

    def __init__(self, conn: sqlite3.Connection, tolerance: float = 0.6):
        self.conn = conn
        self.tolerance = tolerance
        self._cv2 = None
        self._cascade = None

    def _ensure_imports(self):
        """Lazy import opencv."""
        if self._cv2 is None:
            try:
                import cv2
                self._cv2 = cv2
                # Use OpenCV's built-in face cascade
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self._cascade = cv2.CascadeClassifier(cascade_path)
                logger.info("OpenCV face detection loaded")
            except ImportError:
                logger.error("opencv not installed. Run: pip install opencv-python")
                raise

    def detect_faces(self, image_path: str, media_file_id: int) -> list:
        """Detect faces in an image using OpenCV Haar Cascade."""
        self._ensure_imports()

        try:
            # Load image
            image = self._cv2.imread(image_path)
            if image is None:
                return []

            h, w = image.shape[:2]

            # Convert to grayscale for detection
            gray = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2GRAY)

            # Detect faces
            faces_rect = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )

            if len(faces_rect) == 0:
                return []

            faces = []
            cur = self.conn.cursor()

            for idx, (x, y, width, height) in enumerate(faces_rect):
                bbox_json = json.dumps({
                    "x": int(x), "y": int(y), "width": int(width), "height": int(height),
                    "top": int(y), "right": int(x + width), "bottom": int(y + height), "left": int(x)
                })

                # Extract face region for later clustering
                face_region = image[y:y+height, x:x+width]
                if face_region.size > 0:
                    # Create a simple encoding based on resized face
                    face_resized = self._cv2.resize(face_region, (64, 64))
                    face_gray = self._cv2.cvtColor(face_resized, self._cv2.COLOR_BGR2GRAY)
                    encoding = face_gray.flatten().astype(np.float32) / 255.0
                    encoding_blob = encoding.tobytes()
                else:
                    encoding_blob = None

                faces.append({
                    "media_file_id": media_file_id,
                    "face_index": idx,
                    "bbox": bbox_json,
                    "encoding_blob": encoding_blob
                })

            # Batch insert with retry
            self._save_faces_with_retry(cur, faces)
            return faces

        except Exception as e:
            logger.error(f"Error detecting faces in {image_path}: {e}")
            return []

    def _save_faces_with_retry(self, cur, faces: list, max_retries: int = 3):
        """Save face detections with retry logic for database locks."""
        import time

        for attempt in range(max_retries):
            try:
                for face in faces:
                    cur.execute("""
                        INSERT OR REPLACE INTO face_detections
                        (media_file_id, face_index, bounding_box, face_encoding, confidence)
                        VALUES (?, ?, ?, ?, ?)
                    """, (face["media_file_id"], face["face_index"], face["bbox"],
                          face["encoding_blob"], 0.8))
                self.conn.commit()
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

    def cluster_faces(self, min_cluster_size: int = 2):
        """Cluster detected faces using simple image similarity."""
        self._ensure_imports()

        cur = self.conn.cursor()

        # Get all face encodings
        cur.execute("""
            SELECT face_id, media_file_id, face_encoding
            FROM face_detections
            WHERE face_encoding IS NOT NULL
            AND cluster_id IS NULL
        """)

        faces = []
        for row in cur.fetchall():
            face_id, media_file_id, encoding_blob = row
            if encoding_blob:
                encoding = np.frombuffer(encoding_blob, dtype=np.float32)
                faces.append({
                    "face_id": face_id,
                    "media_file_id": media_file_id,
                    "encoding": encoding
                })

        if not faces:
            logger.warning("No unclustered faces found")
            return

        logger.info(f"Clustering {len(faces)} faces...")

        # Simple clustering using cosine similarity
        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

        clusters = []
        similarity_threshold = 0.85  # High similarity required

        for face in faces:
            matched_cluster = None

            for cluster in clusters:
                # Compare to cluster centroid
                sim = cosine_similarity(cluster["centroid"], face["encoding"])
                if sim > similarity_threshold:
                    matched_cluster = cluster
                    break

            if matched_cluster:
                matched_cluster["faces"].append(face)
                # Update centroid
                all_encodings = [f["encoding"] for f in matched_cluster["faces"]]
                matched_cluster["centroid"] = np.mean(all_encodings, axis=0)
            else:
                # Create new cluster
                clusters.append({
                    "faces": [face],
                    "centroid": face["encoding"].copy()
                })

        # Filter clusters by minimum size
        significant_clusters = [c for c in clusters if len(c["faces"]) >= min_cluster_size]

        logger.info(f"Found {len(significant_clusters)} clusters with {min_cluster_size}+ faces")

        # Store clusters
        for idx, cluster in enumerate(significant_clusters):
            centroid_blob = cluster["centroid"].tobytes()

            cur.execute("""
                INSERT INTO face_clusters (face_count, centroid_encoding)
                VALUES (?, ?)
            """, (len(cluster["faces"]), centroid_blob))

            cluster_id = cur.lastrowid

            # Update face records with cluster ID
            for face in cluster["faces"]:
                cur.execute("""
                    UPDATE face_detections SET cluster_id = ? WHERE face_id = ?
                """, (cluster_id, face["face_id"]))

            # Set representative face (first one found)
            cur.execute("""
                UPDATE face_clusters SET representative_face_id = ? WHERE cluster_id = ?
            """, (cluster["faces"][0]["face_id"], cluster_id))

        self.conn.commit()
        logger.info(f"Created {len(significant_clusters)} face clusters")


class SceneAnalyzer:
    """Handles scene analysis using vision AI APIs."""

    def __init__(self, conn: sqlite3.Connection, provider: str = "openai"):
        self.conn = conn
        self.provider = provider
        self._client = None

    def _ensure_client(self):
        """Initialize the AI client."""
        if self._client is not None:
            return

        if self.provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI()
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.error("openai not installed. Run: pip install openai")
                raise
        elif self.provider == "anthropic":
            try:
                import anthropic
                self._client = anthropic.Anthropic()
                logger.info("Anthropic client initialized")
            except ImportError:
                logger.error("anthropic not installed. Run: pip install anthropic")
                raise

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    def _get_media_type(self, image_path: str) -> str:
        """Get MIME type from file extension."""
        ext = Path(image_path).suffix.lower()
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }.get(ext, "image/jpeg")

    def analyze_scene(self, image_path: str, media_file_id: int) -> dict:
        """Analyze a scene using vision AI."""
        self._ensure_client()

        try:
            image_data = self._encode_image(image_path)
            media_type = self._get_media_type(image_path)

            prompt = """Analyze this image and provide a JSON response with:
{
    "scene_type": "photo|document|screenshot|artwork|other",
    "scene_description": "Brief description of what's in the image",
    "detected_objects": ["list", "of", "notable", "objects"],
    "detected_text": "Any visible text in the image (OCR)",
    "location_hints": "Any clues about location (landmarks, signs, architecture style)",
    "date_hints": "Any clues about when this was taken (clothing, technology, vehicles)",
    "is_document": true/false,
    "is_photo": true/false,
    "people_visible": true/false,
    "people_count": 0
}

Be concise but thorough. If you can't determine something, use null."""

            if self.provider == "openai":
                response = self._client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{image_data}",
                                        "detail": "low"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=500
                )
                result_text = response.choices[0].message.content

            elif self.provider == "anthropic":
                response = self._client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": image_data
                                    }
                                },
                                {"type": "text", "text": prompt}
                            ]
                        }
                    ]
                )
                result_text = response.content[0].text

            # Parse JSON from response
            try:
                # Extract JSON from response (might have markdown code blocks)
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]

                result = json.loads(result_text.strip())
            except json.JSONDecodeError:
                result = {"scene_description": result_text, "error": "Could not parse JSON"}

            # Store in database
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO scene_analysis
                (media_file_id, scene_type, scene_description, detected_objects,
                 detected_text, location_hints, date_hints, is_document, is_photo,
                 confidence, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                media_file_id,
                result.get("scene_type"),
                result.get("scene_description"),
                json.dumps(result.get("detected_objects", [])),
                result.get("detected_text"),
                result.get("location_hints"),
                result.get("date_hints"),
                1 if result.get("is_document") else 0,
                1 if result.get("is_photo") else 0,
                0.9,
                self.provider
            ))
            self.conn.commit()

            return result

        except Exception as e:
            logger.error(f"Error analyzing scene {image_path}: {e}")
            return {"error": str(e)}


class OCRAnalyzer:
    """Handles OCR text extraction using Tesseract."""

    def __init__(self):
        self._pytesseract = None
        self._cv2 = None

    def _ensure_imports(self):
        if self._pytesseract is None:
            try:
                import pytesseract
                import cv2
                self._pytesseract = pytesseract
                self._cv2 = cv2
            except ImportError:
                logger.error("pytesseract not installed. Run: pip install pytesseract opencv-python")
                raise

    def extract_text(self, image_path: str) -> str:
        """Extract text from image using OCR."""
        self._ensure_imports()

        try:
            image = self._cv2.imread(image_path)
            if image is None:
                return ""

            # Convert to grayscale
            gray = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2GRAY)

            # Apply threshold
            _, thresh = self._cv2.threshold(gray, 0, 255, self._cv2.THRESH_BINARY + self._cv2.THRESH_OTSU)

            # Extract text
            text = self._pytesseract.image_to_string(thresh)
            return text.strip()

        except Exception as e:
            logger.error(f"OCR error for {image_path}: {e}")
            return ""


def run_face_analysis(conn: sqlite3.Connection, batch_size: int = 100, cluster: bool = True):
    """Run face detection and clustering."""
    analyzer = FaceAnalyzer(conn)

    total_faces = 0
    batch_num = 0

    while True:
        media_files = get_unprocessed_media(conn, "faces", batch_size)
        if not media_files:
            break

        batch_num += 1
        logger.info(f"Processing face detection batch {batch_num} ({len(media_files)} images)")

        for media_file_id, file_path in media_files:
            if not file_path or not os.path.exists(file_path):
                continue

            faces = analyzer.detect_faces(file_path, media_file_id)
            total_faces += len(faces)

            if faces:
                logger.debug(f"Found {len(faces)} faces in {file_path}")

    logger.info(f"Face detection complete. Found {total_faces} faces total.")

    if cluster and total_faces > 0:
        logger.info("Clustering faces...")
        analyzer.cluster_faces(min_cluster_size=2)


def run_scene_analysis(conn: sqlite3.Connection, provider: str, batch_size: int = 50):
    """Run scene analysis on images."""
    analyzer = SceneAnalyzer(conn, provider)

    total_analyzed = 0
    batch_num = 0

    while True:
        media_files = get_unprocessed_media(conn, "scenes", batch_size)
        if not media_files:
            break

        batch_num += 1
        logger.info(f"Processing scene analysis batch {batch_num} ({len(media_files)} images)")

        for media_file_id, file_path in media_files:
            if not file_path or not os.path.exists(file_path):
                continue

            result = analyzer.analyze_scene(file_path, media_file_id)
            total_analyzed += 1

            if total_analyzed % 10 == 0:
                logger.info(f"Analyzed {total_analyzed} scenes...")

    logger.info(f"Scene analysis complete. Analyzed {total_analyzed} images.")


def get_cluster_summary(conn: sqlite3.Connection):
    """Get summary of face clusters."""
    cur = conn.cursor()

    cur.execute("""
        SELECT
            fc.cluster_id,
            fc.person_name,
            fc.face_count,
            GROUP_CONCAT(DISTINCT mf.file_path) as sample_images
        FROM face_clusters fc
        LEFT JOIN face_detections fd ON fc.cluster_id = fd.cluster_id
        LEFT JOIN media_files mf ON fd.media_file_id = mf.media_file_id
        GROUP BY fc.cluster_id
        ORDER BY fc.face_count DESC
        LIMIT 20
    """)

    print("\n" + "="*60)
    print("TOP FACE CLUSTERS (by frequency)")
    print("="*60)

    for row in cur.fetchall():
        cluster_id, name, count, samples = row
        name_display = name if name else f"[Unnamed Cluster {cluster_id}]"
        print(f"\n{name_display}: {count} appearances")
        if samples:
            sample_list = samples.split(",")[:3]
            for s in sample_list:
                print(f"  - {s}")


def main():
    parser = argparse.ArgumentParser(description="Vision Analysis for Epstein Document Images")
    parser.add_argument("--faces-only", action="store_true", help="Only run face detection/clustering")
    parser.add_argument("--scenes-only", action="store_true", help="Only run scene analysis")
    parser.add_argument("--full-analysis", action="store_true", help="Run all analysis types")
    parser.add_argument("--cluster-only", action="store_true", help="Only run face clustering (on existing detections)")
    parser.add_argument("--summary", action="store_true", help="Show cluster summary")
    parser.add_argument("--provider", choices=["openai", "anthropic"], default="openai",
                        help="Vision AI provider for scene analysis")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for processing")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Database path")

    args = parser.parse_args()

    # Connect to database with timeout for concurrent access
    conn = sqlite3.connect(args.db, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout
    conn.execute("PRAGMA journal_mode = WAL")  # Better concurrent access
    ensure_tables_exist(conn)

    try:
        if args.summary:
            get_cluster_summary(conn)
            return

        if args.cluster_only:
            analyzer = FaceAnalyzer(conn)
            analyzer.cluster_faces(min_cluster_size=2)
            get_cluster_summary(conn)
            return

        if args.faces_only or args.full_analysis:
            logger.info("Starting face detection and clustering...")
            run_face_analysis(conn, args.batch_size)

        if args.scenes_only or args.full_analysis:
            logger.info(f"Starting scene analysis with {args.provider}...")
            run_scene_analysis(conn, args.provider, args.batch_size)

        if not any([args.faces_only, args.scenes_only, args.full_analysis]):
            parser.print_help()

    finally:
        conn.close()


if __name__ == "__main__":
    main()

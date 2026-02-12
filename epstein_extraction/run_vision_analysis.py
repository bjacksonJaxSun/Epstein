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

    # Document classification table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_classifications (
            classification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_file_id INTEGER NOT NULL UNIQUE,
            is_document INTEGER DEFAULT 0,
            is_photo INTEGER DEFAULT 0,
            document_type TEXT,
            document_subtype TEXT,
            has_handwriting INTEGER DEFAULT 0,
            has_signature INTEGER DEFAULT 0,
            has_letterhead INTEGER DEFAULT 0,
            has_stamp INTEGER DEFAULT 0,
            text_density REAL,
            estimated_date TEXT,
            confidence REAL,
            classification_method TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_file_id) REFERENCES media_files(media_file_id)
        )
    """)

    # Create index for faster lookups
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_doc_class_type
        ON document_classifications(document_type)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_doc_class_is_doc
        ON document_classifications(is_document)
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

            # Detect faces with stricter parameters to reduce false positives
            faces_rect = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=8,  # Increased from 5 for fewer false positives
                minSize=(60, 60),  # Increased from 30 for realistic face size
                flags=self._cv2.CASCADE_SCALE_IMAGE
            )

            if len(faces_rect) == 0:
                return []

            faces = []
            cur = self.conn.cursor()

            for idx, (x, y, width, height) in enumerate(faces_rect):
                # Filter out unlikely faces
                aspect_ratio = width / height if height > 0 else 0
                # Faces should be roughly square (0.7 to 1.4 aspect ratio)
                if aspect_ratio < 0.7 or aspect_ratio > 1.4:
                    continue
                # Face should be at least 2% of image area (filter tiny detections)
                face_area = width * height
                image_area = w * h
                if face_area < image_area * 0.02:
                    continue
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


class DocumentClassifier:
    """Classifies images as documents vs photos and categorizes document types."""

    # Document type categories
    DOCUMENT_TYPES = {
        "letter": ["dear", "sincerely", "regards", "yours truly", "to whom"],
        "legal": ["court", "plaintiff", "defendant", "hereby", "witness", "sworn", "affidavit", "subpoena"],
        "financial": ["invoice", "receipt", "payment", "amount", "total", "balance", "account"],
        "form": ["please fill", "check one", "date of birth", "signature", "print name"],
        "memo": ["memo", "memorandum", "from:", "to:", "subject:", "re:"],
        "fax": ["fax", "facsimile", "pages including cover"],
        "email": ["from:", "sent:", "to:", "subject:", "@"],
        "newspaper": ["associated press", "reuters", "byline", "continued on page"],
        "report": ["executive summary", "conclusion", "findings", "appendix"],
        "list": ["1.", "2.", "3.", "items:", "inventory"],
        "handwritten": [],  # Detected by visual analysis
        "photo": [],  # Actual photographs
        "other": []
    }

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._cv2 = None

    def _ensure_imports(self):
        if self._cv2 is None:
            try:
                import cv2
                self._cv2 = cv2
            except ImportError:
                logger.error("opencv not installed. Run: pip install opencv-python")
                raise

    def classify_image(self, image_path: str, media_file_id: int) -> dict:
        """Classify an image as document or photo and determine document type."""
        self._ensure_imports()

        try:
            image = self._cv2.imread(image_path)
            if image is None:
                return {"error": "Could not load image"}

            h, w = image.shape[:2]
            gray = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2GRAY)

            # Calculate various metrics
            metrics = self._calculate_metrics(image, gray)

            # Determine if document or photo
            is_document = self._is_document(metrics)
            is_photo = not is_document

            # Classify document type if it's a document
            doc_type = "photo"
            doc_subtype = None
            has_handwriting = False
            has_signature = False
            has_letterhead = False
            has_stamp = False

            if is_document:
                doc_type, doc_subtype = self._classify_document_type(image, gray, metrics)
                has_handwriting = self._detect_handwriting(gray)
                has_signature = self._detect_signature_region(gray)
                has_letterhead = self._detect_letterhead(gray, h)
                has_stamp = self._detect_stamp(image)

            result = {
                "is_document": is_document,
                "is_photo": is_photo,
                "document_type": doc_type,
                "document_subtype": doc_subtype,
                "has_handwriting": has_handwriting,
                "has_signature": has_signature,
                "has_letterhead": has_letterhead,
                "has_stamp": has_stamp,
                "text_density": metrics.get("text_density", 0),
                "confidence": metrics.get("confidence", 0.5)
            }

            # Save to database
            self._save_classification(media_file_id, result)

            return result

        except Exception as e:
            logger.error(f"Error classifying {image_path}: {e}")
            return {"error": str(e)}

    def _calculate_metrics(self, image, gray) -> dict:
        """Calculate image metrics for classification."""
        h, w = gray.shape

        # Aspect ratio (documents are usually portrait/letter-sized)
        aspect_ratio = h / w if w > 0 else 1

        # Color variance (documents tend to have low color variance)
        if len(image.shape) == 3:
            hsv = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2HSV)
            saturation = hsv[:, :, 1]
            color_variance = np.std(saturation)
        else:
            color_variance = 0

        # Edge density (documents have more structured edges)
        edges = self._cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / (h * w)

        # Text-like regions (using morphological operations)
        _, binary = self._cv2.threshold(gray, 0, 255, self._cv2.THRESH_BINARY_INV + self._cv2.THRESH_OTSU)
        kernel = self._cv2.getStructuringElement(self._cv2.MORPH_RECT, (5, 1))
        dilated = self._cv2.dilate(binary, kernel, iterations=2)
        contours, _ = self._cv2.findContours(dilated, self._cv2.RETR_EXTERNAL, self._cv2.CHAIN_APPROX_SIMPLE)

        # Count text-like contours (horizontal rectangles)
        text_contours = 0
        for cnt in contours:
            x, y, cw, ch = self._cv2.boundingRect(cnt)
            if cw > ch * 2 and cw > 20:  # Wide, horizontal shapes
                text_contours += 1

        text_density = text_contours / (h * w / 10000) if h * w > 0 else 0

        # White space ratio (documents have more white space)
        white_pixels = np.sum(gray > 240)
        white_ratio = white_pixels / (h * w)

        # Horizontal line detection (documents often have lines)
        horizontal_kernel = self._cv2.getStructuringElement(self._cv2.MORPH_RECT, (40, 1))
        horizontal_lines = self._cv2.morphologyEx(binary, self._cv2.MORPH_OPEN, horizontal_kernel)
        line_density = np.sum(horizontal_lines > 0) / (h * w)

        return {
            "aspect_ratio": aspect_ratio,
            "color_variance": color_variance,
            "edge_density": edge_density,
            "text_density": text_density,
            "white_ratio": white_ratio,
            "line_density": line_density,
            "confidence": 0.7  # Base confidence
        }

    def _is_document(self, metrics: dict) -> bool:
        """Determine if image is a document based on metrics."""
        score = 0

        # Documents tend to be portrait orientation
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

        # Threshold: 5+ points = document
        return score >= 5

    def _classify_document_type(self, image, gray, metrics: dict) -> tuple:
        """Classify the type of document."""
        h, w = gray.shape

        # Check for specific patterns
        if metrics["line_density"] > 0.02:
            return ("form", None)

        # Check aspect ratio for specific types
        if metrics["aspect_ratio"] > 1.3 and metrics["white_ratio"] > 0.7:
            return ("letter", None)

        # Check for tabular data
        if self._has_table_structure(gray):
            return ("financial", "table")

        # Default classification based on metrics
        if metrics["text_density"] > 1.0:
            return ("document", "text_heavy")
        elif metrics["white_ratio"] > 0.8:
            return ("document", "sparse")
        else:
            return ("document", None)

    def _has_table_structure(self, gray) -> bool:
        """Detect if image has table-like structure."""
        _, binary = self._cv2.threshold(gray, 0, 255, self._cv2.THRESH_BINARY_INV + self._cv2.THRESH_OTSU)

        # Detect horizontal lines
        h_kernel = self._cv2.getStructuringElement(self._cv2.MORPH_RECT, (40, 1))
        h_lines = self._cv2.morphologyEx(binary, self._cv2.MORPH_OPEN, h_kernel)

        # Detect vertical lines
        v_kernel = self._cv2.getStructuringElement(self._cv2.MORPH_RECT, (1, 40))
        v_lines = self._cv2.morphologyEx(binary, self._cv2.MORPH_OPEN, v_kernel)

        # If both horizontal and vertical lines exist, likely a table
        h_count = np.sum(h_lines > 0)
        v_count = np.sum(v_lines > 0)

        return h_count > 1000 and v_count > 1000

    def _detect_handwriting(self, gray) -> bool:
        """Detect presence of handwriting (irregular strokes)."""
        _, binary = self._cv2.threshold(gray, 0, 255, self._cv2.THRESH_BINARY_INV + self._cv2.THRESH_OTSU)

        # Find contours
        contours, _ = self._cv2.findContours(binary, self._cv2.RETR_EXTERNAL, self._cv2.CHAIN_APPROX_SIMPLE)

        if len(contours) < 10:
            return False

        # Analyze contour irregularity
        irregularity_scores = []
        for cnt in contours[:100]:  # Sample first 100
            if len(cnt) < 5:
                continue
            area = self._cv2.contourArea(cnt)
            perimeter = self._cv2.arcLength(cnt, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter ** 2)
                irregularity_scores.append(1 - circularity)

        if not irregularity_scores:
            return False

        avg_irregularity = np.mean(irregularity_scores)
        return avg_irregularity > 0.7  # High irregularity suggests handwriting

    def _detect_signature_region(self, gray) -> bool:
        """Detect presence of signature (typically bottom of document)."""
        h, w = gray.shape

        # Look at bottom third of document
        bottom_region = gray[int(h * 0.7):, :]

        _, binary = self._cv2.threshold(bottom_region, 0, 255, self._cv2.THRESH_BINARY_INV + self._cv2.THRESH_OTSU)

        contours, _ = self._cv2.findContours(binary, self._cv2.RETR_EXTERNAL, self._cv2.CHAIN_APPROX_SIMPLE)

        # Look for signature-like patterns (curved, connected strokes)
        for cnt in contours:
            x, y, cw, ch = self._cv2.boundingRect(cnt)
            aspect = cw / ch if ch > 0 else 0

            # Signatures are typically wide and short
            if 2 < aspect < 10 and cw > 50 and ch > 10:
                return True

        return False

    def _detect_letterhead(self, gray, h: int) -> bool:
        """Detect presence of letterhead (typically top of document)."""
        # Look at top 15% of document
        top_region = gray[:int(h * 0.15), :]

        # Letterheads often have more ink/content density
        _, binary = self._cv2.threshold(top_region, 0, 255, self._cv2.THRESH_BINARY_INV + self._cv2.THRESH_OTSU)
        ink_density = np.sum(binary > 0) / binary.size

        return ink_density > 0.1  # More than 10% ink coverage suggests letterhead

    def _detect_stamp(self, image) -> bool:
        """Detect presence of stamps (often circular, colored)."""
        hsv = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2HSV)

        # Look for circular shapes
        gray = self._cv2.cvtColor(image, self._cv2.COLOR_BGR2GRAY)
        circles = self._cv2.HoughCircles(
            gray, self._cv2.HOUGH_GRADIENT, 1, 50,
            param1=50, param2=30, minRadius=20, maxRadius=100
        )

        if circles is not None and len(circles[0]) > 0:
            # Check if circles are in colored regions (stamps often have color)
            for circle in circles[0]:
                x, y, r = map(int, circle)
                if 0 <= y < image.shape[0] and 0 <= x < image.shape[1]:
                    region = hsv[max(0, y-5):min(y+5, hsv.shape[0]),
                                max(0, x-5):min(x+5, hsv.shape[1])]
                    if region.size > 0:
                        sat = np.mean(region[:, :, 1])
                        if sat > 50:  # Colored region
                            return True

        return False

    def _save_classification(self, media_file_id: int, result: dict, max_retries: int = 3):
        """Save classification to database with retry logic."""
        import time

        for attempt in range(max_retries):
            try:
                cur = self.conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO document_classifications
                    (media_file_id, is_document, is_photo, document_type, document_subtype,
                     has_handwriting, has_signature, has_letterhead, has_stamp,
                     text_density, confidence, classification_method)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    media_file_id,
                    1 if result.get("is_document") else 0,
                    1 if result.get("is_photo") else 0,
                    result.get("document_type"),
                    result.get("document_subtype"),
                    1 if result.get("has_handwriting") else 0,
                    1 if result.get("has_signature") else 0,
                    1 if result.get("has_letterhead") else 0,
                    1 if result.get("has_stamp") else 0,
                    result.get("text_density", 0),
                    result.get("confidence", 0.5),
                    "opencv_heuristic"
                ))
                self.conn.commit()
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise


def get_unprocessed_for_classification(conn: sqlite3.Connection, limit: int = 100) -> list:
    """Get media files that haven't been classified yet."""
    cur = conn.cursor()
    cur.execute("""
        SELECT m.media_file_id, m.file_path
        FROM media_files m
        LEFT JOIN document_classifications dc ON m.media_file_id = dc.media_file_id
        WHERE m.media_type = 'image'
        AND dc.classification_id IS NULL
        AND m.file_path IS NOT NULL
        LIMIT ?
    """, (limit,))
    return cur.fetchall()


def run_document_classification(conn: sqlite3.Connection, batch_size: int = 200):
    """Run document classification on all images."""
    classifier = DocumentClassifier(conn)

    total_classified = 0
    batch_num = 0
    doc_count = 0
    photo_count = 0

    while True:
        media_files = get_unprocessed_for_classification(conn, batch_size)
        if not media_files:
            break

        batch_num += 1
        logger.info(f"Processing classification batch {batch_num} ({len(media_files)} images)")

        for media_file_id, file_path in media_files:
            if not file_path or not os.path.exists(file_path):
                continue

            result = classifier.classify_image(file_path, media_file_id)
            total_classified += 1

            if result.get("is_document"):
                doc_count += 1
            else:
                photo_count += 1

            if total_classified % 100 == 0:
                logger.info(f"Classified {total_classified} images (docs: {doc_count}, photos: {photo_count})")

    logger.info(f"Classification complete. Total: {total_classified} (Documents: {doc_count}, Photos: {photo_count})")


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


def get_classification_summary(conn: sqlite3.Connection):
    """Get summary of document classifications."""
    cur = conn.cursor()

    # Overall counts
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(is_document) as documents,
            SUM(is_photo) as photos
        FROM document_classifications
    """)
    row = cur.fetchone()
    total, docs, photos = row if row else (0, 0, 0)

    print("\n" + "="*60)
    print("DOCUMENT CLASSIFICATION SUMMARY")
    print("="*60)
    print(f"\nTotal classified: {total}")
    print(f"  Documents: {docs}")
    print(f"  Photos: {photos}")

    # By document type
    cur.execute("""
        SELECT document_type, COUNT(*) as cnt
        FROM document_classifications
        WHERE is_document = 1
        GROUP BY document_type
        ORDER BY cnt DESC
    """)

    print("\nDocument Types:")
    for doc_type, cnt in cur.fetchall():
        print(f"  {doc_type}: {cnt}")

    # Special features
    cur.execute("""
        SELECT
            SUM(has_handwriting) as handwriting,
            SUM(has_signature) as signatures,
            SUM(has_letterhead) as letterheads,
            SUM(has_stamp) as stamps
        FROM document_classifications
        WHERE is_document = 1
    """)
    row = cur.fetchone()
    if row:
        hw, sig, lh, st = row
        print("\nDocument Features:")
        print(f"  With handwriting: {hw or 0}")
        print(f"  With signatures: {sig or 0}")
        print(f"  With letterhead: {lh or 0}")
        print(f"  With stamps: {st or 0}")


def main():
    parser = argparse.ArgumentParser(description="Vision Analysis for Epstein Document Images")
    parser.add_argument("--faces-only", action="store_true", help="Only run face detection/clustering")
    parser.add_argument("--scenes-only", action="store_true", help="Only run scene analysis")
    parser.add_argument("--classify-only", action="store_true", help="Only run document classification")
    parser.add_argument("--full-analysis", action="store_true", help="Run all analysis types")
    parser.add_argument("--cluster-only", action="store_true", help="Only run face clustering (on existing detections)")
    parser.add_argument("--summary", action="store_true", help="Show cluster summary")
    parser.add_argument("--class-summary", action="store_true", help="Show classification summary")
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

        if args.class_summary:
            get_classification_summary(conn)
            return

        if args.cluster_only:
            analyzer = FaceAnalyzer(conn)
            analyzer.cluster_faces(min_cluster_size=2)
            get_cluster_summary(conn)
            return

        if args.classify_only:
            logger.info("Starting document classification...")
            run_document_classification(conn, args.batch_size)
            get_classification_summary(conn)
            return

        if args.faces_only or args.full_analysis:
            logger.info("Starting face detection and clustering...")
            run_face_analysis(conn, args.batch_size)

        if args.scenes_only or args.full_analysis:
            logger.info(f"Starting scene analysis with {args.provider}...")
            run_scene_analysis(conn, args.provider, args.batch_size)

        if args.full_analysis:
            logger.info("Starting document classification...")
            run_document_classification(conn, args.batch_size)

        if not any([args.faces_only, args.scenes_only, args.classify_only, args.full_analysis]):
            parser.print_help()

    finally:
        conn.close()


if __name__ == "__main__":
    main()

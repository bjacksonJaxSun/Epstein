#!/usr/bin/env python3
"""
Label Face and Location Clusters

This script helps you label detected face clusters with person names
and location clusters with place names.

Usage:
    python label_clusters.py --list-faces          # List all face clusters
    python label_clusters.py --label-face 1 "Jeffrey Epstein"
    python label_clusters.py --list-locations      # List location clusters
    python label_clusters.py --label-location 1 "Little St. James Island"
    python label_clusters.py --export-faces        # Export face clusters for review
    python label_clusters.py --search-web 1        # Web search for face cluster
"""

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "extraction_output" / "epstein_documents.db"


def get_conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def list_face_clusters(conn: sqlite3.Connection, unlabeled_only: bool = False):
    """List all face clusters."""
    cur = conn.cursor()

    query = """
        SELECT
            fc.cluster_id,
            fc.person_name,
            fc.face_count,
            p.name as linked_person,
            (SELECT mf.file_path FROM face_detections fd
             JOIN media_files mf ON fd.media_file_id = mf.media_file_id
             WHERE fd.cluster_id = fc.cluster_id LIMIT 1) as sample_image
        FROM face_clusters fc
        LEFT JOIN people p ON fc.person_id = p.person_id
    """

    if unlabeled_only:
        query += " WHERE fc.person_name IS NULL"

    query += " ORDER BY fc.face_count DESC"

    cur.execute(query)

    print("\n" + "=" * 70)
    print("FACE CLUSTERS")
    print("=" * 70)
    print(f"{'ID':<6} {'Name':<30} {'Count':<8} {'Sample Image'}")
    print("-" * 70)

    for row in cur.fetchall():
        cluster_id, name, count, linked, sample = row
        name_display = name or linked or "[Unlabeled]"
        sample_display = (sample[:40] + "...") if sample and len(sample) > 40 else (sample or "N/A")
        print(f"{cluster_id:<6} {name_display:<30} {count:<8} {sample_display}")


def label_face_cluster(conn: sqlite3.Connection, cluster_id: int, name: str, link_person: bool = True):
    """Label a face cluster with a person name."""
    cur = conn.cursor()

    # Update cluster name
    cur.execute("UPDATE face_clusters SET person_name = ? WHERE cluster_id = ?", (name, cluster_id))

    if link_person:
        # Try to find or create person record
        cur.execute("SELECT person_id FROM people WHERE name = ?", (name,))
        row = cur.fetchone()

        if row:
            person_id = row[0]
            print(f"Linking to existing person: {name} (ID: {person_id})")
        else:
            cur.execute("INSERT INTO people (name) VALUES (?)", (name,))
            person_id = cur.lastrowid
            print(f"Created new person: {name} (ID: {person_id})")

        cur.execute("UPDATE face_clusters SET person_id = ? WHERE cluster_id = ?", (person_id, cluster_id))

        # Also link all media files with this face to the person via media_people
        cur.execute("""
            INSERT OR IGNORE INTO media_people (media_file_id, person_id, relationship_type)
            SELECT fd.media_file_id, ?, 'appears_in'
            FROM face_detections fd
            WHERE fd.cluster_id = ?
        """, (person_id, cluster_id))

    conn.commit()
    print(f"Labeled cluster {cluster_id} as '{name}'")


def export_face_clusters(conn: sqlite3.Connection, output_dir: str = "face_clusters_review"):
    """Export sample images from each cluster for easy review."""
    cur = conn.cursor()

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    cur.execute("""
        SELECT
            fc.cluster_id,
            fc.person_name,
            fc.face_count
        FROM face_clusters fc
        ORDER BY fc.face_count DESC
    """)

    clusters = cur.fetchall()

    for cluster_id, name, count in clusters:
        # Get sample images for this cluster
        cur.execute("""
            SELECT DISTINCT mf.file_path
            FROM face_detections fd
            JOIN media_files mf ON fd.media_file_id = mf.media_file_id
            WHERE fd.cluster_id = ?
            LIMIT 5
        """, (cluster_id,))

        images = cur.fetchall()

        if images:
            cluster_name = name.replace(" ", "_") if name else f"unknown_{cluster_id}"
            cluster_dir = output_path / f"cluster_{cluster_id}_{cluster_name}_{count}faces"
            cluster_dir.mkdir(exist_ok=True)

            for idx, (img_path,) in enumerate(images):
                if img_path and os.path.exists(img_path):
                    ext = Path(img_path).suffix
                    dest = cluster_dir / f"sample_{idx + 1}{ext}"
                    try:
                        shutil.copy(img_path, dest)
                    except Exception as e:
                        print(f"Error copying {img_path}: {e}")

    print(f"\nExported clusters to: {output_path.absolute()}")
    print("Review the images and use --label-face to name clusters")


def search_face_web(conn: sqlite3.Connection, cluster_id: int):
    """Prepare images for reverse image search."""
    cur = conn.cursor()

    cur.execute("""
        SELECT mf.file_path
        FROM face_detections fd
        JOIN media_files mf ON fd.media_file_id = mf.media_file_id
        WHERE fd.cluster_id = ?
        LIMIT 1
    """, (cluster_id,))

    row = cur.fetchone()
    if row and row[0] and os.path.exists(row[0]):
        print(f"\nSample image for cluster {cluster_id}: {row[0]}")
        print("\nTo identify this person:")
        print("1. Open Google Images: https://images.google.com/")
        print("2. Click the camera icon for reverse image search")
        print(f"3. Upload: {row[0]}")
        print("\nOr use TinEye: https://tineye.com/")

        # On Windows, try to open the image
        if sys.platform == "win32":
            try:
                os.startfile(row[0])
            except:
                pass
    else:
        print(f"No image found for cluster {cluster_id}")


def list_location_clusters(conn: sqlite3.Connection):
    """List location clusters from scene analysis."""
    cur = conn.cursor()

    # Group by location hints
    cur.execute("""
        SELECT
            location_hints,
            COUNT(*) as count,
            GROUP_CONCAT(media_file_id) as media_ids
        FROM scene_analysis
        WHERE location_hints IS NOT NULL
        AND location_hints != ''
        AND location_hints != 'null'
        GROUP BY location_hints
        ORDER BY count DESC
        LIMIT 30
    """)

    print("\n" + "=" * 70)
    print("LOCATION CLUSTERS (from scene analysis)")
    print("=" * 70)

    for row in cur.fetchall():
        hints, count, media_ids = row
        print(f"\n[{count} images] {hints}")
        ids = media_ids.split(",")[:3]
        print(f"  Sample IDs: {', '.join(ids)}")


def get_stats(conn: sqlite3.Connection):
    """Get overall statistics."""
    cur = conn.cursor()

    print("\n" + "=" * 70)
    print("VISION ANALYSIS STATISTICS")
    print("=" * 70)

    # Face stats
    cur.execute("SELECT COUNT(*) FROM face_detections")
    face_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM face_clusters")
    cluster_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM face_clusters WHERE person_name IS NOT NULL")
    labeled_count = cur.fetchone()[0]

    print(f"\nFaces detected: {face_count:,}")
    print(f"Face clusters: {cluster_count:,}")
    print(f"Labeled clusters: {labeled_count:,}")

    # Scene stats
    cur.execute("SELECT COUNT(*) FROM scene_analysis")
    scene_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM scene_analysis WHERE is_document = 1")
    doc_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM scene_analysis WHERE is_photo = 1")
    photo_count = cur.fetchone()[0]

    print(f"\nScenes analyzed: {scene_count:,}")
    print(f"  Documents: {doc_count:,}")
    print(f"  Photos: {photo_count:,}")

    # Top scene types
    cur.execute("""
        SELECT scene_type, COUNT(*) as cnt
        FROM scene_analysis
        WHERE scene_type IS NOT NULL
        GROUP BY scene_type
        ORDER BY cnt DESC
        LIMIT 5
    """)

    print("\nTop scene types:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:,}")


def main():
    parser = argparse.ArgumentParser(description="Label Face and Location Clusters")
    parser.add_argument("--list-faces", action="store_true", help="List all face clusters")
    parser.add_argument("--unlabeled", action="store_true", help="Show only unlabeled clusters")
    parser.add_argument("--label-face", nargs=2, metavar=("CLUSTER_ID", "NAME"),
                        help="Label a face cluster")
    parser.add_argument("--export-faces", action="store_true", help="Export face samples for review")
    parser.add_argument("--search-web", type=int, metavar="CLUSTER_ID",
                        help="Get image for reverse image search")
    parser.add_argument("--list-locations", action="store_true", help="List location hints")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Database path")

    args = parser.parse_args()

    conn = get_conn(args.db)

    try:
        if args.list_faces:
            list_face_clusters(conn, args.unlabeled)
        elif args.label_face:
            cluster_id = int(args.label_face[0])
            name = args.label_face[1]
            label_face_cluster(conn, cluster_id, name)
        elif args.export_faces:
            export_face_clusters(conn)
        elif args.search_web:
            search_face_web(conn, args.search_web)
        elif args.list_locations:
            list_location_clusters(conn)
        elif args.stats:
            get_stats(conn)
        else:
            parser.print_help()

    finally:
        conn.close()


if __name__ == "__main__":
    main()

"""
Merge distributed OCR results back into the main database.

Usage:
    python ocr_merge_results.py --input-dir \\server\share\ocr_results
"""
import argparse
import json
import sqlite3
from pathlib import Path
from loguru import logger


def main():
    parser = argparse.ArgumentParser(description='Merge OCR results into database')
    parser.add_argument('--input-dir', type=str, required=True, help='Directory with OCR result JSON files')
    parser.add_argument('--db-path', type=str,
                        default=r'C:\Development\EpsteinDownloader\extraction_output\epstein_documents.db',
                        help='Path to SQLite database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()

    input_path = Path(args.input_dir)
    json_files = sorted(input_path.glob('ocr_results_*.json'))

    logger.info(f"Found {len(json_files)} result files in {args.input_dir}")

    if not json_files:
        logger.warning("No result files found. Exiting.")
        return

    conn = sqlite3.connect(args.db_path, timeout=60)
    cursor = conn.cursor()

    total_updated = 0
    total_with_text = 0
    total_no_text = 0

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            results = data.get('results', [])
            file_updated = 0

            for result in results:
                doc_id = result['document_id']
                full_text = result.get('full_text')
                page_count = result.get('page_count', 1)
                has_text = result.get('has_text', False)

                if args.dry_run:
                    logger.debug(f"Would update doc {doc_id}: has_text={has_text}")
                else:
                    if has_text and full_text:
                        cursor.execute('''
                            UPDATE documents
                            SET full_text = ?,
                                extraction_status = 'completed',
                                page_count = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE document_id = ?
                            AND (full_text IS NULL OR LENGTH(full_text) < 100)
                        ''', (full_text, page_count, doc_id))
                        total_with_text += 1
                    else:
                        cursor.execute('''
                            UPDATE documents
                            SET extraction_status = 'completed',
                                page_count = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE document_id = ?
                            AND extraction_status = 'partial'
                        ''', (page_count, doc_id))
                        total_no_text += 1

                    file_updated += cursor.rowcount

            if not args.dry_run:
                conn.commit()

            total_updated += file_updated
            logger.info(f"Processed {json_file.name}: {len(results)} results, {file_updated} updated")

        except Exception as e:
            logger.error(f"Error processing {json_file}: {e}")
            continue

    conn.close()

    logger.info(f"\n=== Merge Complete ===")
    logger.info(f"Files processed: {len(json_files)}")
    logger.info(f"Documents updated: {total_updated:,}")
    logger.info(f"With text: {total_with_text:,}")
    logger.info(f"Without text: {total_no_text:,}")

    if args.dry_run:
        logger.info("(Dry run - no changes made)")


if __name__ == "__main__":
    main()

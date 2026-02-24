"""
register_missing_pdfs.py
Ensures every PDF in R2 has a documents record with r2_key populated.

Two operations per dataset:
  1. INSERT stub records for PDFs in R2 that have no DB record yet.
  2. UPDATE r2_key on existing records where it is NULL but the EFTA is found in R2.

r2_key is the authoritative R2 object key (e.g. DataSet_9/0001/EFTA00000001.pdf).
It is only set when confirmed from R2 — never assumed or derived.

R2 is the authoritative source. Re-runnable as more PDFs are uploaded.

Usage:
  # All datasets
  python register_missing_pdfs.py

  # Specific datasets
  python register_missing_pdfs.py --dataset DataSet_9 DataSet_11

  # Preview only
  python register_missing_pdfs.py --dry-run
"""

import argparse
from pathlib import Path

import boto3
from sqlalchemy import text, bindparam, String
from sqlalchemy.dialects.postgresql import ARRAY

from config import SessionLocal

R2_ENDPOINT = "https://f8370fa3403bc68c2a46a3ad87be970d.r2.cloudflarestorage.com"
R2_ACCESS_KEY = "ae0a78c0037d7ac13df823d2e085777c"
R2_SECRET_KEY = "6aed78ea947b634aa80d78b3d7d976493c1926501eecd77e4faa0691bc85faa2"
R2_BUCKET = "epsteinfiles"
INSERT_BATCH_SIZE = 500    # rows per INSERT commit
UPDATE_BATCH_SIZE = 5000   # rows per bulk UPDATE commit (unnest is very efficient)

ALL_DATASETS = [
    "DataSet_1",
    "DataSet_2",
    "DataSet_3",
    "DataSet_4",
    "DataSet_5",
    "DataSet_6",
    "DataSet_7",
    "DataSet_8",
    "DataSet_9",
    "DataSet_10",
    "DataSet_11",
    "DataSet_12",
]


def paginate_r2(s3, dataset_name: str) -> dict[str, str]:
    """Paginate R2 for a dataset prefix. Returns {stem_upper: full_r2_key}."""
    prefix = f"{dataset_name}/"
    paginator = s3.get_paginator("list_objects_v2")
    result: dict[str, str] = {}
    page_count = 0
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix):
        page_count += 1
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".pdf"):
                stem = Path(key).stem.upper()
                result[stem] = key
        if page_count % 10 == 0:
            print(f"  [{dataset_name}] {page_count} pages, {len(result)} PDFs so far...")
    return result


def register_dataset(
    dataset_name: str,
    s3,
    db,
    existing_all: dict[str, int],  # stem_upper -> document_id
    dry_run: bool,
) -> tuple[int, int]:
    """
    Process one dataset. Returns (inserted, updated).

    existing_all: mapping of ALL efta stems already in DB to their document_id.
    """
    print(f"\n[{dataset_name}] Paginating R2...")
    r2_keys = paginate_r2(s3, dataset_name)  # {stem: r2_key}
    print(f"  [{dataset_name}] R2 total: {len(r2_keys)} PDFs")

    # --- Determine work ---
    # 1. New stubs: in R2 but not in DB at all
    missing_stems = sorted(s for s in r2_keys if s not in existing_all)

    # 2. Backfill r2_key: in DB but r2_key is NULL
    needs_backfill_stems = sorted(
        s for s in r2_keys
        if s in existing_all
    )
    # We'll filter to r2_key IS NULL in the DB query below

    print(
        f"  [{dataset_name}] New stubs to insert: {len(missing_stems)} | "
        f"Candidates for r2_key backfill: {len(needs_backfill_stems)}"
    )

    if dry_run:
        if missing_stems:
            print(f"  [{dataset_name}] [DRY-RUN] Would insert {len(missing_stems)} stubs.")
            for s in missing_stems[:5]:
                print(f"    INSERT  {r2_keys[s]}")
            if len(missing_stems) > 5:
                print(f"    ... and {len(missing_stems) - 5} more")
        if needs_backfill_stems:
            print(f"  [{dataset_name}] [DRY-RUN] Would backfill r2_key on up to {len(needs_backfill_stems)} records.")
            for s in needs_backfill_stems[:5]:
                print(f"    UPDATE  {r2_keys[s]}")
            if len(needs_backfill_stems) > 5:
                print(f"    ... and {len(needs_backfill_stems) - 5} more")
        return 0, 0

    # --- INSERT new stubs ---
    inserted = 0
    for i in range(0, len(missing_stems), INSERT_BATCH_SIZE):
        batch = missing_stems[i : i + INSERT_BATCH_SIZE]
        db.execute(
            text("""
                INSERT INTO documents (efta_number, file_path, r2_key, extraction_status, created_at, updated_at)
                VALUES (:efta, :r2_key, :r2_key, 'pending', NOW(), NOW())
            """),
            [{"efta": stem, "r2_key": r2_keys[stem]} for stem in batch],
        )
        db.commit()
        inserted += len(batch)
        print(f"  [{dataset_name}] Inserted {min(i + INSERT_BATCH_SIZE, len(missing_stems))}/{len(missing_stems)}")

    # --- BACKFILL r2_key on existing records ---
    # One bulk UPDATE per batch using unnest — far faster than per-row updates.
    # Only touches rows where r2_key IS NULL — never overwrites confirmed keys.
    updated = 0
    for i in range(0, len(needs_backfill_stems), UPDATE_BATCH_SIZE):
        batch = needs_backfill_stems[i : i + UPDATE_BATCH_SIZE]
        eftas = [stem for stem in batch]
        keys  = [r2_keys[stem] for stem in batch]
        db.execute(
            text("""
                UPDATE documents d
                SET r2_key = v.r2_key, updated_at = NOW()
                FROM unnest(:eftas, :keys) AS v(efta, r2_key)
                WHERE d.efta_number = v.efta
                  AND d.r2_key IS NULL
            """).bindparams(
                bindparam("eftas", type_=ARRAY(String())),
                bindparam("keys",  type_=ARRAY(String())),
            ),
            {"eftas": eftas, "keys": keys},
        )
        db.commit()
        updated += len(batch)
        if updated % 50000 == 0 or updated == len(needs_backfill_stems):
            print(f"  [{dataset_name}] Backfilled {updated}/{len(needs_backfill_stems)}")

    print(f"  [{dataset_name}] Done. Inserted: {inserted} | r2_key backfilled: up to {updated} records")
    return inserted, updated


def main(datasets: list[str], dry_run: bool = False):
    print(f"Datasets to process: {datasets}")
    print("Connecting to R2...")
    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
    )

    db = SessionLocal()
    try:
        # Load ALL existing efta_numbers once — used to detect missing stubs
        print("Loading existing efta_numbers from DB...")
        rows = db.execute(
            text("SELECT UPPER(efta_number), document_id FROM documents WHERE efta_number IS NOT NULL")
        ).fetchall()
        existing_all = {r[0]: r[1] for r in rows}
        print(f"Existing records in DB: {len(existing_all)}")

        total_inserted = 0
        total_updated = 0
        for dataset_name in datasets:
            ins, upd = register_dataset(dataset_name, s3, db, existing_all, dry_run)
            total_inserted += ins
            total_updated += upd

        print(f"\nAll done. Stubs inserted: {total_inserted} | r2_key backfilled: {total_updated}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Register R2 PDFs in documents table and populate r2_key"
    )
    parser.add_argument(
        "--dataset",
        nargs="+",
        choices=ALL_DATASETS,
        default=ALL_DATASETS,
        metavar="DATASET",
        help=f"Dataset(s) to process (default: all). Choices: {', '.join(ALL_DATASETS)}",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    args = parser.parse_args()
    main(datasets=args.dataset, dry_run=args.dry_run)

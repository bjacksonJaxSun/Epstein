"""
Compare the DOJ catalog against what's in the local PostgreSQL database.
Run after catalog_doj_files.py has finished.

Outputs:
  - missing_from_db.txt  : EFTAs on DOJ site but not in our database
  - extra_in_db.txt      : EFTAs in our database but not on DOJ site (possible duplicates/errors)
  - summary to stdout

Usage:
    python compare_doj_catalog.py
"""
import os
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
CATALOG_FILE = SCRIPT_DIR / "doj_catalog.txt"
MISSING_FILE = SCRIPT_DIR / "missing_from_db.txt"
EXTRA_FILE = SCRIPT_DIR / "extra_in_db.txt"

# Database connection
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "epstein_documents")
DB_USER = os.getenv("DB_USER", "epstein_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "epstein_secure_pw_2024")


def load_catalog():
    """Load DOJ catalog: returns dict of {efta: (dataset, url)}"""
    catalog = {}
    if not CATALOG_FILE.exists():
        print(f"ERROR: Catalog file not found: {CATALOG_FILE}")
        print("Run catalog_doj_files.py first.")
        sys.exit(1)

    with open(CATALOG_FILE, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2 and parts[0].startswith('EFTA'):
                efta = parts[0]
                dataset = parts[1] if len(parts) > 1 else '?'
                url = parts[2] if len(parts) > 2 else ''
                catalog[efta] = (dataset, url)

    return catalog


def get_db_eftas():
    """Get all EFTA numbers from the database"""
    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()
    cursor.execute("SELECT efta_number FROM documents WHERE efta_number IS NOT NULL")
    eftas = {row[0] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return eftas


def main():
    print("Loading DOJ catalog...")
    catalog = load_catalog()
    doj_eftas = set(catalog.keys())
    print(f"  DOJ catalog: {len(doj_eftas)} unique EFTAs")

    print("Loading database EFTAs...")
    db_eftas = get_db_eftas()
    print(f"  Database: {len(db_eftas)} unique EFTAs")

    # Compare
    missing = doj_eftas - db_eftas  # On DOJ but not in DB
    extra = db_eftas - doj_eftas    # In DB but not on DOJ
    overlap = doj_eftas & db_eftas  # In both

    print(f"\n{'='*60}")
    print(f"COMPARISON RESULTS")
    print(f"{'='*60}")
    print(f"  On DOJ site:         {len(doj_eftas):>8}")
    print(f"  In database:         {len(db_eftas):>8}")
    print(f"  In both (matched):   {len(overlap):>8}")
    print(f"  Missing from DB:     {len(missing):>8}  <- need to download & import")
    print(f"  Extra in DB:         {len(extra):>8}  <- not on DOJ (duplicates?)")

    # Break down missing by dataset
    if missing:
        print(f"\nMissing by dataset:")
        by_dataset = {}
        for efta in missing:
            ds = catalog[efta][0]
            by_dataset.setdefault(ds, []).append(efta)
        for ds in sorted(by_dataset.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            print(f"  Dataset {ds}: {len(by_dataset[ds])} files")

        # Save missing list
        with open(MISSING_FILE, 'w') as f:
            f.write(f"# Missing from database - generated {__import__('datetime').datetime.now()}\n")
            f.write(f"# Total: {len(missing)}\n")
            f.write(f"# Format: EFTA\\tDataset\\tURL\n")
            for efta in sorted(missing):
                ds, url = catalog[efta]
                f.write(f"{efta}\t{ds}\t{url}\n")
        print(f"\nMissing list saved to: {MISSING_FILE}")

    # Save extra list
    if extra:
        print(f"\nExtra EFTAs in DB (first 20):")
        for efta in sorted(extra)[:20]:
            print(f"  {efta}")
        if len(extra) > 20:
            print(f"  ... and {len(extra) - 20} more")

        with open(EXTRA_FILE, 'w') as f:
            f.write(f"# In database but not on DOJ site\n")
            f.write(f"# Total: {len(extra)}\n")
            for efta in sorted(extra):
                f.write(f"{efta}\n")
        print(f"Extra list saved to: {EXTRA_FILE}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()

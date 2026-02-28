"""
Three-way gap analysis: DOJ catalog vs PostgreSQL database vs physical files on disk.

Compares all three sources to identify:
  - Files needing download (in catalog but not on disk)
  - Files needing DB import (on disk but not in DB)
  - Dataset assignment conflicts (disk/DB disagrees with catalog)
  - DB orphans (in DB but no physical file)

Outputs:
  - gap_report.txt        : Summary with per-dataset breakdown
  - need_download.txt     : EFTAs to download with URLs
  - need_db_import.txt    : EFTAs on disk but not in DB
  - dataset_conflicts.txt : EFTAs where disk/DB dataset != catalog dataset

Usage:
    python gap_analysis.py [--skip-db] [--skip-disk] [--files-root PATH]
"""
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CATALOG_FILE = SCRIPT_DIR / "doj_catalog.txt"
OUTPUT_DIR = SCRIPT_DIR

# Database connection
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "epstein_documents")
DB_USER = os.getenv("DB_USER", "epstein_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "epstein_secure_pw_2024")

DEFAULT_FILES_ROOT = r"D:\Personal\Epstein\data\files"

# Regex to extract dataset number from paths like "DataSet_9", "DataSet 9", "DataSet9"
DATASET_RE = re.compile(r'DataSet[_ ]?(\d+)', re.IGNORECASE)


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
    """Get all EFTA numbers and their dataset assignments from the database.

    Returns dict of {efta: dataset_str} where dataset is extracted from file_path.
    """
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()
    cursor.execute(
        "SELECT efta_number, file_path FROM documents WHERE efta_number IS NOT NULL"
    )
    db_eftas = {}
    for efta, file_path in cursor.fetchall():
        dataset = '?'
        if file_path:
            m = DATASET_RE.search(file_path)
            if m:
                dataset = m.group(1)
        db_eftas[efta] = dataset

    cursor.close()
    conn.close()
    return db_eftas


def scan_disk_files(files_root):
    """Scan physical PDF files on disk.

    Returns dict of {efta: dataset_str} extracted from directory structure.
    Excludes .azDownload-* temp files.
    """
    disk_eftas = {}
    files_root = Path(files_root)

    if not files_root.exists():
        print(f"WARNING: Files root not found: {files_root}")
        return disk_eftas

    for root, dirs, files in os.walk(files_root):
        # Extract dataset from directory path
        root_str = str(root)
        ds_match = DATASET_RE.search(root_str)
        dataset = ds_match.group(1) if ds_match else '?'

        for f in files:
            # Skip temp files
            if '.azDownload-' in f:
                continue
            if not f.lower().endswith('.pdf'):
                continue
            # Extract EFTA number
            efta_match = re.match(r'(EFTA\d{8})', f, re.IGNORECASE)
            if efta_match:
                efta = efta_match.group(1).upper()
                disk_eftas[efta] = dataset

    return disk_eftas


def run_analysis(catalog, db_eftas, disk_eftas, skip_db, skip_disk):
    """Run the three-way gap analysis and return all computed sets."""
    catalog_set = set(catalog.keys())
    db_set = set(db_eftas.keys()) if not skip_db else set()
    disk_set = set(disk_eftas.keys()) if not skip_disk else set()

    # Core gap sets
    need_download = catalog_set - disk_set          # In catalog, not on disk
    need_db_import = disk_set - db_set              # On disk, not in DB
    catalog_only = catalog_set - disk_set - db_set  # Only in catalog
    db_orphans = db_set - disk_set                  # In DB but no file on disk
    in_all_three = catalog_set & db_set & disk_set  # In all three sources

    # Dataset assignment conflicts: where disk or DB disagrees with catalog
    conflicts = []
    for efta in catalog_set & (disk_set | db_set):
        cat_ds = catalog[efta][0]
        disk_ds = disk_eftas.get(efta)
        db_ds = db_eftas.get(efta)

        disk_conflict = disk_ds is not None and disk_ds != cat_ds and disk_ds != '?'
        db_conflict = db_ds is not None and db_ds != cat_ds and db_ds != '?'

        if disk_conflict or db_conflict:
            conflicts.append((efta, cat_ds, disk_ds, db_ds))

    return {
        'catalog_set': catalog_set,
        'db_set': db_set,
        'disk_set': disk_set,
        'need_download': need_download,
        'need_db_import': need_db_import,
        'catalog_only': catalog_only,
        'db_orphans': db_orphans,
        'in_all_three': in_all_three,
        'conflicts': conflicts,
    }


def dataset_breakdown(efta_set, source_map):
    """Group EFTAs by dataset from a source map. Returns {dataset: count}."""
    breakdown = {}
    for efta in efta_set:
        ds = source_map.get(efta, '?')
        breakdown[ds] = breakdown.get(ds, 0) + 1
    return breakdown


def write_gap_report(results, catalog, db_eftas, disk_eftas, skip_db, skip_disk):
    """Write the summary gap report."""
    report_file = OUTPUT_DIR / "gap_report.txt"
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines = []
    lines.append(f"{'='*70}")
    lines.append(f"GAP ANALYSIS REPORT — {now}")
    lines.append(f"{'='*70}")
    lines.append("")
    lines.append("SOURCE COUNTS:")
    lines.append(f"  DOJ Catalog:      {len(results['catalog_set']):>10}")
    if not skip_disk:
        lines.append(f"  Physical files:   {len(results['disk_set']):>10}")
    else:
        lines.append(f"  Physical files:   {'(skipped)':>10}")
    if not skip_db:
        lines.append(f"  Database records: {len(results['db_set']):>10}")
    else:
        lines.append(f"  Database records: {'(skipped)':>10}")
    lines.append("")

    lines.append("GAP SUMMARY:")
    lines.append(f"  In all three:              {len(results['in_all_three']):>10}")
    lines.append(f"  Need download (catalog-disk): {len(results['need_download']):>10}")
    if not skip_db:
        lines.append(f"  Need DB import (disk-DB):  {len(results['need_db_import']):>10}")
        lines.append(f"  DB orphans (DB-disk):      {len(results['db_orphans']):>10}")
    lines.append(f"  Catalog-only (not on disk/DB): {len(results['catalog_only']):>10}")
    lines.append(f"  Dataset conflicts:         {len(results['conflicts']):>10}")
    lines.append("")

    # Per-dataset breakdown of files needing download
    if results['need_download']:
        lines.append("NEED DOWNLOAD — by dataset (catalog assignment):")
        # Use catalog as dataset source for these
        bd = {}
        for efta in results['need_download']:
            ds = catalog[efta][0]
            bd[ds] = bd.get(ds, 0) + 1
        for ds in sorted(bd.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            lines.append(f"  Dataset {ds:>2}: {bd[ds]:>8} files")
        lines.append(f"  {'TOTAL':>12}: {sum(bd.values()):>8} files")
        lines.append("")

    # Per-dataset breakdown of DB imports needed
    if not skip_db and results['need_db_import']:
        lines.append("NEED DB IMPORT — by dataset (disk assignment):")
        bd = dataset_breakdown(results['need_db_import'], disk_eftas)
        for ds in sorted(bd.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            lines.append(f"  Dataset {ds:>2}: {bd[ds]:>8} files")
        lines.append(f"  {'TOTAL':>12}: {sum(bd.values()):>8} files")
        lines.append("")

    # Conflicts summary
    if results['conflicts']:
        lines.append("DATASET CONFLICTS (top 20):")
        lines.append(f"  {'EFTA':<16} {'Catalog':>8} {'Disk':>8} {'DB':>8}")
        lines.append(f"  {'-'*14} {'-'*8} {'-'*8} {'-'*8}")
        for efta, cat_ds, disk_ds, db_ds in sorted(results['conflicts'])[:20]:
            disk_str = disk_ds if disk_ds else '-'
            db_str = db_ds if db_ds else '-'
            lines.append(f"  {efta:<16} {cat_ds:>8} {disk_str:>8} {db_str:>8}")
        if len(results['conflicts']) > 20:
            lines.append(f"  ... and {len(results['conflicts']) - 20} more (see dataset_conflicts.txt)")
        lines.append("")

    lines.append(f"{'='*70}")

    report_text = '\n'.join(lines)
    with open(report_file, 'w') as f:
        f.write(report_text)

    # Also print to stdout
    print(report_text)
    print(f"\nReport saved to: {report_file}")


def write_need_download(results, catalog):
    """Write need_download.txt — EFTAs to download with URLs."""
    out_file = OUTPUT_DIR / "need_download.txt"
    with open(out_file, 'w') as f:
        f.write(f"# Files needing download — generated {datetime.now()}\n")
        f.write(f"# Total: {len(results['need_download'])}\n")
        f.write(f"# Format: EFTA\\tCatalogDataset\\tURL\n")
        for efta in sorted(results['need_download']):
            ds, url = catalog[efta]
            f.write(f"{efta}\t{ds}\t{url}\n")

    print(f"Need-download list: {out_file} ({len(results['need_download'])} entries)")


def write_need_db_import(results, disk_eftas):
    """Write need_db_import.txt — EFTAs on disk but not in DB."""
    out_file = OUTPUT_DIR / "need_db_import.txt"
    with open(out_file, 'w') as f:
        f.write(f"# Files on disk but not in DB — generated {datetime.now()}\n")
        f.write(f"# Total: {len(results['need_db_import'])}\n")
        f.write(f"# Format: EFTA\\tDiskDataset\n")
        for efta in sorted(results['need_db_import']):
            ds = disk_eftas.get(efta, '?')
            f.write(f"{efta}\t{ds}\n")

    print(f"Need-DB-import list: {out_file} ({len(results['need_db_import'])} entries)")


def write_dataset_conflicts(results):
    """Write dataset_conflicts.txt — EFTAs where disk/DB disagrees with catalog."""
    out_file = OUTPUT_DIR / "dataset_conflicts.txt"
    with open(out_file, 'w') as f:
        f.write(f"# Dataset assignment conflicts — generated {datetime.now()}\n")
        f.write(f"# Catalog is source of truth. Disk/DB have different dataset.\n")
        f.write(f"# Total: {len(results['conflicts'])}\n")
        f.write(f"# Format: EFTA\\tCatalogDS\\tDiskDS\\tDB_DS\n")
        for efta, cat_ds, disk_ds, db_ds in sorted(results['conflicts']):
            disk_str = disk_ds if disk_ds else '-'
            db_str = db_ds if db_ds else '-'
            f.write(f"{efta}\t{cat_ds}\t{disk_str}\t{db_str}\n")

    print(f"Dataset conflicts: {out_file} ({len(results['conflicts'])} entries)")


def main():
    parser = argparse.ArgumentParser(
        description="Three-way gap analysis: DOJ catalog vs DB vs disk"
    )
    parser.add_argument(
        '--skip-db', action='store_true',
        help='Skip database comparison'
    )
    parser.add_argument(
        '--skip-disk', action='store_true',
        help='Skip disk file scanning'
    )
    parser.add_argument(
        '--files-root', type=str, default=DEFAULT_FILES_ROOT,
        help=f'Root directory for physical PDF files (default: {DEFAULT_FILES_ROOT})'
    )
    args = parser.parse_args()

    print(f"{'='*70}")
    print(f"THREE-WAY GAP ANALYSIS")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    # Step 1: Load all three sources
    print("\n[1/4] Loading DOJ catalog...")
    catalog = load_catalog()
    print(f"  Catalog: {len(catalog)} unique EFTAs")

    db_eftas = {}
    if not args.skip_db:
        print("\n[2/4] Loading database records...")
        db_eftas = get_db_eftas()
        print(f"  Database: {len(db_eftas)} unique EFTAs")
    else:
        print("\n[2/4] Database: SKIPPED")

    disk_eftas = {}
    if not args.skip_disk:
        print(f"\n[3/4] Scanning physical files at {args.files_root}...")
        disk_eftas = scan_disk_files(args.files_root)
        print(f"  Disk: {len(disk_eftas)} unique EFTAs")
    else:
        print("\n[3/4] Disk scan: SKIPPED")

    # Step 2-3: Run analysis
    print("\n[4/4] Computing gaps...")
    results = run_analysis(catalog, db_eftas, disk_eftas, args.skip_db, args.skip_disk)

    # Step 4: Write outputs
    print("")
    write_gap_report(results, catalog, db_eftas, disk_eftas, args.skip_db, args.skip_disk)
    write_need_download(results, catalog)

    if not args.skip_db:
        write_need_db_import(results, disk_eftas)

    write_dataset_conflicts(results)

    print(f"\nDone. {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

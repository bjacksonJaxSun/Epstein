#!/usr/bin/env python3
"""
Flatten extracted dataset folders.

Moves all DATA, IMAGES, NATIVES directories from deeply nested paths
to sit directly under DataSet_N/.

Before:
  DataSet_4/DataSet4_extracted/DataSet 4/VOL00004/IMAGES/0001/EFTA*.pdf
After:
  DataSet_4/IMAGES/0001/EFTA*.pdf

Usage:
  python flatten-extracted.py                    # Dry run
  python flatten-extracted.py --execute          # Actually move files
  python flatten-extracted.py --execute --dataset 4  # Only flatten DS4
"""

import argparse
import os
import shutil
import sys

BASE_PATH = r"D:\Personal\Epstein\data\files"
TARGET_FOLDERS = {"DATA", "IMAGES", "NATIVES"}


def find_target_dirs(dataset_root):
    """Find all DATA/IMAGES/NATIVES dirs anywhere under dataset_root,
    excluding those already at the root level."""
    found = []
    for dirpath, dirnames, filenames in os.walk(dataset_root):
        for dname in dirnames:
            if dname in TARGET_FOLDERS:
                full_path = os.path.join(dirpath, dname)
                # Skip if already at root level
                if os.path.dirname(full_path) == dataset_root:
                    continue
                found.append((dname, full_path))
    return found


def count_files(path):
    """Count total files recursively."""
    total = 0
    for _, _, files in os.walk(path):
        total += len(files)
    return total


def move_tree(src, dst, execute=False):
    """Move contents of src into dst, merging directories.
    Returns (files_moved, dirs_created)."""
    files_moved = 0
    dirs_created = 0

    for dirpath, dirnames, filenames in os.walk(src):
        # Compute relative path from src
        rel = os.path.relpath(dirpath, src)
        target_dir = os.path.join(dst, rel) if rel != "." else dst

        # Create target directory if needed
        if not os.path.exists(target_dir):
            if execute:
                os.makedirs(target_dir, exist_ok=True)
            dirs_created += 1

        # Move each file
        for fname in filenames:
            src_file = os.path.join(dirpath, fname)
            dst_file = os.path.join(target_dir, fname)

            if os.path.exists(dst_file):
                # File already exists at target - skip
                src_size = os.path.getsize(src_file)
                dst_size = os.path.getsize(dst_file)
                if src_size == dst_size:
                    print(f"    SKIP (exists, same size): {fname}")
                    if execute:
                        os.remove(src_file)
                    files_moved += 1
                else:
                    print(f"    CONFLICT: {fname} (src={src_size}, dst={dst_size})")
            else:
                if execute:
                    shutil.move(src_file, dst_file)
                files_moved += 1

    return files_moved, dirs_created


def remove_empty_dirs(path):
    """Remove empty directories recursively (bottom-up)."""
    removed = 0
    for dirpath, dirnames, filenames in os.walk(path, topdown=False):
        if not filenames and not os.listdir(dirpath):
            try:
                os.rmdir(dirpath)
                removed += 1
            except OSError:
                pass
    return removed


def flatten_dataset(ds_num, execute=False):
    """Flatten a single dataset."""
    ds_name = f"DataSet_{ds_num}"
    ds_root = os.path.join(BASE_PATH, ds_name)

    if not os.path.isdir(ds_root):
        print(f"  {ds_name}: NOT FOUND, skipping")
        return

    # Find nested DATA/IMAGES/NATIVES dirs
    nested = find_target_dirs(ds_root)

    if not nested:
        print(f"  {ds_name}: Already flat (no nested DATA/IMAGES/NATIVES)")
        return

    print(f"  {ds_name}: Found {len(nested)} nested folder(s)")

    total_files = 0
    for folder_type, src_path in nested:
        file_count = count_files(src_path)
        rel_src = os.path.relpath(src_path, ds_root)
        target = os.path.join(ds_root, folder_type)

        action = "Moving" if execute else "Would move"
        print(f"    {action} {rel_src}/ ({file_count} files) -> {ds_name}/{folder_type}/")

        if file_count == 0:
            print(f"    (empty, skipping)")
            continue

        moved, created = move_tree(src_path, target, execute=execute)
        total_files += moved

    # Clean up empty extracted directories
    if execute:
        # Look for *_extracted dirs and clean them up
        for item in os.listdir(ds_root):
            item_path = os.path.join(ds_root, item)
            if os.path.isdir(item_path) and "_extracted" in item:
                remaining = count_files(item_path)
                if remaining == 0:
                    print(f"    Removing empty: {item}/")
                    shutil.rmtree(item_path)
                else:
                    print(f"    Keeping {item}/ ({remaining} files still inside)")

        # Also clean VOL* dirs at root level if they're now empty
        for item in os.listdir(ds_root):
            item_path = os.path.join(ds_root, item)
            if os.path.isdir(item_path) and item.startswith("VOL"):
                remaining = count_files(item_path)
                if remaining == 0:
                    print(f"    Removing empty: {item}/")
                    shutil.rmtree(item_path)
                else:
                    print(f"    Keeping {item}/ ({remaining} files still inside)")

    print(f"    Total: {total_files} files {'moved' if execute else 'to move'}")


def main():
    parser = argparse.ArgumentParser(description="Flatten extracted dataset folders")
    parser.add_argument("--execute", action="store_true", help="Actually move files (default is dry run)")
    parser.add_argument("--dataset", type=int, help="Only process this dataset number")
    args = parser.parse_args()

    if not os.path.isdir(BASE_PATH):
        print(f"ERROR: Base path not found: {BASE_PATH}")
        sys.exit(1)

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"=== Flatten Extracted Datasets ({mode}) ===\n")

    if args.dataset:
        datasets = [args.dataset]
    else:
        datasets = list(range(1, 13))

    for ds in datasets:
        flatten_dataset(ds, execute=args.execute)
        print()

    if not args.execute:
        print("This was a dry run. Use --execute to actually move files.")


if __name__ == "__main__":
    main()

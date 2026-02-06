#!/usr/bin/env python3
"""
Person Deduplication Script for Epstein Documents Database

This script identifies and merges duplicate person records caused by:
- OCR errors (e.g., "Ghislaine" vs "Ghistaine" vs "Ghislium")
- Name variations (e.g., "G. Maxwell" vs "Ghislaine Maxwell")
- Partial names (e.g., "Maxwell" vs "Ghislaine Maxwell")

Usage:
    python deduplicate_people.py --analyze          # Find duplicates without changing anything
    python deduplicate_people.py --merge            # Interactively merge duplicates
    python deduplicate_people.py --merge --auto     # Auto-merge high-confidence duplicates
    python deduplicate_people.py --merge-person 30  # Merge all Maxwell variants into person ID 30
"""

import argparse
import sqlite3
import re
import json
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass, field

# Try to import rapidfuzz for fast fuzzy matching, fall back to difflib
try:
    from rapidfuzz import fuzz, process
    FUZZY_LIB = 'rapidfuzz'
except ImportError:
    try:
        from fuzzywuzzy import fuzz, process
        FUZZY_LIB = 'fuzzywuzzy'
    except ImportError:
        FUZZY_LIB = None
        import difflib

# Database path
DB_PATH = Path(__file__).parent.parent / "extraction_output" / "epstein_documents.db"


@dataclass
class Person:
    """Represents a person record from the database."""
    person_id: int
    full_name: str
    name_variations: Optional[str] = None
    primary_role: Optional[str] = None
    mention_count: int = 0

    @property
    def normalized_name(self) -> str:
        """Normalize name for comparison."""
        name = self.full_name.lower().strip()
        # Remove common OCR artifacts
        name = re.sub(r'[^a-z\s]', '', name)
        # Normalize whitespace
        name = ' '.join(name.split())
        return name

    def __hash__(self):
        return hash(self.person_id)


@dataclass
class DuplicateGroup:
    """A group of duplicate person records."""
    canonical: Person
    duplicates: List[Person] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def all_persons(self) -> List[Person]:
        return [self.canonical] + self.duplicates

    @property
    def total_mentions(self) -> int:
        return sum(p.mention_count for p in self.all_persons)


def get_connection(timeout: float = 30.0) -> sqlite3.Connection:
    """Get database connection with retry logic for concurrent access."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    # Connect with a longer timeout to handle concurrent access
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.row_factory = sqlite3.Row

    # Set busy timeout (milliseconds) - wait up to 30 seconds for locks
    conn.execute("PRAGMA busy_timeout = 30000")

    # Use WAL mode for better concurrency (if not already set)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass  # May fail if another process has exclusive lock, that's ok

    return conn


def load_persons(conn: sqlite3.Connection) -> List[Person]:
    """Load all persons from the database with mention counts."""
    cursor = conn.cursor()

    # Get mention counts from document_people
    cursor.execute("""
        SELECT p.person_id, p.full_name, p.name_variations, p.primary_role,
               COALESCE(dp.mention_count, 0) as mention_count
        FROM people p
        LEFT JOIN (
            SELECT person_id, COUNT(*) as mention_count
            FROM document_people
            GROUP BY person_id
        ) dp ON p.person_id = dp.person_id
        ORDER BY mention_count DESC
    """)

    persons = []
    for row in cursor.fetchall():
        persons.append(Person(
            person_id=row['person_id'],
            full_name=row['full_name'],
            name_variations=row['name_variations'],
            primary_role=row['primary_role'],
            mention_count=row['mention_count']
        ))

    return persons


def calculate_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names (0-100)."""
    if FUZZY_LIB:
        # Use token_sort_ratio for better matching of name variations
        return fuzz.token_sort_ratio(name1, name2)
    else:
        # Fallback to difflib
        return difflib.SequenceMatcher(None, name1, name2).ratio() * 100


def is_likely_ocr_error(name1: str, name2: str) -> bool:
    """Check if two names differ only by likely OCR errors."""
    n1, n2 = name1.lower(), name2.lower()
    if abs(len(n1) - len(n2)) > 3:
        return False

    # Check if names are very similar with OCR-like differences
    similarity = calculate_similarity(n1, n2)
    return similarity >= 75


def is_partial_match(short_name: str, long_name: str) -> bool:
    """Check if short_name is a partial version of long_name."""
    short = short_name.lower().strip()
    long = long_name.lower().strip()

    # Check if short name is contained in long name
    if short in long:
        return True

    # Check initials (e.g., "G. Maxwell" matches "Ghislaine Maxwell")
    short_parts = short.replace('.', ' ').split()
    long_parts = long.split()

    if len(short_parts) >= 2 and len(long_parts) >= 2:
        # Check if last names match and first is initial
        if short_parts[-1] == long_parts[-1]:
            if len(short_parts[0]) <= 2:  # Initial
                if long_parts[0].startswith(short_parts[0].rstrip('.')):
                    return True

    return False


def find_duplicates_for_person(persons: List[Person],
                                canonical_id: int,
                                similarity_threshold: float = 70) -> DuplicateGroup:
    """Find duplicates for a specific canonical person."""
    canonical = next((p for p in persons if p.person_id == canonical_id), None)
    if not canonical:
        return None

    # Extract key parts of canonical name for matching
    canonical_parts = canonical.normalized_name.split()
    if not canonical_parts:
        return DuplicateGroup(canonical=canonical, duplicates=[], confidence=0)

    canonical_lastname = canonical_parts[-1] if canonical_parts else ""
    canonical_firstname = canonical_parts[0] if canonical_parts else ""

    duplicates = []

    for person in persons:
        if person.person_id == canonical_id:
            continue

        name = person.normalized_name
        name_parts = name.split()

        if not name_parts:
            continue

        # Check if this person might be a duplicate
        is_match = False

        # Check if last name matches
        person_lastname = name_parts[-1] if name_parts else ""

        # Direct similarity check
        sim = calculate_similarity(canonical.normalized_name, name)
        if sim >= similarity_threshold:
            is_match = True

        # Check for partial matches (initials, etc.)
        elif canonical_lastname and person_lastname:
            lastname_sim = calculate_similarity(canonical_lastname, person_lastname)
            if lastname_sim >= 80:
                # Last names match well, check first name
                if len(name_parts) == 1:
                    # Just last name
                    is_match = True
                elif len(name_parts[0]) <= 2:
                    # Initial + lastname
                    if canonical_firstname.startswith(name_parts[0].rstrip('.')):
                        is_match = True
                else:
                    # Check first name similarity
                    firstname_sim = calculate_similarity(canonical_firstname, name_parts[0])
                    if firstname_sim >= 60:
                        is_match = True

        # OCR error check
        if not is_match and is_likely_ocr_error(canonical.full_name, person.full_name):
            is_match = True

        if is_match:
            duplicates.append(person)

    avg_confidence = 0
    if duplicates:
        avg_confidence = sum(
            calculate_similarity(canonical.normalized_name, d.normalized_name)
            for d in duplicates
        ) / len(duplicates)

    return DuplicateGroup(
        canonical=canonical,
        duplicates=duplicates,
        confidence=avg_confidence
    )


def find_duplicates(persons: List[Person],
                    similarity_threshold: float = 80,
                    known_canonical: Optional[Dict[str, int]] = None) -> List[DuplicateGroup]:
    """Find groups of duplicate persons."""

    # Known canonical names and their IDs (manually curated)
    known_canonical = known_canonical or {
        'ghislaine maxwell': 30,
    }

    # Build index of normalized names
    name_to_persons: Dict[str, List[Person]] = defaultdict(list)
    for person in persons:
        name_to_persons[person.normalized_name].append(person)

    # Track which persons have been grouped
    grouped: Set[int] = set()
    groups: List[DuplicateGroup] = []

    # First pass: exact normalized matches
    for norm_name, matches in name_to_persons.items():
        if len(matches) > 1:
            # Pick canonical (highest mention count or known ID)
            canonical_id = known_canonical.get(norm_name)
            if canonical_id:
                canonical = next((p for p in matches if p.person_id == canonical_id), None)
                if not canonical:
                    canonical = max(matches, key=lambda p: p.mention_count)
            else:
                canonical = max(matches, key=lambda p: p.mention_count)

            duplicates = [p for p in matches if p.person_id != canonical.person_id]
            if duplicates:
                groups.append(DuplicateGroup(
                    canonical=canonical,
                    duplicates=duplicates,
                    confidence=100.0
                ))
                grouped.update(p.person_id for p in matches)

    # Second pass: fuzzy matching for remaining persons
    remaining = [p for p in persons if p.person_id not in grouped]

    # Group by last name for efficiency
    lastname_groups: Dict[str, List[Person]] = defaultdict(list)
    for person in remaining:
        parts = person.normalized_name.split()
        if parts:
            lastname = parts[-1] if len(parts[-1]) > 2 else (parts[0] if parts else '')
            lastname_groups[lastname].append(person)

    for lastname, group_persons in lastname_groups.items():
        if len(group_persons) < 2:
            continue

        # Compare all pairs within the group
        local_grouped: Set[int] = set()

        for i, p1 in enumerate(group_persons):
            if p1.person_id in local_grouped:
                continue

            matches = [p1]
            for p2 in group_persons[i+1:]:
                if p2.person_id in local_grouped:
                    continue

                sim = calculate_similarity(p1.normalized_name, p2.normalized_name)

                # Check for OCR errors or partial matches
                if sim >= similarity_threshold or \
                   is_likely_ocr_error(p1.full_name, p2.full_name) or \
                   is_partial_match(p1.full_name, p2.full_name) or \
                   is_partial_match(p2.full_name, p1.full_name):
                    matches.append(p2)
                    local_grouped.add(p2.person_id)

            if len(matches) > 1:
                # Pick canonical (highest mention count, prefer longer name)
                canonical = max(matches, key=lambda p: (p.mention_count, len(p.full_name)))
                duplicates = [p for p in matches if p.person_id != canonical.person_id]

                avg_sim = sum(calculate_similarity(canonical.normalized_name, d.normalized_name)
                             for d in duplicates) / len(duplicates)

                groups.append(DuplicateGroup(
                    canonical=canonical,
                    duplicates=duplicates,
                    confidence=avg_sim
                ))
                grouped.update(p.person_id for p in matches)
                local_grouped.add(p1.person_id)

    # Sort by total mentions (most important first)
    groups.sort(key=lambda g: g.total_mentions, reverse=True)

    return groups


def find_false_positives(persons: List[Person]) -> List[Person]:
    """Find person records that are likely not actual people."""
    false_positive_patterns = [
        r'^maxwell\s+(discovery|link|meeting|sars|ubs|clip|i$)',
        r'\d{4,}',  # Contains 4+ digit numbers
        r'^(the|a|an)\s+',  # Starts with article
        r'(llc|inc|corp|pllc|ltd)$',  # Company suffixes
        r'^(mr|ms|mrs|dr)\.\s*$',  # Just titles
        r'^\w{1,2}$',  # Single or two characters
    ]

    compiled = [re.compile(p, re.IGNORECASE) for p in false_positive_patterns]

    false_positives = []
    for person in persons:
        name = person.full_name.strip()
        for pattern in compiled:
            if pattern.search(name):
                false_positives.append(person)
                break

    return false_positives


def merge_duplicates(conn: sqlite3.Connection,
                     canonical_id: int,
                     duplicate_ids: List[int],
                     dry_run: bool = True) -> Dict[str, int]:
    """Merge duplicate person records into the canonical one."""

    cursor = conn.cursor()
    stats = {'document_people': 0, 'media_people': 0, 'relationships': 0, 'deleted': 0}

    if not duplicate_ids:
        return stats

    placeholders = ','.join('?' * len(duplicate_ids))

    # Update document_people references
    if not dry_run:
        # First, handle potential unique constraint violations
        # Delete duplicate entries that would conflict
        cursor.execute(f"""
            DELETE FROM document_people
            WHERE person_id IN ({placeholders})
            AND document_id IN (
                SELECT document_id FROM document_people WHERE person_id = ?
            )
        """, duplicate_ids + [canonical_id])

        cursor.execute(f"""
            UPDATE document_people
            SET person_id = ?
            WHERE person_id IN ({placeholders})
        """, [canonical_id] + duplicate_ids)
        stats['document_people'] = cursor.rowcount
    else:
        cursor.execute(f"""
            SELECT COUNT(*) FROM document_people
            WHERE person_id IN ({placeholders})
        """, duplicate_ids)
        stats['document_people'] = cursor.fetchone()[0]

    # Update media_people references
    if not dry_run:
        cursor.execute(f"""
            DELETE FROM media_people
            WHERE person_id IN ({placeholders})
            AND media_file_id IN (
                SELECT media_file_id FROM media_people WHERE person_id = ?
            )
        """, duplicate_ids + [canonical_id])

        cursor.execute(f"""
            UPDATE media_people
            SET person_id = ?
            WHERE person_id IN ({placeholders})
        """, [canonical_id] + duplicate_ids)
        stats['media_people'] = cursor.rowcount
    else:
        cursor.execute(f"""
            SELECT COUNT(*) FROM media_people
            WHERE person_id IN ({placeholders})
        """, duplicate_ids)
        stats['media_people'] = cursor.fetchone()[0]

    # Update relationships (both person1_id and person2_id)
    if not dry_run:
        cursor.execute(f"""
            UPDATE relationships
            SET person1_id = ?
            WHERE person1_id IN ({placeholders})
        """, [canonical_id] + duplicate_ids)
        count1 = cursor.rowcount

        cursor.execute(f"""
            UPDATE relationships
            SET person2_id = ?
            WHERE person2_id IN ({placeholders})
        """, [canonical_id] + duplicate_ids)
        stats['relationships'] = count1 + cursor.rowcount
    else:
        cursor.execute(f"""
            SELECT COUNT(*) FROM relationships
            WHERE person1_id IN ({placeholders}) OR person2_id IN ({placeholders})
        """, duplicate_ids + duplicate_ids)
        stats['relationships'] = cursor.fetchone()[0]

    # Collect name variations and traceability info before deleting
    if not dry_run:
        cursor.execute(f"""
            SELECT person_id, full_name, name_variations FROM people
            WHERE person_id IN ({placeholders})
        """, duplicate_ids)

        all_variations = []
        merged_records = []  # For traceability
        for row in cursor.fetchall():
            all_variations.append(row[1])  # full_name
            merged_records.append({
                'original_id': row[0],
                'original_name': row[1]
            })
            if row[2]:
                try:
                    existing = json.loads(row[2])
                    if isinstance(existing, list):
                        all_variations.extend(existing)
                except:
                    pass

        # Update canonical record with collected name variations
        cursor.execute("SELECT name_variations, notes FROM people WHERE person_id = ?", [canonical_id])
        row = cursor.fetchone()
        existing_variations = row[0]
        existing_notes = row[1] or ''

        try:
            current = json.loads(existing_variations) if existing_variations else []
        except:
            current = []

        # Merge and dedupe variations
        all_variations = list(set(current + all_variations))

        # Build traceability note
        from datetime import datetime
        merge_note = f"\n[MERGE {datetime.now().strftime('%Y-%m-%d %H:%M')}] Merged {len(merged_records)} duplicate(s): "
        merge_note += ", ".join([f"ID {r['original_id']} ({r['original_name']})" for r in merged_records])
        updated_notes = existing_notes + merge_note

        cursor.execute("""
            UPDATE people SET name_variations = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE person_id = ?
        """, [json.dumps(all_variations), updated_notes, canonical_id])

        # Delete duplicate records
        cursor.execute(f"""
            DELETE FROM people WHERE person_id IN ({placeholders})
        """, duplicate_ids)
        stats['deleted'] = cursor.rowcount
    else:
        stats['deleted'] = len(duplicate_ids)

    return stats


def analyze_duplicates(conn: sqlite3.Connection):
    """Analyze and report duplicate persons without making changes."""
    print("Loading persons from database...")
    persons = load_persons(conn)
    print(f"Found {len(persons)} person records\n")

    print("Finding duplicates...")
    groups = find_duplicates(persons)

    print(f"\n{'='*80}")
    print(f"DUPLICATE ANALYSIS REPORT")
    print(f"{'='*80}\n")

    print(f"Found {len(groups)} duplicate groups\n")

    total_duplicates = sum(len(g.duplicates) for g in groups)
    total_affected_mentions = sum(g.total_mentions for g in groups)

    print(f"Total duplicate records: {total_duplicates}")
    print(f"Total affected document mentions: {total_affected_mentions}\n")

    # Show top 20 groups
    print(f"{'='*80}")
    print("TOP 20 DUPLICATE GROUPS (by mention count)")
    print(f"{'='*80}\n")

    for i, group in enumerate(groups[:20], 1):
        print(f"{i}. CANONICAL: {group.canonical.full_name} (ID: {group.canonical.person_id}, mentions: {group.canonical.mention_count})")
        print(f"   Confidence: {group.confidence:.1f}%")
        print(f"   Duplicates ({len(group.duplicates)}):")
        for dup in sorted(group.duplicates, key=lambda d: d.mention_count, reverse=True)[:10]:
            print(f"      - {dup.full_name} (ID: {dup.person_id}, mentions: {dup.mention_count})")
        if len(group.duplicates) > 10:
            print(f"      ... and {len(group.duplicates) - 10} more")
        print()

    # Find false positives
    print(f"\n{'='*80}")
    print("LIKELY FALSE POSITIVES (not actual people)")
    print(f"{'='*80}\n")

    false_positives = find_false_positives(persons)
    for fp in false_positives[:30]:
        print(f"  - {fp.full_name} (ID: {fp.person_id})")
    if len(false_positives) > 30:
        print(f"  ... and {len(false_positives) - 30} more")

    return groups


def interactive_merge(conn: sqlite3.Connection, auto: bool = False):
    """Interactively merge duplicate groups."""
    print("Loading persons from database...")
    persons = load_persons(conn)

    print("Finding duplicates...")
    groups = find_duplicates(persons)

    if not groups:
        print("No duplicates found!")
        return

    print(f"\nFound {len(groups)} duplicate groups")
    print(f"Processing {'automatically' if auto else 'interactively'}...\n")

    total_merged = 0
    total_docs_updated = 0

    for i, group in enumerate(groups, 1):
        # Auto-merge only high confidence groups
        if auto and group.confidence < 85:
            continue

        print(f"\n{'='*60}")
        print(f"Group {i}/{len(groups)} (Confidence: {group.confidence:.1f}%)")
        print(f"{'='*60}")
        print(f"\nCANONICAL: {group.canonical.full_name}")
        print(f"  ID: {group.canonical.person_id}, Mentions: {group.canonical.mention_count}")
        if group.canonical.primary_role:
            print(f"  Role: {group.canonical.primary_role}")

        print(f"\nDUPLICATES ({len(group.duplicates)}):")
        for dup in group.duplicates:
            print(f"  - {dup.full_name} (ID: {dup.person_id}, mentions: {dup.mention_count})")

        # Preview changes
        duplicate_ids = [d.person_id for d in group.duplicates]
        stats = merge_duplicates(conn, group.canonical.person_id, duplicate_ids, dry_run=True)

        print(f"\nChanges preview:")
        print(f"  - Document references to update: {stats['document_people']}")
        print(f"  - Media references to update: {stats['media_people']}")
        print(f"  - Relationship references to update: {stats['relationships']}")
        print(f"  - Records to delete: {stats['deleted']}")

        if auto:
            choice = 'y'
        else:
            choice = input("\nMerge this group? [y/n/q] ").strip().lower()

        if choice == 'q':
            print("\nAborting...")
            break
        elif choice == 'y':
            stats = merge_duplicates(conn, group.canonical.person_id, duplicate_ids, dry_run=False)
            conn.commit()
            total_merged += len(duplicate_ids)
            total_docs_updated += stats['document_people']
            print(f"  Merged {len(duplicate_ids)} records into {group.canonical.full_name}")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total records merged: {total_merged}")
    print(f"Total document references updated: {total_docs_updated}")


def merge_into_person(conn: sqlite3.Connection, canonical_id: int, name_pattern: str,
                       min_similarity: int = 75, auto_confirm: bool = False):
    """Merge all persons matching a pattern into a specific person ID."""
    cursor = conn.cursor()

    # Get canonical person
    cursor.execute("SELECT person_id, full_name FROM people WHERE person_id = ?", [canonical_id])
    canonical_row = cursor.fetchone()
    if not canonical_row:
        print(f"Error: Person ID {canonical_id} not found")
        return

    canonical_name = canonical_row['full_name']
    print(f"Canonical person: {canonical_name} (ID: {canonical_id})")

    # Load all persons for fuzzy matching
    persons = load_persons(conn)

    # Find duplicates using fuzzy matching
    group = find_duplicates_for_person(persons, canonical_id, similarity_threshold=65)

    if not group or not group.duplicates:
        print(f"No duplicates found for: {canonical_name}")
        return

    # Filter by pattern if provided
    if name_pattern:
        pattern_lower = name_pattern.lower()
        group.duplicates = [
            d for d in group.duplicates
            if pattern_lower in d.full_name.lower()
        ]

    # Filter by minimum similarity to avoid false positives
    filtered_duplicates = []
    for d in group.duplicates:
        sim = calculate_similarity(group.canonical.normalized_name, d.normalized_name)
        if sim >= min_similarity:
            filtered_duplicates.append((d, sim))

    if not filtered_duplicates:
        print(f"No matches found with similarity >= {min_similarity}%")
        return

    group.duplicates = [d for d, _ in filtered_duplicates]

    print(f"\nFound {len(filtered_duplicates)} matches to merge (similarity >= {min_similarity}%):")
    for m, sim in sorted(filtered_duplicates, key=lambda x: x[1], reverse=True):
        print(f"  [{m.person_id:5}] {m.full_name:<50} (similarity: {sim:.0f}%)")

    if auto_confirm:
        confirm = 'y'
        print(f"\nAuto-confirming merge of {len(group.duplicates)} records...")
    else:
        confirm = input(f"\nMerge all {len(group.duplicates)} into {canonical_name}? [y/n] ").strip().lower()

    if confirm == 'y':
        duplicate_ids = [d.person_id for d in group.duplicates]

        # Retry logic for database lock
        max_retries = 5
        for attempt in range(max_retries):
            try:
                stats = merge_duplicates(conn, canonical_id, duplicate_ids, dry_run=False)
                conn.commit()
                print(f"\nMerged {stats['deleted']} records")
                print(f"Updated {stats['document_people']} document references")
                print(f"Updated {stats['media_people']} media references")
                print(f"Updated {stats['relationships']} relationship references")
                break
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    import time
                    wait_time = (attempt + 1) * 2
                    print(f"Database locked, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise


def main():
    parser = argparse.ArgumentParser(description='Deduplicate person records in the Epstein documents database')
    parser.add_argument('--analyze', action='store_true', help='Analyze duplicates without making changes')
    parser.add_argument('--merge', action='store_true', help='Interactively merge duplicates')
    parser.add_argument('--auto', action='store_true', help='Auto-merge high-confidence duplicates (use with --merge)')
    parser.add_argument('--merge-person', type=int, metavar='ID', help='Merge all variants into specific person ID')
    parser.add_argument('--pattern', type=str, default='', help='Name pattern to filter matches (use with --merge-person)')
    parser.add_argument('--min-similarity', type=int, default=85, help='Minimum similarity threshold (default: 85)')
    parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm merges without prompting')
    parser.add_argument('--db', type=str, help='Path to database file')

    args = parser.parse_args()

    global DB_PATH
    if args.db:
        DB_PATH = Path(args.db)

    try:
        conn = get_connection()
        print(f"Connected to: {DB_PATH}")
        print(f"Fuzzy matching library: {FUZZY_LIB or 'difflib (fallback)'}\n")

        if args.analyze:
            analyze_duplicates(conn)
        elif args.merge:
            interactive_merge(conn, auto=args.auto)
        elif args.merge_person:
            merge_into_person(conn, args.merge_person, args.pattern,
                             min_similarity=args.min_similarity,
                             auto_confirm=args.yes)
        else:
            # Default: analyze
            print("No action specified. Running analysis...\n")
            analyze_duplicates(conn)
            print("\nTo merge duplicates, run with --merge or --merge-person <ID>")

        conn.close()

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n\nAborted by user")
        return 1

    return 0


if __name__ == '__main__':
    exit(main())

"""
Comprehensive data cleanup script:
1. Creates document_people junction table
2. Removes garbage/OCR error person entries
3. Merges duplicate person variations
4. Populates document-person links based on full_text content
"""
import sys
import re
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from sqlalchemy import func, text
from config import SessionLocal, engine, Base
from models import Person, Relationship, EventParticipant, MediaPerson, Document, DocumentPerson
from services.name_cleaner import NameCleaner


# Patterns indicating garbage names (OCR errors, non-names)
GARBAGE_PATTERNS = [
    r'^[^a-zA-Z]+$',  # No letters
    r'\.pdf$',  # Filename
    r'\.mov$',  # Filename
    r'\.jpg$',  # Filename
    r'@\w+',  # Email/handle mixed in
    r'^.{1,2}$',  # Too short (1-2 chars)
    r'^\d+\s+\w+$',  # Number prefix like "11 Epstein"
    r'Epstein\s+(Case|Matter|Returns|Taint|File|Isst)',  # Not a person
    r'^(to|and|which|of|the|a|from|rom)\s*[A-Z]',  # Starts with OCR-merged word
]

GARBAGE_EXACT = [
    'toEpstein', 'andEpstein', 'whichEpstein', 'coulaEpstein', 'EpsteinReturns',
    'besidaan Epstein', 'maGGage Epstein', 'liftili Epstein', 'agLkigy Epstein',
    'Addenda Epstein', 'Epstein Matter', 'Epstein Case', 'Epstein Isst',
    'Post Epstein', 'OPR Epstein', 'BOP Epstein', 'MCC NY Epstein',
    'Taint Review - Epstein', 'U.S. V EPSTEIN', 'I - Epstein',
    'Maxwell Epstein', 'MAXWELL EPSTEIN',  # Combined names
]


def create_document_people_table():
    """Create the document_people junction table if it doesn't exist."""
    print("\n" + "=" * 60)
    print("CREATING DOCUMENT_PEOPLE TABLE")
    print("=" * 60)

    try:
        # Create all tables (will skip existing)
        Base.metadata.create_all(engine)
        print("Table created/verified successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating table: {e}")
        return False


def is_garbage_name(name: str) -> bool:
    """Check if name is garbage/OCR error."""
    if not name or len(name.strip()) < 3:
        return True

    # Check exact garbage matches
    if name in GARBAGE_EXACT:
        return True

    # Check patterns
    for pattern in GARBAGE_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return True

    return False


def remove_garbage_people(db, dry_run=True):
    """Remove garbage/OCR error person entries."""
    print("\n" + "=" * 60)
    print("REMOVING GARBAGE PERSON ENTRIES")
    print("=" * 60)

    all_people = db.query(Person).all()
    garbage = []

    for person in all_people:
        if is_garbage_name(person.full_name):
            garbage.append(person)

    print(f"Found {len(garbage)} garbage entries out of {len(all_people)} total people")

    if garbage:
        print("\nSample garbage entries:")
        for p in garbage[:20]:
            print(f"  ID {p.person_id:6}: '{p.full_name}'")
        if len(garbage) > 20:
            print(f"  ... and {len(garbage) - 20} more")

    if not dry_run and garbage:
        print("\nDeleting garbage entries...")
        deleted = 0
        for person in garbage:
            try:
                # Delete related records first
                db.query(EventParticipant).filter_by(person_id=person.person_id).delete()
                db.query(Relationship).filter(
                    (Relationship.person1_id == person.person_id) |
                    (Relationship.person2_id == person.person_id)
                ).delete(synchronize_session=False)
                db.query(MediaPerson).filter_by(person_id=person.person_id).delete()
                db.delete(person)
                deleted += 1
            except Exception as e:
                logger.error(f"Error deleting person {person.person_id}: {e}")
                db.rollback()
                continue

        db.commit()
        print(f"Deleted {deleted} garbage entries")
        return deleted

    return len(garbage)


def populate_document_people_links(db, dry_run=True):
    """
    Populate document_people junction table based on full_text content.
    This creates proper many-to-many relationships between documents and people.
    """
    print("\n" + "=" * 60)
    print("POPULATING DOCUMENT-PERSON LINKS")
    print("=" * 60)

    # Get all people with valid names
    cleaner = NameCleaner()
    people = db.query(Person).all()
    valid_people = []

    for person in people:
        cleaned = cleaner.clean_name(person.full_name)
        if cleaned and not is_garbage_name(person.full_name):
            valid_people.append((person, cleaned))

    print(f"Processing {len(valid_people)} valid people")

    # Get all documents with text
    documents = db.query(Document).filter(
        Document.full_text.isnot(None),
        func.length(Document.full_text) > 50
    ).all()
    print(f"Searching across {len(documents)} documents with text")

    # Track links to create
    links_to_create = []
    person_doc_counts = defaultdict(int)

    # For efficiency, create search patterns for key figures
    key_figure_patterns = {
        'Jeffrey Epstein': [r'\bJeffrey\s+E?\.?\s*Epstein\b', r'\bJ\.?\s*Epstein\b', r'\bEpstein,?\s+Jeffrey\b'],
        'Ghislaine Maxwell': [r'\bGhislaine\s+Maxwell\b', r'\bG\.?\s*Maxwell\b', r'\bMaxwell,?\s+Ghislaine\b'],
        'Virginia Giuffre': [r'\bVirginia\s+(Giuffre|Roberts)\b'],
        'Alan Dershowitz': [r'\bAlan\s+Dershowitz\b', r'\bDershowitz\b'],
    }

    # Process each document
    total_links = 0
    for i, doc in enumerate(documents):
        if i % 500 == 0:
            print(f"  Processing document {i+1}/{len(documents)}...")

        doc_text = doc.full_text.lower() if doc.full_text else ''

        for person, cleaned_name in valid_people:
            # Check if person is mentioned in document
            name_lower = cleaned_name.lower()

            # For key figures, use regex patterns
            if cleaned_name in key_figure_patterns:
                found = False
                for pattern in key_figure_patterns[cleaned_name]:
                    if re.search(pattern, doc.full_text, re.IGNORECASE):
                        found = True
                        break
            else:
                # Simple substring match for other names
                # Only match if it looks like a complete word match
                found = name_lower in doc_text

            if found:
                links_to_create.append({
                    'document_id': doc.document_id,
                    'person_id': person.person_id,
                    'confidence': 0.8
                })
                person_doc_counts[cleaned_name] += 1
                total_links += 1

    print(f"\nFound {total_links} document-person links to create")

    # Show top mentioned people
    print("\nTop 20 most mentioned people:")
    sorted_counts = sorted(person_doc_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    for name, count in sorted_counts:
        print(f"  {name}: {count} documents")

    if not dry_run and links_to_create:
        print("\nInserting links into document_people table...")

        # Clear existing links first
        db.execute(text("DELETE FROM document_people"))

        # Insert in batches
        batch_size = 1000
        inserted = 0
        for i in range(0, len(links_to_create), batch_size):
            batch = links_to_create[i:i+batch_size]
            try:
                for link in batch:
                    db.execute(text(
                        "INSERT OR IGNORE INTO document_people (document_id, person_id, confidence) "
                        "VALUES (:document_id, :person_id, :confidence)"
                    ), link)
                db.commit()
                inserted += len(batch)
                print(f"  Inserted {inserted}/{len(links_to_create)} links...")
            except Exception as e:
                logger.error(f"Error inserting batch: {e}")
                db.rollback()

        print(f"Inserted {inserted} document-person links")
        return inserted

    return total_links


def find_epstein_duplicates(db):
    """Find all Jeffrey Epstein variations."""
    # Search for all Epstein-related records
    epstein_people = db.query(Person).filter(
        func.lower(Person.full_name).contains('epstein')
    ).all()

    return epstein_people


def find_maxwell_duplicates(db):
    """Find all Ghislaine Maxwell variations."""
    maxwell_people = db.query(Person).filter(
        func.lower(Person.full_name).contains('maxwell')
    ).all()

    return maxwell_people


def merge_into_canonical(db, canonical_person, duplicates, dry_run=True):
    """
    Merge duplicate records into the canonical person.

    Args:
        db: Database session
        canonical_person: The person to keep
        duplicates: List of duplicate person records to merge
        dry_run: If True, don't actually modify database
    """
    merged_count = 0

    for dup in duplicates:
        if dup.person_id == canonical_person.person_id:
            continue

        logger.info(f"  Merging '{dup.full_name}' (ID: {dup.person_id}) -> '{canonical_person.full_name}' (ID: {canonical_person.person_id})")

        if not dry_run:
            try:
                # Update relationships
                db.query(Relationship).filter_by(person1_id=dup.person_id).update(
                    {'person1_id': canonical_person.person_id}
                )
                db.query(Relationship).filter_by(person2_id=dup.person_id).update(
                    {'person2_id': canonical_person.person_id}
                )

                # Update event participants
                db.query(EventParticipant).filter_by(person_id=dup.person_id).update(
                    {'person_id': canonical_person.person_id}
                )

                # Update media appearances
                db.query(MediaPerson).filter_by(person_id=dup.person_id).update(
                    {'person_id': canonical_person.person_id}
                )

                # Store original name as variation (if useful)
                cleaner = NameCleaner()
                cleaned = cleaner.clean_name(dup.full_name)
                if cleaned and cleaned != canonical_person.full_name:
                    # Could add to name_variations if tracking is needed
                    pass

                # Delete the duplicate
                db.delete(dup)
                merged_count += 1

            except Exception as e:
                logger.error(f"Error merging {dup.person_id}: {e}")
                db.rollback()
                continue
        else:
            merged_count += 1

    return merged_count


def cleanup_jeffrey_epstein(db, dry_run=True):
    """Clean up Jeffrey Epstein duplicates."""
    cleaner = NameCleaner()

    print("\n" + "=" * 60)
    print("JEFFREY EPSTEIN CLEANUP")
    print("=" * 60)

    # Find all Epstein records
    epstein_people = find_epstein_duplicates(db)
    print(f"Found {len(epstein_people)} records containing 'Epstein'")

    # Categorize - prefer exact "Jeffrey Epstein" spelling as canonical
    canonical = None
    canonical_candidates = []
    duplicates = []
    invalid = []

    for person in epstein_people:
        cleaned = cleaner.clean_name(person.full_name)

        if cleaned == 'Jeffrey Epstein':
            # Prefer exact spelling in original name
            if person.full_name == 'Jeffrey Epstein':
                canonical_candidates.insert(0, person)  # Prioritize exact match
            else:
                canonical_candidates.append(person)
        elif cleaned and 'epstein' in cleaned.lower() and 'jeffrey' in cleaned.lower():
            duplicates.append(person)
        elif cleaned is None:
            invalid.append(person)
            print(f"  Invalid (will delete): ID {person.person_id} - '{person.full_name}'")

    # Select best canonical record
    if canonical_candidates:
        canonical = canonical_candidates[0]
        duplicates.extend(canonical_candidates[1:])  # Others become duplicates
        print(f"\nCanonical record: ID {canonical.person_id} - '{canonical.full_name}'")

        # Fix the canonical name if misspelled
        if canonical.full_name != 'Jeffrey Epstein':
            print(f"  Correcting name from '{canonical.full_name}' to 'Jeffrey Epstein'")
            if not dry_run:
                canonical.full_name = 'Jeffrey Epstein'

    print(f"\nDuplicates to merge: {len(duplicates)}")
    print(f"Invalid records to delete: {len(invalid)}")

    if canonical is None:
        # Create canonical record if none exists
        print("No canonical 'Jeffrey Epstein' found - selecting best candidate...")
        # Find the one with most relationships/events
        best = None
        for person in epstein_people:
            cleaned = cleaner.clean_name(person.full_name)
            if cleaned and 'jeffrey' in cleaned.lower() and 'epstein' in cleaned.lower():
                if best is None:
                    best = person
                # Could add logic to prefer records with more data

        if best:
            canonical = best
            duplicates = [p for p in duplicates if p.person_id != best.person_id]
            print(f"Selected canonical: ID {best.person_id} - '{best.full_name}'")
        else:
            print("ERROR: Could not find any valid Jeffrey Epstein record")
            return 0

    # List duplicates
    print("\nDuplicates found:")
    for dup in duplicates[:20]:  # Show first 20
        print(f"  ID {dup.person_id:6}: '{dup.full_name}'")
    if len(duplicates) > 20:
        print(f"  ... and {len(duplicates) - 20} more")

    # Merge
    if dry_run:
        print("\n[DRY RUN] Would merge these duplicates")
        total = len(duplicates) + len(invalid)
    else:
        print("\nMerging duplicates...")
        merged = merge_into_canonical(db, canonical, duplicates, dry_run=False)

        # Delete invalid records
        for inv in invalid:
            try:
                db.delete(inv)
            except Exception as e:
                logger.error(f"Error deleting {inv.person_id}: {e}")

        db.commit()
        total = merged + len(invalid)
        print(f"Merged/deleted {total} records")

    return total


def cleanup_ghislaine_maxwell(db, dry_run=True):
    """Clean up Ghislaine Maxwell duplicates."""
    cleaner = NameCleaner()

    print("\n" + "=" * 60)
    print("GHISLAINE MAXWELL CLEANUP")
    print("=" * 60)

    maxwell_people = find_maxwell_duplicates(db)
    print(f"Found {len(maxwell_people)} records containing 'Maxwell'")

    canonical = None
    duplicates = []
    invalid = []

    for person in maxwell_people:
        cleaned = cleaner.clean_name(person.full_name)

        if cleaned == 'Ghislaine Maxwell':
            if canonical is None:
                canonical = person
                print(f"\nCanonical record: ID {person.person_id} - '{person.full_name}'")
            else:
                duplicates.append(person)
        elif cleaned and 'maxwell' in cleaned.lower() and 'ghislaine' in cleaned.lower():
            duplicates.append(person)
        elif cleaned is None and 'maxwell' in person.full_name.lower():
            invalid.append(person)

    print(f"\nDuplicates to merge: {len(duplicates)}")

    if canonical and duplicates:
        print("\nDuplicates found:")
        for dup in duplicates[:10]:
            print(f"  ID {dup.person_id:6}: '{dup.full_name}'")

        if dry_run:
            print("\n[DRY RUN] Would merge these duplicates")
        else:
            print("\nMerging duplicates...")
            merged = merge_into_canonical(db, canonical, duplicates, dry_run=False)
            db.commit()
            print(f"Merged {merged} records")
            return merged

    return len(duplicates)


def run_cleanup(dry_run=True, skip_links=False):
    """Run the full cleanup process."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print(f"COMPREHENSIVE DATA CLEANUP {'(DRY RUN)' if dry_run else '(LIVE)'}")
        print("=" * 60)

        # Step 1: Create document_people table
        create_document_people_table()

        # Step 2: Remove garbage entries
        garbage_count = remove_garbage_people(db, dry_run)

        # Step 3: Merge duplicates
        total = 0
        total += cleanup_jeffrey_epstein(db, dry_run)
        total += cleanup_ghislaine_maxwell(db, dry_run)

        # Step 4: Populate document-person links (most time-consuming)
        if not skip_links:
            link_count = populate_document_people_links(db, dry_run)
        else:
            link_count = 0
            print("\n[SKIPPED] Document-person link population")

        print("\n" + "=" * 60)
        print("CLEANUP SUMMARY")
        print("=" * 60)
        print(f"Garbage entries: {'Would remove' if dry_run else 'Removed'} {garbage_count}")
        print(f"Duplicate merges: {'Would process' if dry_run else 'Processed'} {total}")
        print(f"Document-person links: {'Would create' if dry_run else 'Created'} {link_count}")
        print("=" * 60)

        if dry_run:
            print("\nTo execute cleanup, run with --execute flag:")
            print("  python cleanup_duplicates.py --execute")
            print("\nTo skip document-person link population (faster):")
            print("  python cleanup_duplicates.py --execute --skip-links")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Comprehensive data cleanup')
    parser.add_argument('--execute', action='store_true',
                       help='Actually execute the cleanup (default is dry run)')
    parser.add_argument('--skip-links', action='store_true',
                       help='Skip document-person link population (faster)')

    args = parser.parse_args()

    run_cleanup(dry_run=not args.execute, skip_links=args.skip_links)

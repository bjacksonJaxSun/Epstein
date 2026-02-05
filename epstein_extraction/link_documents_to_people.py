#!/usr/bin/env python3
"""
Link documents to people based on name mentions in document text.
This improves the document_people associations in the database.
"""

import sqlite3
import re
from typing import Set, Dict, List, Tuple
from collections import defaultdict

DB_PATH = "C:/Development/EpsteinDownloader/extraction_output/epstein_documents.db"

# Minimum name length to avoid false positives
MIN_NAME_LENGTH = 5

# Names to exclude (common words, partial matches)
EXCLUDED_NAMES = {
    'the', 'and', 'for', 'from', 'with', 'that', 'this', 'have', 'will',
    'would', 'could', 'should', 'about', 'their', 'there', 'which', 'other',
    'under', 'where', 'after', 'before', 'between', 'through', 'during',
    'united', 'states', 'state', 'court', 'case', 'filed', 'document',
    'plaintiff', 'defendant', 'judge', 'attorney', 'witness', 'office',
    'district', 'southern', 'northern', 'eastern', 'western', 'federal',
    'county', 'city', 'street', 'avenue', 'place', 'first', 'second',
    'third', 'fourth', 'fifth', 'number', 'page', 'exhibit', 'evidence',
    'motion', 'order', 'hearing', 'trial', 'appeal', 'request', 'response',
    # Names that are too common or ambiguous
    'john', 'jane', 'james', 'david', 'michael', 'robert', 'william',
    'richard', 'thomas', 'charles', 'mary', 'patricia', 'jennifer',
    'elizabeth', 'linda', 'barbara', 'susan', 'jessica', 'sarah', 'karen',
    'nancy', 'betty', 'helen', 'sandra', 'donna', 'carol', 'ruth', 'sharon',
    'michelle', 'laura', 'bryan', 'baker', 'brown', 'smith', 'jones',
    'johnson', 'williams', 'miller', 'davis', 'garcia', 'rodriguez',
    'wilson', 'martinez', 'anderson', 'taylor', 'thomas', 'hernandez',
    'moore', 'martin', 'jackson', 'thompson', 'white', 'lopez', 'lee',
    'gonzalez', 'harris', 'clark', 'lewis', 'robinson', 'walker', 'young',
    'allen', 'king', 'wright', 'scott', 'torres', 'nguyen', 'hill', 'adams',
}


def get_well_known_people(conn: sqlite3.Connection) -> List[Tuple[int, str]]:
    """Get people with distinctive names that are worth linking."""
    cur = conn.cursor()

    # Get people who already have relationships or documents
    cur.execute('''
        SELECT DISTINCT p.person_id, p.full_name
        FROM people p
        WHERE p.full_name IS NOT NULL
        AND LENGTH(p.full_name) >= ?
        AND (
            -- Has relationships
            EXISTS (SELECT 1 FROM relationships r WHERE r.person1_id = p.person_id OR r.person2_id = p.person_id)
            -- Or has distinctive name patterns (first + last)
            OR p.full_name LIKE '% %'
        )
        ORDER BY p.person_id
    ''', (MIN_NAME_LENGTH,))

    return cur.fetchall()


def is_valid_name(name: str) -> bool:
    """Check if a name is valid for matching."""
    if not name or len(name) < MIN_NAME_LENGTH:
        return False

    name_lower = name.lower().strip()

    # Skip if it's in excluded names
    if name_lower in EXCLUDED_NAMES:
        return False

    # Skip if it contains only common words
    words = name_lower.split()
    if all(w in EXCLUDED_NAMES for w in words):
        return False

    # Skip if it looks like a fragment (no spaces and all caps or all lower)
    if ' ' not in name and (name.isupper() or name.islower()):
        if len(name) < 8:  # Allow longer single words
            return False

    return True


def find_name_in_text(name: str, text: str) -> bool:
    """Check if a name appears in text with word boundaries."""
    if not name or not text:
        return False

    # Create a regex pattern with word boundaries
    pattern = r'\b' + re.escape(name) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def link_documents_to_people():
    """Main function to link documents to people."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("Loading documents...")
    cur.execute('''
        SELECT document_id, full_text
        FROM documents
        WHERE full_text IS NOT NULL AND LENGTH(full_text) > 100
    ''')
    documents = cur.fetchall()
    print(f"Loaded {len(documents)} documents with text")

    print("Loading people...")
    people = get_well_known_people(conn)
    print(f"Found {len(people)} people to check")

    # Filter to valid names
    valid_people = [(pid, name) for pid, name in people if is_valid_name(name)]
    print(f"After filtering: {len(valid_people)} valid names")

    # Get existing links
    cur.execute('SELECT document_id, person_id FROM document_people')
    existing_links = set(cur.fetchall())
    print(f"Existing document-person links: {len(existing_links)}")

    # Find new links
    new_links = []
    link_counts = defaultdict(int)

    print("\nSearching for name mentions...")
    for i, (doc_id, text) in enumerate(documents):
        if i % 100 == 0:
            print(f"  Processing document {i+1}/{len(documents)}...")

        text_lower = text.lower()

        for person_id, name in valid_people:
            # Skip if already linked
            if (doc_id, person_id) in existing_links:
                continue

            # Check for name mention
            if find_name_in_text(name, text):
                new_links.append((doc_id, person_id))
                link_counts[person_id] += 1

    print(f"\nFound {len(new_links)} new document-person links")

    # Show top people by new links
    if link_counts:
        print("\nTop 20 people by new document links:")
        for pid, count in sorted(link_counts.items(), key=lambda x: -x[1])[:20]:
            cur.execute('SELECT full_name FROM people WHERE person_id = ?', (pid,))
            name = cur.fetchone()[0]
            print(f"  {name}: {count} new links")

    # Insert new links
    if new_links:
        print(f"\nInserting {len(new_links)} new links...")
        cur.executemany(
            'INSERT OR IGNORE INTO document_people (document_id, person_id) VALUES (?, ?)',
            new_links
        )
        conn.commit()
        print("Done!")

    # Show final counts
    cur.execute('''
        SELECT p.full_name, COUNT(dp.document_id) as doc_count
        FROM people p
        INNER JOIN document_people dp ON p.person_id = dp.person_id
        GROUP BY p.person_id
        ORDER BY doc_count DESC
        LIMIT 25
    ''')
    print("\nTop 25 people by total document count:")
    for name, count in cur.fetchall():
        print(f"  {name}: {count} documents")

    conn.close()


if __name__ == '__main__':
    link_documents_to_people()

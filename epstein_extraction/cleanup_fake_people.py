"""
Clean up people records that are clearly not people.
"""
import sqlite3
import re

# Words that are clearly not people names
NOT_PEOPLE = {
    # Common words
    'money', 'hollywood', 'funds', 'through', 'gross', 'finra', 'gibraltar',
    'goldman', 'coleman', 'greatest', 'normal', 'cell', 'unit', 'floor',
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'have', 'been',
    'their', 'would', 'could', 'should', 'about', 'which', 'when', 'where',
    'what', 'who', 'how', 'why', 'some', 'other', 'more', 'most', 'such',
    'only', 'very', 'just', 'also', 'well', 'back', 'after', 'before',
    'between', 'under', 'over', 'into', 'upon', 'within', 'without',
    'yes', 'no', 'not', 'all', 'any', 'each', 'every', 'both', 'few',
    'many', 'much', 'none', 'nothing', 'something', 'everything', 'anything',
    'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
    'first', 'second', 'third', 'last', 'next', 'new', 'old', 'good', 'bad',
    'great', 'small', 'large', 'big', 'little', 'long', 'short', 'high', 'low',
    'right', 'left', 'early', 'late', 'real', 'true', 'false',
    'information', 'service', 'services', 'system', 'program', 'process',
    'case', 'cases', 'court', 'law', 'order', 'part', 'place', 'point',
    'state', 'states', 'time', 'times', 'way', 'ways', 'work', 'world',
    'year', 'years', 'day', 'days', 'week', 'weeks', 'month', 'months',
    'office', 'number', 'numbers', 'page', 'pages', 'date',
    'hereby', 'herein', 'thereof', 'whereof', 'pursuant', 'whereas',
    'further', 'therefore', 'however', 'moreover', 'nevertheless',
    'mr', 'mrs', 'ms', 'dr', 'jr', 'sr', 'inc', 'llc', 'ltd', 'corp',
    # Places/Organizations often misidentified as people
    'america', 'american', 'united', 'national', 'international', 'federal',
    'county', 'city', 'town', 'village', 'district', 'region', 'area',
    'north', 'south', 'east', 'west', 'central', 'eastern', 'western',
    'bank', 'trust', 'insurance', 'investment', 'securities', 'capital',
    'management', 'holdings', 'group', 'company', 'corporation', 'enterprise',
    'foundation', 'institute', 'association', 'organization', 'society',
    'department', 'agency', 'bureau', 'commission', 'committee', 'council',
    'police', 'sheriff', 'prison', 'jail', 'detention', 'correctional',
    'hospital', 'medical', 'health', 'clinic', 'center', 'facility',
    'school', 'university', 'college', 'academy', 'education',
    'church', 'temple', 'mosque', 'synagogue', 'religious',
    # Legal terms
    'plaintiff', 'defendant', 'petitioner', 'respondent', 'appellant',
    'appellee', 'claimant', 'complainant', 'prosecution', 'defense',
    'court', 'judge', 'jury', 'witness', 'attorney', 'counsel', 'lawyer',
    'evidence', 'exhibit', 'document', 'record', 'file', 'motion',
    'order', 'judgment', 'verdict', 'sentence', 'appeal', 'hearing',
    # Common OCR errors and artifacts
    'page', 'case', 'docket', 'filed', 'redacted', 'sealed', 'confidential',
}

def is_not_person(name):
    """Check if a name is clearly not a person."""
    if not name:
        return True

    name = name.strip()
    name_lower = name.lower()

    # Too short
    if len(name) <= 2:
        return True

    # Contains newlines (OCR artifact)
    if '\n' in name:
        return True

    # All numbers or starts with numbers
    if re.match(r'^[\d\s\-\.]+$', name):
        return True

    # Single word that's in our not-people list
    if name_lower in NOT_PEOPLE:
        return True

    # All caps short words (likely acronyms)
    if name.isupper() and len(name) <= 5 and ' ' not in name:
        return True

    # Contains only special characters
    if re.match(r'^[\W\d_]+$', name):
        return True

    return False


def main():
    conn = sqlite3.connect('../extraction_output/epstein_documents.db')
    cur = conn.cursor()

    # Get all people
    cur.execute('SELECT person_id, full_name FROM people')
    all_people = cur.fetchall()

    to_delete = []
    for person_id, name in all_people:
        if is_not_person(name):
            to_delete.append((person_id, name))

    print(f"Found {len(to_delete)} non-person records to delete out of {len(all_people)} total")
    print("\nSample of records to delete:")
    for pid, name in to_delete[:30]:
        print(f"  ID {pid}: \"{name}\"")

    if len(to_delete) > 30:
        print(f"  ... and {len(to_delete) - 30} more")

    # Confirm deletion
    response = input(f"\nDelete {len(to_delete)} records? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return

    # Delete related records first
    person_ids = [p[0] for p in to_delete]

    # Delete in batches to avoid SQL limits
    batch_size = 500
    for i in range(0, len(person_ids), batch_size):
        batch = person_ids[i:i+batch_size]
        placeholders = ','.join('?' * len(batch))

        cur.execute(f"DELETE FROM document_people WHERE person_id IN ({placeholders})", batch)
        cur.execute(f"DELETE FROM event_participants WHERE person_id IN ({placeholders})", batch)
        cur.execute(f"DELETE FROM media_people WHERE person_id IN ({placeholders})", batch)
        cur.execute(f"DELETE FROM relationships WHERE person1_id IN ({placeholders}) OR person2_id IN ({placeholders})", batch + batch)
        cur.execute(f"DELETE FROM financial_transactions WHERE from_person_id IN ({placeholders}) OR to_person_id IN ({placeholders})", batch + batch)
        cur.execute(f"DELETE FROM people WHERE person_id IN ({placeholders})", batch)

    conn.commit()

    # Get new count
    cur.execute('SELECT COUNT(*) FROM people')
    new_count = cur.fetchone()[0]
    print(f"\nDeleted {len(to_delete)} records. {new_count} people remaining.")

    conn.close()


if __name__ == '__main__':
    main()

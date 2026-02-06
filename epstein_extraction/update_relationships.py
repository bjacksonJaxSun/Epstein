"""
Update Epstein relationship data and merge duplicate persons.
3-point verified relationship descriptions from public sources.

Usage: python update_relationships.py
"""

import sqlite3
import time
import sys

import argparse

# Default to the working copy; pass --live to update the live database directly
_parser = argparse.ArgumentParser()
_parser.add_argument("--live", action="store_true", help="Update the live database directly")
_args, _ = _parser.parse_known_args()

DB_PATH = (
    r"C:\Development\EpsteinDownloader\extraction_output\epstein_documents.db"
    if _args.live
    else r"C:\Development\EpsteinDownloader\extraction_output\epstein_documents_update.db"
)

# ── 3-Point Verified Relationship Data ────────────────────────────────────────
# Each entry: (person_id, epstein_relationship, primary_role)
# Verified from 3+ independent sources (DOJ, major news outlets, Wikipedia, court records)

RELATIONSHIP_UPDATES = [
    # === Core conspirators ===
    (30, "Girlfriend and co-conspirator; convicted of sex trafficking conspiracy for recruiting and grooming underage girls for Epstein from 1994-2004. Sentenced to 20 years in prison.", "co-conspirator"),
    (11074, "French modeling agent and co-conspirator who procured young women and minors for Epstein through his MC2 modeling agency, funded by Epstein. Found dead in French prison in 2022 before trial.", "co-conspirator"),
    (4833, "Personal assistant and alleged co-conspirator; named as unindicted co-conspirator in 2008 non-prosecution agreement for scheduling 'massages' and managing victim recruitment logistics.", "co-conspirator"),
    (4825, "Associate since her teens; named as unindicted co-conspirator in 2008 non-prosecution agreement. Accused by victims of participating in sexual assaults. Later became pilot of Epstein's planes.", "co-conspirator"),

    # === Staff and inner circle ===
    (1740, "Chief pilot for over 25 years (1991-2019); testified at Maxwell trial about transporting high-profile passengers. Maintained flight logs documenting passengers on Epstein's private planes.", "employee"),
    (1410, "Pilot for nearly 30 years (1991-2019); authored the primary handwritten flight logs covering 1991-2003 that documented passengers on Epstein's private jets.", "employee"),
    (870, "Personal attorney since 1986 and co-executor of Epstein's estate. Listed as possible co-conspirator by federal authorities in 2019.", "attorney/estate executor"),
    (893, "Long-time accountant and co-executor of Epstein's estate alongside Darren Indyke; managed estate affairs and oversaw $170 million in victim compensation payments.", "accountant/estate executor"),

    # === Legal figures (prosecution/victims' side) ===
    (50, "Victims' attorney who represented Virginia Giuffre and other survivors; spearheaded litigation resulting in $290M JPMorgan and $75M Deutsche Bank settlements.", "victims' attorney"),
    (43, "Victims' attorney who represented 60+ Epstein victims for over 15 years; successfully challenged Epstein's 2008 plea deal as violating the Crime Victims' Rights Act.", "victims' attorney"),
    (1360, "Attorney at Boies Schiller Flexner who represented Virginia Giuffre and other victims for nearly 10 years; successfully unsealed depositions leading to criminal charges against Maxwell.", "victims' attorney"),
    (955, "Victims' rights attorney representing 27+ Epstein survivors; assisted victims in connecting with law enforcement and litigating claims.", "victims' attorney"),

    # === Legal figures (defense side) ===
    (10533, "Defense attorney who joined Epstein's legal team in 2005 and negotiated the controversial 2007 non-prosecution agreement in Florida. Also had social relationship with Epstein; accused by Virginia Giuffre of misconduct.", "defense attorney"),
    (1403, "Defense attorney for Ghislaine Maxwell.", "defense attorney"),
    (111, "Defense attorney for Ghislaine Maxwell at her federal trial.", "defense attorney"),
    (1658, "Defense attorney for Ghislaine Maxwell.", "defense attorney"),
    (112, "Defense attorney for Ghislaine Maxwell.", "defense attorney"),

    # === High-profile social associates ===
    (173, "Social acquaintance from late 1980s through early 2000s; socialized at Mar-a-Lago resort in Florida. Relationship ended around 2004.", "social acquaintance"),
    (1024, "Close social friend from late 1990s; accused by Virginia Giuffre of sexual abuse as a trafficking victim. Settled civil lawsuit in 2022 for undisclosed sum.", "social associate/accused"),
    (865, "Social and professional associate; Epstein visited White House 17+ times (1993-1995) and Clinton flew on Epstein's private plane at least 16 times (2001-2004).", "social/political associate"),
    (187, "Indirect connection through husband Bill Clinton; Epstein attended a 1993 White House donors' reception. No direct personal relationship documented.", "indirect associate"),
    (213, "Major financial client from 1996-2018; paid Epstein approximately $158-170 million for tax, estate planning, and financial advisory services.", "financial client"),
    (3201, "Hired Epstein as personal financial manager from 1987-2007; granted him power of attorney in 1991 giving Epstein control over his finances. Epstein allegedly misappropriated tens of millions.", "financial client/patron"),
    (11874, "Met with Epstein multiple times between 2011-2014 for dinner meetings discussing philanthropic opportunities and potential Gates Foundation contributors. Gates later called the meetings 'a mistake'.", "philanthropic associate"),
    (4809, "Flew on Epstein's private jet in September 2002 on a humanitarian trip to Africa with Bill Clinton and Chris Tucker. Stated he did not know Epstein at the time.", "flight log associate"),
    (4774, "Flew on Epstein's private jet in September 2002 on a humanitarian trip to Africa with Bill Clinton and Kevin Spacey for AIDS and poverty awareness.", "flight log associate"),
    (6535, "Former girlfriend of Epstein (1981-1990); remained close friends for decades after. Epstein was godfather to her three children. Testified at Maxwell trial.", "ex-girlfriend/social associate"),

    # === Journalists ===
    (66, "Miami Herald investigative journalist who re-opened the Epstein case with her November 2018 'Perversion of Justice' series, uncovering 80 victims and leading to Epstein's 2019 arrest.", "journalist/investigator"),

    # === Family members ===
    (74, "Jeffrey Epstein's younger brother; real estate developer who founded Ossa Properties. Jeffrey held a lease at Mark's building.", "brother"),
    (1039, "Ghislaine Maxwell's father; British publishing magnate who reportedly introduced Ghislaine to Epstein in the late 1980s. Died in 1991.", "Maxwell family"),
    (4526, "Ghislaine Maxwell's sister; tech industry executive who supported Ghislaine throughout her trial.", "Maxwell family"),

    # === Victims ===
    (11410, "Sex trafficking victim and survivor; recruited at age 16 by Ghislaine Maxwell. Became first accuser to publicly identify herself in 2011. Filed civil lawsuits against Epstein, Maxwell, and Prince Andrew.", "victim/plaintiff"),

    # === Financial/banking ===
    (9833, "JPMorgan banker described as Epstein's 'chief defender' at the bank; helped maintain Epstein's accounts amid internal concerns. Exchanged 1,200+ emails with Epstein. Resigned as Barclays CEO in 2021.", "banking associate"),

    # === Trump family ===
    (552, "Appeared in 1993 photograph with her father Donald Trump and Epstein. Listed in Epstein's contact information. No evidence of wrongdoing.", "contact/social acquaintance"),

    # === Court figures ===
    (34, "U.S. District Judge who presided over criminal case against Jeffrey Epstein in the Southern District of New York.", "presiding judge"),
    (953, "Former U.S. Attorney for SDNY who oversaw the federal investigation and charges against Jeffrey Epstein in 2019.", "prosecutor"),
    (876, "Acting Director of the Federal Bureau of Prisons at the time of Epstein's death in custody in August 2019.", "BOP official"),
]

# ── Duplicate Merges ──────────────────────────────────────────────────────────
# (canonical_id, [duplicate_ids_to_merge])
# The canonical ID keeps its record; duplicates get their references moved and are then deleted.

DUPLICATE_MERGES = [
    # Ghislaine Maxwell duplicates
    (30, [109, 1648, 2865, 2931, 2932, 3322, 4971, 5535, 5637, 5638, 6564, 6629, 6744, 7011, 7626, 7664, 7665, 7805, 7813, 7978, 8093, 8756, 8766, 10043, 10090, 10091, 10292, 10603, 2348]),

    # Jeffrey Epstein duplicates (OCR fragments, typos)
    (3, [22, 124, 1383, 5447, 6128, 6541, 1538, 2659, 3256, 3460, 3467, 9329, 10211, 10915, 1373, 1380, 2007]),

    # Donald Trump duplicates
    (173, [252]),

    # Prince Andrew duplicates
    (1024, [4227, 5077, 7604, 7608, 7716, 4720, 8313]),

    # Leon Black duplicates
    (213, [3806]),

    # Hillary Clinton duplicates
    (187, [2554, 9993]),

    # Bill Clinton duplicates
    (865, [868, 2514, 7725]),

    # Jean-Luc Brunel duplicates
    (11074, [3345, 4087, 7863, 8183, 9808]),

    # Virginia Giuffre duplicates
    (11410, [7059]),

    # Les Wexner duplicates
    (3201, [3203, 4817, 7203]),

    # Bill Gates duplicates
    (11874, [3119]),

    # Kevin Spacey duplicates
    (4809, [7729]),

    # Chris Tucker duplicates
    (4774, [7724]),

    # Eva Dubin duplicates
    (6535, [6536]),

    # Brad Edwards duplicates (attorney)
    (43, [54, 915, 1473, 3478, 3565, 4701, 4702, 4703, 4765, 4768, 4769, 4843, 4906, 5548, 6038, 6272, 9666]),

    # Larry Visoski duplicates (pilot)
    (1740, [2193, 4254, 4257, 4270, 5314, 5343, 6154, 7329, 7352, 7744, 8157, 8158, 8159, 8160, 10529, 10530, 10531]),

    # David Rodgers duplicates (pilot)
    (1410, [1409, 1411, 1414, 8152, 8185]),

    # Mark Epstein duplicates
    (74, [1653, 1971, 4022, 5317, 5391]),

    # David Boies duplicates
    (50, [2598, 6273]),

    # Gloria Allred duplicates
    (955, [3010, 10928, 11999]),

    # Sarah Kellen duplicates
    (4833, [4808]),

    # Nadia Marcinkova duplicates
    (4825, [4820]),

    # Jes Staley duplicates
    (9833, [9834]),

    # MAXWELL (uppercase) - already merged above
    # Sigrid McCawley - no duplicates found

    # Darren Indyke - no clear duplicates
    # Richard Kahn - no clear duplicates

    # Michael Thomas duplicates
    (4, [2028]),

    # Bobbi Sternheim duplicates
    (111, [2569]),

    # Geoffrey Berman duplicates
    (953, [1160]),

    # Chris Dilorio / Christopher J Dilorio duplicates
    (151, [155]),

    # Laura Menninger - no clear duplicates

    # Chelsea Clinton (legitimate separate person, NOT a duplicate of Hillary/Bill)
    # Ivanka Trump (legitimate separate person, NOT a duplicate of Donald)
    # Robert Maxwell, Isabel Maxwell, Kevin Maxwell, Christine Maxwell, Pandora Maxwell
    #   - all legitimate separate Maxwell family members, NOT duplicates of Ghislaine
]

# Tables that reference person_id and need updating during merges
PERSON_REFERENCE_TABLES = [
    ("document_people", "person_id"),
    ("event_participants", "person_id"),
    ("media_people", "person_id"),
    ("communication_recipients", "person_id"),
]

RELATIONSHIP_PERSON_COLUMNS = [
    ("relationships", "person1_id"),
    ("relationships", "person2_id"),
]


def connect_db():
    """Connect with WAL mode and busy timeout for concurrent access."""
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def add_epstein_relationship_column(conn):
    """Add epstein_relationship column if it doesn't exist."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(people)")
    columns = [row[1] for row in cur.fetchall()]
    if "epstein_relationship" not in columns:
        try:
            cur.execute("ALTER TABLE people ADD COLUMN epstein_relationship TEXT")
            conn.commit()
            print("[+] Added epstein_relationship column to people table")
        except sqlite3.OperationalError as e:
            print(f"[!] Could not add column (may need backend restart): {e}")
            print("    Continuing with updates to existing columns...")
    else:
        print("[=] epstein_relationship column already exists")


def update_relationships(conn):
    """Update epstein_relationship and primary_role for researched people."""
    cur = conn.cursor()

    # Check if epstein_relationship column exists
    cur.execute("PRAGMA table_info(people)")
    columns = [row[1] for row in cur.fetchall()]
    has_er_col = "epstein_relationship" in columns

    updated = 0
    for person_id, relationship, role in RELATIONSHIP_UPDATES:
        # Check person exists
        cur.execute("SELECT full_name FROM people WHERE person_id = ?", (person_id,))
        row = cur.fetchone()
        if not row:
            print(f"  [!] Person ID {person_id} not found, skipping")
            continue

        if has_er_col:
            cur.execute(
                "UPDATE people SET epstein_relationship = ?, primary_role = ? WHERE person_id = ?",
                (relationship, role, person_id),
            )
        else:
            cur.execute(
                "UPDATE people SET primary_role = ? WHERE person_id = ?",
                (role, person_id),
            )
        updated += 1
        print(f"  [+] {row[0]} (ID:{person_id}) -> {role}")

    conn.commit()
    print(f"\n[+] Updated relationships for {updated} people")


def ensure_relationship_to_epstein(conn, person_id):
    """Ensure a relationship record exists between this person and Epstein (ID=3)."""
    cur = conn.cursor()
    cur.execute(
        """SELECT relationship_id FROM relationships
           WHERE (person1_id = 3 AND person2_id = ?)
              OR (person1_id = ? AND person2_id = 3)""",
        (person_id, person_id),
    )
    if not cur.fetchone() and person_id != 3:
        cur.execute(
            """INSERT INTO relationships (person1_id, person2_id, relationship_type, confidence_level, created_at, updated_at)
               VALUES (3, ?, 'associate', 'high', datetime('now'), datetime('now'))""",
            (person_id,),
        )


def merge_duplicates(conn):
    """Merge duplicate persons into canonical records."""
    cur = conn.cursor()
    total_merged = 0
    total_deleted = 0

    for canonical_id, dup_ids in DUPLICATE_MERGES:
        # Verify canonical exists
        cur.execute("SELECT full_name FROM people WHERE person_id = ?", (canonical_id,))
        canonical = cur.fetchone()
        if not canonical:
            print(f"  [!] Canonical ID {canonical_id} not found, skipping merge group")
            continue

        for dup_id in dup_ids:
            cur.execute("SELECT full_name FROM people WHERE person_id = ?", (dup_id,))
            dup = cur.fetchone()
            if not dup:
                continue  # Already deleted or doesn't exist

            # Move references in simple person_id tables
            for table, col in PERSON_REFERENCE_TABLES:
                try:
                    # Use INSERT OR IGNORE to handle unique constraint conflicts
                    cur.execute(
                        f"UPDATE OR IGNORE {table} SET {col} = ? WHERE {col} = ?",
                        (canonical_id, dup_id),
                    )
                    # Delete any remaining rows that couldn't be moved (due to unique constraints)
                    cur.execute(f"DELETE FROM {table} WHERE {col} = ?", (dup_id,))
                except sqlite3.Error:
                    pass

            # Move relationship references
            for table, col in RELATIONSHIP_PERSON_COLUMNS:
                try:
                    cur.execute(
                        f"UPDATE OR IGNORE {table} SET {col} = ? WHERE {col} = ?",
                        (canonical_id, dup_id),
                    )
                    # Clean up any relationships that would be self-referential after merge
                    cur.execute(
                        "DELETE FROM relationships WHERE person1_id = person2_id"
                    )
                    # Delete remaining unmovable rows
                    cur.execute(
                        f"DELETE FROM {table} WHERE {col} = ?", (dup_id,)
                    )
                except sqlite3.Error:
                    pass

            # Delete the duplicate person record
            cur.execute("DELETE FROM people WHERE person_id = ?", (dup_id,))
            total_deleted += 1

        total_merged += 1
        print(f"  [+] Merged {len(dup_ids)} duplicates into '{canonical[0]}' (ID:{canonical_id})")

    conn.commit()
    print(f"\n[+] Processed {total_merged} merge groups, deleted {total_deleted} duplicate records")


def update_relationship_records(conn):
    """Update the relationships table with proper types and descriptions for Epstein connections."""
    cur = conn.cursor()
    updated = 0

    for person_id, relationship, role in RELATIONSHIP_UPDATES:
        if person_id == 3:
            continue  # Skip Epstein himself

        # Update existing relationship records with Epstein
        cur.execute(
            """UPDATE relationships
               SET relationship_type = ?,
                   relationship_description = ?,
                   confidence_level = 'high',
                   updated_at = datetime('now')
               WHERE (person1_id = 3 AND person2_id = ?)
                  OR (person1_id = ? AND person2_id = 3)""",
            (role, relationship, person_id, person_id),
        )

        if cur.rowcount == 0:
            # No existing relationship - create one
            ensure_relationship_to_epstein(conn, person_id)
            cur.execute(
                """UPDATE relationships
                   SET relationship_type = ?,
                       relationship_description = ?,
                       confidence_level = 'high',
                       updated_at = datetime('now')
                   WHERE (person1_id = 3 AND person2_id = ?)
                      OR (person1_id = ? AND person2_id = 3)""",
                (role, relationship, person_id, person_id),
            )

        updated += 1

    conn.commit()
    print(f"[+] Updated {updated} relationship records in relationships table")


def print_summary(conn):
    """Print summary of the database state after updates."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM people")
    total_people = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM people WHERE epstein_relationship IS NOT NULL")
    with_rel = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT relationship_type) FROM relationships")
    rel_types = cur.fetchone()[0]
    cur.execute("SELECT relationship_type, COUNT(*) FROM relationships GROUP BY relationship_type ORDER BY COUNT(*) DESC")
    type_counts = cur.fetchall()

    print(f"\n{'='*60}")
    print(f"DATABASE SUMMARY")
    print(f"{'='*60}")
    print(f"Total people:                 {total_people}")
    print(f"With epstein_relationship:    {with_rel}")
    print(f"Distinct relationship types:  {rel_types}")
    print(f"\nRelationship type breakdown:")
    for rtype, count in type_counts:
        print(f"  {rtype:30s} {count:>5}")


def main():
    print("=" * 60)
    print("Epstein Relationship Updater")
    print("3-point verified from DOJ, court records, and major outlets")
    print("=" * 60)

    max_retries = 10
    for attempt in range(max_retries):
        try:
            conn = connect_db()
            break
        except sqlite3.OperationalError as e:
            print(f"Attempt {attempt+1}/{max_retries}: {e}")
            time.sleep(3)
    else:
        print("ERROR: Could not connect to database after retries. Is the backend running with an exclusive lock?")
        sys.exit(1)

    try:
        print("\n[1/5] Adding epstein_relationship column...")
        add_epstein_relationship_column(conn)

        print("\n[2/5] Updating relationship descriptions...")
        update_relationships(conn)

        print("\n[3/5] Updating relationships table records...")
        update_relationship_records(conn)

        print("\n[4/5] Merging duplicate persons...")
        merge_duplicates(conn)

        print("\n[5/5] Summary...")
        print_summary(conn)

    except sqlite3.OperationalError as e:
        print(f"\nERROR: Database locked - {e}")
        print("Try stopping the backend server first, then re-run this script.")
        sys.exit(1)
    finally:
        conn.close()

    print("\nDone!")


if __name__ == "__main__":
    main()

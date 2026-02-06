"""
Enrich organization data with web search results.
Uses known organization data to populate type, headquarters, and description fields.
"""
import sqlite3

# Well-known organizations with verified details
KNOWN_ORGANIZATIONS = {
    "Federal Bureau of Prisons": {
        "type": "Government Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "A federal law enforcement agency under the U.S. Department of Justice responsible for the care, custody, and control of incarcerated individuals.",
        "website": "https://www.bop.gov"
    },
    "MCC New York": {
        "type": "Correctional Facility",
        "headquarters": "New York, NY, USA",
        "description": "Metropolitan Correctional Center, New York - a federal administrative detention facility in Manhattan that housed pre-trial and sentenced inmates. Closed in 2021.",
    },
    "U.S. Department of Justice": {
        "type": "Government Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "The federal executive department responsible for the enforcement of federal law and administration of justice in the United States.",
        "website": "https://www.justice.gov"
    },
    "Office of the Inspector General": {
        "type": "Government Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "An independent oversight office within the Department of Justice that investigates allegations of waste, fraud, and abuse.",
    },
    "U.S. District Court for the Southern District of New York": {
        "type": "Federal Court",
        "headquarters": "New York, NY, USA",
        "description": "A federal district court covering Manhattan, the Bronx, and several counties north of New York City. One of the busiest and most prominent federal courts.",
    },
    "American Correctional Association": {
        "type": "Professional Organization",
        "headquarters": "Alexandria, VA, USA",
        "description": "A professional organization for correctional workers that provides accreditation and certification programs for correctional facilities.",
        "website": "https://www.aca.org"
    },
    "FBI": {
        "type": "Law Enforcement Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "Federal Bureau of Investigation - the domestic intelligence and security service of the United States and its principal federal law enforcement agency.",
        "website": "https://www.fbi.gov"
    },
    "Federal Bureau of Investigation": {
        "type": "Law Enforcement Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "The domestic intelligence and security service of the United States and its principal federal law enforcement agency.",
        "website": "https://www.fbi.gov"
    },
    "SEC": {
        "type": "Government Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "Securities and Exchange Commission - an independent federal government agency responsible for protecting investors and maintaining fair markets.",
        "website": "https://www.sec.gov"
    },
    "Securities and Exchange Commission": {
        "type": "Government Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "An independent federal government agency responsible for protecting investors, maintaining fair markets, and facilitating capital formation.",
        "website": "https://www.sec.gov"
    },
    "JPMorgan Chase": {
        "type": "Financial Institution",
        "headquarters": "New York, NY, USA",
        "description": "A multinational investment bank and financial services holding company, one of the largest banks in the United States.",
        "website": "https://www.jpmorganchase.com"
    },
    "Deutsche Bank": {
        "type": "Financial Institution",
        "headquarters": "Frankfurt, Germany",
        "description": "A German multinational investment bank and financial services company.",
        "website": "https://www.db.com"
    },
    "Harvard University": {
        "type": "Educational Institution",
        "headquarters": "Cambridge, MA, USA",
        "description": "A private Ivy League research university, the oldest institution of higher learning in the United States.",
        "website": "https://www.harvard.edu"
    },
    "MIT": {
        "type": "Educational Institution",
        "headquarters": "Cambridge, MA, USA",
        "description": "Massachusetts Institute of Technology - a private research university known for its programs in engineering, science, and technology.",
        "website": "https://www.mit.edu"
    },
    "Massachusetts Institute of Technology": {
        "type": "Educational Institution",
        "headquarters": "Cambridge, MA, USA",
        "description": "A private research university known for its programs in engineering, science, and technology.",
        "website": "https://www.mit.edu"
    },
    "Victoria's Secret": {
        "type": "Retail Company",
        "headquarters": "Columbus, OH, USA",
        "description": "An American lingerie, clothing, and beauty retailer known for its high-visibility marketing and fashion shows.",
        "website": "https://www.victoriassecret.com"
    },
    "L Brands": {
        "type": "Retail Company",
        "headquarters": "Columbus, OH, USA",
        "description": "An American fashion retailer, formerly the parent company of Victoria's Secret and Bath & Body Works.",
    },
    "The Wexner Foundation": {
        "type": "Non-Profit Foundation",
        "headquarters": "Columbus, OH, USA",
        "description": "A private foundation focused on strengthening Jewish professional and volunteer leadership.",
    },
    "Palm Beach Police Department": {
        "type": "Law Enforcement Agency",
        "headquarters": "Palm Beach, FL, USA",
        "description": "The municipal police department serving the Town of Palm Beach, Florida.",
    },
    "New York Police Department": {
        "type": "Law Enforcement Agency",
        "headquarters": "New York, NY, USA",
        "description": "The primary law enforcement agency within New York City, the largest municipal police force in the United States.",
        "website": "https://www.nyc.gov/nypd"
    },
    "NYPD": {
        "type": "Law Enforcement Agency",
        "headquarters": "New York, NY, USA",
        "description": "New York Police Department - the primary law enforcement agency within New York City.",
        "website": "https://www.nyc.gov/nypd"
    },
    "Southern District of New York": {
        "type": "Federal Court",
        "headquarters": "New York, NY, USA",
        "description": "U.S. District Court covering Manhattan, the Bronx, and counties north of NYC. Known for high-profile cases.",
    },
    "Bureau of Prisons": {
        "type": "Government Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "Federal Bureau of Prisons - responsible for the care, custody, and control of incarcerated individuals in federal prisons.",
        "website": "https://www.bop.gov"
    },
    "Department of Justice": {
        "type": "Government Agency",
        "headquarters": "Washington, D.C., USA",
        "description": "The U.S. Department of Justice - federal executive department responsible for enforcement of federal law.",
        "website": "https://www.justice.gov"
    },
    "MC2": {
        "type": "Modeling Agency",
        "headquarters": "Miami, FL, USA",
        "description": "A modeling agency co-founded by Jean-Luc Brunel, linked to Jeffrey Epstein's trafficking network.",
    },
    "Les Wexner Foundation": {
        "type": "Non-Profit Foundation",
        "headquarters": "Columbus, OH, USA",
        "description": "A private foundation established by Leslie Wexner focused on Jewish leadership development.",
    },
}

# Patterns to match organization names (handles variations)
NAME_PATTERNS = {
    "mcc new york": "MCC New York",
    "mcc": "MCC New York",
    "metropolitan correctional center": "MCC New York",
    "federal bureau of prisons": "Federal Bureau of Prisons",
    "bop": "Federal Bureau of Prisons",
    "bureau of prisons": "Bureau of Prisons",
    "department of justice": "Department of Justice",
    "doj": "Department of Justice",
    "u.s. department of justice": "U.S. Department of Justice",
    "fbi": "FBI",
    "federal bureau of investigation": "Federal Bureau of Investigation",
    "sec": "SEC",
    "securities and exchange commission": "Securities and Exchange Commission",
    "jpmorgan": "JPMorgan Chase",
    "jp morgan": "JPMorgan Chase",
    "deutsche bank": "Deutsche Bank",
    "harvard": "Harvard University",
    "mit": "MIT",
    "massachusetts institute of technology": "Massachusetts Institute of Technology",
    "victoria's secret": "Victoria's Secret",
    "victorias secret": "Victoria's Secret",
    "l brands": "L Brands",
    "wexner foundation": "The Wexner Foundation",
    "palm beach police": "Palm Beach Police Department",
    "nypd": "NYPD",
    "new york police": "New York Police Department",
    "southern district of new york": "Southern District of New York",
    "sdny": "Southern District of New York",
    "office of the inspector general": "Office of the Inspector General",
    "oig": "Office of the Inspector General",
    "american correctional association": "American Correctional Association",
    "mc2": "MC2",
}


def normalize_name(name):
    """Normalize organization name for matching."""
    return name.lower().strip().replace('\n', ' ').replace('  ', ' ')


def find_matching_org(org_name):
    """Find matching known organization."""
    normalized = normalize_name(org_name)

    # Direct pattern match
    if normalized in NAME_PATTERNS:
        return KNOWN_ORGANIZATIONS.get(NAME_PATTERNS[normalized])

    # Partial match for longer names
    for pattern, known_name in NAME_PATTERNS.items():
        if pattern in normalized or normalized in pattern:
            return KNOWN_ORGANIZATIONS.get(known_name)

    # Direct match in known orgs
    for known_name, data in KNOWN_ORGANIZATIONS.items():
        if normalize_name(known_name) == normalized:
            return data

    return None


def main():
    conn = sqlite3.connect('../extraction_output/epstein_documents.db')
    cur = conn.cursor()

    # Get all organizations without details
    cur.execute('''
        SELECT organization_id, organization_name
        FROM organizations
        WHERE (organization_type IS NULL OR organization_type = '')
        AND LENGTH(organization_name) > 3
    ''')
    orgs = cur.fetchall()

    print(f"Checking {len(orgs)} organizations...")

    updated = 0
    for org_id, org_name in orgs:
        match = find_matching_org(org_name)
        if match:
            cur.execute('''
                UPDATE organizations
                SET organization_type = ?,
                    headquarters_location = ?,
                    description = ?,
                    website = ?
                WHERE organization_id = ?
            ''', (
                match.get('type'),
                match.get('headquarters'),
                match.get('description'),
                match.get('website'),
                org_id
            ))
            print(f"  Updated: {org_name} -> {match.get('type')}")
            updated += 1

    conn.commit()

    # Get stats
    cur.execute('SELECT COUNT(*) FROM organizations WHERE organization_type IS NOT NULL')
    with_type = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM organizations')
    total = cur.fetchone()[0]

    print(f"\nUpdated {updated} organizations")
    print(f"Organizations with type: {with_type} / {total}")

    conn.close()


if __name__ == '__main__':
    main()

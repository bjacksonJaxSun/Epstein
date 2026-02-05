"""
View extracted data from the database
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import SessionLocal
from models import Document, Person, Organization, Location, Event, Relationship

def show_statistics():
    """Show extraction statistics"""
    db = SessionLocal()

    print("=" * 70)
    print("EXTRACTION STATISTICS")
    print("=" * 70)

    doc_count = db.query(Document).count()
    people_count = db.query(Person).count()
    org_count = db.query(Organization).count()
    location_count = db.query(Location).count()
    event_count = db.query(Event).count()
    relationship_count = db.query(Relationship).count()

    print(f"Documents Processed:    {doc_count}")
    print(f"People Extracted:       {people_count}")
    print(f"Organizations Extracted: {org_count}")
    print(f"Locations Extracted:    {location_count}")
    print(f"Events Extracted:       {event_count}")
    print(f"Relationships Found:    {relationship_count}")
    print("=" * 70)
    print()

    db.close()

def show_documents():
    """Show processed documents"""
    db = SessionLocal()

    print("=" * 70)
    print("PROCESSED DOCUMENTS")
    print("=" * 70)

    documents = db.query(Document).order_by(Document.created_at).limit(20).all()

    for doc in documents:
        print(f"\n📄 {doc.efta_number}")
        print(f"   Type: {doc.document_type or 'Unknown'}")
        print(f"   Date: {doc.document_date or 'N/A'}")
        print(f"   Title: {doc.document_title[:80] if doc.document_title else 'N/A'}...")
        print(f"   Text Length: {len(doc.full_text) if doc.full_text else 0} characters")
        print(f"   Pages: {doc.page_count or 'N/A'}")

    print("\n" + "=" * 70)
    print()

    db.close()

def show_people():
    """Show extracted people"""
    db = SessionLocal()

    print("=" * 70)
    print("EXTRACTED PEOPLE")
    print("=" * 70)

    people = db.query(Person).order_by(Person.created_at).limit(30).all()

    for person in people:
        print(f"\n👤 {person.full_name}")
        if person.primary_role:
            print(f"   Role: {person.primary_role}")
        if person.email_addresses:
            print(f"   Emails: {person.email_addresses}")

        # Show which document this person was first mentioned in
        if person.first_mentioned_in_doc_id:
            doc = db.query(Document).get(person.first_mentioned_in_doc_id)
            if doc:
                print(f"   First mentioned in: {doc.efta_number}")

    print("\n" + "=" * 70)
    print()

    db.close()

def show_organizations():
    """Show extracted organizations"""
    db = SessionLocal()

    print("=" * 70)
    print("EXTRACTED ORGANIZATIONS")
    print("=" * 70)

    orgs = db.query(Organization).order_by(Organization.created_at).limit(30).all()

    for org in orgs:
        print(f"\n🏢 {org.organization_name}")
        if org.organization_type:
            print(f"   Type: {org.organization_type}")

        # Show which document this org was first mentioned in
        if org.first_mentioned_in_doc_id:
            doc = db.query(Document).get(org.first_mentioned_in_doc_id)
            if doc:
                print(f"   First mentioned in: {doc.efta_number}")

    print("\n" + "=" * 70)
    print()

    db.close()

def show_locations():
    """Show extracted locations"""
    db = SessionLocal()

    print("=" * 70)
    print("EXTRACTED LOCATIONS")
    print("=" * 70)

    locations = db.query(Location).order_by(Location.created_at).limit(20).all()

    for loc in locations:
        print(f"\n📍 {loc.location_name}")
        if loc.location_type:
            print(f"   Type: {loc.location_type}")
        if loc.city or loc.country:
            print(f"   Location: {loc.city or ''} {loc.country or ''}")

        # Show which document this location was first mentioned in
        if loc.first_mentioned_in_doc_id:
            doc = db.query(Document).get(loc.first_mentioned_in_doc_id)
            if doc:
                print(f"   First mentioned in: {doc.efta_number}")

    print("\n" + "=" * 70)
    print()

    db.close()

def show_events():
    """Show extracted events"""
    db = SessionLocal()

    print("=" * 70)
    print("EXTRACTED EVENTS")
    print("=" * 70)

    events = db.query(Event).order_by(Event.event_date).limit(20).all()

    for event in events:
        print(f"\n📅 {event.event_date or 'Unknown date'}")
        print(f"   Type: {event.event_type}")
        if event.title:
            print(f"   Title: {event.title}")
        if event.description:
            desc = event.description[:100]
            print(f"   Description: {desc}...")

        # Show source document
        if event.source_document_id:
            doc = db.query(Document).get(event.source_document_id)
            if doc:
                print(f"   Source: {doc.efta_number}")

    print("\n" + "=" * 70)
    print()

    db.close()

def show_sample_document_content():
    """Show full content from one document"""
    db = SessionLocal()

    print("=" * 70)
    print("SAMPLE DOCUMENT CONTENT")
    print("=" * 70)

    # Get first processed document
    doc = db.query(Document).order_by(Document.created_at).first()

    if doc:
        print(f"\n📄 Document: {doc.efta_number}")
        print(f"   File: {doc.file_path}")
        print(f"   Type: {doc.document_type}")
        print(f"   Date: {doc.document_date}")
        print(f"   Title: {doc.document_title}")
        print(f"   Pages: {doc.page_count}")
        print(f"\n--- TEXT CONTENT (first 1000 characters) ---")
        if doc.full_text:
            print(doc.full_text[:1000])
            print("\n[... truncated ...]")
        else:
            print("(No text extracted)")
        print("\n" + "=" * 70)

    db.close()

if __name__ == "__main__":
    show_statistics()
    show_documents()
    show_people()
    show_organizations()
    show_locations()
    show_events()
    show_sample_document_content()

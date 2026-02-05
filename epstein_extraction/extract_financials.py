"""
Financial Transaction Extraction Script

Processes existing documents in the database to extract financial transactions.
"""
import sys
from datetime import datetime, date
from loguru import logger
from sqlalchemy import text
from config import SessionLocal
from models import Document, Person, Organization
from services.database_service import DatabaseService
from extractors.financial_extractor import FinancialExtractor


def get_documents_with_financial_content(session, limit: int = None):
    """Get documents that likely contain financial information"""
    query = session.query(Document).filter(
        Document.full_text.isnot(None),
        Document.full_text != ''
    ).filter(
        # Look for documents containing dollar signs or financial keywords
        (Document.full_text.like('%$%')) |
        (Document.full_text.ilike('%payment%')) |
        (Document.full_text.ilike('%transfer%')) |
        (Document.full_text.ilike('%million%')) |
        (Document.full_text.ilike('%wire%')) |
        (Document.full_text.ilike('%donation%'))
    )

    if limit:
        query = query.limit(limit)

    return query.all()


def get_all_people(session):
    """Get list of all known people names"""
    people = session.query(Person).all()
    return {p.full_name: p for p in people}


def get_all_organizations(session):
    """Get list of all known organization names"""
    orgs = session.query(Organization).all()
    return {o.organization_name: o for o in orgs}


def extract_financials_from_documents(limit: int = None):
    """Main extraction function"""
    session = SessionLocal()
    db_service = DatabaseService(session)
    extractor = FinancialExtractor()

    logger.info("Loading known entities...")
    people_map = get_all_people(session)
    org_map = get_all_organizations(session)

    known_people = list(people_map.keys())
    known_orgs = list(org_map.keys())

    logger.info(f"Loaded {len(known_people)} people and {len(known_orgs)} organizations")

    logger.info("Finding documents with financial content...")
    documents = get_documents_with_financial_content(session, limit)
    logger.info(f"Found {len(documents)} documents to process")

    total_transactions = 0
    processed_docs = 0

    for doc in documents:
        if not doc.full_text:
            continue

        processed_docs += 1
        if processed_docs % 50 == 0:
            logger.info(f"Processed {processed_docs}/{len(documents)} documents...")

        try:
            # Extract transactions from document text
            transactions = extractor.extract(
                doc.full_text,
                known_people=known_people,
                known_orgs=known_orgs
            )

            for tx in transactions:
                # Resolve entity IDs
                from_person_id = None
                from_org_id = None
                to_person_id = None
                to_org_id = None

                if tx.from_entity:
                    if tx.from_entity_type == 'person' and tx.from_entity in people_map:
                        from_person_id = people_map[tx.from_entity].person_id
                    elif tx.from_entity_type == 'organization' and tx.from_entity in org_map:
                        from_org_id = org_map[tx.from_entity].organization_id
                    elif tx.from_entity_type == 'organization':
                        # Create new organization if not exists
                        org = db_service.get_or_create_organization(
                            tx.from_entity,
                            first_mentioned_in_doc_id=doc.document_id
                        )
                        if org:
                            from_org_id = org.organization_id
                            org_map[tx.from_entity] = org

                if tx.to_entity:
                    if tx.to_entity_type == 'person' and tx.to_entity in people_map:
                        to_person_id = people_map[tx.to_entity].person_id
                    elif tx.to_entity_type == 'organization' and tx.to_entity in org_map:
                        to_org_id = org_map[tx.to_entity].organization_id
                    elif tx.to_entity_type == 'organization':
                        # Create new organization if not exists
                        org = db_service.get_or_create_organization(
                            tx.to_entity,
                            first_mentioned_in_doc_id=doc.document_id
                        )
                        if org:
                            to_org_id = org.organization_id
                            org_map[tx.to_entity] = org

                # Parse transaction date or use document date
                tx_date = None
                if tx.transaction_date:
                    try:
                        tx_date = datetime.strptime(tx.transaction_date, '%Y-%m-%d').date()
                    except ValueError:
                        tx_date = doc.document_date
                else:
                    tx_date = doc.document_date

                # Default to a reasonable date if none found
                if not tx_date:
                    tx_date = date(2000, 1, 1)  # Placeholder for unknown dates

                # Skip if we have no entity links at all
                if not (from_person_id or from_org_id or to_person_id or to_org_id):
                    continue

                tx_data = {
                    'amount': tx.amount,
                    'currency': tx.currency,
                    'transaction_date': tx_date,
                    'transaction_type': tx.transaction_type,
                    'from_person_id': from_person_id,
                    'from_organization_id': from_org_id,
                    'to_person_id': to_person_id,
                    'to_organization_id': to_org_id,
                    'purpose': tx.purpose,
                    'source_document_id': doc.document_id
                }

                result = db_service.insert_financial_transaction(tx_data)
                if result:
                    total_transactions += 1

        except Exception as e:
            logger.error(f"Error processing document {doc.efta_number}: {e}")
            continue

    logger.info(f"Extraction complete!")
    logger.info(f"Processed {processed_docs} documents")
    logger.info(f"Extracted {total_transactions} financial transactions")

    # Print summary stats
    tx_count = session.execute(text("SELECT COUNT(*) FROM financial_transactions")).scalar()
    logger.info(f"Total transactions in database: {tx_count}")

    session.close()
    return total_transactions


if __name__ == "__main__":
    # Optional limit from command line
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    logger.info("Starting financial transaction extraction...")
    if limit:
        logger.info(f"Processing up to {limit} documents")

    count = extract_financials_from_documents(limit)
    print(f"\nExtracted {count} financial transactions")

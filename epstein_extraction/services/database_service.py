"""
Database service for inserting and querying extracted data
"""
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import (
    Document, Person, Organization, Location, Event,
    Relationship, EventParticipant, Communication,
    FinancialTransaction, MediaFile, ImageAnalysis,
    VisualEntity, MediaPerson, MediaEvent, ExtractionLog
)

class DatabaseService:
    """Service for database operations"""

    def __init__(self, db_session: Session):
        self.db = db_session

    # ============================================
    # DOCUMENT OPERATIONS
    # ============================================

    def insert_document(self, doc_data: Dict) -> Optional[Document]:
        """
        Insert or update a document

        Args:
            doc_data: Dictionary with document data

        Returns:
            Document object or None
        """
        try:
            # Check if document already exists
            existing = self.db.query(Document).filter_by(
                efta_number=doc_data['efta_number']
            ).first()

            if existing:
                logger.info(f"Document {doc_data['efta_number']} already exists, updating...")
                for key, value in doc_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
                self.db.commit()
                return existing

            # Create new document
            document = Document(
                efta_number=doc_data['efta_number'],
                file_path=doc_data['file_path'],
                document_type=doc_data.get('document_type'),
                document_date=doc_data.get('document_date'),
                document_title=doc_data.get('document_title'),
                author=doc_data.get('author'),
                recipient=doc_data.get('recipient'),
                subject=doc_data.get('subject'),
                full_text=doc_data.get('full_text'),
                page_count=doc_data.get('page_count'),
                file_size_bytes=doc_data.get('file_size_bytes'),
                is_redacted=doc_data.get('is_redacted', False),
                redaction_level=doc_data.get('redaction_level'),
                extraction_status='extracted',
                extraction_confidence=doc_data.get('extraction_confidence', 0.8)
            )

            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)

            logger.info(f"Inserted document: {document.efta_number}")
            return document

        except IntegrityError as e:
            logger.error(f"Database integrity error inserting document: {e}")
            self.db.rollback()
            return None
        except Exception as e:
            logger.error(f"Error inserting document: {e}")
            self.db.rollback()
            return None

    # ============================================
    # PERSON OPERATIONS
    # ============================================

    def insert_person(self, person_data: Dict) -> Optional[Person]:
        """
        Insert or get existing person

        Args:
            person_data: Dictionary with person data

        Returns:
            Person object or None
        """
        try:
            full_name = person_data['full_name']

            # Check if person already exists (fuzzy matching in production)
            existing = self.db.query(Person).filter_by(full_name=full_name).first()

            if existing:
                logger.debug(f"Person '{full_name}' already exists")
                return existing

            # Create new person
            person = Person(
                full_name=full_name,
                primary_role=person_data.get('primary_role'),
                roles=person_data.get('roles', []),
                email_addresses=person_data.get('email_addresses', []),
                phone_numbers=person_data.get('phone_numbers', []),
                is_redacted=person_data.get('is_redacted', False),
                victim_identifier=person_data.get('victim_identifier'),
                confidence_level=person_data.get('confidence_level', 'medium'),
                first_mentioned_in_doc_id=person_data.get('first_mentioned_in_doc_id')
            )

            self.db.add(person)
            self.db.commit()
            self.db.refresh(person)

            logger.info(f"Inserted person: {full_name}")
            return person

        except Exception as e:
            logger.error(f"Error inserting person: {e}")
            self.db.rollback()
            return None

    def get_or_create_person(self, full_name: str, **kwargs) -> Optional[Person]:
        """Get existing person or create new one"""
        existing = self.db.query(Person).filter_by(full_name=full_name).first()
        if existing:
            return existing

        person_data = {'full_name': full_name, **kwargs}
        return self.insert_person(person_data)

    # ============================================
    # ORGANIZATION OPERATIONS
    # ============================================

    def insert_organization(self, org_data: Dict) -> Optional[Organization]:
        """Insert or get existing organization"""
        try:
            org_name = org_data['organization_name']

            existing = self.db.query(Organization).filter_by(
                organization_name=org_name
            ).first()

            if existing:
                return existing

            organization = Organization(
                organization_name=org_name,
                organization_type=org_data.get('organization_type'),
                description=org_data.get('description'),
                first_mentioned_in_doc_id=org_data.get('first_mentioned_in_doc_id')
            )

            self.db.add(organization)
            self.db.commit()
            self.db.refresh(organization)

            logger.info(f"Inserted organization: {org_name}")
            return organization

        except Exception as e:
            logger.error(f"Error inserting organization: {e}")
            self.db.rollback()
            return None

    # ============================================
    # LOCATION OPERATIONS
    # ============================================

    def insert_location(self, loc_data: Dict) -> Optional[Location]:
        """Insert or get existing location"""
        try:
            location = Location(
                location_name=loc_data.get('location_name'),
                location_type=loc_data.get('location_type'),
                street_address=loc_data.get('street_address'),
                city=loc_data.get('city'),
                state_province=loc_data.get('state_province'),
                country=loc_data.get('country'),
                latitude=loc_data.get('latitude'),
                longitude=loc_data.get('longitude'),
                first_mentioned_in_doc_id=loc_data.get('first_mentioned_in_doc_id')
            )

            self.db.add(location)
            self.db.commit()
            self.db.refresh(location)

            logger.info(f"Inserted location: {loc_data.get('location_name')}")
            return location

        except Exception as e:
            logger.error(f"Error inserting location: {e}")
            self.db.rollback()
            return None

    # ============================================
    # EVENT OPERATIONS
    # ============================================

    def insert_event(self, event_data: Dict) -> Optional[Event]:
        """Insert event"""
        try:
            event = Event(
                event_type=event_data['event_type'],
                title=event_data.get('title'),
                description=event_data.get('description'),
                event_date=event_data['event_date'],
                event_time=event_data.get('event_time'),
                location_id=event_data.get('location_id'),
                source_document_id=event_data.get('source_document_id'),
                confidence_level=event_data.get('confidence_level', 'medium')
            )

            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)

            logger.info(f"Inserted event: {event.title or event.event_type}")
            return event

        except Exception as e:
            logger.error(f"Error inserting event: {e}")
            self.db.rollback()
            return None

    def link_event_participant(self, event_id: int, person_id: int, role: str = None):
        """Link a person to an event"""
        try:
            participant = EventParticipant(
                event_id=event_id,
                person_id=person_id,
                participation_role=role
            )
            self.db.add(participant)
            self.db.commit()
            logger.debug(f"Linked person {person_id} to event {event_id}")
        except Exception as e:
            logger.error(f"Error linking event participant: {e}")
            self.db.rollback()

    # ============================================
    # RELATIONSHIP OPERATIONS
    # ============================================

    def insert_relationship(self, rel_data: Dict) -> Optional[Relationship]:
        """Insert relationship between two people"""
        try:
            # Check if relationship already exists
            existing = self.db.query(Relationship).filter_by(
                person1_id=rel_data['person1_id'],
                person2_id=rel_data['person2_id'],
                relationship_type=rel_data['relationship_type']
            ).first()

            if existing:
                return existing

            relationship = Relationship(
                person1_id=rel_data['person1_id'],
                person2_id=rel_data['person2_id'],
                relationship_type=rel_data['relationship_type'],
                relationship_description=rel_data.get('relationship_description'),
                source_document_id=rel_data.get('source_document_id'),
                confidence_level=rel_data.get('confidence_level', 'medium')
            )

            self.db.add(relationship)
            self.db.commit()
            self.db.refresh(relationship)

            logger.info(f"Inserted relationship: {rel_data['relationship_type']}")
            return relationship

        except Exception as e:
            logger.error(f"Error inserting relationship: {e}")
            self.db.rollback()
            return None

    # ============================================
    # MEDIA FILE OPERATIONS
    # ============================================

    def insert_media_file(self, media_data: Dict) -> Optional[MediaFile]:
        """Insert media file"""
        try:
            # Check if file already exists (by checksum)
            if media_data.get('checksum'):
                existing = self.db.query(MediaFile).filter_by(
                    checksum=media_data['checksum']
                ).first()
                if existing:
                    logger.info(f"Media file with checksum {media_data['checksum'][:8]}... already exists")
                    return existing

            media_file = MediaFile(
                file_path=media_data['file_path'],
                file_name=media_data['file_name'],
                media_type=media_data['media_type'],
                file_format=media_data.get('file_format'),
                file_size_bytes=media_data.get('file_size_bytes'),
                checksum=media_data.get('checksum'),
                date_taken=media_data.get('date_taken'),
                camera_make=media_data.get('camera_make'),
                camera_model=media_data.get('camera_model'),
                gps_latitude=media_data.get('gps_latitude'),
                gps_longitude=media_data.get('gps_longitude'),
                gps_altitude=media_data.get('gps_altitude'),
                width_pixels=media_data.get('width_pixels'),
                height_pixels=media_data.get('height_pixels'),
                orientation=media_data.get('orientation'),
                source_document_id=media_data.get('source_document_id'),
                location_id=media_data.get('location_id')
            )

            self.db.add(media_file)
            self.db.commit()
            self.db.refresh(media_file)

            logger.info(f"Inserted media file: {media_file.file_name}")
            return media_file

        except Exception as e:
            logger.error(f"Error inserting media file: {e}")
            self.db.rollback()
            return None

    # ============================================
    # IMAGE ANALYSIS OPERATIONS
    # ============================================

    def insert_image_analysis(self, analysis_data: Dict) -> Optional[ImageAnalysis]:
        """Insert image analysis results"""
        try:
            analysis = ImageAnalysis(
                media_file_id=analysis_data['media_file_id'],
                description=analysis_data.get('description'),
                generated_caption=analysis_data.get('generated_caption'),
                tags=analysis_data.get('tags', []),
                categories=analysis_data.get('categories', []),
                analysis_provider=analysis_data.get('analysis_provider', 'local'),
                confidence_score=analysis_data.get('confidence_score'),
                contains_text=analysis_data.get('contains_text', False),
                extracted_text=analysis_data.get('extracted_text'),
                contains_faces=analysis_data.get('contains_faces', False),
                face_count=analysis_data.get('face_count', 0),
                scene_type=analysis_data.get('scene_type')
            )

            self.db.add(analysis)
            self.db.commit()
            self.db.refresh(analysis)

            logger.info(f"Inserted image analysis for media file {analysis_data['media_file_id']}")
            return analysis

        except Exception as e:
            logger.error(f"Error inserting image analysis: {e}")
            self.db.rollback()
            return None

    # ============================================
    # EXTRACTION LOG
    # ============================================

    def log_extraction(self, log_data: Dict):
        """Log extraction results"""
        try:
            log = ExtractionLog(
                document_id=log_data.get('document_id'),
                media_file_id=log_data.get('media_file_id'),
                extraction_type=log_data['extraction_type'],
                status=log_data['status'],
                entities_extracted=log_data.get('entities_extracted', 0),
                relationships_extracted=log_data.get('relationships_extracted', 0),
                events_extracted=log_data.get('events_extracted', 0),
                error_message=log_data.get('error_message'),
                processing_time_ms=log_data.get('processing_time_ms')
            )

            self.db.add(log)
            self.db.commit()

        except Exception as e:
            logger.error(f"Error logging extraction: {e}")
            self.db.rollback()

    # ============================================
    # QUERY OPERATIONS
    # ============================================

    def get_document_by_efta(self, efta_number: str) -> Optional[Document]:
        """Get document by EFTA number"""
        return self.db.query(Document).filter_by(efta_number=efta_number).first()

    def get_person_by_name(self, full_name: str) -> Optional[Person]:
        """Get person by full name"""
        return self.db.query(Person).filter_by(full_name=full_name).first()

    def get_all_people(self) -> List[Person]:
        """Get all people"""
        return self.db.query(Person).all()

    def get_pending_documents(self, limit: int = 100) -> List[Document]:
        """Get documents pending extraction"""
        return self.db.query(Document).filter_by(
            extraction_status='pending'
        ).limit(limit).all()

    def get_extraction_stats(self) -> Dict:
        """Get extraction statistics"""
        return {
            'total_documents': self.db.query(Document).count(),
            'total_people': self.db.query(Person).count(),
            'total_organizations': self.db.query(Organization).count(),
            'total_locations': self.db.query(Location).count(),
            'total_events': self.db.query(Event).count(),
            'total_relationships': self.db.query(Relationship).count(),
            'total_media_files': self.db.query(MediaFile).count(),
            'pending_documents': self.db.query(Document).filter_by(extraction_status='pending').count(),
            'extracted_documents': self.db.query(Document).filter_by(extraction_status='extracted').count(),
        }

"""
SQLAlchemy ORM models mapping to PostgreSQL schema
"""
import os
from sqlalchemy import (
    Column, Integer, String, Text, Date, Time, DateTime, Boolean,
    Numeric, ARRAY, ForeignKey, CheckConstraint, UniqueConstraint, BigInteger, JSON
)
from sqlalchemy.dialects.postgresql import TSVECTOR, JSONB, BYTEA
from sqlalchemy.orm import relationship
from datetime import datetime
from config import Base

# Use Text/JSON for SQLite compatibility, TSVECTOR/ARRAY for PostgreSQL
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
FullTextSearchType = Text if DB_TYPE == "sqlite" else TSVECTOR
ArrayType = lambda: JSON if DB_TYPE == "sqlite" else ARRAY(Text)

# ============================================
# CORE TABLES
# ============================================

class Document(Base):
    __tablename__ = 'documents'

    document_id = Column(Integer, primary_key=True)
    efta_number = Column(String(50), unique=True, nullable=False)
    file_path = Column(String(500), nullable=False)
    document_type = Column(String(100))
    document_date = Column(Date)
    document_title = Column(String(500))
    author = Column(String(255))
    recipient = Column(String(255))
    subject = Column(String(500))

    full_text = Column(Text)
    full_text_searchable = Column(FullTextSearchType)  # TSVECTOR for PostgreSQL, Text for SQLite
    page_count = Column(Integer)
    file_size_bytes = Column(BigInteger)

    classification_level = Column(String(50))
    is_redacted = Column(Boolean, default=False)
    redaction_level = Column(String(50))

    source_agency = Column(String(100))
    extraction_status = Column(String(50), default='pending')
    extraction_confidence = Column(Numeric(5, 4))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    events = relationship("Event", back_populates="source_document")
    media_files = relationship("MediaFile", back_populates="source_document")
    communications = relationship("Communication", back_populates="source_document")
    people_mentioned = relationship("DocumentPerson", back_populates="document")

    # PostgreSQL-specific constraints removed for SQLite compatibility
    # __table_args__ = (
    #     CheckConstraint("efta_number ~ '^EFTA\\d{8}$'", name='chk_efta_format'),
    # )

class Person(Base):
    __tablename__ = 'people'

    person_id = Column(Integer, primary_key=True)
    full_name = Column(String(255), nullable=False)
    name_variations = Column(ArrayType())

    primary_role = Column(String(100))
    roles = Column(ArrayType())

    email_addresses = Column(ArrayType())
    phone_numbers = Column(ArrayType())
    addresses = Column(ArrayType())

    is_redacted = Column(Boolean, default=False)
    victim_identifier = Column(String(50))

    date_of_birth = Column(Date)
    nationality = Column(String(100))
    occupation = Column(String(255))

    first_mentioned_in_doc_id = Column(Integer, ForeignKey('documents.document_id'))
    confidence_level = Column(String(50), default='medium')
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    relationships_from = relationship("Relationship", foreign_keys="Relationship.person1_id", back_populates="person1")
    relationships_to = relationship("Relationship", foreign_keys="Relationship.person2_id", back_populates="person2")
    event_participations = relationship("EventParticipant", back_populates="person")
    media_appearances = relationship("MediaPerson", back_populates="person")
    document_mentions = relationship("DocumentPerson", back_populates="person")


class DocumentPerson(Base):
    """Junction table linking documents to people mentioned in them"""
    __tablename__ = 'document_people'

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False)
    person_id = Column(Integer, ForeignKey('people.person_id', ondelete='CASCADE'), nullable=False)

    mention_count = Column(Integer, default=1)  # How many times person is mentioned in doc
    mention_context = Column(Text)  # Sample context where person is mentioned
    role_in_document = Column(String(100))  # Role of person in this specific document
    confidence = Column(Numeric(5, 4), default=0.8)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="people_mentioned")
    person = relationship("Person", back_populates="document_mentions")

    __table_args__ = (
        UniqueConstraint('document_id', 'person_id', name='uq_document_person'),
    )


class Organization(Base):
    __tablename__ = 'organizations'

    organization_id = Column(Integer, primary_key=True)
    organization_name = Column(String(255), nullable=False)
    organization_type = Column(String(100))

    parent_organization_id = Column(Integer, ForeignKey('organizations.organization_id'))
    headquarters_location = Column(String(255))
    website = Column(String(255))

    description = Column(Text)
    first_mentioned_in_doc_id = Column(Integer, ForeignKey('documents.document_id'))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Location(Base):
    __tablename__ = 'locations'

    location_id = Column(Integer, primary_key=True)
    location_name = Column(String(255))
    location_type = Column(String(100))

    street_address = Column(String(500))
    city = Column(String(100))
    state_province = Column(String(100))
    country = Column(String(100))
    postal_code = Column(String(20))

    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))

    owner_person_id = Column(Integer, ForeignKey('people.person_id'))
    owner_organization_id = Column(Integer, ForeignKey('organizations.organization_id'))

    description = Column(Text)
    first_mentioned_in_doc_id = Column(Integer, ForeignKey('documents.document_id'))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    events = relationship("Event", back_populates="location")
    media_files = relationship("MediaFile", back_populates="location")

class Event(Base):
    __tablename__ = 'events'

    event_id = Column(Integer, primary_key=True)
    event_type = Column(String(100), nullable=False)
    title = Column(String(500))
    description = Column(Text)

    event_date = Column(Date, nullable=False)
    event_time = Column(Time)
    end_date = Column(Date)
    end_time = Column(Time)
    duration_minutes = Column(Integer)

    location_id = Column(Integer, ForeignKey('locations.location_id'))
    source_document_id = Column(Integer, ForeignKey('documents.document_id'))
    additional_source_docs = Column(ArrayType())

    confidence_level = Column(String(50), default='medium')
    verification_status = Column(String(50), default='unverified')

    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    location = relationship("Location", back_populates="events")
    source_document = relationship("Document", back_populates="events")
    participants = relationship("EventParticipant", back_populates="event")
    media_events = relationship("MediaEvent", back_populates="event")

# ============================================
# RELATIONSHIP TABLES
# ============================================

class Relationship(Base):
    __tablename__ = 'relationships'

    relationship_id = Column(Integer, primary_key=True)
    person1_id = Column(Integer, ForeignKey('people.person_id', ondelete='CASCADE'), nullable=False)
    person2_id = Column(Integer, ForeignKey('people.person_id', ondelete='CASCADE'), nullable=False)

    relationship_type = Column(String(100), nullable=False)
    relationship_description = Column(Text)

    start_date = Column(Date)
    end_date = Column(Date)
    is_current = Column(Boolean, default=True)

    source_document_id = Column(Integer, ForeignKey('documents.document_id'))
    confidence_level = Column(String(50), default='medium')

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    person1 = relationship("Person", foreign_keys=[person1_id], back_populates="relationships_from")
    person2 = relationship("Person", foreign_keys=[person2_id], back_populates="relationships_to")

    __table_args__ = (
        CheckConstraint('person1_id != person2_id', name='chk_different_people'),
    )

class EventParticipant(Base):
    __tablename__ = 'event_participants'

    participant_id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey('events.event_id', ondelete='CASCADE'), nullable=False)
    person_id = Column(Integer, ForeignKey('people.person_id', ondelete='CASCADE'))
    organization_id = Column(Integer, ForeignKey('organizations.organization_id', ondelete='CASCADE'))

    participation_role = Column(String(100))
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    event = relationship("Event", back_populates="participants")
    person = relationship("Person", back_populates="event_participations")

# ============================================
# COMMUNICATIONS
# ============================================

class Communication(Base):
    __tablename__ = 'communications'

    communication_id = Column(Integer, primary_key=True)
    communication_type = Column(String(50), nullable=False)

    sender_person_id = Column(Integer, ForeignKey('people.person_id'))
    sender_organization_id = Column(Integer, ForeignKey('organizations.organization_id'))

    subject = Column(String(500))
    body_text = Column(Text)

    communication_date = Column(Date)
    communication_time = Column(Time)

    source_document_id = Column(Integer, ForeignKey('documents.document_id'))

    has_attachments = Column(Boolean, default=False)
    attachment_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source_document = relationship("Document", back_populates="communications")
    recipients = relationship("CommunicationRecipient", back_populates="communication")

class CommunicationRecipient(Base):
    __tablename__ = 'communication_recipients'

    recipient_id = Column(Integer, primary_key=True)
    communication_id = Column(Integer, ForeignKey('communications.communication_id', ondelete='CASCADE'), nullable=False)
    person_id = Column(Integer, ForeignKey('people.person_id', ondelete='CASCADE'))
    organization_id = Column(Integer, ForeignKey('organizations.organization_id', ondelete='CASCADE'))

    recipient_type = Column(String(20), nullable=False)  # 'to', 'cc', 'bcc'

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    communication = relationship("Communication", back_populates="recipients")

# ============================================
# FINANCIAL TRANSACTIONS
# ============================================

class FinancialTransaction(Base):
    __tablename__ = 'financial_transactions'

    transaction_id = Column(Integer, primary_key=True)
    transaction_type = Column(String(100))

    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), default='USD')

    from_person_id = Column(Integer, ForeignKey('people.person_id'))
    from_organization_id = Column(Integer, ForeignKey('organizations.organization_id'))
    to_person_id = Column(Integer, ForeignKey('people.person_id'))
    to_organization_id = Column(Integer, ForeignKey('organizations.organization_id'))

    transaction_date = Column(Date, nullable=False)
    purpose = Column(Text)
    reference_number = Column(String(100))

    from_account = Column(String(100))
    to_account = Column(String(100))
    bank_name = Column(String(255))

    source_document_id = Column(Integer, ForeignKey('documents.document_id'))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ============================================
# MEDIA FILES & IMAGE METADATA
# ============================================

class MediaFile(Base):
    __tablename__ = 'media_files'

    media_file_id = Column(Integer, primary_key=True)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    media_type = Column(String(50), nullable=False)
    file_format = Column(String(20))
    file_size_bytes = Column(BigInteger)
    checksum = Column(String(64))

    date_taken = Column(DateTime)
    camera_make = Column(String(100))
    camera_model = Column(String(100))
    gps_latitude = Column(Numeric(10, 8))
    gps_longitude = Column(Numeric(11, 8))
    gps_altitude = Column(Numeric(10, 2))

    width_pixels = Column(Integer)
    height_pixels = Column(Integer)
    duration_seconds = Column(Integer)
    orientation = Column(String(20))

    original_filename = Column(String(255))
    caption = Column(Text)

    source_document_id = Column(Integer, ForeignKey('documents.document_id'))
    evidence_item_id = Column(Integer, ForeignKey('evidence_items.evidence_id'))
    location_id = Column(Integer, ForeignKey('locations.location_id'))

    is_explicit = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    classification_level = Column(String(50))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source_document = relationship("Document", back_populates="media_files")
    location = relationship("Location", back_populates="media_files")
    image_analysis = relationship("ImageAnalysis", back_populates="media_file", uselist=False)
    visual_entities = relationship("VisualEntity", back_populates="media_file")
    media_people = relationship("MediaPerson", back_populates="media_file")
    media_events = relationship("MediaEvent", back_populates="media_file")

    __table_args__ = (
        CheckConstraint("media_type IN ('image', 'video', 'audio', 'document')", name='chk_media_type'),
        CheckConstraint("LENGTH(checksum) = 64 OR checksum IS NULL", name='chk_checksum_length'),
    )

class ImageAnalysis(Base):
    __tablename__ = 'image_analysis'

    analysis_id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.media_file_id', ondelete='CASCADE'), nullable=False)

    description = Column(Text)
    generated_caption = Column(Text)
    tags = Column(ArrayType())
    categories = Column(ArrayType())

    analysis_provider = Column(String(50))
    analysis_model_version = Column(String(50))
    analysis_date = Column(DateTime, default=datetime.utcnow)
    confidence_score = Column(Numeric(5, 4))

    contains_text = Column(Boolean, default=False)
    extracted_text = Column(Text)
    text_language = Column(String(20))

    contains_faces = Column(Boolean, default=False)
    face_count = Column(Integer, default=0)

    scene_type = Column(String(100))
    is_explicit = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    moderation_labels = Column(ArrayType())

    dominant_colors = Column(ArrayType())

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    media_file = relationship("MediaFile", back_populates="image_analysis")

class VisualEntity(Base):
    __tablename__ = 'visual_entities'

    entity_id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.media_file_id', ondelete='CASCADE'), nullable=False)

    entity_type = Column(String(50), nullable=False)
    entity_label = Column(String(255))
    entity_description = Column(Text)

    bbox_x = Column(Numeric(5, 4))
    bbox_y = Column(Numeric(5, 4))
    bbox_width = Column(Numeric(5, 4))
    bbox_height = Column(Numeric(5, 4))

    confidence = Column(Numeric(5, 4))
    person_id = Column(Integer, ForeignKey('people.person_id'))

    estimated_age_range = Column(String(20))
    gender = Column(String(20))
    facial_expression = Column(String(50))
    face_encoding = Column(Text)  # Use Text for SQLite, BYTEA for PostgreSQL

    attributes = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    media_file = relationship("MediaFile", back_populates="visual_entities")

class MediaPerson(Base):
    __tablename__ = 'media_people'

    media_person_id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.media_file_id', ondelete='CASCADE'), nullable=False)
    person_id = Column(Integer, ForeignKey('people.person_id', ondelete='CASCADE'), nullable=False)
    visual_entity_id = Column(Integer, ForeignKey('visual_entities.entity_id', ondelete='SET NULL'))

    identification_method = Column(String(50))
    confidence = Column(Numeric(5, 4))

    position_description = Column(String(255))
    notes = Column(Text)

    tagged_by = Column(String(100))
    verified = Column(Boolean, default=False)
    verified_by = Column(String(100))
    verified_date = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    media_file = relationship("MediaFile", back_populates="media_people")
    person = relationship("Person", back_populates="media_appearances")

    __table_args__ = (
        UniqueConstraint('media_file_id', 'person_id', name='uq_media_person'),
    )

class MediaEvent(Base):
    __tablename__ = 'media_events'

    media_event_id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.media_file_id', ondelete='CASCADE'), nullable=False)
    event_id = Column(Integer, ForeignKey('events.event_id', ondelete='CASCADE'), nullable=False)

    is_primary_evidence = Column(Boolean, default=False)
    sequence_number = Column(Integer)
    relationship_description = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    media_file = relationship("MediaFile", back_populates="media_events")
    event = relationship("Event", back_populates="media_events")

    __table_args__ = (
        UniqueConstraint('media_file_id', 'event_id', name='uq_media_event'),
    )

# ============================================
# EVIDENCE & LEGAL TRACKING
# ============================================

class EvidenceItem(Base):
    __tablename__ = 'evidence_items'

    evidence_id = Column(Integer, primary_key=True)
    evidence_type = Column(String(100))
    description = Column(Text, nullable=False)

    evidence_number = Column(String(100))
    chain_of_custody = Column(Text)

    seized_from_location_id = Column(Integer, ForeignKey('locations.location_id'))
    seized_from_person_id = Column(Integer, ForeignKey('people.person_id'))
    seizure_date = Column(Date)

    current_location = Column(String(255))
    status = Column(String(50))

    source_document_id = Column(Integer, ForeignKey('documents.document_id'))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ============================================
# EXTRACTION LOGS
# ============================================

class ExtractionLog(Base):
    __tablename__ = 'extraction_log'

    log_id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.document_id', ondelete='CASCADE'))
    media_file_id = Column(Integer, ForeignKey('media_files.media_file_id', ondelete='CASCADE'))

    extraction_type = Column(String(50))
    status = Column(String(50))

    entities_extracted = Column(Integer, default=0)
    relationships_extracted = Column(Integer, default=0)
    events_extracted = Column(Integer, default=0)

    error_message = Column(Text)
    warnings = Column(ArrayType())

    processing_time_ms = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

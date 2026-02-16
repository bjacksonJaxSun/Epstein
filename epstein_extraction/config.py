"""
Configuration and database connection settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from loguru import logger

# Load environment variables
load_dotenv()

# ============================================
# TESSERACT OCR CONFIGURATION
# ============================================
TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if Path(TESSERACT_PATH).exists():
    # Configure pytesseract to use the correct path
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        logger.info(f"Tesseract OCR configured: {TESSERACT_PATH}")
    except ImportError:
        pass  # pytesseract not installed yet

# ============================================
# PATHS
# ============================================
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "epstein_files"
DATASET_9_DIR = DATA_DIR / "DataSet_9"
OUTPUT_DIR = BASE_DIR / "extraction_output"
LOGS_DIR = OUTPUT_DIR / "logs"

# Create directories if they don't exist
OUTPUT_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ============================================
# DATASET CONFIGURATIONS
# ============================================
# Each dataset can be configured with its path and type
# type: 'load_file' (has OPT/DAT files) or 'directory' (flat PDF directory)
DATASETS = {
    'dataset_1': {
        'name': 'DataSet 1 - FBI Evidence Photos',
        'path': Path(r'D:\DataSet1_extracted\DataSet 1\DataSet 1'),
        'type': 'load_file',
        'volume_pattern': 'VOL*',
        'description': 'FBI evidence photographs from July 2019 search',
    },
    'dataset_9': {
        'name': 'DataSet 9',
        'path': DATASET_9_DIR,
        'type': 'directory',
        'file_pattern': 'EFTA*.pdf',
        'description': 'Document collection',
    },
}

# Default dataset to process
DEFAULT_DATASET = os.getenv('DATASET', 'dataset_1')

# ============================================
# DATABASE CONFIGURATION
# ============================================
DB_TYPE = os.getenv("DB_TYPE", "postgresql")  # 'sqlite' or 'postgresql'

if DB_TYPE == "sqlite":
    # SQLite configuration (easier for getting started)
    DB_PATH = OUTPUT_DIR / "epstein_documents.db"
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    logger.info(f"Using SQLite database: {DB_PATH}")
else:
    # PostgreSQL configuration
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "epstein_documents")
    DB_USER = os.getenv("DB_USER", "epstein_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "epstein_secure_pw_2024")
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    logger.info(f"Using PostgreSQL database: {DB_HOST}:{DB_PORT}/{DB_NAME}")

# ============================================
# EXTRACTION SETTINGS
# ============================================
BATCH_SIZE = 100  # Process documents in batches
MAX_WORKERS = 4   # Number of parallel workers
ENABLE_OCR = True  # Enable OCR for scanned documents
ENABLE_IMAGE_ANALYSIS = False  # Enable AI image analysis (requires API keys)

# Confidence thresholds
MIN_NER_CONFIDENCE = 0.75
MIN_FACE_CONFIDENCE = 0.80
MIN_IMAGE_ANALYSIS_CONFIDENCE = 0.70

# ============================================
# NLP SETTINGS
# ============================================
SPACY_MODEL = "en_core_web_trf"  # Transformer-based model (most accurate)
# Alternative: "en_core_web_lg" (faster, less accurate)

# ============================================
# AI PROVIDER SETTINGS (Optional)
# ============================================
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

AZURE_VISION_KEY = os.getenv("AZURE_VISION_KEY")
AZURE_VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT")

GOOGLE_CLOUD_CREDENTIALS = os.getenv("GOOGLE_CLOUD_CREDENTIALS")

# ============================================
# LOGGING CONFIGURATION
# ============================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = LOGS_DIR / "extraction_{time:YYYY-MM-DD}.log"

logger.add(
    LOG_FILE,
    rotation="500 MB",
    retention="30 days",
    level=LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
)

# ============================================
# DATABASE ENGINE & SESSION
# ============================================
# Pool configuration optimized for high concurrency (2000+ users)
# When using Azure PostgreSQL with PgBouncer, these settings work with the pooler
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "50"))  # Base pool size
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "100"))  # Additional connections when needed
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "300"))  # Recycle connections every 5 minutes

engine = create_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=POOL_RECYCLE,  # Recycle stale connections
    pool_timeout=30,  # Wait 30s for connection from pool
    echo=False  # Set to True for SQL query logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================
# REGEX PATTERNS
# ============================================
import re

PATTERNS = {
    'efta_number': re.compile(r'EFTA\d{8}'),
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    'phone': re.compile(r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b'),
    'case_number': re.compile(r'\b\d{2}-(?:CR|cv)-\d{5}\b', re.IGNORECASE),
    'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    'money': re.compile(r'\$[\d,]+(?:\.\d{2})?'),
    'date': re.compile(r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b')
}

# ============================================
# DOCUMENT TYPE MAPPING
# ============================================
DOCUMENT_TYPE_KEYWORDS = {
    'email': ['from:', 'to:', 'subject:', 'sent:', 're:'],
    'court_filing': ['united states district court', 'plaintiff', 'defendant', 'motion', 'order'],
    'police_report': ['incident report', 'case number', 'officer', 'detective'],
    'memo': ['memorandum', 'memo to', 'memo from'],
    'letter': ['dear', 'sincerely', 'regards'],
    'transcript': ['transcript', 'deposition', 'testimony'],
    'affidavit': ['affidavit', 'sworn statement', 'notary'],
    'subpoena': ['subpoena', 'you are hereby commanded'],
    'warrant': ['warrant', 'probable cause'],
    'detention_record': ['bureau of prisons', 'inmate', 'register number', 'detention'],
}

# ============================================
# ENTITY ROLE KEYWORDS
# ============================================
ROLE_KEYWORDS = {
    'victim': ['victim', 'minor victim', 'jane doe', 'complainant'],
    'defendant': ['defendant', 'accused', 'charged with'],
    'prosecutor': ['assistant united states attorney', 'ausa', 'prosecutor'],
    'defense_attorney': ['defense attorney', 'counsel for', 'attorney for defendant'],
    'judge': ['judge', 'honorable', 'magistrate'],
    'witness': ['witness', 'testified', 'deponent'],
    'investigator': ['agent', 'detective', 'investigator', 'special agent'],
    'employee': ['employee', 'worked for', 'employed by'],
}

logger.info("Configuration loaded successfully")
logger.info(f"Data directory: {DATA_DIR}")
logger.info(f"Output directory: {OUTPUT_DIR}")

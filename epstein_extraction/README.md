# Epstein Document Extraction Pipeline

Comprehensive Python extraction system for processing PDF documents and images into a structured PostgreSQL database with Named Entity Recognition (NER), relationship mapping, and timeline construction.

## Features

- **PDF Text Extraction**: Multi-method extraction (pdfplumber, PyPDF2, OCR)
- **Named Entity Recognition**: AI-powered entity extraction using spaCy
- **Image Metadata**: EXIF data extraction (GPS, camera, timestamps)
- **Relationship Mapping**: Automatic relationship inference
- **Entity Deduplication**: Fuzzy matching to merge duplicates
- **Timeline Construction**: Chronological event tracking
- **Batch Processing**: Parallel processing for performance
- **Progress Tracking**: Real-time extraction logging

## Architecture

```
epstein_extraction/
├── config.py                 # Configuration & database connection
├── models.py                # SQLAlchemy ORM models (33 tables)
├── extractors/
│   ├── pdf_extractor.py     # PDF text extraction (3 methods)
│   ├── image_extractor.py   # EXIF metadata extraction
│   └── ner_processor.py     # spaCy NER processing
├── services/
│   ├── database_service.py  # Database CRUD operations
│   ├── deduplication.py     # Entity deduplication
│   └── relationship_builder.py  # Relationship inference
├── main.py                  # Main orchestration script
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## Installation

### Prerequisites

- Python 3.9+
- PostgreSQL 14+
- Tesseract OCR (for scanned documents)

### Step 1: Install Python Dependencies

```bash
cd epstein_extraction

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy language model
python -m spacy download en_core_web_trf
```

### Step 2: Install Tesseract OCR

**Windows:**
```bash
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Install and add to PATH
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

### Step 3: Setup PostgreSQL Database

```bash
# Create database
psql -U postgres
CREATE DATABASE epstein_documents;
\q

# Database will be initialized automatically on first run
```

### Step 4: Configure Environment

Create `.env` file in the `epstein_extraction` directory:

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=epstein_documents
DB_USER=postgres
DB_PASSWORD=your_password_here

# Extraction Settings
BATCH_SIZE=100
MAX_WORKERS=4
ENABLE_OCR=True

# spaCy Model
SPACY_MODEL=en_core_web_trf

# Logging
LOG_LEVEL=INFO

# Optional: AI Image Analysis (if enabled)
# AWS_ACCESS_KEY=your_aws_key
# AWS_SECRET_KEY=your_aws_secret
# AZURE_VISION_KEY=your_azure_key
# AZURE_VISION_ENDPOINT=your_azure_endpoint
```

## Usage

### Quick Start

**Option 1: Process files while downloading (Recommended)**

```bash
# Start processing files as they arrive
python continuous_processor.py --mode continuous
```

See [CONCURRENT_PROCESSING.md](CONCURRENT_PROCESSING.md) for full details.

**Option 2: Process existing files once**

```bash
# Process first 10 documents
python main.py
```

### Full Pipeline

```python
from main import ExtractionOrchestrator

orchestrator = ExtractionOrchestrator()

# Initialize database
orchestrator.initialize_database()

# Extract all documents (or specify limit)
orchestrator.extract_all_documents(limit=100)  # First 100 docs

# Build relationships
orchestrator.build_relationships()

# Deduplicate entities
orchestrator.deduplicate_entities()

# Print statistics
orchestrator.print_statistics()
```

### Process Specific Files

```python
from pathlib import Path

orchestrator = ExtractionOrchestrator()

# Process specific directory
pdf_files = orchestrator.get_pdf_files(
    directory=Path("/path/to/pdfs"),
    limit=50
)

orchestrator.process_batch(pdf_files)
```

### Extract Images from PDFs

```python
from extractors import ImageExtractor

extractor = ImageExtractor()

# Extract embedded images
images = extractor.extract_embedded_images_from_pdf("path/to/file.pdf")

# Extract EXIF from image
metadata = extractor.extract("path/to/image.jpg")
print(metadata['gps_latitude'], metadata['gps_longitude'])
```

### Named Entity Recognition

```python
from extractors import NERProcessor

processor = NERProcessor()

text = "Jeffrey Epstein met with Bill Clinton in New York on July 15, 2019."

# Extract entities
entities = processor.process(text)
print(entities['people'])        # ['Jeffrey Epstein', 'Bill Clinton']
print(entities['locations'])     # ['New York']
print(entities['dates'])         # ['July 15, 2019']

# Extract relationships
relationships = processor.extract_relationships(text)
print(relationships)
```

### Database Queries

```python
from config import SessionLocal
from services import DatabaseService

db = SessionLocal()
db_service = DatabaseService(db)

# Get document by EFTA number
doc = db_service.get_document_by_efta("EFTA00068050")

# Get person by name
person = db_service.get_person_by_name("Jeffrey Epstein")

# Get extraction statistics
stats = db_service.get_extraction_stats()
print(f"Total Documents: {stats['total_documents']}")
print(f"Total People: {stats['total_people']}")

db.close()
```

### Deduplication

```python
from services import DeduplicationService

dedup = DeduplicationService(db)

# Find duplicates
duplicates = dedup.find_duplicate_people("Jeffrey Epstein")

# Get merge suggestions
suggestions = dedup.suggest_merges('person')
for suggestion in suggestions:
    print(f"{suggestion['primary_name']} == {suggestion['duplicate_name']} "
          f"({suggestion['similarity']:.2f})")

# Auto-merge high confidence (95%+)
merged_count = dedup.auto_merge_high_confidence(min_similarity=0.95)
```

### Relationship Analysis

```python
from services import RelationshipBuilder

builder = RelationshipBuilder(db)

# Build relationships
builder.build_relationships_from_events()
builder.build_relationships_from_communications()

# Get statistics
stats = builder.get_relationship_statistics()
print(stats['top_connected_people'])

# Find connection path
path = builder.find_connection_path("Person A", "Person B", max_depth=3)
print(" -> ".join(path))
```

## Database Schema

### Core Tables (33 total)

**Documents & Entities:**
- `documents` - PDF documents with full text
- `people` - Individuals mentioned
- `organizations` - Companies, agencies
- `locations` - Geographic locations
- `events` - Timeline events

**Relationships:**
- `relationships` - Person-to-person connections
- `event_participants` - Event attendance
- `person_organizations` - Employment/affiliation

**Media:**
- `media_files` - Images/videos with EXIF
- `image_analysis` - AI analysis results
- `visual_entities` - Detected objects/faces
- `media_people` - People in images
- `media_events` - Images linked to events

**Legal:**
- `legal_cases` - Court cases
- `court_filings` - Legal documents
- `detention_records` - Custody records
- `evidence_items` - Evidence catalog

**Communications:**
- `communications` - Emails, calls
- `communication_recipients` - Recipients

**Financial:**
- `financial_transactions` - Money transfers

**Support:**
- `tags` - Categorization
- `document_mentions` - Entity mentions
- `extraction_log` - Processing logs

### Views

- `v_timeline` - Chronological event timeline
- `v_person_network` - Relationship graph
- `v_financial_summary` - Financial activity
- `v_document_summary` - Entity counts
- `v_image_timeline` - Image timeline with people/locations
- `v_person_profile` - Complete person profile

## Performance

### Benchmarks

- **PDF Extraction**: ~500-1000ms per document (with OCR)
- **NER Processing**: ~200-500ms per document
- **Database Insert**: ~50-100ms per document
- **Parallel Processing**: 4-8x speedup with 4-8 workers

### Recommendations

- Start with small batches (100-500 documents)
- Monitor memory usage (spaCy models are large)
- Use PostgreSQL connection pooling
- Enable parallel processing for large datasets
- Use SSD storage for database

## Troubleshooting

### Common Issues

**1. spaCy model not found**
```bash
python -m spacy download en_core_web_trf
```

**2. Database connection failed**
- Check PostgreSQL is running
- Verify credentials in `.env`
- Ensure database exists

**3. OCR not working**
- Install Tesseract OCR
- Add to system PATH
- Verify with: `tesseract --version`

**4. Out of memory**
- Reduce `BATCH_SIZE` in config
- Reduce `MAX_WORKERS`
- Use smaller spaCy model: `en_core_web_lg`

**5. Slow extraction**
- Disable OCR if not needed: `ENABLE_OCR=False`
- Use parallel processing: `use_parallel=True`
- Process in smaller batches

## Development

### Running Tests

```bash
# Test PDF extraction
python extractors/pdf_extractor.py

# Test image extraction
python extractors/image_extractor.py

# Test NER
python extractors/ner_processor.py

# Test database service
python services/database_service.py
```

### Adding Custom Extractors

```python
# Create custom extractor
class CustomExtractor:
    def extract(self, file_path: str) -> Dict:
        # Your extraction logic
        return extracted_data

# Integrate into pipeline
orchestrator.custom_extractor = CustomExtractor()
```

### Database Migrations

If schema changes are needed:

```bash
# Using Alembic (recommended for production)
pip install alembic
alembic init migrations
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

## API Integration (Future)

The extraction pipeline can be extended with a REST API:

```python
from fastapi import FastAPI
from services import DatabaseService

app = FastAPI()

@app.get("/people/{name}")
def get_person(name: str):
    db = SessionLocal()
    db_service = DatabaseService(db)
    person = db_service.get_person_by_name(name)
    return person
```

## Data Export

Export to various formats:

```python
# Export to JSON
import json
people = db_service.get_all_people()
with open('people.json', 'w') as f:
    json.dump([p.__dict__ for p in people], f)

# Export to CSV
import pandas as pd
df = pd.read_sql("SELECT * FROM v_timeline", db.bind)
df.to_csv('timeline.csv', index=False)
```

## License

This extraction pipeline is for research and analysis purposes only. All extracted data remains subject to its original source licensing and restrictions.

## Support

For issues, questions, or contributions, please refer to the main project repository.

## Next Steps

After running the extraction pipeline:

1. **Review Statistics**: Check extraction quality and coverage
2. **Deduplicate Entities**: Merge duplicate people/organizations
3. **Build Relationships**: Infer connections between entities
4. **Validate Data**: Manually review high-priority entities
5. **Export Results**: Generate reports, visualizations, timelines
6. **Scale Up**: Process remaining 246k documents

## Example Output

```
EXTRACTION STATISTICS
============================================================
Total Documents:       10
Extracted Documents:   10
Pending Documents:     0
Total People:          47
Total Organizations:   12
Total Locations:       8
Total Events:          23
Total Relationships:   15
Total Media Files:     0
============================================================
```

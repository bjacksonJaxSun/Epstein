"""
PDF text extraction with OCR fallback
"""
import os
import re
from pathlib import Path
from typing import Dict, Optional, List
from loguru import logger
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import dateparser
from config import PATTERNS, DOCUMENT_TYPE_KEYWORDS, ENABLE_OCR

class PDFExtractor:
    """Extract text and metadata from PDF documents"""

    def __init__(self):
        self.enable_ocr = ENABLE_OCR

    def extract(self, pdf_path: str) -> Dict:
        """
        Extract all data from a PDF file

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with extracted data
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None

        logger.info(f"Extracting: {pdf_path.name}")

        data = {
            'efta_number': self._extract_efta_number(pdf_path),
            'file_path': str(pdf_path.absolute()),
            'file_name': pdf_path.name,
            'file_size_bytes': pdf_path.stat().st_size,
            'full_text': '',
            'page_count': 0,
            'document_type': None,
            'document_date': None,
            'document_title': None,
            'author': None,
            'recipient': None,
            'subject': None,
            'is_redacted': False,
            'redaction_level': 'none',
            'extraction_method': None,
        }

        # Try multiple extraction methods
        success = False

        # Method 1: PyMuPDF/fitz (fastest, C-based)
        try:
            text, page_count = self._extract_with_pymupdf(pdf_path)
            if text and len(text.strip()) > 100:
                data['full_text'] = text
                data['page_count'] = page_count
                data['extraction_method'] = 'pymupdf'
                success = True
                logger.debug(f"Extracted {len(text)} chars with PyMuPDF")
        except Exception as e:
            logger.warning(f"PyMuPDF failed: {e}")

        # Method 2: pdfplumber (fallback, better layout)
        if not success:
            try:
                text, page_count = self._extract_with_pdfplumber(pdf_path)
                if text and len(text.strip()) > 100:
                    data['full_text'] = text
                    data['page_count'] = page_count
                    data['extraction_method'] = 'pdfplumber'
                    success = True
                    logger.debug(f"Extracted {len(text)} chars with pdfplumber")
            except Exception as e:
                logger.warning(f"pdfplumber failed: {e}")

        # Method 3: OCR with PyMuPDF (for scanned documents)
        if not success and self.enable_ocr:
            try:
                text, page_count = self._extract_with_ocr(pdf_path)
                if text and len(text.strip()) > 50:
                    data['full_text'] = text
                    data['page_count'] = page_count
                    data['extraction_method'] = 'ocr'
                    success = True
                    logger.debug(f"Extracted {len(text)} chars with OCR")
            except Exception as e:
                logger.warning(f"OCR failed: {e}")

        if not success:
            logger.error(f"All extraction methods failed for {pdf_path.name}")
            data['extraction_method'] = 'failed'
            return data

        # Extract metadata from text
        self._extract_metadata(data)

        # Detect document type
        data['document_type'] = self._detect_document_type(data['full_text'])

        # Detect redaction
        data['is_redacted'], data['redaction_level'] = self._detect_redaction(data['full_text'])

        return data

    def _extract_efta_number(self, pdf_path: Path) -> Optional[str]:
        """Extract EFTA number from filename"""
        match = PATTERNS['efta_number'].search(pdf_path.name)
        if match:
            return match.group(0)
        return None

    def _extract_with_pymupdf(self, pdf_path: Path) -> tuple:
        """Extract text using PyMuPDF (fitz) - fastest method"""
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        text_parts = []
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)
        doc.close()
        return '\n\n'.join(text_parts), page_count

    def _extract_with_pdfplumber(self, pdf_path: Path) -> tuple:
        """Extract text using pdfplumber"""
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n\n'.join(text_parts), page_count

    def _extract_with_pypdf2(self, pdf_path: Path) -> tuple:
        """Extract text using PyPDF2"""
        text_parts = []
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            page_count = len(reader.pages)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return '\n\n'.join(text_parts), page_count

    def _extract_with_ocr(self, pdf_path: Path) -> tuple:
        """Extract text using OCR (for scanned documents)"""
        text_parts = []
        doc = fitz.open(pdf_path)
        page_count = doc.page_count

        for page_num in range(page_count):
            page = doc[page_num]

            # Convert page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # OCR the image
            page_text = pytesseract.image_to_string(img)
            if page_text:
                text_parts.append(page_text)

        doc.close()
        return '\n\n'.join(text_parts), page_count

    def _extract_metadata(self, data: Dict):
        """Extract metadata from document text"""
        text = data['full_text']
        lower_text = text.lower()

        # Extract document title (first meaningful line)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            # Skip very short lines and common headers
            for line in lines[:10]:
                if len(line) > 20 and not line.upper().isupper():
                    data['document_title'] = line[:500]
                    break

        # Extract dates
        date_matches = PATTERNS['date'].findall(text[:2000])  # Check first 2000 chars
        if date_matches:
            parsed_date = dateparser.parse(date_matches[0])
            if parsed_date:
                data['document_date'] = parsed_date.date()

        # Extract author (look for common patterns)
        author_patterns = [
            r'from:\s*([^\n]+)',
            r'by:\s*([^\n]+)',
            r'author:\s*([^\n]+)',
            r'prepared by:\s*([^\n]+)',
        ]
        for pattern in author_patterns:
            match = re.search(pattern, lower_text)
            if match:
                data['author'] = match.group(1).strip()[:255]
                break

        # Extract recipient
        recipient_patterns = [
            r'to:\s*([^\n]+)',
            r'for:\s*([^\n]+)',
        ]
        for pattern in recipient_patterns:
            match = re.search(pattern, lower_text)
            if match:
                data['recipient'] = match.group(1).strip()[:255]
                break

        # Extract subject
        subject_patterns = [
            r'subject:\s*([^\n]+)',
            r're:\s*([^\n]+)',
        ]
        for pattern in subject_patterns:
            match = re.search(pattern, lower_text)
            if match:
                data['subject'] = match.group(1).strip()[:500]
                break

    def _detect_document_type(self, text: str) -> Optional[str]:
        """Detect document type based on keywords"""
        text_lower = text.lower()

        scores = {}
        for doc_type, keywords in DOCUMENT_TYPE_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[doc_type] = score

        if scores:
            return max(scores, key=scores.get)
        return 'unknown'

    def _detect_redaction(self, text: str) -> tuple:
        """Detect if document is redacted and severity"""
        redaction_indicators = [
            'redacted',
            '[redacted]',
            'xxxxx',
            'jane doe',
            'john doe',
            'minor victim',
            'victim-1',
            'witness-1',
            '█████',  # Redaction blocks
        ]

        text_lower = text.lower()
        redaction_count = sum(text_lower.count(indicator) for indicator in redaction_indicators)

        if redaction_count == 0:
            return False, 'none'
        elif redaction_count < 5:
            return True, 'light'
        elif redaction_count < 20:
            return True, 'moderate'
        else:
            return True, 'heavy'

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract basic entities using regex (before NLP)

        Returns:
            Dictionary with entity lists
        """
        entities = {
            'emails': [],
            'phones': [],
            'case_numbers': [],
            'money_amounts': [],
            'dates': [],
        }

        # Extract emails
        entities['emails'] = list(set(PATTERNS['email'].findall(text)))

        # Extract phone numbers
        entities['phones'] = list(set(PATTERNS['phone'].findall(text)))

        # Extract case numbers
        entities['case_numbers'] = list(set(PATTERNS['case_number'].findall(text)))

        # Extract money amounts
        entities['money_amounts'] = list(set(PATTERNS['money'].findall(text)))

        # Extract dates
        entities['dates'] = list(set(PATTERNS['date'].findall(text)))

        return entities


if __name__ == "__main__":
    # Test extraction
    extractor = PDFExtractor()
    test_file = Path("C:/Development/JaxSun.Ideas/tools/EpsteinDownloader/epstein_files/DataSet_9/EFTA00068047.pdf")

    if test_file.exists():
        result = extractor.extract(str(test_file))
        print(f"\nEFTA Number: {result['efta_number']}")
        print(f"Document Type: {result['document_type']}")
        print(f"Date: {result['document_date']}")
        print(f"Title: {result['document_title']}")
        print(f"Pages: {result['page_count']}")
        print(f"Text Length: {len(result['full_text'])} chars")
        print(f"Redacted: {result['is_redacted']} ({result['redaction_level']})")
        print(f"Extraction Method: {result['extraction_method']}")

        entities = extractor.extract_entities(result['full_text'])
        print(f"\nExtracted Entities:")
        for entity_type, values in entities.items():
            if values:
                print(f"  {entity_type}: {len(values)} found")
    else:
        print(f"Test file not found: {test_file}")

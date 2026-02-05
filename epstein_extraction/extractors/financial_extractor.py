"""
Financial Transaction Extractor

Identifies and extracts financial transactions from document text by:
1. Finding monetary amounts
2. Identifying associated parties (payer/payee)
3. Extracting dates
4. Classifying transaction types
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class ExtractedTransaction:
    """Represents an extracted financial transaction"""
    amount: float
    currency: str = "USD"
    from_entity: Optional[str] = None
    from_entity_type: Optional[str] = None  # 'person' or 'organization'
    to_entity: Optional[str] = None
    to_entity_type: Optional[str] = None
    transaction_date: Optional[str] = None
    transaction_type: Optional[str] = None
    purpose: Optional[str] = None
    context: str = ""  # The sentence/paragraph where this was found
    confidence: float = 0.5


class FinancialExtractor:
    """Extracts financial transactions from document text"""

    # Money patterns
    MONEY_PATTERNS = [
        # $1,234,567.89 or $1234567.89
        r'\$\s*([\d,]+(?:\.\d{2})?)\s*(?:million|billion|thousand|M|B|K)?',
        # USD 1,234.56
        r'(?:USD|EUR|GBP|CHF)\s*([\d,]+(?:\.\d{2})?)',
        # 1.5 million dollars
        r'([\d.]+)\s*(?:million|billion)\s*(?:dollars?|USD)',
    ]

    # Transaction type keywords
    TRANSACTION_TYPES = {
        'payment': ['payment', 'paid', 'paying', 'pays', 'remittance'],
        'transfer': ['transfer', 'transferred', 'wire', 'wired', 'sent'],
        'donation': ['donation', 'donated', 'gift', 'gifted', 'contributed'],
        'investment': ['investment', 'invested', 'stake', 'equity'],
        'loan': ['loan', 'loaned', 'borrowed', 'lending', 'credit'],
        'salary': ['salary', 'compensation', 'wages', 'earnings', 'paid.*annually'],
        'purchase': ['purchase', 'purchased', 'bought', 'acquisition', 'acquired'],
        'sale': ['sale', 'sold', 'selling', 'proceeds'],
        'fee': ['fee', 'fees', 'commission', 'retainer'],
        'settlement': ['settlement', 'settled', 'settlement agreement'],
        'trust': ['trust', 'trust fund', 'endowment'],
    }

    # Direction keywords (from/to indicators)
    FROM_INDICATORS = ['from', 'by', 'paid by', 'sent by', 'transferred by', 'received from']
    TO_INDICATORS = ['to', 'for', 'paid to', 'sent to', 'transferred to', 'received by']

    def __init__(self, nlp=None):
        """
        Initialize the financial extractor.

        Args:
            nlp: Optional spaCy model for NER. If not provided, uses regex-based extraction.
        """
        self.nlp = nlp
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        self.money_regexes = [re.compile(p, re.IGNORECASE) for p in self.MONEY_PATTERNS]

        # Compile transaction type patterns
        self.type_patterns = {}
        for tx_type, keywords in self.TRANSACTION_TYPES.items():
            pattern = '|'.join(keywords)
            self.type_patterns[tx_type] = re.compile(pattern, re.IGNORECASE)

    def extract(self, text: str, known_people: List[str] = None,
                known_orgs: List[str] = None) -> List[ExtractedTransaction]:
        """
        Extract financial transactions from text.

        Args:
            text: Document text to analyze
            known_people: List of known person names from NER
            known_orgs: List of known organization names from NER

        Returns:
            List of extracted transactions
        """
        if not text or len(text) < 10:
            return []

        known_people = known_people or []
        known_orgs = known_orgs or []

        transactions = []

        # Split into sentences/paragraphs for context
        sentences = self._split_into_sentences(text)

        for sentence in sentences:
            # Find money amounts in this sentence
            amounts = self._extract_amounts(sentence)

            if not amounts:
                continue

            for amount, currency in amounts:
                # Skip very small amounts (likely noise)
                if amount < 100:
                    continue

                # Extract transaction details
                tx = self._extract_transaction_details(
                    sentence, amount, currency,
                    known_people, known_orgs
                )

                if tx:
                    transactions.append(tx)

        # Deduplicate similar transactions
        transactions = self._deduplicate(transactions)

        logger.info(f"Extracted {len(transactions)} financial transactions")
        return transactions

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences, keeping context"""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Also split on newlines for structured documents
        result = []
        for s in sentences:
            parts = s.split('\n')
            result.extend([p.strip() for p in parts if p.strip()])

        return result

    def _extract_amounts(self, text: str) -> List[Tuple[float, str]]:
        """Extract monetary amounts from text"""
        amounts = []
        seen_amounts = set()

        # Enhanced patterns that capture multipliers with the amount
        amount_patterns = [
            # $1,234,567.89 million/billion (multiplier directly after)
            r'\$\s*([\d,]+(?:\.\d{2})?)\s*(million|billion|thousand|M|B|K)?',
            # USD 1,234.56 million/billion
            r'(?:USD|EUR|GBP|CHF)\s*([\d,]+(?:\.\d{2})?)\s*(million|billion|thousand|M|B|K)?',
            # 1.5 million dollars (already has multiplier in number context)
            r'([\d.]+)\s*(million|billion)\s*(?:dollars?|USD)',
        ]

        for pattern in amount_patterns:
            regex = re.compile(pattern, re.IGNORECASE)
            for match in regex.finditer(text):
                try:
                    amount_str = match.group(1)
                    if not amount_str:
                        continue

                    # Remove commas and parse
                    amount_str = amount_str.replace(',', '')
                    amount = float(amount_str)

                    # Get multiplier from the regex group (if captured)
                    multiplier = match.group(2) if len(match.groups()) > 1 else None

                    if multiplier:
                        mult_lower = multiplier.lower()
                        if mult_lower in ('billion', 'b'):
                            amount *= 1_000_000_000
                        elif mult_lower in ('million', 'm'):
                            amount *= 1_000_000
                        elif mult_lower in ('thousand', 'k'):
                            amount *= 1_000

                    # Skip unrealistic amounts (over $100 trillion)
                    if amount > 100_000_000_000_000:
                        continue

                    # Determine currency from the matched text context
                    currency = 'USD'
                    match_context = text[max(0, match.start()-10):match.end()+10]
                    if 'EUR' in match_context or '€' in match_context:
                        currency = 'EUR'
                    elif 'GBP' in match_context or '£' in match_context:
                        currency = 'GBP'
                    elif 'CHF' in match_context:
                        currency = 'CHF'

                    # Deduplicate by amount value
                    amount_key = (round(amount, 2), currency)
                    if amount_key not in seen_amounts:
                        seen_amounts.add(amount_key)
                        amounts.append((amount, currency))

                except (ValueError, TypeError, IndexError):
                    continue

        return amounts

    def _extract_transaction_details(self, sentence: str, amount: float,
                                     currency: str, known_people: List[str],
                                     known_orgs: List[str]) -> Optional[ExtractedTransaction]:
        """Extract full transaction details from a sentence containing an amount"""

        tx = ExtractedTransaction(
            amount=amount,
            currency=currency,
            context=sentence[:500]  # Limit context length
        )

        # Determine transaction type
        tx.transaction_type = self._identify_transaction_type(sentence)

        # Find parties involved
        from_entity, from_type = self._find_party(sentence, known_people, known_orgs, 'from')
        to_entity, to_type = self._find_party(sentence, known_people, known_orgs, 'to')

        tx.from_entity = from_entity
        tx.from_entity_type = from_type
        tx.to_entity = to_entity
        tx.to_entity_type = to_type

        # Extract date if present
        tx.transaction_date = self._extract_date(sentence)

        # Extract purpose
        tx.purpose = self._extract_purpose(sentence)

        # Calculate confidence based on completeness
        tx.confidence = self._calculate_confidence(tx)

        # Only return if we have at least one party or a transaction type
        if tx.from_entity or tx.to_entity or tx.transaction_type:
            return tx

        return None

    def _identify_transaction_type(self, text: str) -> Optional[str]:
        """Identify the type of transaction from keywords"""
        text_lower = text.lower()

        for tx_type, pattern in self.type_patterns.items():
            if pattern.search(text_lower):
                return tx_type

        return None

    # Names to exclude from matching (common false positives)
    EXCLUDED_NAMES = {
        'million', 'billion', 'thousand', 'dollar', 'dollars', 'usd', 'eur', 'gbp',
        'the', 'and', 'for', 'from', 'with', 'sur', 'ion', 'lion', 'mend', 'limit',
        'hall', 'than', 'she', 'her', 'his', 'him', 'they', 'them', 'jan', 'feb',
        'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
    }

    def _is_valid_entity_match(self, name: str, text: str) -> bool:
        """Check if the name match is valid (not part of another word)"""
        if len(name) < 5:  # Require minimum 5 characters
            return False

        name_lower = name.lower()

        # Exclude common false positives
        if name_lower in self.EXCLUDED_NAMES:
            return False

        # Check for word boundary match
        pattern = r'\b' + re.escape(name) + r'\b'
        return bool(re.search(pattern, text, re.IGNORECASE))

    def _find_party(self, text: str, known_people: List[str],
                    known_orgs: List[str], direction: str) -> Tuple[Optional[str], Optional[str]]:
        """Find a party (person or organization) in the text"""

        text_lower = text.lower()

        # Choose indicators based on direction
        if direction == 'from':
            indicators = self.FROM_INDICATORS
        else:
            indicators = self.TO_INDICATORS

        # Look for known entities near direction indicators
        for indicator in indicators:
            if indicator in text_lower:
                # Get the portion after the indicator
                idx = text_lower.find(indicator)
                context = text[idx:idx+100]

                # Check for known people (prefer longer names first)
                for person in sorted(known_people, key=len, reverse=True):
                    if self._is_valid_entity_match(person, context):
                        return (person, 'person')

                # Check for known organizations (prefer longer names first)
                for org in sorted(known_orgs, key=len, reverse=True):
                    if self._is_valid_entity_match(org, context):
                        return (org, 'organization')

        # Fallback: look for any known entity in the full text
        # Prefer people with longer names and those that appear as whole words
        for person in sorted(known_people, key=len, reverse=True):
            if self._is_valid_entity_match(person, text):
                return (person, 'person')

        for org in sorted(known_orgs, key=len, reverse=True):
            if self._is_valid_entity_match(org, text):
                return (org, 'organization')

        return (None, None)

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract a date from the text"""
        # Common date patterns
        date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{2,4})',
            r'(\d{4}-\d{2}-\d{2})',
            r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})',
            r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                # Try to normalize to YYYY-MM-DD
                try:
                    for fmt in ['%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%B %d, %Y', '%B %d %Y', '%b. %d, %Y', '%b %d, %Y']:
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            return dt.strftime('%Y-%m-%d')
                        except ValueError:
                            continue
                except:
                    return date_str

        return None

    def _extract_purpose(self, text: str) -> Optional[str]:
        """Extract the purpose or description of the transaction"""
        # Look for common purpose indicators
        purpose_patterns = [
            r'for\s+([^,.]+)',
            r'purpose[:\s]+([^,.]+)',
            r'regarding\s+([^,.]+)',
        ]

        for pattern in purpose_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                purpose = match.group(1).strip()
                if len(purpose) > 5 and len(purpose) < 200:
                    return purpose

        return None

    def _calculate_confidence(self, tx: ExtractedTransaction) -> float:
        """Calculate confidence score based on transaction completeness"""
        score = 0.3  # Base score for having an amount

        if tx.from_entity:
            score += 0.2
        if tx.to_entity:
            score += 0.2
        if tx.transaction_date:
            score += 0.1
        if tx.transaction_type:
            score += 0.1
        if tx.purpose:
            score += 0.1

        return min(score, 1.0)

    def _deduplicate(self, transactions: List[ExtractedTransaction]) -> List[ExtractedTransaction]:
        """Remove duplicate transactions"""
        seen = set()
        unique = []

        for tx in transactions:
            # Create a key based on amount and parties
            key = (tx.amount, tx.from_entity, tx.to_entity, tx.transaction_type)
            if key not in seen:
                seen.add(key)
                unique.append(tx)

        return unique


# Singleton instance
financial_extractor = FinancialExtractor()


if __name__ == "__main__":
    # Test the extractor
    test_text = """
    Jeffrey Epstein made a payment of $500,000 to Ghislaine Maxwell on March 15, 2005.
    The transfer was for personal services rendered.

    Les Wexner donated $10 million to the foundation in 2008.

    A wire transfer of $2.5 million was sent from Epstein's account to an offshore entity.

    The settlement agreement was for $1,500,000 paid to Jane Doe.
    """

    extractor = FinancialExtractor()
    results = extractor.extract(
        test_text,
        known_people=['Jeffrey Epstein', 'Ghislaine Maxwell', 'Les Wexner', 'Jane Doe'],
        known_orgs=['the foundation']
    )

    print(f"\nExtracted {len(results)} transactions:\n")
    for tx in results:
        print(f"Amount: ${tx.amount:,.2f} {tx.currency}")
        print(f"From: {tx.from_entity} ({tx.from_entity_type})")
        print(f"To: {tx.to_entity} ({tx.to_entity_type})")
        print(f"Type: {tx.transaction_type}")
        print(f"Date: {tx.transaction_date}")
        print(f"Confidence: {tx.confidence:.2f}")
        print(f"Context: {tx.context[:100]}...")
        print("-" * 50)

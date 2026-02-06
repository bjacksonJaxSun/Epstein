"""
Text cleaning and normalization for search optimization.
Handles redaction markers, OCR artifacts, and text normalization.
"""

import re
from typing import Tuple, List, Dict, Any
from dataclasses import dataclass


@dataclass
class CleaningResult:
    """Result of text cleaning operation."""
    cleaned_text: str
    redaction_count: int
    redaction_positions: List[Dict[str, Any]]
    original_length: int
    cleaned_length: int


class TextCleaner:
    """Cleans and normalizes document text for search optimization."""

    # Patterns for various redaction markers found in legal documents
    REDACTION_PATTERNS = [
        # Explicit markers
        (r'\[REDACTED\]', '[R]'),
        (r'\[SEALED\]', '[R]'),
        (r'\[CONFIDENTIAL\]', '[R]'),
        (r'\[RESTRICTED\]', '[R]'),
        (r'\[CLASSIFIED\]', '[R]'),
        (r'\[WITHHELD\]', '[R]'),
        (r'\[REMOVED\]', '[R]'),
        (r'\[DELETED\]', '[R]'),
        (r'\[EXPUNGED\]', '[R]'),
        # Partial redaction markers
        (r'\[.*?REDACTED.*?\]', '[R]'),
        (r'\[.*?SEALED.*?\]', '[R]'),
        # Unicode block characters (common in redacted PDFs)
        (r'█+', '[R]'),
        (r'▓+', '[R]'),
        (r'▒+', '[R]'),
        (r'░+', '[R]'),
        (r'■+', '[R]'),
        # Character-based redactions
        (r'X{5,}', '[R]'),  # XXXXX or more
        (r'\*{5,}', '[R]'),  # ***** or more
        (r'_{10,}', '[R]'),  # __________ or more (often used for blanks)
        (r'-{10,}', '[R]'),  # ---------- or more
        (r'\.{10,}', '[R]'),  # .......... or more
        # OCR artifacts from blacked-out text
        (r'(?:\s*[Il1\|]{10,}\s*)', '[R]'),  # Repeated I, l, 1, | from OCR
    ]

    # Patterns for normalizing whitespace and formatting
    NORMALIZE_PATTERNS = [
        (r'\r\n', '\n'),  # Normalize line endings
        (r'\r', '\n'),
        (r'[ \t]+', ' '),  # Collapse horizontal whitespace
        (r'\n{3,}', '\n\n'),  # Max 2 consecutive newlines
        (r'^\s+', ''),  # Leading whitespace
        (r'\s+$', ''),  # Trailing whitespace
    ]

    def __init__(self, collapse_redactions: bool = True):
        """
        Initialize the text cleaner.

        Args:
            collapse_redactions: If True, collapse consecutive [R] markers into one
        """
        self.collapse_redactions = collapse_redactions

    def clean_for_search(self, text: str) -> CleaningResult:
        """
        Clean text for search indexing.

        Args:
            text: Raw document text

        Returns:
            CleaningResult with cleaned text and metadata
        """
        if not text:
            return CleaningResult(
                cleaned_text='',
                redaction_count=0,
                redaction_positions=[],
                original_length=0,
                cleaned_length=0
            )

        original_length = len(text)
        cleaned = text
        redaction_count = 0
        redaction_positions = []

        # Apply redaction pattern replacements
        for pattern, replacement in self.REDACTION_PATTERNS:
            try:
                matches = list(re.finditer(pattern, cleaned, re.IGNORECASE))
                redaction_count += len(matches)
                for m in matches:
                    redaction_positions.append({
                        'start': m.start(),
                        'end': m.end(),
                        'original': m.group()[:50],  # Truncate for storage
                        'pattern': pattern
                    })
                cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
            except re.error:
                # Skip invalid patterns
                continue

        # Collapse multiple [R] markers if enabled
        if self.collapse_redactions:
            cleaned = re.sub(r'(\[R\]\s*)+', '[R] ', cleaned)

        # Apply normalization patterns
        for pattern, replacement in self.NORMALIZE_PATTERNS:
            cleaned = re.sub(pattern, replacement, cleaned)

        # Final cleanup
        cleaned = cleaned.strip()

        return CleaningResult(
            cleaned_text=cleaned,
            redaction_count=redaction_count,
            redaction_positions=redaction_positions,
            original_length=original_length,
            cleaned_length=len(cleaned)
        )

    def clean_for_display(self, text: str, max_length: int = 500) -> str:
        """
        Clean text for display in search results.
        Preserves some formatting for readability.

        Args:
            text: Text to clean
            max_length: Maximum length of result

        Returns:
            Cleaned text suitable for display
        """
        result = self.clean_for_search(text)
        display_text = result.cleaned_text

        if len(display_text) > max_length:
            # Try to break at a sentence or word boundary
            truncated = display_text[:max_length]
            last_period = truncated.rfind('.')
            last_space = truncated.rfind(' ')

            if last_period > max_length * 0.7:
                display_text = truncated[:last_period + 1]
            elif last_space > max_length * 0.8:
                display_text = truncated[:last_space] + '...'
            else:
                display_text = truncated + '...'

        return display_text

    def extract_searchable_segments(self, text: str, min_segment_length: int = 50) -> List[Dict[str, Any]]:
        """
        Extract meaningful text segments between redactions.
        Useful for understanding document structure and content.

        Args:
            text: Cleaned text with [R] markers
            min_segment_length: Minimum chars for a segment to be included

        Returns:
            List of segment dictionaries with position and text
        """
        # Split on redaction markers
        segments = re.split(r'\[R\]', text)
        results = []

        current_pos = 0
        for i, segment in enumerate(segments):
            segment_text = segment.strip()

            if len(segment_text) >= min_segment_length:
                results.append({
                    'index': i,
                    'position': current_pos,
                    'text': segment_text,
                    'length': len(segment_text),
                    'has_preceding_redaction': i > 0,
                    'has_following_redaction': i < len(segments) - 1
                })

            current_pos += len(segment) + 3  # +3 for [R]

        return results

    def get_redaction_density(self, text: str) -> float:
        """
        Calculate the density of redactions in a document.

        Args:
            text: Original or cleaned text

        Returns:
            Float between 0.0 (no redactions) and 1.0 (fully redacted)
        """
        if not text:
            return 0.0

        result = self.clean_for_search(text)

        if result.original_length == 0:
            return 0.0

        # Estimate redacted character count
        redacted_chars = sum(
            pos['end'] - pos['start']
            for pos in result.redaction_positions
        )

        return min(1.0, redacted_chars / result.original_length)

    def is_heavily_redacted(self, text: str, threshold: float = 0.5) -> bool:
        """
        Check if a document is heavily redacted.

        Args:
            text: Document text
            threshold: Redaction density threshold (default 50%)

        Returns:
            True if document exceeds redaction threshold
        """
        return self.get_redaction_density(text) >= threshold


# Convenience function for quick cleaning
def clean_text(text: str) -> str:
    """Quick text cleaning for search indexing."""
    cleaner = TextCleaner()
    result = cleaner.clean_for_search(text)
    return result.cleaned_text

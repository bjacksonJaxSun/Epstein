"""
Semantic document chunking for search and RAG.
Splits documents into overlapping chunks while preserving context.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import hashlib


@dataclass
class DocumentChunk:
    """A chunk of document text with metadata."""
    chunk_id: str
    document_id: int
    efta_number: str
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    page_number: Optional[int] = None
    has_redaction: bool = False
    preceding_context: str = ""
    following_context: str = ""
    token_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            'chunk_id': self.chunk_id,
            'document_id': self.document_id,
            'efta_number': self.efta_number,
            'chunk_index': self.chunk_index,
            'chunk_text': self.text,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'page_number': self.page_number,
            'has_redaction': self.has_redaction,
            'preceding_context': self.preceding_context,
            'following_context': self.following_context,
            'token_count': self.token_count,
        }


class SemanticChunker:
    """
    Chunks documents while preserving semantic boundaries.
    Uses paragraph and sentence boundaries when possible.
    Maintains overlap between chunks for context continuity.
    """

    # Patterns that indicate good break points
    PARAGRAPH_BREAK = re.compile(r'\n\s*\n')
    SENTENCE_END = re.compile(r'[.!?]\s+(?=[A-Z])')
    LIST_ITEM = re.compile(r'\n\s*(?:\d+\.|\-|\*|\•)\s+')

    # Redaction patterns
    REDACTION_PATTERN = re.compile(r'\[R\]|\[REDACTED\]|█+', re.IGNORECASE)

    def __init__(
        self,
        target_chunk_size: int = 1000,
        min_chunk_size: int = 200,
        max_chunk_size: int = 1500,
        overlap_size: int = 100,
        context_size: int = 100,
    ):
        """
        Initialize the chunker.

        Args:
            target_chunk_size: Target characters per chunk
            min_chunk_size: Minimum chunk size (avoid tiny chunks)
            max_chunk_size: Maximum chunk size (hard limit)
            overlap_size: Characters to overlap between chunks
            context_size: Characters of context to store for each chunk
        """
        self.target_size = target_chunk_size
        self.min_size = min_chunk_size
        self.max_size = max_chunk_size
        self.overlap_size = overlap_size
        self.context_size = context_size

    def chunk_document(
        self,
        document_id: int,
        efta_number: str,
        text: str,
        page_boundaries: Optional[List[int]] = None,
    ) -> List[DocumentChunk]:
        """
        Split a document into semantic chunks.

        Args:
            document_id: Database ID of the document
            efta_number: EFTA identifier
            text: Full document text
            page_boundaries: Optional list of character positions where pages start

        Returns:
            List of DocumentChunk objects
        """
        if not text or len(text.strip()) < self.min_size:
            # Document too short to chunk meaningfully
            if text and text.strip():
                return [self._create_chunk(
                    document_id=document_id,
                    efta_number=efta_number,
                    chunk_index=0,
                    text=text.strip(),
                    start_char=0,
                    page_boundaries=page_boundaries,
                )]
            return []

        # Split into semantic segments
        segments = self._split_into_segments(text)

        # Build chunks from segments
        chunks = self._build_chunks(
            document_id=document_id,
            efta_number=efta_number,
            segments=segments,
            page_boundaries=page_boundaries,
        )

        # Add context references between chunks
        self._add_context_references(chunks)

        return chunks

    def _split_into_segments(self, text: str) -> List[Tuple[int, str]]:
        """
        Split text into segments at semantic boundaries.

        Returns list of (start_position, segment_text) tuples.
        """
        segments = []

        # First, split on paragraph breaks
        paragraphs = self.PARAGRAPH_BREAK.split(text)
        current_pos = 0

        for para in paragraphs:
            if para.strip():
                # Find actual position in original text
                actual_pos = text.find(para, current_pos)
                if actual_pos == -1:
                    actual_pos = current_pos

                segments.append((actual_pos, para))
                current_pos = actual_pos + len(para)

        # If we got very few segments, try sentence splitting
        if len(segments) <= 2 and len(text) > self.target_size * 2:
            segments = self._split_into_sentences(text)

        return segments

    def _split_into_sentences(self, text: str) -> List[Tuple[int, str]]:
        """Split text into sentences."""
        segments = []
        current_pos = 0

        for match in self.SENTENCE_END.finditer(text):
            end_pos = match.end()
            segment = text[current_pos:end_pos].strip()
            if segment:
                segments.append((current_pos, segment + ' '))
            current_pos = end_pos

        # Don't forget the last segment
        if current_pos < len(text):
            remaining = text[current_pos:].strip()
            if remaining:
                segments.append((current_pos, remaining))

        return segments if segments else [(0, text)]

    def _build_chunks(
        self,
        document_id: int,
        efta_number: str,
        segments: List[Tuple[int, str]],
        page_boundaries: Optional[List[int]],
    ) -> List[DocumentChunk]:
        """Build chunks from segments, respecting size limits."""
        chunks = []
        current_text = ""
        current_start = 0
        chunk_index = 0

        for seg_start, seg_text in segments:
            # Check if adding this segment would exceed max size
            combined_len = len(current_text) + len(seg_text)

            if combined_len > self.max_size and len(current_text) >= self.min_size:
                # Save current chunk
                chunks.append(self._create_chunk(
                    document_id=document_id,
                    efta_number=efta_number,
                    chunk_index=chunk_index,
                    text=current_text.strip(),
                    start_char=current_start,
                    page_boundaries=page_boundaries,
                ))
                chunk_index += 1

                # Start new chunk with overlap
                overlap_text = current_text[-self.overlap_size:] if len(current_text) > self.overlap_size else ""
                current_text = overlap_text + seg_text
                current_start = seg_start - len(overlap_text)

            elif combined_len > self.target_size and len(current_text) >= self.min_size:
                # At target size, save if we have enough
                chunks.append(self._create_chunk(
                    document_id=document_id,
                    efta_number=efta_number,
                    chunk_index=chunk_index,
                    text=current_text.strip(),
                    start_char=current_start,
                    page_boundaries=page_boundaries,
                ))
                chunk_index += 1

                # Start new chunk with overlap
                overlap_text = current_text[-self.overlap_size:] if len(current_text) > self.overlap_size else ""
                current_text = overlap_text + seg_text
                current_start = seg_start - len(overlap_text)

            else:
                # Add segment to current chunk
                if not current_text:
                    current_start = seg_start
                current_text += seg_text + "\n\n"

        # Don't forget the last chunk
        if current_text.strip():
            chunks.append(self._create_chunk(
                document_id=document_id,
                efta_number=efta_number,
                chunk_index=chunk_index,
                text=current_text.strip(),
                start_char=current_start,
                page_boundaries=page_boundaries,
            ))

        return chunks

    def _create_chunk(
        self,
        document_id: int,
        efta_number: str,
        chunk_index: int,
        text: str,
        start_char: int,
        page_boundaries: Optional[List[int]],
    ) -> DocumentChunk:
        """Create a DocumentChunk with computed metadata."""
        # Generate unique chunk ID
        chunk_id = f"{efta_number}_chunk_{chunk_index}"

        # Determine page number
        page_number = None
        if page_boundaries:
            for i, boundary in enumerate(page_boundaries):
                if start_char < boundary:
                    page_number = i + 1  # 1-indexed pages
                    break
            if page_number is None:
                page_number = len(page_boundaries) + 1

        # Check for redactions
        has_redaction = bool(self.REDACTION_PATTERN.search(text))

        # Estimate token count (rough: ~4 chars per token)
        token_count = len(text) // 4

        return DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            efta_number=efta_number,
            chunk_index=chunk_index,
            text=text,
            start_char=start_char,
            end_char=start_char + len(text),
            page_number=page_number,
            has_redaction=has_redaction,
            token_count=token_count,
        )

    def _add_context_references(self, chunks: List[DocumentChunk]) -> None:
        """Add preceding/following context to each chunk."""
        for i, chunk in enumerate(chunks):
            # Preceding context from previous chunk
            if i > 0:
                prev_text = chunks[i - 1].text
                chunk.preceding_context = prev_text[-self.context_size:] if len(prev_text) > self.context_size else prev_text

            # Following context from next chunk
            if i < len(chunks) - 1:
                next_text = chunks[i + 1].text
                chunk.following_context = next_text[:self.context_size] if len(next_text) > self.context_size else next_text

    def estimate_chunk_count(self, text_length: int) -> int:
        """Estimate number of chunks for a given text length."""
        if text_length < self.min_size:
            return 1 if text_length > 0 else 0

        # Account for overlap
        effective_chunk_size = self.target_size - self.overlap_size
        return max(1, (text_length + effective_chunk_size - 1) // effective_chunk_size)


def chunk_document(
    document_id: int,
    efta_number: str,
    text: str,
    target_size: int = 1000,
    overlap: int = 100,
) -> List[DocumentChunk]:
    """
    Convenience function for chunking a document.

    Args:
        document_id: Database document ID
        efta_number: EFTA identifier
        text: Document text
        target_size: Target chunk size in characters
        overlap: Overlap between chunks

    Returns:
        List of DocumentChunk objects
    """
    chunker = SemanticChunker(
        target_chunk_size=target_size,
        overlap_size=overlap,
    )
    return chunker.chunk_document(document_id, efta_number, text)

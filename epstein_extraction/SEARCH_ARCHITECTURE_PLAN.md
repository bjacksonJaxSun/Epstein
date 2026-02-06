# Epstein Document Search Architecture Plan

## Data Coverage

**This plan covers ALL data from Datasets 1-12:**

| Dataset | Status | Source Path | Documents |
|---------|--------|-------------|-----------|
| Dataset 1 | Loaded | D:\DataSet1_extracted | 10,859 |
| Dataset 2 | Loaded | D:\DataSet2_extracted | 726 |
| Dataset 3 | Loaded | D:\DataSet3_extracted | 67 |
| Dataset 4 | Loaded | D:\DataSet4_extracted | 152 |
| Dataset 5 | Loaded | D:\DataSet5_extracted | 120 |
| Dataset 6 | Loaded | D:\DataSet6_extracted | 13 |
| Dataset 7 | Loaded | D:\DataSet7_extracted | 17 |
| Dataset 8 | Loaded | D:\DataSet8_extracted | 10,593 |
| Dataset 9 | Loaded | DataSet_9 (Archive.org) | 41,951 |
| Dataset 10 | Loading | D:\DataSet 10.zip (incremental) | 452+ |
| Dataset 11 | Loaded | D:\DataSet11_extracted | 7,099 |
| Dataset 12 | Loaded | D:\DataSet12_extracted | 152 |

**Total: 64,377+ documents** (Dataset 10 still loading in background)

All 12 datasets are independently loaded from their respective source directories. Datasets 11 and 12 contain unique EFTA numbers (EFTA022xxxxx and EFTA0273xxxx ranges) not duplicated elsewhere.

---

## Executive Summary

This plan outlines a comprehensive search architecture to make the Epstein document corpus searchable by both users and AI systems. The architecture prioritizes:
- Context preservation across document chunks
- Intelligent handling of redacted content
- Hybrid search combining keyword and semantic approaches
- RAG (Retrieval Augmented Generation) readiness for AI integration

---

## Phase 1: Enhanced Full-Text Search with Redaction Handling

### 1.1 SQLite FTS5 Integration

**Objective:** Enable fast full-text search over 64,000+ documents without additional infrastructure.

**Database Schema Extensions:**

```sql
-- Full-text search virtual table
CREATE VIRTUAL TABLE documents_fts USING fts5(
    efta_number,
    full_text,
    cleaned_text,          -- Text with redaction markers normalized
    content='documents',
    content_rowid='document_id',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER documents_fts_insert AFTER INSERT ON documents BEGIN
    INSERT INTO documents_fts(rowid, efta_number, full_text, cleaned_text)
    VALUES (new.document_id, new.efta_number, new.full_text, new.cleaned_text);
END;

CREATE TRIGGER documents_fts_delete AFTER DELETE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, efta_number, full_text, cleaned_text)
    VALUES ('delete', old.document_id, old.efta_number, old.full_text, old.cleaned_text);
END;

CREATE TRIGGER documents_fts_update AFTER UPDATE ON documents BEGIN
    INSERT INTO documents_fts(documents_fts, rowid, efta_number, full_text, cleaned_text)
    VALUES ('delete', old.document_id, old.efta_number, old.full_text, old.cleaned_text);
    INSERT INTO documents_fts(rowid, efta_number, full_text, cleaned_text)
    VALUES (new.document_id, new.efta_number, new.full_text, new.cleaned_text);
END;
```

### 1.2 Redaction Normalization

**Problem:** Documents contain various redaction markers that disrupt search:
- `[REDACTED]`, `[SEALED]`, `[CONFIDENTIAL]`
- `████████` (Unicode block characters)
- `XXXXX`, `*****`
- OCR artifacts from blacked-out text

**Solution - Text Cleaning Pipeline:**

```python
# services/text_cleaner.py

import re
from typing import Tuple

class TextCleaner:
    """Cleans and normalizes document text for search optimization."""

    REDACTION_PATTERNS = [
        (r'\[REDACTED\]', '[R]'),
        (r'\[SEALED\]', '[R]'),
        (r'\[CONFIDENTIAL\]', '[R]'),
        (r'█+', '[R]'),
        (r'X{5,}', '[R]'),
        (r'\*{5,}', '[R]'),
        (r'_{10,}', '[R]'),
        (r'\[.*?REDACTED.*?\]', '[R]'),
    ]

    def clean_for_search(self, text: str) -> Tuple[str, dict]:
        """
        Clean text for search indexing.

        Returns:
            Tuple of (cleaned_text, metadata)
            metadata includes redaction_count, redaction_positions
        """
        cleaned = text
        redaction_count = 0
        redaction_positions = []

        for pattern, replacement in self.REDACTION_PATTERNS:
            matches = list(re.finditer(pattern, cleaned, re.IGNORECASE))
            redaction_count += len(matches)
            for m in matches:
                redaction_positions.append({
                    'start': m.start(),
                    'end': m.end(),
                    'original': m.group()
                })
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        # Collapse multiple [R] markers
        cleaned = re.sub(r'(\[R\]\s*)+', '[R] ', cleaned)

        # Normalize whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned, {
            'redaction_count': redaction_count,
            'redaction_positions': redaction_positions
        }

    def extract_searchable_context(self, text: str, window: int = 200) -> list:
        """
        Extract contextual snippets around non-redacted content.
        Useful for building better search results.
        """
        # Split on redaction markers
        segments = re.split(r'\[R\]', text)
        contexts = []

        for i, segment in enumerate(segments):
            if len(segment.strip()) > 50:  # Meaningful content
                contexts.append({
                    'position': i,
                    'text': segment.strip()[:window],
                    'has_context_before': i > 0,
                    'has_context_after': i < len(segments) - 1
                })

        return contexts
```

### 1.3 Search API Endpoints

**Backend Implementation (ASP.NET Core):**

```csharp
// Controllers/SearchController.cs

[ApiController]
[Route("api/[controller]")]
public class SearchController : ControllerBase
{
    private readonly ISearchService _searchService;

    [HttpGet]
    public async Task<ActionResult<SearchResults>> Search(
        [FromQuery] string q,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        [FromQuery] bool includeRedacted = true)
    {
        var results = await _searchService.SearchAsync(new SearchQuery
        {
            Query = q,
            Page = page,
            PageSize = pageSize,
            DateFrom = dateFrom,
            DateTo = dateTo,
            IncludeRedactedContent = includeRedacted
        });

        return Ok(results);
    }

    [HttpGet("suggest")]
    public async Task<ActionResult<List<string>>> Suggest([FromQuery] string q)
    {
        var suggestions = await _searchService.GetSuggestionsAsync(q);
        return Ok(suggestions);
    }
}
```

**Files to Create/Modify:**
- `epstein_extraction/services/text_cleaner.py` - Text cleaning utilities
- `epstein_extraction/migrations/add_fts5.py` - FTS5 setup migration
- `dashboard/backend/src/EpsteinDashboard.Application/Services/SearchService.cs`
- `dashboard/backend/src/EpsteinDashboard.Api/Controllers/SearchController.cs`
- `dashboard/frontend/src/pages/SearchPage.tsx`

---

## Phase 2: Document Chunking for Context Preservation

### 2.1 Chunking Strategy

**Problem:** Full documents are too large for:
- Vector embeddings (token limits)
- AI context windows
- Meaningful search result snippets

**Solution - Semantic Chunking with Overlap:**

```python
# services/document_chunker.py

from dataclasses import dataclass
from typing import List, Optional
import re

@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: int
    efta_number: str
    chunk_index: int
    text: str
    start_char: int
    end_char: int
    page_number: Optional[int]
    has_redaction: bool
    preceding_context: str  # Last 100 chars of previous chunk
    following_context: str  # First 100 chars of next chunk

class SemanticChunker:
    """
    Chunks documents while preserving semantic boundaries.
    Uses paragraph/sentence boundaries when possible.
    """

    def __init__(
        self,
        target_chunk_size: int = 1000,  # Target chars per chunk
        overlap_size: int = 100,         # Overlap between chunks
        min_chunk_size: int = 200,       # Don't create tiny chunks
    ):
        self.target_size = target_chunk_size
        self.overlap_size = overlap_size
        self.min_size = min_chunk_size

    def chunk_document(
        self,
        document_id: int,
        efta_number: str,
        text: str,
        page_boundaries: Optional[List[int]] = None
    ) -> List[DocumentChunk]:
        """
        Split document into overlapping semantic chunks.

        Args:
            document_id: Database ID
            efta_number: Document identifier
            text: Full document text
            page_boundaries: Optional list of character positions where pages start
        """
        chunks = []

        # Split into paragraphs first
        paragraphs = self._split_into_paragraphs(text)

        current_chunk_text = ""
        current_start = 0
        chunk_index = 0

        for para_start, para_text in paragraphs:
            # Check if adding this paragraph exceeds target
            if len(current_chunk_text) + len(para_text) > self.target_size:
                if len(current_chunk_text) >= self.min_size:
                    # Save current chunk
                    chunks.append(self._create_chunk(
                        document_id=document_id,
                        efta_number=efta_number,
                        chunk_index=chunk_index,
                        text=current_chunk_text,
                        start_char=current_start,
                        page_boundaries=page_boundaries
                    ))
                    chunk_index += 1

                    # Start new chunk with overlap
                    overlap_text = current_chunk_text[-self.overlap_size:]
                    current_chunk_text = overlap_text + para_text
                    current_start = para_start - len(overlap_text)
                else:
                    current_chunk_text += para_text
            else:
                if not current_chunk_text:
                    current_start = para_start
                current_chunk_text += para_text

        # Don't forget the last chunk
        if current_chunk_text:
            chunks.append(self._create_chunk(
                document_id=document_id,
                efta_number=efta_number,
                chunk_index=chunk_index,
                text=current_chunk_text,
                start_char=current_start,
                page_boundaries=page_boundaries
            ))

        # Add context references
        self._add_context_references(chunks)

        return chunks

    def _split_into_paragraphs(self, text: str) -> List[tuple]:
        """Split text into (position, paragraph) tuples."""
        paragraphs = []
        pattern = r'\n\s*\n'  # Double newline = paragraph break

        last_end = 0
        for match in re.finditer(pattern, text):
            para_text = text[last_end:match.start()]
            if para_text.strip():
                paragraphs.append((last_end, para_text + '\n\n'))
            last_end = match.end()

        # Last paragraph
        if last_end < len(text):
            paragraphs.append((last_end, text[last_end:]))

        return paragraphs

    def _create_chunk(
        self,
        document_id: int,
        efta_number: str,
        chunk_index: int,
        text: str,
        start_char: int,
        page_boundaries: Optional[List[int]]
    ) -> DocumentChunk:
        """Create a DocumentChunk with metadata."""
        # Determine page number
        page_number = None
        if page_boundaries:
            for i, boundary in enumerate(page_boundaries):
                if start_char < boundary:
                    page_number = i
                    break
            else:
                page_number = len(page_boundaries)

        # Check for redactions
        has_redaction = bool(re.search(r'\[R\]|\[REDACTED\]|█', text))

        return DocumentChunk(
            chunk_id=f"{efta_number}_chunk_{chunk_index}",
            document_id=document_id,
            efta_number=efta_number,
            chunk_index=chunk_index,
            text=text,
            start_char=start_char,
            end_char=start_char + len(text),
            page_number=page_number,
            has_redaction=has_redaction,
            preceding_context="",  # Filled in later
            following_context=""   # Filled in later
        )

    def _add_context_references(self, chunks: List[DocumentChunk]):
        """Add preceding/following context to each chunk."""
        for i, chunk in enumerate(chunks):
            if i > 0:
                chunk.preceding_context = chunks[i-1].text[-100:]
            if i < len(chunks) - 1:
                chunk.following_context = chunks[i+1].text[:100]
```

### 2.2 Chunk Storage Schema

```sql
-- New table for document chunks
CREATE TABLE document_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id INTEGER NOT NULL,
    efta_number TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    page_number INTEGER,
    has_redaction BOOLEAN DEFAULT FALSE,
    preceding_context TEXT,
    following_context TEXT,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (document_id) REFERENCES documents(document_id)
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_efta ON document_chunks(efta_number);
CREATE INDEX idx_chunks_page ON document_chunks(page_number);
CREATE INDEX idx_chunks_redaction ON document_chunks(has_redaction);

-- FTS5 for chunk search
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    chunk_id,
    chunk_text,
    content='document_chunks',
    content_rowid='rowid',
    tokenize='porter unicode61'
);
```

**Files to Create:**
- `epstein_extraction/services/document_chunker.py`
- `epstein_extraction/models/chunk.py` - SQLAlchemy model
- `epstein_extraction/migrations/add_chunks_table.py`
- `epstein_extraction/run_chunking.py` - Batch processing script

---

## Phase 3: Vector Embeddings for Semantic Search

### 3.1 Embedding Generation

**Technology Choice:** Use local embeddings initially (no API costs), with option to upgrade.

| Option | Pros | Cons |
|--------|------|------|
| `sentence-transformers` (local) | Free, fast, no API | Slightly lower quality |
| OpenAI `text-embedding-3-small` | High quality | $0.02/1M tokens |
| Anthropic | Integrated with Claude | May need API setup |

**Recommended: Start with `all-MiniLM-L6-v2` (384 dimensions), upgrade later if needed.**

```python
# services/embedding_service.py

from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    """Generate and manage vector embeddings for document chunks."""

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        return self.model.encode(text, convert_to_numpy=True)

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for multiple texts efficiently."""
        return self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )

    def embed_with_context(self, chunk_text: str, preceding: str, following: str) -> np.ndarray:
        """
        Generate embedding with surrounding context for better semantic understanding.
        This helps preserve document flow in embeddings.
        """
        contextual_text = f"{preceding} {chunk_text} {following}".strip()
        return self.embed_text(contextual_text)
```

### 3.2 Vector Storage Options

**Option A: SQLite with numpy (Simple, No Dependencies)**

```python
# Store embeddings as BLOB in SQLite
import sqlite3
import numpy as np

def store_embedding(conn, chunk_id: str, embedding: np.ndarray):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chunk_embeddings (chunk_id, embedding) VALUES (?, ?)",
        (chunk_id, embedding.tobytes())
    )
    conn.commit()

def search_similar(conn, query_embedding: np.ndarray, limit: int = 10):
    cursor = conn.cursor()
    cursor.execute("SELECT chunk_id, embedding FROM chunk_embeddings")

    results = []
    for chunk_id, blob in cursor.fetchall():
        stored = np.frombuffer(blob, dtype=np.float32)
        similarity = np.dot(query_embedding, stored)
        results.append((chunk_id, similarity))

    return sorted(results, key=lambda x: x[1], reverse=True)[:limit]
```

**Option B: ChromaDB (Recommended for Production)**

```python
# services/vector_store.py

import chromadb
from chromadb.config import Settings

class VectorStore:
    """Manage vector storage and similarity search."""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="epstein_documents",
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[dict]
    ):
        """Add chunks with embeddings to the vector store."""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 10,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None
    ):
        """Search for similar chunks."""
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"]
        )
```

### 3.3 Embedding Schema Extension

```sql
-- For SQLite blob storage
CREATE TABLE chunk_embeddings (
    chunk_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (chunk_id) REFERENCES document_chunks(chunk_id)
);
```

**Files to Create:**
- `epstein_extraction/services/embedding_service.py`
- `epstein_extraction/services/vector_store.py`
- `epstein_extraction/run_embeddings.py` - Batch embedding generation

---

## Phase 4: Hybrid Search Implementation

### 4.1 Combining Keyword and Semantic Search

```python
# services/hybrid_search.py

from dataclasses import dataclass
from typing import List, Optional
from .embedding_service import EmbeddingService
from .vector_store import VectorStore

@dataclass
class SearchResult:
    chunk_id: str
    document_id: int
    efta_number: str
    text: str
    score: float
    match_type: str  # 'keyword', 'semantic', 'hybrid'
    highlights: List[str]
    page_number: Optional[int]

class HybridSearchService:
    """
    Combines FTS5 keyword search with vector similarity search.
    Uses Reciprocal Rank Fusion (RRF) for result merging.
    """

    def __init__(
        self,
        db_session,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        keyword_weight: float = 0.5,
        semantic_weight: float = 0.5
    ):
        self.session = db_session
        self.embedder = embedding_service
        self.vectors = vector_store
        self.keyword_weight = keyword_weight
        self.semantic_weight = semantic_weight

    def search(
        self,
        query: str,
        limit: int = 20,
        exclude_redacted: bool = False,
        document_filter: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining keyword and semantic approaches.

        Args:
            query: Search query string
            limit: Maximum results to return
            exclude_redacted: Skip chunks with redactions
            document_filter: Optional list of EFTA numbers to search within
        """
        # Get keyword results from FTS5
        keyword_results = self._keyword_search(query, limit * 2)

        # Get semantic results from vector store
        query_embedding = self.embedder.embed_text(query)

        where_filter = {}
        if exclude_redacted:
            where_filter["has_redaction"] = False
        if document_filter:
            where_filter["efta_number"] = {"$in": document_filter}

        semantic_results = self.vectors.search(
            query_embedding=query_embedding.tolist(),
            n_results=limit * 2,
            where=where_filter if where_filter else None
        )

        # Merge using Reciprocal Rank Fusion
        merged = self._reciprocal_rank_fusion(
            keyword_results,
            semantic_results,
            k=60  # RRF constant
        )

        return merged[:limit]

    def _keyword_search(self, query: str, limit: int) -> List[tuple]:
        """Execute FTS5 search."""
        # Escape special FTS5 characters
        safe_query = query.replace('"', '""')

        sql = """
            SELECT
                dc.chunk_id,
                dc.document_id,
                dc.efta_number,
                dc.chunk_text,
                dc.page_number,
                dc.has_redaction,
                bm25(chunks_fts) as score
            FROM chunks_fts cf
            JOIN document_chunks dc ON cf.rowid = dc.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """

        result = self.session.execute(sql, (f'"{safe_query}"', limit))
        return list(result)

    def _reciprocal_rank_fusion(
        self,
        keyword_results: List,
        semantic_results: dict,
        k: int = 60
    ) -> List[SearchResult]:
        """
        Merge results using Reciprocal Rank Fusion.
        RRF(d) = Σ 1/(k + rank(d))
        """
        scores = {}

        # Score keyword results
        for rank, row in enumerate(keyword_results, 1):
            chunk_id = row[0]
            rrf_score = self.keyword_weight / (k + rank)
            scores[chunk_id] = {
                'rrf': rrf_score,
                'keyword_rank': rank,
                'semantic_rank': None,
                'data': row
            }

        # Score semantic results
        if semantic_results['ids'] and semantic_results['ids'][0]:
            for rank, chunk_id in enumerate(semantic_results['ids'][0], 1):
                rrf_score = self.semantic_weight / (k + rank)

                if chunk_id in scores:
                    scores[chunk_id]['rrf'] += rrf_score
                    scores[chunk_id]['semantic_rank'] = rank
                else:
                    idx = rank - 1
                    scores[chunk_id] = {
                        'rrf': rrf_score,
                        'keyword_rank': None,
                        'semantic_rank': rank,
                        'data': {
                            'chunk_id': chunk_id,
                            'text': semantic_results['documents'][0][idx],
                            'metadata': semantic_results['metadatas'][0][idx]
                        }
                    }

        # Sort by RRF score and build results
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]['rrf'], reverse=True)

        results = []
        for chunk_id, score_data in sorted_scores:
            # Determine match type
            if score_data['keyword_rank'] and score_data['semantic_rank']:
                match_type = 'hybrid'
            elif score_data['keyword_rank']:
                match_type = 'keyword'
            else:
                match_type = 'semantic'

            data = score_data['data']

            results.append(SearchResult(
                chunk_id=chunk_id,
                document_id=data.get('document_id') or data.get('metadata', {}).get('document_id'),
                efta_number=data.get('efta_number') or data.get('metadata', {}).get('efta_number'),
                text=data.get('chunk_text') or data.get('text', ''),
                score=score_data['rrf'],
                match_type=match_type,
                highlights=[],  # TODO: Add highlighting
                page_number=data.get('page_number') or data.get('metadata', {}).get('page_number')
            ))

        return results
```

**Files to Create:**
- `epstein_extraction/services/hybrid_search.py`
- `dashboard/backend/src/EpsteinDashboard.Application/Services/HybridSearchService.cs`

---

## Phase 5: RAG Pipeline for AI Integration

### 5.1 Context Builder for AI Queries

```python
# services/rag_context.py

from typing import List, Optional
from dataclasses import dataclass

@dataclass
class RAGContext:
    """Context package for AI consumption."""
    query: str
    retrieved_chunks: List[dict]
    total_tokens: int
    source_documents: List[str]
    has_redacted_content: bool
    context_string: str

class RAGContextBuilder:
    """
    Builds optimized context for AI models from search results.
    """

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.chars_per_token = 4  # Rough estimate

    def build_context(
        self,
        query: str,
        search_results: List,
        include_metadata: bool = True
    ) -> RAGContext:
        """
        Build a context string from search results for AI consumption.

        Includes:
        - Document source attribution
        - Redaction warnings
        - Contextual headers
        """
        chunks = []
        source_docs = set()
        has_redacted = False
        total_chars = 0
        max_chars = self.max_tokens * self.chars_per_token

        for result in search_results:
            if total_chars >= max_chars:
                break

            chunk_text = result.text
            total_chars += len(chunk_text)

            source_docs.add(result.efta_number)
            if result.has_redaction:
                has_redacted = True

            chunk_data = {
                'efta_number': result.efta_number,
                'page': result.page_number,
                'text': chunk_text,
                'score': result.score
            }

            if include_metadata:
                chunk_data['chunk_id'] = result.chunk_id

            chunks.append(chunk_data)

        # Build context string
        context_parts = []

        if has_redacted:
            context_parts.append(
                "NOTE: Some retrieved documents contain redacted content marked as [R]. "
                "This redacted content may affect the completeness of the information."
            )

        for i, chunk in enumerate(chunks, 1):
            header = f"[Source: {chunk['efta_number']}"
            if chunk['page']:
                header += f", Page {chunk['page']}"
            header += "]"

            context_parts.append(f"{header}\n{chunk['text']}")

        context_string = "\n\n---\n\n".join(context_parts)

        return RAGContext(
            query=query,
            retrieved_chunks=chunks,
            total_tokens=total_chars // self.chars_per_token,
            source_documents=list(source_docs),
            has_redacted_content=has_redacted,
            context_string=context_string
        )
```

### 5.2 AI Query Interface

```python
# services/ai_query.py

from typing import Optional
import anthropic

class AIQueryService:
    """
    Handles AI-powered queries using RAG.
    """

    def __init__(
        self,
        hybrid_search,
        context_builder,
        anthropic_api_key: Optional[str] = None
    ):
        self.search = hybrid_search
        self.context_builder = context_builder
        self.client = anthropic.Anthropic(api_key=anthropic_api_key) if anthropic_api_key else None

    async def query(
        self,
        question: str,
        search_limit: int = 10,
        model: str = "claude-sonnet-4-20250514"
    ) -> dict:
        """
        Answer a question using retrieved document context.
        """
        # Search for relevant chunks
        search_results = self.search.search(question, limit=search_limit)

        # Build context
        context = self.context_builder.build_context(question, search_results)

        if not self.client:
            # Return context only if no API key
            return {
                'answer': None,
                'context': context,
                'sources': context.source_documents,
                'message': 'AI response unavailable - no API key configured'
            }

        # Generate AI response
        system_prompt = """You are an expert analyst reviewing documents from the Epstein case files.
        Answer questions based solely on the provided document context.
        Always cite your sources using the document identifiers provided.
        If the information is not in the provided context, say so clearly.
        Note any redacted content that may affect your answer."""

        response = self.client.messages.create(
            model=model,
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"Context from Epstein documents:\n\n{context.context_string}\n\nQuestion: {question}"
                }
            ]
        )

        return {
            'answer': response.content[0].text,
            'context': context,
            'sources': context.source_documents,
            'tokens_used': {
                'input': response.usage.input_tokens,
                'output': response.usage.output_tokens
            }
        }
```

**Files to Create:**
- `epstein_extraction/services/rag_context.py`
- `epstein_extraction/services/ai_query.py`
- `dashboard/backend/src/EpsteinDashboard.Api/Controllers/AIQueryController.cs`
- `dashboard/frontend/src/pages/AIQueryPage.tsx`

---

## Implementation Phases Summary

### Phase 1: Full-Text Search (3-5 days)
1. Add `cleaned_text` column to documents table
2. Create text cleaner service
3. Create FTS5 virtual table and triggers
4. Populate FTS with existing documents
5. Add basic search API endpoint
6. Create search UI component

### Phase 2: Document Chunking (2-3 days)
1. Create chunks table and model
2. Implement semantic chunker
3. Run batch chunking for all documents
4. Create chunk FTS5 table

### Phase 3: Vector Embeddings (3-4 days)
1. Install sentence-transformers
2. Set up ChromaDB
3. Create embedding service
4. Batch embed all chunks
5. Add semantic search endpoint

### Phase 4: Hybrid Search (2-3 days)
1. Implement RRF merging
2. Create hybrid search service
3. Add search result highlighting
4. Update search UI with advanced options

### Phase 5: RAG Pipeline (3-4 days)
1. Build context builder
2. Add Anthropic API integration
3. Create AI query endpoint
4. Build AI query UI
5. Add source citation display

---

## Dependencies to Install

```bash
# Python
pip install sentence-transformers chromadb anthropic tiktoken

# Node (for frontend)
npm install @tanstack/react-query lucide-react
```

---

## File Structure

```
epstein_extraction/
├── services/
│   ├── text_cleaner.py      # Phase 1
│   ├── document_chunker.py  # Phase 2
│   ├── embedding_service.py # Phase 3
│   ├── vector_store.py      # Phase 3
│   ├── hybrid_search.py     # Phase 4
│   ├── rag_context.py       # Phase 5
│   └── ai_query.py          # Phase 5
├── migrations/
│   ├── add_fts5.py
│   ├── add_chunks_table.py
│   └── add_embeddings.py
├── run_text_cleaning.py
├── run_chunking.py
└── run_embeddings.py

dashboard/
├── backend/src/EpsteinDashboard.Api/Controllers/
│   ├── SearchController.cs
│   └── AIQueryController.cs
└── frontend/src/pages/
    ├── SearchPage.tsx
    └── AIQueryPage.tsx
```

---

## Implementation Status

### Phase 1: Full-Text Search - CODE COMPLETE
**Files Created:**
- `epstein_extraction/services/text_cleaner.py`
- `epstein_extraction/migrations/001_add_fts5_search.py`
- `epstein_extraction/run_text_cleaning.py`
- Backend: Updated `Fts5SearchProvider.cs` with date/type filtering
- Backend: Updated `SearchResult.cs` with PageCount, IsRedacted
- Frontend: Updated `SearchPage.tsx` with tabs, filters, pagination

**To Run After Dataset 10 Completes:**
```bash
cd epstein_extraction
python migrations/001_add_fts5_search.py up
python run_text_cleaning.py
```

### Phase 2: Document Chunking - CODE COMPLETE
**Files Created:**
- `epstein_extraction/services/document_chunker.py`
- `epstein_extraction/migrations/002_add_chunks_table.py`
- `epstein_extraction/run_chunking.py`
- Backend: `ChunkSearchProvider.cs`, `IChunkSearchService.cs`
- Backend: `ChunkSearchResult.cs`, `ChunkSearchResultDto.cs`
- Frontend: `search.ts` types, `search.ts` API endpoints

**To Run After Phase 1:**
```bash
python migrations/002_add_chunks_table.py up
python run_chunking.py
```

### Phase 3: Vector Embeddings - CODE COMPLETE
**Files Created:**
- `epstein_extraction/services/embedding_service.py`
- `epstein_extraction/migrations/003_add_chunk_embeddings.py`
- `epstein_extraction/run_embeddings.py`

**To Run After Phase 2:**
```bash
pip install sentence-transformers
python migrations/003_add_chunk_embeddings.py up
python run_embeddings.py
```

### Phase 4: Hybrid Search - PLANNED
Waiting for Phases 1-3 to be validated.

### Phase 5: RAG Pipeline - PLANNED
Waiting for Phase 4 completion.

---

## Notes

- **Dataset 10 still loading** - schema migrations require exclusive database access
- Vector embedding generation will take significant time (~1-2 hours for 64k documents)
- Consider running embedding generation overnight
- ChromaDB storage will require ~2-5GB for embeddings (using SQLite blob storage for now)

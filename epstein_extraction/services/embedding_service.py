"""
Embedding service for semantic search and RAG.
Generates vector embeddings for document chunks using sentence-transformers.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
import hashlib
import struct
import sqlite3
from pathlib import Path

# Try to import sentence-transformers (optional dependency)
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None


@dataclass
class EmbeddingResult:
    """Result of embedding a text."""
    text: str
    embedding: np.ndarray
    model_name: str
    dimension: int

    def to_bytes(self) -> bytes:
        """Convert embedding to bytes for storage."""
        return self.embedding.astype(np.float32).tobytes()

    @staticmethod
    def from_bytes(data: bytes, dimension: int) -> np.ndarray:
        """Reconstruct embedding from bytes."""
        return np.frombuffer(data, dtype=np.float32).reshape(dimension)


class EmbeddingService:
    """
    Service for generating and managing text embeddings.
    Uses sentence-transformers for local embedding generation.
    """

    # Recommended models for different use cases
    MODELS = {
        'default': 'all-MiniLM-L6-v2',       # Fast, good quality, 384 dims
        'quality': 'all-mpnet-base-v2',       # Higher quality, 768 dims
        'multilingual': 'paraphrase-multilingual-MiniLM-L12-v2',  # Multi-language
        'legal': 'all-MiniLM-L6-v2',          # Good for legal text
    }

    def __init__(
        self,
        model_name: str = 'default',
        cache_dir: Optional[Path] = None,
        batch_size: int = 32,
    ):
        """
        Initialize the embedding service.

        Args:
            model_name: Model name or key from MODELS dict
            cache_dir: Directory to cache model files
            batch_size: Batch size for embedding generation
        """
        if not EMBEDDINGS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        # Resolve model name
        self.model_name = self.MODELS.get(model_name, model_name)
        self.batch_size = batch_size

        # Load model
        self.model = SentenceTransformer(
            self.model_name,
            cache_folder=str(cache_dir) if cache_dir else None,
        )

        # Get embedding dimension
        self.dimension = self.model.get_sentence_embedding_dimension()

    def embed_text(self, text: str) -> EmbeddingResult:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResult with the embedding vector
        """
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model_name=self.model_name,
            dimension=self.dimension,
        )

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of EmbeddingResult objects
        """
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 100,
        )

        return [
            EmbeddingResult(
                text=text,
                embedding=emb,
                model_name=self.model_name,
                dimension=self.dimension,
            )
            for text, emb in zip(texts, embeddings)
        ]

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Compute cosine similarity between two embeddings.
        Assumes embeddings are already normalized.
        """
        return float(np.dot(embedding1, embedding2))

    def search_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: List[np.ndarray],
        top_k: int = 10,
    ) -> List[Tuple[int, float]]:
        """
        Find most similar embeddings to a query.

        Args:
            query_embedding: Query vector
            candidate_embeddings: List of candidate vectors
            top_k: Number of results to return

        Returns:
            List of (index, similarity_score) tuples, sorted by similarity
        """
        if not candidate_embeddings:
            return []

        # Stack candidates into matrix
        candidates = np.vstack(candidate_embeddings)

        # Compute similarities (dot product for normalized vectors)
        similarities = np.dot(candidates, query_embedding)

        # Get top-k indices
        if top_k >= len(similarities):
            top_indices = np.argsort(similarities)[::-1]
        else:
            top_indices = np.argpartition(similarities, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

        return [(int(idx), float(similarities[idx])) for idx in top_indices]


class EmbeddingCache:
    """
    SQLite-based cache for embeddings.
    Avoids recomputing embeddings for previously processed chunks.
    """

    def __init__(self, db_path: Path, model_name: str, dimension: int):
        """
        Initialize the embedding cache.

        Args:
            db_path: Path to SQLite database
            model_name: Name of the embedding model
            dimension: Embedding dimension
        """
        self.db_path = db_path
        self.model_name = model_name
        self.dimension = dimension
        self._ensure_table()

    def _ensure_table(self):
        """Create cache table if it doesn't exist."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embedding_cache (
                    text_hash TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_model ON embedding_cache(model_name)"
            )
            conn.commit()
        finally:
            conn.close()

    def _hash_text(self, text: str) -> str:
        """Generate hash for text."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:32]

    def get(self, text: str) -> Optional[np.ndarray]:
        """Get cached embedding for text."""
        text_hash = self._hash_text(text)

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT embedding FROM embedding_cache WHERE text_hash = ? AND model_name = ?",
                (text_hash, self.model_name)
            )
            row = cursor.fetchone()
            if row:
                return EmbeddingResult.from_bytes(row[0], self.dimension)
            return None
        finally:
            conn.close()

    def put(self, text: str, embedding: np.ndarray):
        """Cache an embedding."""
        text_hash = self._hash_text(text)
        embedding_bytes = embedding.astype(np.float32).tobytes()

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT OR REPLACE INTO embedding_cache
                   (text_hash, model_name, embedding) VALUES (?, ?, ?)""",
                (text_hash, self.model_name, embedding_bytes)
            )
            conn.commit()
        finally:
            conn.close()

    def get_batch(self, texts: List[str]) -> Tuple[List[np.ndarray], List[int]]:
        """
        Get cached embeddings for multiple texts.

        Returns:
            Tuple of (cached_embeddings, missing_indices)
        """
        results = [None] * len(texts)
        missing = []

        conn = sqlite3.connect(str(self.db_path))
        try:
            for i, text in enumerate(texts):
                text_hash = self._hash_text(text)
                cursor = conn.execute(
                    "SELECT embedding FROM embedding_cache WHERE text_hash = ? AND model_name = ?",
                    (text_hash, self.model_name)
                )
                row = cursor.fetchone()
                if row:
                    results[i] = EmbeddingResult.from_bytes(row[0], self.dimension)
                else:
                    missing.append(i)
        finally:
            conn.close()

        return results, missing

    def put_batch(self, texts: List[str], embeddings: List[np.ndarray]):
        """Cache multiple embeddings."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            for text, embedding in zip(texts, embeddings):
                text_hash = self._hash_text(text)
                embedding_bytes = embedding.astype(np.float32).tobytes()
                conn.execute(
                    """INSERT OR REPLACE INTO embedding_cache
                       (text_hash, model_name, embedding) VALUES (?, ?, ?)""",
                    (text_hash, self.model_name, embedding_bytes)
                )
            conn.commit()
        finally:
            conn.close()


def check_embedding_support() -> dict:
    """
    Check if embedding support is available.

    Returns:
        Dict with availability info and installation instructions
    """
    info = {
        'available': EMBEDDINGS_AVAILABLE,
        'models': EmbeddingService.MODELS if EMBEDDINGS_AVAILABLE else {},
    }

    if not EMBEDDINGS_AVAILABLE:
        info['install_command'] = 'pip install sentence-transformers'
        info['message'] = (
            'sentence-transformers not installed. '
            'Vector search and RAG features require this library.'
        )

    return info

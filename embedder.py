"""
ProteusP Embedding Pipeline
BAAI/bge-m3 임베딩 모델 기반 텍스트 → 벡터 변환
태블릿 CPU 환경에 최적화 (batch, caching, fallback)
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from tqdm import tqdm

from proteusp.config import ProteusPConfig, get_config


class EmbeddingCache:
    """Simple disk-based embedding cache for deduplication."""

    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir) / "embed_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._mem_cache: Dict[str, List[float]] = {}
        self.hits = 0
        self.misses = 0

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def get(self, text: str) -> Optional[List[float]]:
        key = self._hash(text)
        # Check memory first
        if key in self._mem_cache:
            self.hits += 1
            return self._mem_cache[key]
        # Check disk
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                vec = json.loads(cache_file.read_text())
                self._mem_cache[key] = vec
                self.hits += 1
                return vec
            except (json.JSONDecodeError, IOError):
                pass
        self.misses += 1
        return None

    def put(self, text: str, vector: List[float]) -> None:
        key = self._hash(text)
        self._mem_cache[key] = vector
        cache_file = self.cache_dir / f"{key}.json"
        try:
            cache_file.write_text(json.dumps(vector))
        except IOError:
            pass

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "cache_size": len(self._mem_cache)}


class EmbeddingModel:
    """
    SentenceTransformer 기반 임베딩 모델 래퍼.
    CPU 태블릿 환경에 맞게 설계: 배치 처리, 캐싱, 지연 로딩.
    """

    def __init__(self, config: Optional[ProteusPConfig] = None):
        self.config = config or get_config()
        self._model = None
        self._model_name = self.config.embedding_model
        self._device = self.config.embedding_device
        self._batch_size = self.config.embedding_batch_size
        self._normalize = self.config.embedding_normalize
        self.dimension: int = 1024  # bge-m3 default; updated after load

        # Cache directory alongside vector DB
        cache_dir = Path(self.config.vector_db_path).parent
        self.cache = EmbeddingCache(str(cache_dir))

    def load(self) -> None:
        """Lazy-load the embedding model."""
        if self._model is not None:
            return

        print(f"Loading embedding model: {self._model_name} on {self._device}...")
        t0 = time.time()

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self._model_name,
                device=self._device,
                trust_remote_code=True,
            )
            # Get embedding dimension
            test_emb = self._model.encode(["test"], normalize_embeddings=self._normalize)
            self.dimension = test_emb.shape[1]
            print(f"Model loaded in {time.time()-t0:.1f}s | dim={self.dimension}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{self._model_name}': {e}\n"
                f"Try: pip install sentence-transformers"
            ) from e

    @property
    def model(self):
        if self._model is None:
            self.load()
        return self._model

    def encode(self, texts: List[str], show_progress: bool = True) -> np.ndarray:
        """
        Encode a list of texts into embeddings.
        Uses cache for deduplication and batches for memory efficiency.
        """
        if not texts:
            return np.array([], dtype=np.float32)

        self.load()

        # Check cache first
        uncached_texts: List[str] = []
        uncached_indices: List[int] = []
        embeddings_list: List[Optional[List[float]]] = [None] * len(texts)

        for i, text in enumerate(texts):
            cached = self.cache.get(text)
            if cached is not None:
                embeddings_list[i] = cached
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        # Encode uncached texts in batches
        if uncached_texts:
            print(f"Encoding {len(uncached_texts)} uncached texts "
                  f"(cache hits: {self.cache.hits})...")

            iterator = range(0, len(uncached_texts), self._batch_size)
            if show_progress:
                iterator = tqdm(iterator, desc="Embedding")

            for start in iterator:
                batch = uncached_texts[start:start + self._batch_size]
                batch_embeddings = self.model.encode(
                    batch,
                    normalize_embeddings=self._normalize,
                    show_progress_bar=False,
                )
                for j, emb in enumerate(batch_embeddings):
                    actual_idx = uncached_indices[start + j]
                    vec = emb.tolist() if hasattr(emb, "tolist") else list(emb)
                    embeddings_list[actual_idx] = vec
                    self.cache.put(uncached_texts[start + j], vec)

        # Flatten to numpy array
        valid_embeddings = [e for e in embeddings_list if e is not None]
        if not valid_embeddings:
            return np.array([], dtype=np.float32)

        return np.array(valid_embeddings, dtype=np.float32)

    def encode_one(self, text: str) -> np.ndarray:
        """Encode a single text string."""
        result = self.encode([text], show_progress=False)
        return result[0] if len(result) > 0 else np.array([], dtype=np.float32)


# Singleton
_embedder: Optional[EmbeddingModel] = None


def get_embedder(config: Optional[ProteusPConfig] = None) -> EmbeddingModel:
    """Get or create the global embedder singleton."""
    global _embedder
    if _embedder is None:
        _embedder = EmbeddingModel(config or get_config())
    return _embedder


def reset_embedder() -> None:
    """Reset embedder singleton."""
    global _embedder
    _embedder = None

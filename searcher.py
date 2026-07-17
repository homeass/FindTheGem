"""
ProteusP Hybrid Search & Reranker
BM25 키워드 검색 + Vector 의미 검색 + FlashRank 재정렬
"""

import time
from typing import Any, Dict, List, Optional

import numpy as np

from proteusp.config import ProteusPConfig, get_config
from proteusp.embedder import EmbeddingModel, get_embedder
from proteusp.vectorstore import VectorStore, get_vector_store


class BM25Index:
    """
    BM25 키워드 검색 인덱스 (경량, 인메모리).
    랭크-BM25 라이브러리 기반.
    """

    def __init__(self, language: str = "korean"):
        self._bm25 = None
        self._documents: List[str] = []
        self._doc_ids: List[str] = []
        self._initialized = False
        self._language = language

    def build(self, documents: List[str], doc_ids: List[str]) -> None:
        """Build BM25 index from documents."""
        try:
            from rank_bm25 import BM25Okapi
            import re

            # Simple Korean-friendly tokenization
            tokenized = []
            for doc in documents:
                # Split on whitespace and punctuation, preserve Korean
                tokens = re.findall(r"[가-힣a-zA-Z0-9_]+", doc.lower())
                tokenized.append(tokens)

            self._bm25 = BM25Okapi(tokenized)
            self._documents = documents
            self._doc_ids = doc_ids
            self._initialized = True
            print(f"BM25 index built with {len(documents)} documents")
        except Exception as e:
            print(f"Warning: BM25 initialization failed: {e}")
            self._initialized = False

    def search(self, query: str, top_k: int = 20) -> List[dict]:
        """Search using BM25 scoring."""
        if not self._initialized or not self._bm25:
            return []

        import re
        query_tokens = re.findall(r"[가-힣a-zA-Z0-9_]+", query.lower())
        scores = self._bm25.get_scores(query_tokens)

        # Get top-k results
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "id": self._doc_ids[idx],
                    "document": self._documents[idx],
                    "bm25_score": float(scores[idx]),
                    "score": float(scores[idx]),
                })
        return results


class Reranker:
    """
    FlashRank 기반 재정렬 (Reranking).
    검색된 결과의 순위를 질문과의 실제 관련성에 따라 재조정.
    """

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or "ms-marco-MiniLM-L-12-v2"
        self._ranker = None
        self._initialized = False

    def load(self) -> None:
        """Lazy-load the reranker model."""
        if self._initialized:
            return
        try:
            from flashrank import Ranker
            self._ranker = Ranker(model_name=self._model_name)
            self._initialized = True
            print(f"Reranker loaded: {self._model_name}")
        except Exception as e:
            print(f"Warning: FlashRank reranker unavailable: {e}")
            print("Falling back: no reranking will be applied")
            self._initialized = False

    def rerank(
        self,
        query: str,
        passages: List[dict],
        top_k: int = 5,
    ) -> List[dict]:
        """Rerank passages by relevance to query."""
        if not passages:
            return []

        self.load()
        if not self._initialized:
            # Fallback: return original order
            return passages[:top_k]

        try:
            # FlashRank expects list of dicts with 'id' and 'text'
            flashrank_passages = [
                {"id": p["id"], "text": p["document"][:512]}  # truncate for speed
                for p in passages
            ]

            results = self._ranker.rerank(query, flashrank_passages)
            ranked = []
            for r in results[:top_k]:
                # Map back to original passage
                for p in passages:
                    if p["id"] == r["id"]:
                        p["rerank_score"] = r["score"]
                        p["score"] = r["score"]
                        ranked.append(p)
                        break
            return ranked
        except Exception as e:
            print(f"Warning: Reranking failed: {e}")
            return passages[:top_k]


class HybridSearcher:
    """
    BM25 + Vector 하이브리드 검색 + Reranker.
    두 검색 결과를 정규화하여 결합하고 최종 재정렬.
    """

    def __init__(
        self,
        config: Optional[ProteusPConfig] = None,
        vector_store: Optional[VectorStore] = None,
        embedder: Optional[EmbeddingModel] = None,
    ):
        self.config = config or get_config()
        self.vector_store = vector_store or get_vector_store(self.config)
        self.embedder = embedder or get_embedder(self.config)
        self.bm25 = BM25Index()
        self.reranker = Reranker(self.config.reranker_model)
        self._bm25_built = False

    def build_bm25_index(self) -> None:
        """Build BM25 index from all chunks in the vector store."""
        chunks = self.vector_store.get_all_chunks()
        if not chunks:
            print("Warning: No chunks available for BM25 index")
            return

        documents = [c["document"] for c in chunks]
        doc_ids = [c["id"] for c in chunks]
        self.bm25.build(documents, doc_ids)
        self._bm25_built = True

    @property
    def bm25_ready(self) -> bool:
        return self._bm25_built and self.bm25._initialized

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        rerank: bool = True,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute hybrid search:
        1. Vector search (semantic)
        2. BM25 search (keyword)
        3. Normalize & fuse scores
        4. Optional reranking
        """
        t0 = time.time()
        cfg = self.config
        top_k = top_k or cfg.search_rerank_top_k
        hybrid_top_k = cfg.search_hybrid_top_k

        # 1. Vector search
        query_emb = self.embedder.encode_one(query)
        if query_emb.size == 0:
            return {"query": query, "results": [], "time": 0, "count": 0}

        vector_results = self.vector_store.search(
            query_emb.tolist(),
            top_k=hybrid_top_k,
            where_filter=where_filter,
        )

        # 2. BM25 search
        bm25_results = []
        if self.bm25_ready:
            bm25_results = self.bm25.search(query, top_k=hybrid_top_k)

        # 3. Fuse results (Reciprocal Rank Fusion)
        fused = self._fuse_results(vector_results, bm25_results, cfg)

        # 4. Rerank if requested
        if rerank and fused:
            fused = self.reranker.rerank(query, fused, top_k=top_k)

        elapsed = time.time() - t0
        return {
            "query": query,
            "results": fused[:top_k],
            "time": round(elapsed, 2),
            "count": len(fused[:top_k]),
            "vector_count": len(vector_results),
            "bm25_count": len(bm25_results),
        }

    def _fuse_results(
        self,
        vector_results: List[dict],
        bm25_results: List[dict],
        cfg: ProteusPConfig,
    ) -> List[dict]:
        """
        Fuse vector and BM25 results using Reciprocal Rank Fusion (RRF).
        Ensures unique results with combined scores.
        """
        from collections import OrderedDict

        # Normalize scores to 0-1 range
        v_weight = cfg.search_vector_weight
        b_weight = cfg.search_bm25_weight

        # Track seen IDs
        seen: Dict[str, dict] = OrderedDict()

        # Process vector results
        for rank, r in enumerate(vector_results):
            doc_id = r["id"]
            rrf_score = 1.0 / (rank + 60)  # RRF constant k=60
            r["rrf_score"] = rrf_score
            r["vector_rank"] = rank
            r["bm25_rank"] = -1
            r["combined_score"] = rrf_score * v_weight
            seen[doc_id] = r

        # Process BM25 results
        for rank, r in enumerate(bm25_results):
            doc_id = r["id"]
            rrf_score = 1.0 / (rank + 60)
            if doc_id in seen:
                # Already have it - update score
                existing = seen[doc_id]
                existing["rrf_score"] += rrf_score
                existing["bm25_rank"] = rank
                existing["combined_score"] = (
                    existing.get("rrf_score", 0)
                )
            else:
                r["rrf_score"] = rrf_score
                r["vector_rank"] = -1
                r["bm25_rank"] = rank
                r["combined_score"] = rrf_score * b_weight
                seen[doc_id] = r

        # Sort by combined score descending
        fused = list(seen.values())
        fused.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
        return fused


# Singleton
_searcher: Optional[HybridSearcher] = None


def get_searcher(config: Optional[ProteusPConfig] = None) -> HybridSearcher:
    """Get or create global HybridSearcher singleton."""
    global _searcher
    if _searcher is None:
        _searcher = HybridSearcher(config or get_config())
    return _searcher


def reset_searcher() -> None:
    """Reset searcher singleton."""
    global _searcher
    _searcher = None

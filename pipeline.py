"""
ProteusP Main Pipeline Orchestration
전체 RAG 파이프라인 조정: 수집 → 파싱 → 청킹 → 임베딩 → 색인 → 검색 → 생성
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from proteusp.chunker import DocumentChunk, chunk_vault
from proteusp.config import ProteusPConfig, get_config
from proteusp.embedder import EmbeddingModel, get_embedder, reset_embedder
from proteusp.ingestion import VaultWatcher
from proteusp.llm_service import LLMService, get_llm
from proteusp.parser import ObsidianDocument, parse_vault
from proteusp.searcher import HybridSearcher, get_searcher
from proteusp.vectorstore import VectorStore, get_vector_store


@dataclass
class PipelineStatus:
    """Current status of the pipeline."""
    state: str = "idle"  # idle, indexing, searching, error
    last_index_time: Optional[float] = None
    last_index_duration: Optional[float] = None
    total_documents: int = 0
    total_chunks: int = 0
    vector_count: int = 0
    vault_path: str = ""
    ollama_available: bool = False
    ollama_model: str = ""
    errors: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)

    def add_message(self, msg: str) -> None:
        self.messages.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    @property
    def summary(self) -> dict:
        return {
            "state": self.state,
            "documents": self.total_documents,
            "chunks": self.total_chunks,
            "vectors": self.vector_count,
            "last_index": (time.strftime("%Y-%m-%d %H:%M", time.localtime(self.last_index_time))
                          if self.last_index_time else "Never"),
            "ollama": "Connected" if self.ollama_available else "Disconnected",
        }


class ProteusPPipeline:
    """
    Main pipeline orchestrator.
    Manages the complete RAG pipeline lifecycle.
    """

    def __init__(
        self,
        config: Optional[ProteusPConfig] = None,
        auto_init: bool = True,
    ):
        self.config = config or get_config()
        self.status = PipelineStatus(vault_path=self.config.vault_path)
        self._watcher: Optional[VaultWatcher] = None

        # Lazy-loaded components
        self._parser = None
        self._chunker = None
        self._embedder: Optional[EmbeddingModel] = None
        self._vector_store: Optional[VectorStore] = None
        self._searcher: Optional[HybridSearcher] = None
        self._llm: Optional[LLMService] = None

        # Progress callbacks
        self._on_progress: Optional[Callable] = None

        if auto_init:
            pass  # Components load on demand

    @property
    def embedder(self) -> EmbeddingModel:
        if self._embedder is None:
            self._embedder = get_embedder(self.config)
        return self._embedder

    @property
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = get_vector_store(self.config)
        return self._vector_store

    @property
    def searcher(self) -> HybridSearcher:
        if self._searcher is None:
            self._searcher = get_searcher(self.config)
        return self._searcher

    @property
    def llm(self) -> LLMService:
        if self._llm is None:
            self._llm = get_llm(self.config)
        return self._llm

    def set_progress_callback(self, callback: Callable) -> None:
        """Set a callback for progress updates (used by Streamlit GUI)."""
        self._on_progress = callback

    def _update_progress(self, message: str, progress: float = 0) -> None:
        """Update progress via callback if set."""
        self.status.add_message(message)
        if self._on_progress:
            self._on_progress(message, progress)

    # ──────────── Indexing Pipeline ────────────

    def index_vault(self, full_rebuild: bool = False) -> Dict[str, Any]:
        """
        Run the full indexing pipeline:
        Parse → Chunk → Embed → Upsert to Vector DB
        
        Args:
            full_rebuild: If True, clear existing index and rebuild from scratch

        Returns:
            Stats dict with indexing results
        """
        t0 = time.time()
        self.status.state = "indexing"

        try:
            self._update_progress("📂 Obsidian Vault 파싱 시작...", 0.1)

            # Step 1: Parse vault
            vault_path = self.config.vault_path
            if not Path(vault_path).exists():
                self.status.state = "error"
                err_msg = f"Vault path not found: {vault_path}"
                self._update_progress(f"❌ {err_msg}")
                self.status.errors.append(err_msg)
                return {"status": "error", "message": err_msg}

            documents = parse_vault(vault_path, self.config.vault_watch_recursive)
            self.status.total_documents = len(documents)
            self._update_progress(f"✅ {len(documents)}개 문서 파싱 완료", 0.3)

            if not documents:
                self.status.state = "idle"
                self._update_progress("⚠️ 파싱된 문서가 없습니다.")
                return {"status": "warning", "documents": 0}

            # Step 2: Chunk documents
            self._update_progress("✂️ 문서 청킹 중...", 0.4)
            chunks = chunk_vault(documents, self.config)
            self.status.total_chunks = len(chunks)
            self._update_progress(f"✅ {len(chunks)}개 청크 생성 완료", 0.6)

            # Step 3: Full rebuild if requested
            if full_rebuild:
                self._update_progress("🗑️ 기존 인덱스 초기화 중...", 0.65)
                self.vector_store.delete_all()

            # Step 4: Upsert chunks to vector store
            self._update_progress(f"🧠 임베딩 생성 및 벡터 DB 저장 중...", 0.7)
            upserted = self.vector_store.upsert_chunks(chunks)
            self.status.vector_count = self.vector_store.count()
            self._update_progress(
                f"✅ {upserted}개 청크 벡터 DB 저장 완료 (총 {self.status.vector_count})", 0.9
            )

            # Step 5: Rebuild BM25 index
            self._update_progress("🔍 BM25 검색 인덱스 구축 중...", 0.92)
            try:
                self.searcher.build_bm25_index()
                self._update_progress("✅ BM25 인덱스 구축 완료", 0.95)
            except Exception as e:
                self._update_progress(f"⚠️ BM25 인덱스 구축 실패 (선택 사항): {e}")

            # Step 6: Check Ollama
            try:
                ollama_status = self.llm.check_availability()
                self.status.ollama_available = ollama_status.get("available", False)
                self.status.ollama_model = self.config.llm_model
                if self.status.ollama_available:
                    self._update_progress(f"🤖 Ollama LLM 연결됨: {self.config.llm_model}", 1.0)
                else:
                    self._update_progress(
                        f"⚠️ Ollama 연결 실패: {ollama_status.get('error', '알 수 없음')}", 1.0
                    )
            except Exception as e:
                self._update_progress(f"⚠️ Ollama 확인 실패: {e}", 1.0)

            elapsed = time.time() - t0
            self.status.last_index_time = time.time()
            self.status.last_index_duration = elapsed
            self.status.state = "idle"

            result = {
                "status": "success",
                "documents": len(documents),
                "chunks": len(chunks),
                "upserted": upserted,
                "vector_count": self.status.vector_count,
                "time_seconds": round(elapsed, 2),
                "vault_path": vault_path,
            }
            self._update_progress(f"✅ 인덱싱 완료! ({elapsed:.1f}초)", 1.0)
            return result

        except Exception as e:
            self.status.state = "error"
            err_msg = f"Indexing failed: {e}"
            self.status.errors.append(err_msg)
            self._update_progress(f"❌ {err_msg}")
            return {"status": "error", "message": err_msg}

    # ──────────── Incremental Update ────────────

    def update_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Incrementally update index for changed files.
        Re-parses and re-embeds only the changed files.
        """
        if not file_paths:
            return {"status": "noop"}

        self.status.state = "indexing"
        md_files = [f for f in file_paths if f.endswith(".md")]

        if not md_files:
            self.status.state = "idle"
            return {"status": "noop", "message": "No markdown files changed"}

        try:
            from proteusp.parser import parse_obsidian_file
            from proteusp.chunker import chunk_document

            for file_path in md_files:
                # Parse
                doc = parse_obsidian_file(file_path)
                if not doc:
                    continue

                # Chunk
                chunks = chunk_document(doc, self.config)

                # Delete old chunks for this file
                self.vector_store.delete_chunks([str(Path(file_path).resolve())])

                # Upsert new chunks
                if chunks:
                    self.vector_store.upsert_chunks(chunks)

            # Rebuild BM25 index
            try:
                self.searcher.build_bm25_index()
            except Exception:
                pass

            self.status.vector_count = self.vector_store.count()
            self.status.state = "idle"
            self.status.last_index_time = time.time()

            return {
                "status": "updated",
                "files_processed": len(md_files),
                "vector_count": self.status.vector_count,
            }
        except Exception as e:
            self.status.state = "error"
            self.status.errors.append(str(e))
            return {"status": "error", "message": str(e)}

    # ──────────── Search & Query ────────────

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        rerank: bool = True,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Search the indexed vault using hybrid search.
        """
        self.status.state = "searching"
        try:
            result = self.searcher.search(query, top_k, rerank, where_filter)
            self.status.state = "idle"
            return result
        except Exception as e:
            self.status.state = "idle"
            return {"query": query, "results": [], "error": str(e)}

    def query(
        self,
        query: str,
        top_k: Optional[int] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Full RAG query: Search → Generate LLM response.
        """
        # 1. Search for relevant context
        search_result = self.search(query, top_k)
        chunks = search_result.get("results", [])

        # 2. Generate LLM response with context
        response = self.llm.generate(
            query=query,
            context_chunks=chunks,
            stream=stream,
        )
        response["search_results"] = search_result
        return response

    # ──────────── Watch & Sync ────────────

    def start_watching(self) -> None:
        """Start file watcher on the vault."""
        self._watcher = VaultWatcher(
            vault_path=self.config.vault_path,
            on_change=self.update_files,
            debounce_seconds=self.config.vault_watch_debounce_seconds,
            recursive=self.config.vault_watch_recursive,
        )
        self._watcher.start()

    def stop_watching(self) -> None:
        """Stop file watcher."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    # ──────────── Status ────────────

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status."""
        ve_status = {"count": 0, "db_path": ""}
        try:
            ve_status = self.vector_store.get_stats()
        except Exception:
            pass

        ollama_status = {"available": False}
        try:
            ollama_status = self.llm.check_availability()
        except Exception:
            pass

        return {
            "status": self.status.summary,
            "vector_store": ve_status,
            "ollama": ollama_status,
            "config": self.config.to_dict(),
            "pipeline": {
                "state": self.status.state,
                "last_index": self.status.last_index_time,
                "last_index_duration": self.status.last_index_duration,
                "errors": self.status.errors[-5:],  # Last 5 errors
            },
            "recent_messages": self.status.messages[-20:],  # Last 20 messages
        }

    def close(self) -> None:
        """Clean up resources."""
        self.stop_watching()
        reset_embedder()
        self._embedder = None
        self._vector_store = None
        self._searcher = None
        self._llm = None


# Global pipeline instance
_pipeline: Optional[ProteusPPipeline] = None


def get_pipeline(config: Optional[ProteusPConfig] = None) -> ProteusPPipeline:
    """Get or create the global pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = ProteusPPipeline(config or get_config())
    return _pipeline


def reset_pipeline() -> None:
    """Reset pipeline singleton."""
    global _pipeline
    if _pipeline:
        _pipeline.close()
    _pipeline = None

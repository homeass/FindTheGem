"""
ProteusP Vector Store (ChromaDB)
벡터 DB 생성, Upsert, 삭제, 검색 관리
"""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from proteusp.chunker import DocumentChunk
from proteusp.config import ProteusPConfig, get_config
from proteusp.embedder import EmbeddingModel, get_embedder


class VectorStore:
    """
    ChromaDB 기반 벡터 저장소.
    로컬 파일 기반 (경량, 태블릿 최적화).
    """

    def __init__(
        self,
        config: Optional[ProteusPConfig] = None,
        embedder: Optional[EmbeddingModel] = None,
    ):
        self.config = config or get_config()
        self.embedder = embedder or get_embedder(self.config)
        self._collection = None
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._init_client()
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._get_or_create_collection()
        return self._collection

    def _init_client(self) -> None:
        """Initialize ChromaDB persistent client."""
        db_path = Path(self.config.vector_db_path)
        db_path.mkdir(parents=True, exist_ok=True)

        try:
            import chromadb
            self._client = chromadb.PersistentClient(
                path=str(db_path),
                settings=chromadb.Settings(
                    anonymized_telemetry=False,
                    allow_reset=False,
                ),
            )
            print(f"ChromaDB initialized at {db_path}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize ChromaDB at {db_path}: {e}"
            ) from e

    def _get_or_create_collection(self) -> None:
        """Get or create the collection for Obsidian chunks."""
        if self._client is None:
            self._init_client()

        collection_name = self.config.vector_db_collection

        # Ensure embedder is loaded (needs dimension info)
        self.embedder.load()

        try:
            # Try to get existing collection
            self._collection = self._client.get_collection(collection_name)
            count = self._collection.count()
            print(f"Using existing collection '{collection_name}' ({count} chunks)")
        except ValueError:
            # Create new collection
            self._collection = self._client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine", "dimension": self.embedder.dimension},
            )
            print(f"Created new collection '{collection_name}' (dim={self.embedder.dimension})")

    def count(self) -> int:
        """Return number of chunks in the collection."""
        return self.collection.count()

    def upsert_chunks(self, chunks: List[DocumentChunk]) -> int:
        """
        Upsert chunks into the vector store.
        Returns number of chunks upserted.
        """
        if not chunks:
            return 0

        self.embedder.load()
        t0 = time.time()

        # Prepare data
        ids = []
        texts = []
        metadatas = []
        for chunk in chunks:
            chunk_id = chunk.chunk_id or f"chunk_{hash(chunk.text) % 10**8:08d}"
            ids.append(chunk_id)
            texts.append(chunk.text)

            # ChromaDB metadata must be flat, string-keyed, and JSON-serializable
            meta: Dict[str, Any] = {}
            meta["source"] = chunk.source_file
            meta["header"] = chunk.source_header[:200] if chunk.source_header else ""
            meta["tags"] = chunk.metadata.get("tags", "")
            meta["file_name"] = chunk.metadata.get("file_name", "")
            meta["chunk_index"] = chunk.chunk_index

            # Add frontmatter date if available
            for key in ("fm_created", "fm_modified", "fm_date"):
                if key in chunk.metadata:
                    meta[key] = str(chunk.metadata[key])

            metadatas.append(meta)

        # Generate embeddings
        embeddings = self.embedder.encode(texts, show_progress=True)

        # Upsert to ChromaDB
        # Process in batches to avoid memory issues
        batch_size = min(100, len(ids))
        total_upserted = 0

        for start in range(0, len(ids), batch_size):
            end = start + batch_size
            self.collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end].tolist(),
                documents=texts[start:end],
                metadatas=metadatas[start:end],
            )
            total_upserted += (end - start)

        elapsed = time.time() - t0
        print(f"Upserted {total_upserted} chunks in {elapsed:.1f}s")
        return total_upserted

    def delete_chunks(self, source_files: List[str]) -> int:
        """
        Delete all chunks originating from specified source files.
        Returns number of deleted chunks.
        """
        if not source_files:
            return 0

        deleted_count = 0
        for src in source_files:
            try:
                result = self.collection.delete(where={"source": src})
                deleted_count += 1
            except Exception as e:
                print(f"Warning: Failed to delete chunks from {src}: {e}")

        print(f"Deleted chunks from {deleted_count} source files")
        return deleted_count

    def delete_all(self) -> None:
        """Delete all chunks in the collection."""
        try:
            count = self.collection.count()
            self._client.delete_collection(self.config.vector_db_collection)
            self._collection = None
            print(f"Deleted collection with {count} chunks")
        except Exception as e:
            print(f"Warning: Failed to delete collection: {e}")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[dict]:
        """
        Search for similar chunks by embedding vector.
        Returns list of {id, document, metadata, distance}
        """
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            kwargs["where"] = where_filter

        result = self.collection.query(**kwargs)

        # Format results
        results_list = []
        if result["ids"] and result["ids"][0]:
            for i, doc_id in enumerate(result["ids"][0]):
                results_list.append({
                    "id": doc_id,
                    "document": result["documents"][0][i] if result["documents"] else "",
                    "metadata": result["metadatas"][0][i] if result["metadatas"] else {},
                    "distance": result["distances"][0][i] if result["distances"] else 0.0,
                    "score": 1.0 - (result["distances"][0][i] if result["distances"] else 0.0),
                })
        return results_list

    def get_all_chunks(self) -> List[dict]:
        """Retrieve all chunks (with documents and metadata)."""
        try:
            result = self.collection.get(include=["documents", "metadatas"])
            chunks = []
            if result["ids"]:
                for i, doc_id in enumerate(result["ids"]):
                    chunks.append({
                        "id": doc_id,
                        "document": result["documents"][i] if result["documents"] else "",
                        "metadata": result["metadatas"][i] if result["metadatas"] else {},
                    })
            return chunks
        except Exception as e:
            print(f"Warning: Failed to get chunks: {e}")
            return []

    def get_stats(self) -> dict:
        """Get collection statistics."""
        try:
            chunk_count = self.collection.count()
            return {
                "chunks": chunk_count,
                "collection": self.config.vector_db_collection,
                "db_path": self.config.vector_db_path,
            }
        except Exception as e:
            return {"error": str(e)}


# Singleton
_store: Optional[VectorStore] = None


def get_vector_store(config: Optional[ProteusPConfig] = None) -> VectorStore:
    """Get or create the global VectorStore singleton."""
    global _store
    if _store is None:
        _store = VectorStore(config or get_config())
    return _store


def reset_vector_store() -> None:
    """Reset vector store singleton."""
    global _store
    _store = None

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chunker import DocumentChunk

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "deeplens_index"


class SearchResult:
    __slots__ = ("chunk_id", "document_id", "content", "score", "metadata")

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        content: str,
        score: float,
        metadata: Dict[str, Any],
    ) -> None:
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.content = content
        self.score = score
        self.metadata = metadata


class VectorStore:
    """
    Persistent ChromaDB-backed vector store.

    All data is written to `persist_dir` so the index survives restarts
    without any external services or API keys.
    """

    def __init__(self, persist_dir: str | Path = "./data/chroma") -> None:
        self.persist_dir = str(Path(persist_dir).resolve())
        self._client = None
        self._collection = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._client is not None:
            return
        try:
            import chromadb  # type: ignore
        except ImportError:
            raise ImportError("chromadb is required: pip install chromadb")

        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self.persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.debug("ChromaDB connected at %s", self.persist_dir)

    @property
    def collection(self):
        self._ensure_connected()
        return self._collection

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def add_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]],
    ) -> None:
        """Upsert chunks+embeddings into the collection."""
        if not chunks:
            return
        assert len(chunks) == len(embeddings), "chunks and embeddings must be the same length"

        self.collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,
            documents=[c.content for c in chunks],
            metadatas=[
                {
                    **{k: str(v) for k, v in c.metadata.items()},
                    "document_id": c.document_id,
                    "chunk_index": str(c.chunk_index),
                    "total_chunks": str(c.total_chunks),
                }
                for c in chunks
            ],
        )
        logger.debug("Upserted %d chunks", len(chunks))

    def delete_document(self, document_id: str) -> None:
        """Remove all chunks that belong to `document_id`."""
        results = self.collection.get(where={"document_id": document_id})
        ids = results.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
            logger.debug("Deleted %d chunks for document %s", len(ids), document_id)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[SearchResult]:
        """Return up to `top_k` most similar chunks."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, max(self.collection.count(), 1)),
            include=["documents", "metadatas", "distances"],
        )

        output: List[SearchResult] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for chunk_id, doc, meta, dist in zip(ids, docs, metas, distances):
            output.append(
                SearchResult(
                    chunk_id=chunk_id,
                    document_id=meta.get("document_id", ""),
                    content=doc,
                    score=1.0 - dist,  # cosine distance → similarity
                    metadata=meta,
                )
            )

        return output

    def has_document(self, document_id: str, last_modified: float) -> bool:
        """Return True if this document is already indexed and up-to-date."""
        results = self.collection.get(
            where={"document_id": document_id},
            limit=1,
            include=["metadatas"],
        )
        metas = results.get("metadatas", [])
        if not metas:
            return False
        stored_mtime = metas[0].get("last_modified")
        if stored_mtime is None:
            return False
        try:
            return float(stored_mtime) >= last_modified
        except (ValueError, TypeError):
            return False

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Total number of chunks stored."""
        return self.collection.count()

    def distinct_documents(self) -> int:
        """Approximate number of unique documents (based on metadata)."""
        all_meta = self.collection.get(include=["metadatas"]).get("metadatas", [])
        return len({m.get("document_id") for m in all_meta if m.get("document_id")})

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return one metadata record per unique indexed document."""
        all_meta = self.collection.get(include=["metadatas"]).get("metadatas", []) or []
        seen: Dict[str, Dict[str, Any]] = {}
        for meta in all_meta:
            doc_id = meta.get("document_id", "")
            if doc_id and doc_id not in seen:
                seen[doc_id] = {
                    "document_id": doc_id,
                    "filename": meta.get("filename", ""),
                    "file_path": meta.get("file_path", ""),
                    "file_type": meta.get("file_type", ""),
                    "total_chunks": meta.get("total_chunks", "0"),
                }
        return list(seen.values())

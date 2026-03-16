from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .chunker import TextChunker
from .config import Settings, settings as default_settings
from .embedder import Embedder
from .parser import DocumentParser
from .store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class IndexStats:
    documents: int
    chunks: int
    storage_bytes: int

    @property
    def storage_mb(self) -> float:
        return self.storage_bytes / (1024 * 1024)


class Indexer:
    """Orchestrates parsing → chunking → embedding → storage."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or default_settings
        self.parser = DocumentParser()
        self.chunker = TextChunker(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        self.embedder = Embedder(model_name=self.settings.embedding_model)
        self.store = VectorStore(persist_dir=self.settings.chroma_persist_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_folder(self, path: str | Path) -> List[Path]:
        """Return all files with supported extensions under `path`."""
        root = Path(path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Folder not found: {root}")

        found: List[Path] = []
        exts = set(self.settings.supported_extensions)
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                fp = Path(dirpath) / fname
                if fp.suffix.lower() in exts:
                    found.append(fp)
        return sorted(found)

    def index_file(self, path: str | Path) -> bool:
        """
        Parse, chunk, embed, and store a single file.

        Returns True if the file was (re-)indexed, False if it was skipped.
        Logs a warning and returns False if any step fails.
        """
        fp = Path(path).resolve()
        try:
            stat = fp.stat()
        except OSError as exc:
            logger.warning("Cannot stat %s: %s", fp, exc)
            return False

        # Check if already indexed and current
        doc_id = self._path_hash(fp)
        if self.store.has_document(doc_id, stat.st_mtime):
            logger.debug("Skipping (unchanged): %s", fp.name)
            return False

        try:
            document = self.parser.parse(fp)
        except Exception as exc:
            logger.warning("Parse failed for %s: %s", fp, exc)
            return False

        try:
            chunks = self.chunker.chunk(document)
        except Exception as exc:
            logger.warning("Chunking failed for %s: %s", fp, exc)
            return False

        if not chunks:
            logger.warning("No chunks produced for %s (empty content?)", fp)
            return False

        try:
            texts = [c.content for c in chunks]
            embeddings = self.embedder.embed_batch(texts)
        except Exception as exc:
            logger.warning("Embedding failed for %s: %s", fp, exc)
            return False

        # Persist last_modified so has_document() works next run
        for chunk in chunks:
            chunk.metadata["last_modified"] = str(document.last_modified)

        try:
            # Remove stale chunks first (handles re-index after file edit)
            self.store.delete_document(doc_id)
            self.store.add_chunks(chunks, embeddings)
        except Exception as exc:
            logger.warning("Store failed for %s: %s", fp, exc)
            return False

        logger.info("Indexed %s (%d chunks)", fp.name, len(chunks))
        return True

    def index_folder(self, path: str | Path) -> Dict[str, int]:
        """
        Index all supported files in `path`.

        Returns a summary dict with keys: total, indexed, skipped, failed.
        """
        files = self.scan_folder(path)
        total = len(files)
        indexed = skipped = failed = 0

        for i, fp in enumerate(files, start=1):
            print(f"  [{i}/{total}] {fp.name}", end=" ", flush=True)
            try:
                result = self.index_file(fp)
                if result:
                    indexed += 1
                    print("✓")
                else:
                    skipped += 1
                    print("(skipped)")
            except Exception as exc:
                failed += 1
                logger.warning("Unexpected error indexing %s: %s", fp, exc)
                print(f"✗ {exc}")

        return {"total": total, "indexed": indexed, "skipped": skipped, "failed": failed}

    def search(self, query: str, top_k: int = 5):
        """Embed `query` and return ranked results from the store."""
        query_vec = self.embedder.embed(query)
        return self.store.search(query_vec, top_k=top_k)

    def get_stats(self) -> IndexStats:
        """Return document count, chunk count, and storage size on disk."""
        chunk_count = self.store.count()
        doc_count = self.store.distinct_documents()
        storage = self._dir_size(Path(self.settings.chroma_persist_dir))
        return IndexStats(documents=doc_count, chunks=chunk_count, storage_bytes=storage)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _path_hash(path: Path) -> str:
        import hashlib
        return hashlib.sha256(str(path).encode()).hexdigest()

    @staticmethod
    def _dir_size(directory: Path) -> int:
        total = 0
        if directory.exists():
            for dirpath, _dirs, files in os.walk(directory):
                for fname in files:
                    try:
                        total += (Path(dirpath) / fname).stat().st_size
                    except OSError:
                        pass
        return total

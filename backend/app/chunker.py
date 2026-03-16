from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .parser import Document


@dataclass
class DocumentChunk:
    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    total_chunks: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class TextChunker:
    """
    Splits a Document into overlapping chunks using recursive character splitting.

    Strategy (in priority order):
      1. Split on double-newlines (paragraph boundaries)
      2. Split on single newlines
      3. Split on sentence-ending punctuation
      4. Split on spaces (word boundary)
      5. Hard split at chunk_size characters
    """

    _SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", " ", ""]

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, document: Document) -> List[DocumentChunk]:
        raw_chunks = self._split(document.content)
        total = len(raw_chunks)
        chunks: List[DocumentChunk] = []

        for idx, text in enumerate(raw_chunks):
            meta = {
                **document.metadata,
                "file_path": document.file_path,
                "filename": document.filename,
                "file_type": document.file_type,
                "chunk_index": idx,
                "total_chunks": total,
            }
            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=document.document_id,
                    content=text,
                    chunk_index=idx,
                    total_chunks=total,
                    metadata=meta,
                )
            )

        return chunks

    # ------------------------------------------------------------------
    # Splitting logic
    # ------------------------------------------------------------------

    def _split(self, text: str) -> List[str]:
        """Top-level entry: recursively split then apply sliding window."""
        pieces = self._recursive_split(text, self._SEPARATORS)
        return self._merge_with_overlap(pieces)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """
        Try each separator in order.  If a separator creates pieces that are
        still too large, recurse with the remaining (lower-priority) separators.
        """
        if not text:
            return []

        sep = separators[0]
        remaining_seps = separators[1:]

        if sep == "":
            # Hard character split — base case
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        raw_pieces = text.split(sep)
        result: List[str] = []

        for piece in raw_pieces:
            piece = piece.strip()
            if not piece:
                continue
            if len(piece) <= self.chunk_size:
                result.append(piece)
            elif remaining_seps:
                result.extend(self._recursive_split(piece, remaining_seps))
            else:
                # No more separators; hard-split
                result.extend(piece[i : i + self.chunk_size] for i in range(0, len(piece), self.chunk_size))

        return result

    def _merge_with_overlap(self, pieces: List[str]) -> List[str]:
        """
        Greedily merge small pieces into chunks of at most `chunk_size` chars,
        then emit with `chunk_overlap` chars carried into the next chunk.
        """
        if not pieces:
            return []

        chunks: List[str] = []
        current_parts: List[str] = []
        current_len = 0

        for piece in pieces:
            piece_len = len(piece)

            if current_len + piece_len > self.chunk_size and current_parts:
                # Emit the current chunk
                chunk_text = " ".join(current_parts)
                chunks.append(chunk_text)

                # Carry over tail for overlap
                overlap_text = chunk_text[-self.chunk_overlap :] if self.chunk_overlap else ""
                current_parts = [overlap_text] if overlap_text else []
                current_len = len(overlap_text)

            current_parts.append(piece)
            current_len += piece_len

        if current_parts:
            chunks.append(" ".join(current_parts))

        return [c for c in chunks if c.strip()]

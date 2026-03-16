from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterator, List

from .indexer import Indexer
from .llm import OllamaClient
from .store import SearchResult


@dataclass
class SourceChunk:
    filename: str
    chunk_text: str
    score: float


@dataclass
class RAGResponse:
    answer: str
    sources: List[SourceChunk]
    model_used: str
    query_time_seconds: float


class RAGEngine:
    """Full retrieval-augmented generation pipeline."""

    def __init__(self, indexer: Indexer, ollama: OllamaClient) -> None:
        self.indexer = indexer
        self.ollama = ollama

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(self, question: str, top_k: int = 5, model: str = "llama3.2") -> RAGResponse:
        """Retrieve relevant chunks then generate a grounded answer."""
        t0 = time.perf_counter()

        chunks, context = self._retrieve_and_build_context(question, top_k)
        answer = self.ollama.generate(question, context=context, model=model)

        return RAGResponse(
            answer=answer,
            sources=chunks,
            model_used=model,
            query_time_seconds=time.perf_counter() - t0,
        )

    def query_stream(
        self,
        question: str,
        top_k: int = 5,
        model: str = "llama3.2",
    ) -> tuple[Iterator[str], List[SourceChunk]]:
        """
        Returns (token_iterator, source_chunks).

        Retrieval is done eagerly; generation is streamed.
        Callers should iterate the token_iterator to drive generation.
        """
        chunks, context = self._retrieve_and_build_context(question, top_k)
        token_iter = self.ollama.generate_stream(question, context=context, model=model)
        return token_iter, chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _retrieve_and_build_context(
        self, question: str, top_k: int
    ) -> tuple[List[SourceChunk], str]:
        """Embed question → vector search → build context string."""
        query_vec = self.indexer.embedder.embed(question)
        raw_results: List[SearchResult] = self.indexer.store.search(query_vec, top_k=top_k)

        source_chunks: List[SourceChunk] = []
        context_parts: List[str] = []

        for result in raw_results:
            filename = result.metadata.get("filename", result.metadata.get("file_path", "unknown"))
            source_chunks.append(
                SourceChunk(
                    filename=filename,
                    chunk_text=result.content,
                    score=result.score,
                )
            )
            context_parts.append(f"[Source: {filename}]\n{result.content}")

        context = "\n\n".join(context_parts)
        return source_chunks, context

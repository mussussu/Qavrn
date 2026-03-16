from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .indexer import Indexer
from .llm import OllamaClient
from .rag import RAGEngine

logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


# ---------------------------------------------------------------------------
# Lifespan — initialise shared singletons once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.indexer = Indexer(settings)
    app.state.ollama = OllamaClient(base_url=settings.ollama_url)
    logger.info("DeepLens API ready.")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="DeepLens API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    model: str = "llama3.2"


class IndexRequest(BaseModel):
    folder_path: str


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health(request: Request) -> Dict[str, Any]:
    indexer: Indexer = request.app.state.indexer
    ollama: OllamaClient = request.app.state.ollama

    stats, ollama_ok = await asyncio.gather(
        asyncio.to_thread(indexer.get_stats),
        asyncio.to_thread(ollama.is_available),
    )

    return {
        "status": "ok",
        "documents": stats.documents,
        "chunks": stats.chunks,
        "ollama_available": ollama_ok,
    }


@app.post("/api/ask")
async def ask(body: AskRequest, request: Request) -> StreamingResponse:
    indexer: Indexer = request.app.state.indexer
    ollama: OllamaClient = request.app.state.ollama

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    async def event_stream():
        try:
            rag = RAGEngine(indexer=indexer, ollama=ollama)

            # Retrieval is blocking — run in thread
            token_iter, sources = await asyncio.to_thread(
                rag.query_stream, body.question, body.top_k, body.model
            )

            # Stream tokens; each next() blocks on the Ollama HTTP stream
            def _next(it):
                return next(it, None)

            while True:
                token = await asyncio.to_thread(_next, token_iter)
                if token is None:
                    break
                payload = json.dumps({"type": "token", "content": token})
                yield f"data: {payload}\n\n"

            # Send sources after all tokens
            sources_data = [
                {"filename": s.filename, "chunk_text": s.chunk_text, "score": round(s.score, 4)}
                for s in sources
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources_data})}\n\n"

        except ConnectionError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        except Exception as exc:
            logger.exception("Error during /api/ask streaming")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/index")
async def index_folder(body: IndexRequest, request: Request) -> Dict[str, Any]:
    indexer: Indexer = request.app.state.indexer
    folder = Path(body.folder_path)

    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Folder not found: {folder}")

    # index_folder is slow — run in thread pool so the event loop stays free
    summary = await asyncio.to_thread(indexer.index_folder, folder)
    stats = await asyncio.to_thread(indexer.get_stats)

    return {
        **summary,
        "documents": stats.documents,
        "chunks": stats.chunks,
    }


@app.get("/api/stats")
async def stats(request: Request) -> Dict[str, Any]:
    indexer: Indexer = request.app.state.indexer
    s = await asyncio.to_thread(indexer.get_stats)
    return {
        "documents": s.documents,
        "chunks": s.chunks,
        "storage_mb": round(s.storage_mb, 2),
        "storage_bytes": s.storage_bytes,
    }


@app.get("/api/documents")
async def list_documents(request: Request):
    indexer: Indexer = request.app.state.indexer
    docs = await asyncio.to_thread(indexer.store.list_documents)
    return {"documents": docs}


# ---------------------------------------------------------------------------
# Serve built frontend (production)
# ---------------------------------------------------------------------------

if FRONTEND_DIST.exists():
    # Mount assets (JS/CSS bundles) under /assets
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all: return index.html for any non-API path (SPA fallback)."""
        # Try serving a real file first
        candidate = FRONTEND_DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
else:
    @app.get("/", include_in_schema=False)
    async def no_frontend():
        return {
            "message": "Frontend not built. Run: cd frontend && npm install && npm run build",
            "api_docs": "/docs",
        }

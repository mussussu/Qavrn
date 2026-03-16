<div align="center">

<img src="frontend/public/logo.svg" alt="LocalLens Logo" width="96" height="96" />

# LocalLens

**Your private AI research assistant. Fully local. Fully yours.**

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3B82F6?style=flat-square&logo=python&logoColor=white)
![License MIT](https://img.shields.io/badge/License-MIT-06B6D4?style=flat-square)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-10b981?style=flat-square)

</div>

---

## What is LocalLens?

LocalLens is a local-first RAG (Retrieval-Augmented Generation) engine that indexes your documents and lets you ask questions about them in natural language. Answers are grounded in your actual files with cited sources and relevance scores — not hallucinated from a cloud model's training data. Nothing leaves your machine: no API keys, no telemetry, no internet required after the initial setup.

![LocalLens UI](docs/screenshot.png)

---

## Features

- **Fully offline** — no API keys, no cloud, no data leaves your machine
- **Semantic search** across PDFs, DOCX, Markdown, TXT, HTML, and CSV files
- **Conversational answers** powered by local LLMs via [Ollama](https://ollama.com)
- **Source citations** with per-chunk relevance scores for every answer
- **Real-time streaming** — watch the answer appear token by token
- **Index any folder** and search across all your documents instantly
- **Dark mode UI** built with React, TypeScript, and Tailwind CSS

---

## Quick Start

### Prerequisites

- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 18+](https://nodejs.org/)
- [Ollama](https://ollama.com) installed and running

### Install & run

```bash
git clone https://github.com/YOUR_USERNAME/deeplens.git
cd deeplens

# Install frontend dependencies
cd frontend && npm install && cd ..

# Install Python dependencies
pip install -r backend/requirements.txt

# Pull a local LLM (first time only)
ollama pull llama3.2

# Launch — builds the frontend and starts the server
python start.py
```

Open **http://localhost:8000** in your browser.

> **First launch** will also download the embedding model (~90 MB). Subsequent starts are instant.

---

## Usage

### Web UI

1. Click **Index Folder** in the sidebar and enter a folder path (e.g. `C:\Users\you\Documents`)
2. Wait for indexing to finish — progress is shown in the terminal
3. Type a question in the search bar and press **Enter**
4. Read the streamed answer and expand the source cards to see the matched passages

### CLI

```bash
# Index a folder
python -m backend.app.cli index /path/to/folder

# Ask a question (RAG)
python -m backend.app.cli ask "What does the contract say about termination?"

# Vector search (no LLM)
python -m backend.app.cli search "neural networks"

# Show index statistics
python -m backend.app.cli stats
```

### Development mode

```bash
# Terminal 1 — backend with auto-reload
python start.py --dev --reload

# Terminal 2 — Vite dev server with HMR
cd frontend && npm run dev
```

The Vite dev server runs on **http://localhost:5173** and proxies `/api` requests to the backend on `:8000`.

---

## How it works

```
Your files
    │
    ▼
DocumentParser        ← PyPDF2 · python-docx · markdown · stdlib
    │
    ▼
TextChunker           ← recursive character splitting with overlap
    │
    ▼
Embedder              ← sentence-transformers (all-MiniLM-L6-v2, local)
    │
    ▼
VectorStore           ← ChromaDB, persisted to ./data/chroma/
    │
 query ──► Embedder ──► VectorStore ──► top-k chunks
                                            │
                                            ▼
                                       OllamaClient  ← local LLM, streamed
                                            │
                                            ▼
                                       Answer + sources
```

---

## Supported file types

| Extension | Parser |
|-----------|--------|
| `.pdf`    | PyPDF2 |
| `.docx`   | python-docx |
| `.md`     | markdown → HTML → plain text |
| `.txt`    | plain read |
| `.csv`    | plain read |
| `.html`   | stdlib HTMLParser (strips scripts/styles) |

---

## Configuration

All settings can be overridden via environment variables or a `.env` file in the project root.

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPLENS_CHUNK_SIZE` | `500` | Max characters per chunk |
| `DEEPLENS_CHUNK_OVERLAP` | `50` | Overlap between adjacent chunks |
| `DEEPLENS_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model name |
| `DEEPLENS_CHROMA_PERSIST_DIR` | `./data/chroma` | Vector store location on disk |
| `DEEPLENS_OLLAMA_URL` | `http://localhost:11434` | Ollama base URL |
| `DEEPLENS_SUPPORTED_EXTENSIONS` | see above | Comma-separated list of extensions |

---

## Project structure

```
deeplens/
├── backend/
│   ├── app/
│   │   ├── api.py        # FastAPI server + SSE streaming
│   │   ├── cli.py        # Command-line interface
│   │   ├── config.py     # Pydantic settings
│   │   ├── chunker.py    # Recursive text splitter
│   │   ├── embedder.py   # sentence-transformers wrapper
│   │   ├── indexer.py    # Orchestrator
│   │   ├── llm.py        # Ollama HTTP client
│   │   ├── parser.py     # Multi-format document parser
│   │   ├── rag.py        # RAG pipeline
│   │   └── store.py      # ChromaDB vector store
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   ├── logo.svg
│   │   └── favicon.svg
│   └── src/
│       ├── App.tsx
│       └── components/
│           ├── ChatMessage.tsx
│           ├── SearchBar.tsx
│           ├── Sidebar.tsx
│           └── SourceCard.tsx
├── data/                 # ChromaDB persisted here (git-ignored)
├── start.py              # One-command launcher
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE) for details.

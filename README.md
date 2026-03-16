<div align="center">

<img src="frontend/public/logo.svg" alt="Qavrn Logo" width="96" height="96" />

# Qavrn

**Your private AI research assistant. Fully local. Fully yours.**

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3B82F6?style=flat-square&logo=python&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-stable-f97316?style=flat-square&logo=rust&logoColor=white)
![License MIT](https://img.shields.io/badge/License-MIT-06B6D4?style=flat-square)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-10b981?style=flat-square)

</div>

---

## What is Qavrn?

Qavrn is a local-first RAG (Retrieval-Augmented Generation) engine that indexes your documents and lets you ask questions about them in natural language. Answers are grounded in your actual files with cited sources and relevance scores — not hallucinated from a cloud model's training data. Nothing leaves your machine: no API keys, no telemetry, no internet required after the initial setup.

![Qavrn UI](docs/screenshot.png)

---

## Features

- **Fully offline** — no API keys, no cloud, no data ever leaves your machine
- **Semantic search** across 30+ file types: documents, code, config files, emails, and ebooks
- **Conversational answers** powered by local LLMs via [Ollama](https://ollama.com)
- **Source citations** with per-chunk relevance scores for every answer
- **Real-time streaming** — watch the answer appear token by token
- **File watcher** — add a folder to auto-reindex whenever files are created, modified, or deleted
- **Native desktop app** — bundle as a standalone executable with Tauri v2 (no terminal required)
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
git clone https://github.com/YOUR_USERNAME/qavrn.git
cd qavrn

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
2. Optionally click **Watch & Index** to keep a folder auto-synced on file changes
3. Type a question in the search bar and press **Enter**
4. Read the streamed answer and expand the source cards to see the matched passages

### CLI

```bash
# Index a folder
python -m backend.app.cli index /path/to/folder

# Watch a folder and auto-reindex on changes (Ctrl+C to stop)
python -m backend.app.cli watch /path/to/folder

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

## Desktop App (Tauri)

Qavrn can be bundled as a native desktop application using [Tauri v2](https://tauri.app). The Tauri shell spawns the Python backend automatically on startup and kills it cleanly on exit — no terminal window required.

### Additional prerequisites

- [Rust](https://rustup.rs) stable toolchain — `rustup update stable`
- [Tauri CLI v2](https://tauri.app/reference/cli/) — `cargo install tauri-cli --version "^2"`
- The standard system dependencies for your OS listed in the [Tauri prerequisites guide](https://tauri.app/start/prerequisites/)

### Development (hot-reload)

```powershell
.\scripts\dev-desktop.ps1
```

Starts the Python backend in `--api-only` mode, then runs `cargo tauri dev`, which opens a native window pointed at the Vite dev server with full hot-reload.

### Production build

```powershell
.\scripts\build-desktop.ps1
```

Builds the React frontend, then compiles and bundles the Tauri app. The installer is placed in:

```
src-tauri/target/release/bundle/
  msi/      ← Windows installer
  nsis/     ← Windows NSIS installer
  deb/      ← Linux .deb
  appimage/ ← Linux AppImage
  dmg/      ← macOS disk image
```

### Generate high-quality app icons

```bash
# Export logo.svg to a 1024x1024 PNG first, then:
cargo tauri icon path/to/logo-1024.png
```

This regenerates all sizes in `src-tauri/icons/` from a single high-resolution source.

---

## How it works

```
Your files
    |
    v
DocumentParser        <- PyPDF2 / python-docx / markdown / stdlib / ebooklib
    |
    v
TextChunker           <- recursive character splitting with overlap
    |
    v
Embedder              <- sentence-transformers (all-MiniLM-L6-v2, local)
    |
    v
VectorStore           <- ChromaDB, persisted to ./data/chroma/
    |
 query --> Embedder --> VectorStore --> top-k chunks
                                           |
                                           v
                                      OllamaClient  <- local LLM, streamed
                                           |
                                           v
                                      Answer + sources


File changes
    |
    v
FileWatcher (watchdog) --> debounce 2s --> Indexer (re-index changed file)
```

---

## Supported file types

### Documents

| Extension | Parser |
|-----------|--------|
| `.pdf` | PyPDF2 |
| `.docx` | python-docx |
| `.md` | markdown -> HTML -> plain text |
| `.txt` | plain read |
| `.csv` | plain read |
| `.html` | stdlib HTMLParser (strips scripts/styles) |
| `.rst` | plain read |

### Data & Config

| Extension | Parser |
|-----------|--------|
| `.json` | pretty-printed key/value extraction |
| `.xml` | ElementTree text node extraction |
| `.yaml` / `.yml` | plain read |
| `.toml` | plain read |
| `.env` | plain read |
| `.log` | plain read |

### Source Code (30+ languages)

| Extensions | Notes |
|------------|-------|
| `.py` `.js` `.ts` | Python, JavaScript, TypeScript |
| `.java` `.kt` `.swift` | JVM and Apple ecosystem |
| `.cpp` `.c` `.rs` `.go` | Systems languages |
| `.rb` `.php` | Scripting languages |

### Email & Ebooks

| Extension | Parser |
|-----------|--------|
| `.eml` | stdlib `email` module (headers + body) |
| `.epub` | ebooklib + BeautifulSoup HTML extraction |

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
| `DEEPLENS_SUPPORTED_EXTENSIONS` | see above | Comma-separated list of extensions to index |

---

## Project structure

```
qavrn/
├── backend/
│   ├── app/
│   │   ├── api.py        # FastAPI server + SSE streaming
│   │   ├── cli.py        # Command-line interface
│   │   ├── config.py     # Pydantic settings
│   │   ├── chunker.py    # Recursive text splitter
│   │   ├── embedder.py   # sentence-transformers wrapper
│   │   ├── indexer.py    # Orchestrator
│   │   ├── llm.py        # Ollama HTTP client
│   │   ├── parser.py     # Multi-format document parser (30+ types)
│   │   ├── rag.py        # RAG pipeline
│   │   ├── store.py      # ChromaDB vector store
│   │   └── watcher.py    # watchdog file-change monitor
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
├── src-tauri/            # Tauri v2 desktop wrapper
│   ├── capabilities/
│   │   └── default.json  # Tauri permission set
│   ├── icons/            # App icons (all sizes)
│   ├── src/
│   │   ├── main.rs       # Binary entry point
│   │   └── lib.rs        # Backend lifecycle + Tauri commands
│   ├── build.rs
│   ├── Cargo.toml
│   └── tauri.conf.json
├── scripts/
│   ├── build-desktop.ps1 # Production desktop build
│   └── dev-desktop.ps1   # Development mode (hot-reload)
├── data/                 # ChromaDB persisted here (git-ignored)
├── start.py              # One-command launcher
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE) for details.

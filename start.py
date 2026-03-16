#!/usr/bin/env python3
"""
start.py — Launch the DeepLens server.

Usage:
    python start.py            # start server (auto-builds frontend if needed)
    python start.py --build    # force rebuild frontend before starting
    python start.py --dev      # start backend only (run Vite separately)
    python start.py --port N   # listen on a different port (default: 8000)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
FRONTEND_DIR = ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IS_WINDOWS = sys.platform == "win32"


def _run(cmd: list[str], cwd: Path, check: bool = True) -> int:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd), shell=_IS_WINDOWS)
    if check and result.returncode != 0:
        print(f"\n[error] Command failed with exit code {result.returncode}.", file=sys.stderr)
        sys.exit(result.returncode)
    return result.returncode


def ensure_backend_deps() -> None:
    try:
        import fastapi  # noqa: F401
    except ImportError:
        print("\n── Installing Python dependencies ─────────────────────────")
        _run(
            [sys.executable, "-m", "pip", "install", "-r", "backend/requirements.txt"],
            cwd=ROOT,
        )
        print("Dependencies installed.")


def build_frontend() -> None:
    print("\n── Building frontend ──────────────────────────────────────")
    if not (FRONTEND_DIR / "node_modules").exists():
        print("Installing npm dependencies…")
        _run(["npm", "install"], cwd=FRONTEND_DIR)
    print("Compiling & bundling…")
    _run(["npm", "run", "build"], cwd=FRONTEND_DIR)
    print("Frontend built → frontend/dist/")


def ensure_frontend(force_build: bool) -> None:
    if force_build:
        build_frontend()
        return
    if not DIST_DIR.exists():
        print("[info] frontend/dist not found — building now…")
        build_frontend()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Start the DeepLens server")
    parser.add_argument("--build",  action="store_true", help="Force rebuild the frontend")
    parser.add_argument("--dev",    action="store_true", help="Skip frontend; start backend only")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn auto-reload (dev)")
    parser.add_argument("--port",   type=int, default=8000, metavar="N", help="Port (default 8000)")
    parser.add_argument("--host",   default="0.0.0.0", help="Bind host (default 0.0.0.0)")
    args = parser.parse_args()

    ensure_backend_deps()

    if not args.dev:
        ensure_frontend(args.build)

    print(f"\n── Starting DeepLens ──────────────────────────────────────")
    if DIST_DIR.exists():
        print(f"   UI  →  http://localhost:{args.port}")
    else:
        print(f"   API →  http://localhost:{args.port}/docs  (no frontend built)")
    if args.dev:
        print("   Dev →  run  cd frontend && npm run dev  in another terminal")
    print()

    uvicorn_cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.app.api:app",
        "--host", args.host,
        "--port", str(args.port),
    ]
    if args.reload:
        uvicorn_cmd.append("--reload")

    try:
        subprocess.run(uvicorn_cmd, cwd=str(ROOT))
    except KeyboardInterrupt:
        print("\n[info] Server stopped.")


if __name__ == "__main__":
    main()

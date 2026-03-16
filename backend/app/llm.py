from __future__ import annotations

import json
import logging
from typing import Iterator

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are Qavrn, a private AI research assistant. "
    "Answer questions based ONLY on the provided context from the user's local documents. "
    "Always cite which source file your information comes from. "
    "If the context doesn't contain enough information to answer, say so honestly. "
    "Never make up information."
)


class OllamaClient:
    """Thin client for a locally running Ollama instance."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if Ollama is reachable."""
        try:
            import requests

            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        context: str = "",
        model: str = "llama3.2",
    ) -> str:
        """
        Send a single generate request and return the full response string.
        Internally streams to avoid timeout on large responses, but buffers
        everything before returning.
        """
        return "".join(self._stream(prompt, context, model))

    def generate_stream(
        self,
        prompt: str,
        context: str = "",
        model: str = "llama3.2",
    ) -> Iterator[str]:
        """Yield response tokens one at a time as they arrive from Ollama."""
        yield from self._stream(prompt, context, model)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_body(self, prompt: str, context: str, model: str) -> dict:
        user_content = prompt
        if context:
            user_content = f"Context:\n{context}\n\nQuestion: {prompt}"

        return {
            "model": model,
            "system": _SYSTEM_PROMPT,
            "prompt": user_content,
            "stream": True,
        }

    def _stream(self, prompt: str, context: str, model: str) -> Iterator[str]:
        try:
            import requests
        except ImportError:
            raise ImportError("requests is required: pip install requests")

        body = self._build_body(prompt, context, model)
        url = f"{self.base_url}/api/generate"

        try:
            with requests.post(url, json=body, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue
                    try:
                        data = json.loads(raw_line)
                    except json.JSONDecodeError as exc:
                        logger.warning("Undecodable line from Ollama: %s — %s", raw_line, exc)
                        continue

                    token = data.get("response", "")
                    if token:
                        yield token

                    if data.get("done"):
                        break
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot reach Ollama at {self.base_url}. "
                "Make sure Ollama is running: https://ollama.com"
            )
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(f"Ollama returned an error: {exc}")

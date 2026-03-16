from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class Document:
    file_path: str
    filename: str
    content: str
    file_type: str
    last_modified: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def document_id(self) -> str:
        """Stable hash of the absolute file path."""
        return hashlib.sha256(self.file_path.encode()).hexdigest()


class DocumentParser:
    """Detects file type by extension and extracts plain text."""

    def parse(self, file_path: str | Path) -> Document:
        path = Path(file_path).resolve()
        ext = path.suffix.lower()
        last_modified = path.stat().st_mtime

        content = self._extract(path, ext)

        return Document(
            file_path=str(path),
            filename=path.name,
            content=content,
            file_type=ext.lstrip("."),
            last_modified=last_modified,
            metadata={
                "file_size": path.stat().st_size,
                "extension": ext,
            },
        )

    # ------------------------------------------------------------------
    # Private dispatch
    # ------------------------------------------------------------------

    def _extract(self, path: Path, ext: str) -> str:
        handlers = {
            ".pdf": self._pdf,
            ".docx": self._docx,
            ".md": self._markdown,
            ".txt": self._plain,
            ".csv": self._plain,
            ".html": self._html,
        }
        handler = handlers.get(ext)
        if handler is None:
            raise ValueError(f"Unsupported extension: {ext}")
        return handler(path)

    def _pdf(self, path: Path) -> str:
        try:
            import PyPDF2  # type: ignore
        except ImportError:
            raise ImportError("PyPDF2 is required for PDF parsing: pip install PyPDF2")

        text_parts: list[str] = []
        with open(path, "rb") as fh:
            reader = PyPDF2.PdfReader(fh)
            for page in reader.pages:
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception as exc:
                    logger.warning("Could not extract text from PDF page in %s: %s", path, exc)
        return "\n".join(text_parts)

    def _docx(self, path: Path) -> str:
        try:
            import docx  # type: ignore
        except ImportError:
            raise ImportError("python-docx is required for DOCX parsing: pip install python-docx")

        doc = docx.Document(str(path))
        return "\n".join(para.text for para in doc.paragraphs)

    def _markdown(self, path: Path) -> str:
        try:
            import markdown  # type: ignore
            from html.parser import HTMLParser

            class _Stripper(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self._parts: list[str] = []

                def handle_data(self, data: str) -> None:
                    self._parts.append(data)

                def get_text(self) -> str:
                    return "".join(self._parts)

            raw = path.read_text(encoding="utf-8", errors="replace")
            html = markdown.markdown(raw)
            stripper = _Stripper()
            stripper.feed(html)
            return stripper.get_text()
        except ImportError:
            # Fallback: return raw markdown text without rendering
            logger.warning("markdown package not installed; returning raw MD text for %s", path)
            return path.read_text(encoding="utf-8", errors="replace")

    def _plain(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")

    def _html(self, path: Path) -> str:
        from html.parser import HTMLParser

        class _Stripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self._parts: list[str] = []
                self._skip_tags = {"script", "style"}
                self._current_skip: str | None = None

            def handle_starttag(self, tag: str, attrs) -> None:
                if tag in self._skip_tags:
                    self._current_skip = tag

            def handle_endtag(self, tag: str) -> None:
                if tag == self._current_skip:
                    self._current_skip = None

            def handle_data(self, data: str) -> None:
                if self._current_skip is None:
                    self._parts.append(data)

            def get_text(self) -> str:
                return " ".join(self._parts)

        raw = path.read_text(encoding="utf-8", errors="replace")
        stripper = _Stripper()
        stripper.feed(raw)
        return stripper.get_text()

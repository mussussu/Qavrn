from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


class FileWatcher:
    """
    Monitors one or more folders for filesystem changes and automatically
    re-indexes affected files using the provided Indexer.

    Changes are debounced: if the same file changes multiple times within
    2 seconds only one re-index is triggered.

    Usage::

        watcher = FileWatcher(indexer, settings.supported_extensions)
        watcher.start()
        watcher.watch("/path/to/folder")
        ...
        watcher.stop()
    """

    _DEBOUNCE_SECONDS = 2.0

    def __init__(self, indexer: Any, supported_extensions: List[str]) -> None:
        self._indexer = indexer
        self._exts: Set[str] = {e.lower() for e in supported_extensions}
        self._observer: Any = None           # watchdog Observer (lazy)
        self._watches: Dict[str, Any] = {}   # resolved-path → watchdog Watch handle
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def watched_folders(self) -> List[str]:
        return list(self._watches.keys())

    def start(self) -> None:
        """Start the background observer thread."""
        try:
            from watchdog.observers import Observer  # type: ignore
        except ImportError:
            raise ImportError("watchdog is required: pip install watchdog")
        self._observer = Observer()
        self._observer.start()
        logger.debug("FileWatcher started.")

    def stop(self) -> None:
        """Cancel pending timers and stop the observer thread."""
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        logger.debug("FileWatcher stopped.")

    def watch(self, folder: str) -> None:
        """Begin watching *folder* (and all subdirectories) for changes."""
        if self._observer is None:
            raise RuntimeError("Call start() before watch()")

        key = str(Path(folder).resolve())
        if key in self._watches:
            return  # already watching

        try:
            from watchdog.events import FileSystemEventHandler  # type: ignore
        except ImportError:
            raise ImportError("watchdog is required: pip install watchdog")

        watcher = self  # captured reference for the handler closure

        class _Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    watcher._schedule(event.src_path, "created")

            def on_modified(self, event):
                if not event.is_directory:
                    watcher._schedule(event.src_path, "modified")

            def on_deleted(self, event):
                if not event.is_directory:
                    watcher._handle_deleted(event.src_path)

            def on_moved(self, event):
                if not event.is_directory:
                    watcher._handle_deleted(event.src_path)
                    watcher._schedule(event.dest_path, "moved")

        watch_handle = self._observer.schedule(_Handler(), key, recursive=True)
        self._watches[key] = watch_handle
        logger.info("Now watching: %s", key)

    def unwatch(self, folder: str) -> None:
        """Stop watching *folder*. Already-indexed data is not removed."""
        key = str(Path(folder).resolve())
        handle = self._watches.pop(key, None)
        if handle is not None and self._observer is not None:
            try:
                self._observer.unschedule(handle)
            except Exception:
                pass
            logger.info("Stopped watching: %s", key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _supported(self, path: str) -> bool:
        return Path(path).suffix.lower() in self._exts

    def _schedule(self, path: str, event_type: str) -> None:
        """Debounce a create/modify/move event and schedule a re-index."""
        if not self._supported(path):
            return
        logger.info("Detected change: [%s] %s", event_type, path)
        with self._lock:
            existing = self._timers.pop(path, None)
            if existing:
                existing.cancel()
            timer = threading.Timer(self._DEBOUNCE_SECONDS, self._do_reindex, args=[path])
            self._timers[path] = timer
            timer.start()

    def _handle_deleted(self, path: str) -> None:
        """Remove a deleted file's chunks from the vector store immediately."""
        if not self._supported(path):
            return
        logger.info("Detected change: [deleted] %s", path)
        # Cancel any pending re-index for this file
        with self._lock:
            existing = self._timers.pop(path, None)
            if existing:
                existing.cancel()
        try:
            doc_id = self._indexer._path_hash(Path(path))
            self._indexer.store.delete_document(doc_id)
            logger.info("Removed from index: %s", path)
        except Exception as exc:
            logger.warning("Failed to remove %s from index: %s", path, exc)

    def _do_reindex(self, path: str) -> None:
        """Called after the debounce delay to actually re-index the file."""
        with self._lock:
            self._timers.pop(path, None)
        try:
            result = self._indexer.index_file(path)
            if result:
                logger.info("Re-indexed: %s", path)
        except Exception as exc:
            logger.warning("Failed to re-index %s: %s", path, exc)

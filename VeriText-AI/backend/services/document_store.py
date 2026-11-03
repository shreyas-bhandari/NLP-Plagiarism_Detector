"""
Short-lived session store for extracted document text.

Why it exists
-------------
The comparison viewer needs the full text of both documents *after* the analysis
has finished, but academic documents may be confidential, so the text must not
become permanent data. This store keeps it for a configurable TTL (default 120
minutes), either in memory only or also on disk, and deletes it when:

* the TTL expires (background sweeper),
* the user deletes the analysis (``DELETE /api/analysis/<id>``),
* the process shuts down (disk files are removed on startup as a safety net).

Persisted analysis records (SQLite) keep only short snippets, so deleting the
session entry really removes the document text from the system.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from config import Config

logger = logging.getLogger(__name__)

_DISK_DIR = Config.STORAGE_DIR / "session"


class DocumentStore:
    def __init__(self) -> None:
        self._items: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._disk_dir = _DISK_DIR
        if Config.SESSION_TEXT_TO_DISK:
            self._disk_dir.mkdir(parents=True, exist_ok=True)
            # Safety net: never resurrect text from a previous run.
            for old in self._disk_dir.glob("*.json"):
                try:
                    old.unlink()
                except OSError:  # pragma: no cover
                    pass
        self._sweeper = threading.Thread(target=self._sweep_loop, name="session-store-sweeper", daemon=True)
        self._sweeper.start()

    # ---------------------------------------------------------------- helpers
    def _ttl_seconds(self) -> int:
        return max(0, Config.SESSION_TEXT_TTL_MINUTES * 60)

    def _pickle_path(self, key: str) -> Path:
        safe = "".join(c for c in key if c.isalnum() or c in "-_")
        return self._disk_dir / f"{safe}.json"

    def _expired(self, entry: Dict[str, Any]) -> bool:
        return entry["expires_at"] < time.time()

    # ------------------------------------------------------------------ write
    def put(self, key: str, kind: str, payload: Dict[str, Any]) -> None:
        ttl = self._ttl_seconds()
        if ttl == 0:
            return  # retention disabled -> text is available only during the request
        entry = {
            "kind": kind,
            "payload": payload,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
        }
        with self._lock:
            self._items[key] = entry
        if Config.SESSION_TEXT_TO_DISK:
            try:
                self._disk_dir.mkdir(parents=True, exist_ok=True)
                self._pickle_path(key).write_text(json.dumps(payload), encoding="utf-8")
            except OSError as exc:  # pragma: no cover
                logger.warning("Could not cache document text on disk: %s", exc)

    # ------------------------------------------------------------------- read
    def get(self, key: str, kind: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._items.get(key)
        if entry is None and Config.SESSION_TEXT_TO_DISK:
            path = self._pickle_path(key)
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    entry = {
                        "kind": kind or "unknown",
                        "payload": payload,
                        "created_at": path.stat().st_mtime,
                        "expires_at": path.stat().st_mtime + self._ttl_seconds(),
                    }
                except (OSError, json.JSONDecodeError):
                    return None
        if entry is None:
            return None
        if self._expired(entry):
            self.delete(key)
            return None
        if kind and entry["kind"] != kind:
            return None
        return entry["payload"]

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = self._items.pop(key, None) is not None
        path = self._pickle_path(key)
        if path.exists():
            try:
                path.unlink()
                existed = True
            except OSError:  # pragma: no cover
                pass
        return existed

    def delete_prefix(self, prefix: str) -> int:
        removed = 0
        with self._lock:
            keys = [k for k in self._items if k.startswith(prefix)]
        for key in keys:
            removed += int(self.delete(key))
        if Config.SESSION_TEXT_TO_DISK and self._disk_dir.exists():
            safe_prefix = "".join(c for c in prefix if c.isalnum() or c in "-_")
            for path in self._disk_dir.glob(f"{safe_prefix}*.json"):
                try:
                    path.unlink()
                    removed += 1
                except OSError:  # pragma: no cover
                    pass
        return removed

    # ------------------------------------------------------------------ housekeeping
    def _sweep_loop(self) -> None:
        while True:
            time.sleep(300)
            try:
                self.sweep()
            except Exception:  # pragma: no cover
                logger.exception("Session store sweep failed")

    def sweep(self) -> int:
        now = time.time()
        removed = 0
        with self._lock:
            expired = [k for k, v in self._items.items() if v["expires_at"] < now]
        for key in expired:
            removed += int(self.delete(key))
        if Config.SESSION_TEXT_TO_DISK and self._disk_dir.exists():
            ttl = self._ttl_seconds()
            for path in self._disk_dir.glob("*.json"):
                try:
                    if now - path.stat().st_mtime > ttl:
                        path.unlink()
                        removed += 1
                except OSError:  # pragma: no cover
                    pass
        if removed:
            logger.info("Purged %s expired session document(s)", removed)
        return removed

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            count = len(self._items)
        disk_files = len(list(self._disk_dir.glob("*.json"))) if self._disk_dir.exists() else 0
        return {
            "session_documents_in_memory": count,
            "session_documents_on_disk": disk_files,
            "retention_minutes": Config.SESSION_TEXT_TTL_MINUTES,
            "disk_retention_enabled": Config.SESSION_TEXT_TO_DISK,
        }

    def clear_all(self) -> None:
        with self._lock:
            self._items.clear()
        if self._disk_dir.exists():
            shutil.rmtree(self._disk_dir, ignore_errors=True)


_store: Optional[DocumentStore] = None
_store_lock = threading.Lock()


def get_store() -> DocumentStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = DocumentStore()
    return _store

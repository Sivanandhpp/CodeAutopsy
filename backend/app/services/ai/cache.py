"""
AI Response Cache
=================
Thread-safe in-memory LRU cache shared by all AI providers.
Keyed on (task_type, input_hash) so the same question always returns
the same answer regardless of which provider handles it.
"""

import hashlib
import logging
import threading
from collections import OrderedDict

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIZE = 300


class AICache:
    """Simple thread-safe LRU cache for AI responses."""

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE):
        self._store: OrderedDict[str, dict] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    # ─── Key generation ──────────────────────────────────────

    @staticmethod
    def make_key(task: str, *parts: str) -> str:
        """
        Build a deterministic cache key.

        Parameters
        ----------
        task : str
            Task identifier, e.g. ``"fix"`` or ``"summary"``.
        *parts : str
            Variable parts that uniquely identify the request
            (code snippet, issue type, language, etc.).
        """
        raw = f"{task}|{'|'.join(parts)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    # ─── CRUD ────────────────────────────────────────────────

    def get(self, key: str) -> dict | None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._hits += 1
                return self._store[key].copy()
            self._misses += 1
            return None

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = value
            else:
                if len(self._store) >= self._max_size:
                    evicted_key, _ = self._store.popitem(last=False)
                    logger.debug("Cache evicted key %s", evicted_key)
                self._store[key] = value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
            }


# ─── Singleton ───────────────────────────────────────────────
ai_cache = AICache()

"""
Thread-safe in-process TTL cache for the Coach Khader dashboard.

Render runs a single gunicorn worker with a handful of threads, so a
process-local cache is shared across every request. This collapses the
dashboard's per-client Google Sheets reads — which are slow and rate-limited —
from "every navigation re-fetches everything" down to "fetch once per TTL
window, in parallel". That is the fix for the sluggish, inconsistent navigation
(issue #7).

Design notes:
  * get_or_fetch(key, ttl, loader) returns a fresh cached value when present,
    otherwise calls loader() once and caches the result.
  * Stale-on-error: if loader() raises but a previous (now-expired) value
    exists, the stale value is returned instead of propagating the error. One
    flaky Sheets call must never blank out a page.
  * Per-key locks prevent a stampede: concurrent requests for the SAME key wait
    on one loader call; different keys still run fully in parallel.
  * A sentinel distinguishes "absent" from a legitimately cached falsy value
    (empty dict / list / None), so empty Sheets data still caches correctly.
"""
import time
import threading
import logging

logger = logging.getLogger(__name__)

_MISS = object()


class TTLCache:
    def __init__(self, max_keys: int = 100) -> None:
        self._store: dict = {}     # key -> (expires_at_monotonic, value)
        self._locks: dict = {}     # key -> threading.Lock (per-key anti-stampede)
        self._guard = threading.Lock()
        self._max_keys = max_keys

    def _key_lock(self, key: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def _peek(self, key: str):
        """Return (value, expires_at) or (_MISS, None) without freshness check."""
        entry = self._store.get(key)
        if entry is None:
            return _MISS, None
        return entry[1], entry[0]

    def get_fresh(self, key: str):
        """Return the value if present and unexpired, else the _MISS sentinel."""
        value, expires_at = self._peek(key)
        if value is _MISS:
            return _MISS
        if time.monotonic() < expires_at:
            return value
        return _MISS

    def set(self, key: str, value, ttl: float) -> None:
        self._store[key] = (time.monotonic() + ttl, value)
        if len(self._store) > self._max_keys:
            # Evict the soonest-to-expire entry to stay under the cap.
            oldest = min(self._store, key=lambda k: self._store[k][0])
            self._store.pop(oldest, None)

    def get_or_fetch(self, key: str, ttl: float, loader, stale_on_error: bool = True):
        """
        Return a fresh cached value, or call loader() once (guarded per key) and
        cache it. On loader failure, fall back to any stale value when allowed.
        """
        fresh = self.get_fresh(key)
        if fresh is not _MISS:
            return fresh

        lock = self._key_lock(key)
        with lock:
            # Re-check inside the lock — another thread may have just refreshed.
            fresh = self.get_fresh(key)
            if fresh is not _MISS:
                return fresh
            try:
                value = loader()
            except Exception:
                stale, _ = self._peek(key)
                if stale_on_error and stale is not _MISS:
                    logger.warning("cache loader failed for %s; serving stale value",
                                   key, exc_info=True)
                    return stale
                raise
            self.set(key, value, ttl)
            return value

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Drop every key starting with prefix (e.g. all entries for a sheet)."""
        for k in [k for k in self._store if k.startswith(prefix)]:
            self._store.pop(k, None)

    def clear(self) -> None:
        self._store.clear()


# Module-level singleton shared by the whole app.
store = TTLCache()

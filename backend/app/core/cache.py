"""Cache genérica com TTL e LRU para resultados custosos.

Suporta: OCR, visão, documentos. Usa hashlib para chaves de imagens.
"""

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    access_count: int = 0
    last_access: float = 0.0


class TTLCache:
    """Cache com TTL (time-to-live) e limite de entradas."""

    def __init__(self, max_size: int = 256, ttl_seconds: int = 3600):
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [
            k for k, v in self._store.items()
            if now - v.created_at > self.ttl_seconds
        ]
        for k in expired:
            del self._store[k]

    def _evict_lru(self) -> None:
        if len(self._store) < self.max_size:
            return
        # Remover a entrada menos recentemente acessada
        lru_key = min(self._store, key=lambda k: self._store[k].last_access)
        del self._store[lru_key]

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return None
            now = time.monotonic()
            if now - entry.created_at > self.ttl_seconds:
                del self._store[key]
                self.misses += 1
                return None
            entry.access_count += 1
            entry.last_access = now
            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._evict_expired()
            self._evict_lru()
            now = time.monotonic()
            self._store[key] = CacheEntry(
                value=value,
                created_at=now,
                last_access=now,
            )

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._store),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": (
                    round(self.hits / (self.hits + self.misses), 3)
                    if (self.hits + self.misses) > 0
                    else 0.0
                ),
            }

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0


# ── Instâncias globais ──────────────────────────────────────────

ocr_cache = TTLCache(max_size=128, ttl_seconds=7200)  # 2h para OCR
vision_cache = TTLCache(max_size=64, ttl_seconds=1800)  # 30min para visão
document_cache = TTLCache(max_size=32, ttl_seconds=86400)  # 24h para docs


def image_hash(image_bytes: bytes) -> str:
    """Hash SHA-256 de bytes de imagem para usar como chave de cache."""
    return hashlib.sha256(image_bytes).hexdigest()[:32]

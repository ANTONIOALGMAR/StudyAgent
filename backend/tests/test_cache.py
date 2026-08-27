"""Testes para o módulo de cache TTL+LRU."""

from app.core.cache import TTLCache, document_cache, image_hash, ocr_cache, vision_cache


class TestTTLCache:
    def test_set_get(self):
        c = TTLCache(max_size=10, ttl_seconds=60)
        c.set("k1", "v1")
        assert c.get("k1") == "v1"

    def test_miss(self):
        c = TTLCache(max_size=10, ttl_seconds=60)
        assert c.get("missing") is None

    def test_stats(self):
        c = TTLCache(max_size=10, ttl_seconds=60)
        c.set("a", 1)
        c.get("a")
        c.get("b")
        s = c.stats()
        assert s["size"] == 1
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["hit_rate"] == 0.5

    def test_clear(self):
        c = TTLCache(max_size=10, ttl_seconds=60)
        c.set("a", 1)
        c.clear()
        assert c.get("a") is None
        s = c.stats()
        assert s["size"] == 0

    def test_lru_eviction(self):
        c = TTLCache(max_size=3, ttl_seconds=3600)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        # Acessar 'a' para torná-lo mais recente
        c.get("a")
        c.set("d", 4)  # Deve evict 'b' (menos acessado)
        assert c.get("b") is None
        assert c.get("a") == 1

    def test_ttl_expiry(self):
        import time
        c = TTLCache(max_size=10, ttl_seconds=0)  # TTL = 0 → expira imediatamente
        c.set("k", "v")
        time.sleep(0.01)
        assert c.get("k") is None


class TestImageHash:
    def test_deterministic(self):
        data = b"test image data"
        h1 = image_hash(data)
        h2 = image_hash(data)
        assert h1 == h2

    def test_different_inputs(self):
        h1 = image_hash(b"image1")
        h2 = image_hash(b"image2")
        assert h1 != h2

    def test_length(self):
        h = image_hash(b"test")
        assert len(h) == 32


class TestGlobalCaches:
    def test_ocr_cache_exists(self):
        assert ocr_cache is not None
        assert ocr_cache.max_size == 128

    def test_vision_cache_exists(self):
        assert vision_cache is not None
        assert vision_cache.max_size == 64

    def test_document_cache_exists(self):
        assert document_cache is not None
        assert document_cache.max_size == 32

    def test_ocr_cache_set_get(self):
        ocr_cache.set("test_ocr_key", "ocr result")
        assert ocr_cache.get("test_ocr_key") == "ocr result"
        ocr_cache.clear()

    def test_overwrite_key(self):
        c = TTLCache(max_size=10, ttl_seconds=60)
        c.set("k", "v1")
        c.set("k", "v2")
        assert c.get("k") == "v2"

    def test_many_evictions(self):
        c = TTLCache(max_size=2, ttl_seconds=3600)
        for i in range(10):
            c.set(f"k{i}", i)
        assert c.stats()["size"] == 2
        assert c.get("k9") == 9

    def test_empty_cache_stats(self):
        c = TTLCache(max_size=5, ttl_seconds=60)
        s = c.stats()
        assert s["size"] == 0
        assert s["hits"] == 0
        assert s["misses"] == 0
        assert s["hit_rate"] == 0.0

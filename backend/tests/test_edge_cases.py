"""Testes de edge cases para cache, context manager, e RAG."""

import threading
import time

import numpy as np
import pytest

from app.core.cache import TTLCache, image_hash


# ── Cache Edge Cases ──────────────────────────────────────────────


class TestCacheEdgeCases:
    def test_concurrent_access(self):
        """Cache deve ser thread-safe."""
        c = TTLCache(max_size=50, ttl_seconds=60)
        errors = []

        def writer(n):
            try:
                for i in range(100):
                    c.set(f"t{n}_{i}", i)
            except Exception as e:
                errors.append(e)

        def reader(n):
            try:
                for i in range(100):
                    c.get(f"t{n}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        threads += [threading.Thread(target=reader, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

    def test_large_value(self):
        """Cache deve lidar com valores grandes."""
        c = TTLCache(max_size=10, ttl_seconds=60)
        big = "x" * 1_000_000
        c.set("big", big)
        assert c.get("big") == big

    def test_none_value(self):
        """Cache deve aceitar None como valor."""
        c = TTLCache(max_size=10, ttl_seconds=60)
        c.set("n", None)
        assert "n" in c._store

    def test_unicode_keys(self):
        """Cache deve lidar com chaves unicode."""
        c = TTLCache(max_size=10, ttl_seconds=60)
        c.set("chave_ñ", "valor")
        assert c.get("chave_ñ") == "valor"

    def test_stats_accuracy(self):
        """Stats devem ser precisos após muitas operações."""
        c = TTLCache(max_size=100, ttl_seconds=60)
        for i in range(50):
            c.set(f"k{i}", i)
        # 25 hits (existentes) + 25 misses (não-existentes)
        for i in range(25):
            c.get(f"k{i}")
        for i in range(25):
            c.get(f"missing_{i}")
        s = c.stats()
        assert s["hits"] == 25
        assert s["misses"] == 25
        assert s["hit_rate"] == 0.5

    def test_ttl_different_per_entry(self):
        """Entradas com TTL diferente devem expirar independentemente."""
        c = TTLCache(max_size=10, ttl_seconds=10)
        c.set("long", "v1")
        c.set("short", "v2")
        c._store["short"].created_at = time.monotonic() - 11
        assert c.get("long") is not None
        assert c.get("short") is None


# ── Image Hash Edge Cases ────────────────────────────────────────


class TestImageHashEdgeCases:
    def test_empty_bytes(self):
        h = image_hash(b"")
        assert len(h) == 32

    def test_large_image(self):
        data = bytes(range(256)) * 10000
        h = image_hash(data)
        assert len(h) == 32

    def test_deterministic_across_calls(self):
        data = b"test data for hashing"
        hashes = {image_hash(data) for _ in range(100)}
        assert len(hashes) == 1


# ── Context Manager Edge Cases ────────────────────────────────────


class TestContextManagerEdgeCases:
    def test_trim_history(self):
        """_trim_history deve remover mensagens mais antigas."""
        from app.core.context_manager import ContextManager, MAX_CONTEXT_CHARS, CHARS_PER_TOKEN
        cm = ContextManager.__new__(ContextManager)
        # Primeira mensagem é system (mantida), depois user/assistant
        history = [
            {"role": "system", "content": "Você é um tutor."},
            {"role": "user", "content": "A" * 1000},
            {"role": "assistant", "content": "B" * 1000},
            {"role": "user", "content": "C" * 1000},
        ]
        # max_chars pequeno para forçar trim
        trimmed = cm._trim_history(history, max_chars=500)
        # System message deve ser mantida
        assert trimmed[0]["role"] == "system"
        # Deve ter removido mensagens antigas
        assert len(trimmed) < len(history)

    def test_estimate_tokens_basic(self):
        from app.core.context_manager import _estimate_tokens
        assert _estimate_tokens("hello") > 0
        assert _estimate_tokens("") == 0

    def test_estimate_tokens_proportional(self):
        from app.core.context_manager import _estimate_tokens
        short = _estimate_tokens("hi")
        long = _estimate_tokens("hello world this is a longer text")
        assert long > short


# ── RAG Edge Cases ────────────────────────────────────────────────


class TestRAGEdgeCases:
    def test_chunk_document_empty(self):
        from app.tools.rag import chunk_document
        chunks = chunk_document("")
        assert chunks == []

    def test_chunk_document_with_pages(self):
        from app.tools.rag import chunk_document
        text = "[página 1]\n" + "Conteúdo da página um. " * 10 + "\n[página 2]\n" + "Conteúdo da página dois. " * 10
        chunks = chunk_document(text)
        assert len(chunks) >= 2
        assert chunks[0]["page"] == 1
        assert chunks[1]["page"] == 2

    def test_chunk_document_heading_detection(self):
        from app.tools.rag import chunk_document
        text = "# Capítulo 1\n" + "Conteúdo do capítulo. " * 10
        chunks = chunk_document(text)
        assert len(chunks) >= 1
        assert "heading" in chunks[0]

    def test_has_index_false(self):
        from app.tools.rag import has_index
        assert has_index("nonexistent_doc_12345") is False


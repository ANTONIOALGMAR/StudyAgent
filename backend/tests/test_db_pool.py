"""Testes do pool limitado de conexões SQLite (`app.db`, pool v2).

Cobertura:
- Pool com tamanho fixo (bounded) e estatísticas (`stats`);
- Aquisição sticky por thread: chamadas aninhadas reutilizam a MESMA
  conexão real (sem deadlock por reentrância);
- Devolução automática ao pool: `with`, `close()` e liberação por
  garbage collection do proxy (weakref.finalize, determinístico no CPython);
- TimeoutError quando o pool está esgotado entre threads;
- `db_session` / `db_cursor` (commit/rollback automático);
- Ciclo de vida: `close_all()` / `reset_pools()`.
"""

from __future__ import annotations

import gc
import threading

import pytest

from app import db


@pytest.fixture(autouse=True)
def _isolated_pools():
    """Cada teste parte de um registro global de pools limpo."""
    db.reset_pools()
    yield
    db.reset_pools()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "pool_test.db"


class TestPoolBasics:
    def test_get_pool_same_instance_per_path(self, db_path):
        assert db.get_pool(db_path) is db.get_pool(db_path)

    def test_stats_shape(self, db_path):
        pool = db.ConnectionPool(db_path, size=4)
        try:
            stats = pool.stats()
        finally:
            pool.close_all()
        assert stats["pool_size"] == 4
        assert stats["opened"] == 0
        assert stats["idle"] == 0
        assert stats["closed"] is False
        assert stats["db_path"] == str(db_path)

    def test_proxy_forwards_sqlite_api(self, db_path):
        conn = db.get_connection(db_path)
        try:
            assert conn.execute("SELECT 1 + 1").fetchone()[0] == 2
        finally:
            conn.close()


class TestStickyAcquire:
    def test_nested_acquire_same_thread_reuses_connection(self, db_path):
        pool = db.ConnectionPool(db_path, size=4)
        try:
            c1 = pool.acquire()
            c2 = pool.acquire()  # aninhada na mesma thread
            assert c2 is c1  # reutiliza a MESMA conexão (refcount 2)
            pool.release(c2)
            assert pool.stats()["idle"] == 0  # ainda emprestada (refcount 1)
            pool.release(c1)
            assert pool.stats()["idle"] == 1  # devolvida ao pool
        finally:
            pool.close_all()

    def test_pool_enforces_max_size_across_threads(self, db_path):
        """Pool limitado: a 3ª thread não consegue conexão (timeout)."""
        pool = db.ConnectionPool(db_path, size=2)
        try:
            holder: dict = {}

            def take():
                holder["t1"] = pool.acquire()

            t1 = threading.Thread(target=take)
            t1.start()
            t1.join(timeout=5)
            holder["main"] = pool.acquire()  # 2ª conexão (limite atingido)

            assert pool.stats()["opened"] == 2
            assert pool.stats()["idle"] == 0

            err: dict = {}

            def try_acquire():
                try:
                    pool.acquire(timeout=0.3)
                except TimeoutError as exc:
                    err["exc"] = exc

            t2 = threading.Thread(target=try_acquire)
            t2.start()
            t2.join(timeout=5)
            assert isinstance(err.get("exc"), TimeoutError)
            assert "esgotado" in str(err["exc"])
        finally:
            pool.close_all()


class TestAutoRelease:
    def test_db_session_releases_back_to_pool(self, db_path):
        pool = db.get_pool(db_path)
        with db.db_session(db_path) as conn:
            conn.execute("SELECT 1")
            assert pool.stats()["idle"] == 0
        assert pool.stats()["idle"] == 1

    def test_close_releases_back_to_pool(self, db_path):
        pool = db.get_pool(db_path)
        conn = db.get_connection(db_path)
        conn.close()
        assert pool.stats()["idle"] == 1

    def test_proxy_auto_release_when_unref(self, db_path):
        """Sem `with`: o proxy devolve a conexão ao sair de escopo (CPython)."""
        pool = db.get_pool(db_path)

        def use():
            conn = db.get_connection(db_path)
            conn.execute("SELECT 1")
            # ao retornar, `conn` não tem mais referências → finalize → release

        use()
        gc.collect()
        assert pool.stats()["idle"] == 1


class TestDbCursor:
    def test_commits_on_success(self, db_path):
        with db.db_cursor(db_path) as cur:
            cur.execute("CREATE TABLE t (x INTEGER)")
            cur.execute("INSERT INTO t VALUES (42)")

        conn = db.get_connection(db_path)
        try:
            assert conn.execute("SELECT x FROM t").fetchone()[0] == 42
        finally:
            conn.close()

    def test_rolls_back_on_error(self, db_path):
        with db.db_cursor(db_path) as cur:
            cur.execute("CREATE TABLE t (x INTEGER)")

        with pytest.raises(RuntimeError, match="boom"):
            with db.db_cursor(db_path) as cur:
                cur.execute("INSERT INTO t VALUES (1)")
                raise RuntimeError("boom")

        conn = db.get_connection(db_path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0
        finally:
            conn.close()


class TestLifecycle:
    def test_close_all_marks_pool_closed(self, db_path):
        pool = db.get_pool(db_path)
        db.close_all()
        assert pool.stats()["closed"] is True

    def test_reset_pools_allows_fresh_pool(self, db_path):
        old = db.get_pool(db_path)
        db.reset_pools()
        new = db.get_pool(db_path)
        assert new is not old
        assert new.stats()["closed"] is False

        conn = db.get_connection(db_path)
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        assert new.stats()["idle"] == 1

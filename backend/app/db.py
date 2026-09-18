"""Conexão SQLite centralizada com WAL mode e pool limitado (bounded pool).

Substitui os _conn() duplicados em cada módulo tutor.

Design (v2 — pool):
- `ConnectionPool` mantém no máximo N conexões por arquivo de banco
  (default 16, configurável via `STUDYAGENT_DB_POOL_SIZE`), protegendo o
  processo de esgotar file handles sob carga (FastAPI roda handlers em um
  threadpool de ~40 threads — o modelo antigo, thread-local, criava até
  uma conexão por thread sem limite global).
- Aquisição "sticky" por thread: chamadas aninhadas na mesma thread
  reutilizam a MESMA conexão (referência contada), exatamente como no
  modelo thread-local antigo — sem deadlock por reentrância.
- `get_connection()` mantém a mesma assinatura/semântica das versões
  anteriores: retorna um proxy que devolve a conexão ao pool automaticamente
  quando para de ser referenciado (fim do escopo da função chamada) ou
  quando usado como context manager (`with get_connection() as conn:`).

API pública:
- get_connection(db_path)  → proxy com a API do sqlite3.Connection
- db_session(db_path)      → context manager (aquisição explícita)
- db_cursor(db_path)       → context manager com commit/rollback automático
- close_all()              → encerra todos os pools (shutdown/testes)
"""

from __future__ import annotations

import os
import sqlite3
import threading
import weakref
from contextlib import contextmanager
from pathlib import Path
from queue import Empty, Queue

from .config import MEMORY_DB_PATH

_DEFAULT_POOL_SIZE = max(1, int(os.getenv("STUDYAGENT_DB_POOL_SIZE", "16")))
_ACQUIRE_TIMEOUT_S = float(os.getenv("STUDYAGENT_DB_ACQUIRE_TIMEOUT", "10"))


class ConnectionPool:
    """Pool limitado de conexões sqlite3, thread-safe.

    - Tamanho fixo (default `_DEFAULT_POOL_SIZE`) por caminho de banco.
    - Aquisição sticky por thread: a mesma thread que já tem uma conexão
      emprestada reutiliza-a (refcount), evitando consumo de N conexões
      em chamadas aninhadas e deadlocks.
    - `acquire` bloqueia até o timeout quando o pool está esgotado
      (em vez de criar conexões sem limite).
    """

    def __init__(self, db_path: Path | str, size: int | None = None):
        self.db_path = str(db_path)
        self.size = max(1, size or _DEFAULT_POOL_SIZE)
        self._queue: Queue[sqlite3.Connection] = Queue(maxsize=self.size)
        self._all: list[sqlite3.Connection] = []
        self._lock = threading.Lock()
        self._closed = False
        self._local = threading.local()

    # ── Aquisição / liberação ─────────────────────────────────────

    def acquire(self, timeout: float | None = None) -> sqlite3.Connection:
        """Empresta uma conexão (sticky por thread, refcount)."""
        slot = getattr(self._local, "slot", None)
        if slot is not None:
            slot["refcount"] += 1
            return slot["conn"]

        conn = self._acquire_from_pool(
            _ACQUIRE_TIMEOUT_S if timeout is None else timeout
        )
        self._local.slot = {"conn": conn, "refcount": 1}
        return conn

    def release(self, conn: sqlite3.Connection) -> None:
        """Devolve a conexão emprestada na thread atual (refcount)."""
        slot = getattr(self._local, "slot", None)
        if slot is not None and slot["conn"] is conn:
            slot["refcount"] -= 1
            if slot["refcount"] > 0:
                return
            self._local.slot = None
        self._return_to_pool(conn)

    # ── Internos ──────────────────────────────────────────────────

    def _acquire_from_pool(self, timeout: float) -> sqlite3.Connection:
        try:
            return self._queue.get_nowait()
        except Empty:
            pass
        with self._lock:
            if not self._closed and len(self._all) < self.size:
                conn = self._new_connection()
                self._all.append(conn)
                return conn
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            raise TimeoutError(
                f"Pool de conexões esgotado ({self.size}) após {timeout}s: {self.db_path}"
            )

    def _return_to_pool(self, conn: sqlite3.Connection) -> None:
        if self._closed:
            try:
                conn.close()
            except Exception:
                pass
            return
        try:
            self._queue.put_nowait(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ── Ciclo de vida ─────────────────────────────────────────────

    def close_all(self) -> None:
        """Encerra o pool e todas as conexões (shutdown)."""
        with self._lock:
            self._closed = True
            all_conns = list(self._all)
            self._all.clear()
        while True:
            try:
                all_conns.append(self._queue.get_nowait())
            except Empty:
                break
        for conn in all_conns:
            try:
                conn.close()
            except Exception:
                pass

    def stats(self) -> dict:
        """Métricas simples para observabilidade/health."""
        with self._lock:
            total = len(self._all)
        return {
            "db_path": self.db_path,
            "pool_size": self.size,
            "opened": total,
            "idle": self._queue.qsize(),
            "closed": self._closed,
        }


# ── Registro global de pools (um por caminho de banco) ────────────

_pools: dict[str, ConnectionPool] = {}
_pools_lock = threading.Lock()


def get_pool(
    db_path: Path | str = MEMORY_DB_PATH, size: int | None = None
) -> ConnectionPool:
    """Retorna (criando se necessário) o pool para o caminho de banco."""
    key = str(db_path)
    with _pools_lock:
        pool = _pools.get(key)
        if pool is None:
            pool = ConnectionPool(db_path, size=size)
            _pools[key] = pool
        return pool


def reset_pools() -> None:
    """Fecha e descarta todos os pools (testes/shutdown)."""
    with _pools_lock:
        pools = list(_pools.values())
        _pools.clear()
    for pool in pools:
        pool.close_all()


# ── Proxy com devolução automática ao pool ─────────────────────────


class PooledConnection:
    """Proxy transparente para `sqlite3.Connection` com release automático.

    - `with get_connection() as conn:` → devolve ao pool no `with`.
    - Sem `with`: `weakref.finalize` devolve ao pool quando o proxy deixa
      de ser referenciado (fim do escopo da função que a obteve) — no
      CPython isso é determinístico por contagem de referências.

    Toda chamada não-listada abaixo é encaminhada à conexão real.
    """

    __slots__ = ("_pool", "_conn", "_released", "__weakref__")

    def __init__(self, pool: ConnectionPool, conn: sqlite3.Connection):
        object.__setattr__(self, "_pool", pool)
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_released", False)
        weakref.finalize(self, pool.release, conn)

    def _release(self) -> None:
        if not self._released:
            object.__setattr__(self, "_released", True)
            self._pool.release(self._conn)

    def close(self) -> None:
        self._release()

    def __enter__(self) -> "PooledConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._release()
        return False

    def __getattr__(self, name: str):
        return getattr(object.__getattribute__(self, "_conn"), name)

    def __setattr__(self, name: str, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "_conn"), name, value)

    def __repr__(self) -> str:
        return f"<PooledConnection {self._pool.db_path}>"


# ── API pública (mesma superfície das versões anteriores) ──────────


def get_connection(db_path: Path | str = MEMORY_DB_PATH) -> PooledConnection:
    """Empresta uma conexão do pool (API compatível com a versão antiga).

    A conexão é devolvida ao pool automaticamente quando o proxy deixa de
    ser referenciado, ou imediatamente se usado como context manager.
    """
    pool = get_pool(db_path)
    return PooledConnection(pool, pool.acquire())


@contextmanager
def db_session(db_path: Path | str = MEMORY_DB_PATH):
    """Context manager explícito: `with db_session() as conn:`."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def db_cursor(db_path: Path | str = MEMORY_DB_PATH):
    """Context manager yielding um cursor com commit/rollback automático."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()


def close_all() -> None:
    """Encerra todos os pools (shutdown gracioso)."""
    reset_pools()


# ── Compatibilidade ────────────────────────────────────────────────
# O modelo antigo usava um thread-local (`_local.conns`) como cache.
# Mantido apenas para compatibilidade com código/testes antigos que o
# importam; a pool v2 não usa mais esse cache.


class _LegacyThreadLocal:
    conns: dict = {}


_local = _LegacyThreadLocal()


__all__ = [
    "ConnectionPool",
    "PooledConnection",
    "close_all",
    "db_cursor",
    "db_session",
    "get_connection",
    "get_pool",
    "reset_pools",
]
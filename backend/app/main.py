"""StudyAgent — FastAPI entry point.

Versão 2.0: endpoints movidos para routers/, DB centralizado em db.py.
Rate limiting via slowapi para proteção contra abuso.
Structured logging com request context propagation.
Graceful shutdown com cleanup de recursos.
"""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .core.structured_logging import (
    new_request_id,
    setup_structured_logging,
)
from .routers import audio, chat, documents, exercises, facial, health, screen, tutor

log = logging.getLogger("studyagent.startup")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="StudyAgent", version="2.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Structured logging setup ─────────────────────────────────────
setup_structured_logging()

# ── Environment validation on startup ────────────────────────────
try:
    from .core.env_validation import validate_environment
    validate_environment()
except Exception as exc:
    log.warning("Env validation skipped: %s", exc)

# ── Middleware: request_id + timing ──────────────────────────────


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    rid = new_request_id()
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    response.headers["X-Request-ID"] = rid
    response.headers["X-Duration-MS"] = f"{duration_ms:.1f}"
    return response


# ── CORS ─────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────

app.include_router(chat.router)
app.include_router(screen.router)
app.include_router(exercises.router)
app.include_router(documents.router)
app.include_router(audio.router)
app.include_router(tutor.router)
app.include_router(health.router)
app.include_router(facial.router)


# ── Graceful Shutdown ────────────────────────────────────────────


@app.on_event("startup")
async def on_startup():
    log.info("[STARTUP] StudyAgent v2.0 starting...")


@app.on_event("shutdown")
async def on_shutdown():
    log.info("[SHUTDOWN] StudyAgent shutting down gracefully...")
    # Flush any pending writes
    try:
        from .db import _local
        for conn in _local.conns.values():
            try:
                conn.close()
            except Exception:
                pass
        _local.conns.clear()
    except Exception:
        pass
    log.info("[SHUTDOWN] Cleanup complete.")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("[ERROR] Unhandled: %s %s", type(exc).__name__, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor"},
    )

"""StudyAgent — FastAPI entry point.

Versão 2.0: endpoints movidos para routers/, DB centralizado em db.py.
Rate limiting via slowapi para proteção contra abuso.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .routers import audio, chat, documents, exercises, screen, tutor

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="StudyAgent", version="2.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(screen.router)
app.include_router(exercises.router)
app.include_router(documents.router)
app.include_router(audio.router)
app.include_router(tutor.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor"},
    )

"""StudyAgent — FastAPI entry point.

Versão 2.0: endpoints movidos para routers/, DB centralizado em db.py.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import audio, chat, documents, exercises, screen, tutor

app = FastAPI(title="StudyAgent", version="2.0.0")

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

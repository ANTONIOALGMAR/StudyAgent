"""Router: Áudio (transcrição e fala)."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from ..agent.agent import PermissionDeniedError
from ..audio import speech_to_text, text_to_speech
from ..security.permissions import PermissionManager
from .audio_stream import audio_stream_generator

router = APIRouter(prefix="/api")
permissions = PermissionManager()


class SpeakRequest(BaseModel):
    text: str


@router.post("/audio/transcribe")
async def transcribe(file: UploadFile = File(...)):  # noqa: B008
    try:
        permissions.require("microphone")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="áudio vazio")
    text = await run_in_threadpool(speech_to_text.transcribe, audio_bytes, file.filename or "audio.webm")
    return {"text": text}


@router.post("/audio/speak")
def speak(req: SpeakRequest):
    try:
        wav = text_to_speech.synthesize(req.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=wav, media_type="audio/wav")


@router.post("/audio/stream")
async def speak_stream(messages: list, images: list[str] = None):
    """
    Endpoint de streaming de voz. 
    Recebe a conversa, gera texto via LLM e retorna áudio em chunks.
    """
    try:
        permissions.require("microphone")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
        
    return StreamingResponse(
        audio_stream_generator(messages, images), 
        media_type="audio/wav"
    )

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .agent.agent import PermissionDeniedError, StudyAgent
from .audio import speech_to_text, text_to_speech
from .security.permissions import PermissionManager
from .vision.screen import image_to_base64

app = FastAPI(title="StudyAgent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = StudyAgent()
permissions = PermissionManager()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    use_screen: bool = False
    region: dict | None = None
    monitor: int = 1
    image_b64: str | None = None


class AnalyzeScreenRequest(BaseModel):
    question: str | None = None
    session_id: str | None = None
    region: dict | None = None
    monitor: int = 1


class PermissionUpdate(BaseModel):
    value: bool


class CalculateRequest(BaseModel):
    expression: str


@app.get("/api/health")
def health():
    return {"status": "ok", **agent.status()}


@app.get("/api/permissions")
def get_permissions():
    return permissions.all()


@app.put("/api/permissions/{name}")
def set_permission(name: str, body: PermissionUpdate):
    try:
        permissions.set(name, body.value)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"permissão desconhecida: {name}")
    return {name: body.value}


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        if req.image_b64:
            permissions.require("camera")
        return agent.process(
            req.message,
            session_id=req.session_id,
            use_screen=req.use_screen,
            region=req.region,
            monitor=req.monitor,
            image_b64=req.image_b64,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@app.post("/api/screen/capture")
def screen_capture(region: dict | None = None, monitor: int = 1):
    try:
        shot, info = agent.capture_and_read_screen(region=region, monitor=monitor)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"image_b64": image_to_base64(shot).decode("ascii"), **info}


@app.post("/api/screen/analyze")
def screen_analyze(req: AnalyzeScreenRequest):
    try:
        result = agent.analyze_screen(
            req.question,
            session_id=req.session_id,
            region=req.region,
            monitor=req.monitor,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return result


@app.post("/api/calculate")
def calculate(req: CalculateRequest):
    try:
        return {"result": agent.calculate(req.expression)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/sessions")
def sessions():
    return agent.memory.list_sessions()


@app.get("/api/sessions/{session_id}/messages")
def session_messages(session_id: str):
    return agent.memory.history(session_id, limit=200)


class SpeakRequest(BaseModel):
    text: str


@app.post("/api/audio/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        permissions.require("microphone")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="áudio vazio")
    text = await run_in_threadpool(speech_to_text.transcribe, audio_bytes, file.filename or "audio.webm")
    return {"text": text}


@app.post("/api/audio/speak")
def speak(req: SpeakRequest):
    try:
        wav = text_to_speech.synthesize(req.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return Response(content=wav, media_type="audio/wav")

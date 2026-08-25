import base64
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .agent import exercises
from .agent.agent import PermissionDeniedError, StudyAgent
from .audio import speech_to_text, text_to_speech
from .config import DOCUMENTS_DIR as documents_dir
from .security.permissions import PermissionManager
from .vision import screen
from .vision.screen import image_to_base64, image_to_jpeg_base64

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
    doc_id: str | None = None


class AnalyzeScreenRequest(BaseModel):
    question: str | None = None
    session_id: str | None = None
    region: dict | None = None
    monitor: int = 1


class PermissionUpdate(BaseModel):
    value: bool


class CalculateRequest(BaseModel):
    expression: str


class ExerciseGenerateRequest(BaseModel):
    topic: str
    n: int = 4
    level: str = "ensino fundamental"


class ExerciseGradeRequest(BaseModel):
    exercise_id: str
    answers: dict[str, str]


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
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"permissão desconhecida: {name}") from exc
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
            doc_id=req.doc_id,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/api/screen/capture")
def screen_capture(region: dict | None = None, monitor: int = 1):
    try:
        shot, info = agent.capture_and_read_screen(region=region, monitor=monitor)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"image_b64": base64.b64encode(image_to_base64(shot)).decode("ascii"), **info}


@app.get("/api/screen/monitors")
def screen_monitors():
    return {"monitors": screen.list_monitors()}


@app.get("/api/screen/preview")
def screen_preview(monitor: int = 0):
    try:
        permissions.require("screen_capture")
        shot = screen.capture(monitor=monitor)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    jpeg = image_to_jpeg_base64(shot)
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


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
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return result


@app.post("/api/calculate")
def calculate(req: CalculateRequest):
    try:
        return {"result": agent.calculate(req.expression)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions")
def sessions():
    return agent.memory.list_sessions()


@app.get("/api/sessions/{session_id}/messages")
def session_messages(session_id: str):
    return agent.memory.history(session_id, limit=200)


class SpeakRequest(BaseModel):
    text: str


@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        permissions.require("file_access")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    import uuid as uuid_mod

    from .tools.documents import extract_pdf

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="arquivo vazio")
    name = file.filename or "documento"
    suffix = Path(name).suffix.lower()
    if suffix not in (".pdf", ".txt", ".md"):
        raise HTTPException(status_code=400, detail="formatos aceitos: pdf, txt, md")
    save_path = Path(documents_dir) / f"{uuid_mod.uuid4().hex[:8]}{suffix}"
    save_path.write_bytes(raw)
    if suffix == ".pdf":
        try:
            pages, text = extract_pdf(save_path)
        except Exception as exc:
            save_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"PDF inválido: {exc}") from exc
        save_path.with_suffix(".txt").write_text(text, encoding="utf-8")
    else:
        pages = 1
        text = raw.decode("utf-8", errors="ignore")
    doc_id = agent.memory.add_document(name, str(save_path), pages, len(text))
    return {"id": doc_id, "name": name, "pages": pages, "chars": len(text)}


@app.post("/api/audio/transcribe")
async def transcribe(file: UploadFile = File(...)):
    try:
        permissions.require("microphone")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
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
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(content=wav, media_type="audio/wav")


@app.post("/api/exercises/generate")
def exercises_generate(req: ExerciseGenerateRequest):
    try:
        return exercises.generate(topic=req.topic, n=req.n, level=req.level)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar exercícios: {exc}") from exc


@app.post("/api/exercises/grade")
def exercises_grade(req: ExerciseGradeRequest):
    try:
        return exercises.grade(exercise_id=req.exercise_id, answers=req.answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: str):
    doc = agent.memory.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    path = Path(doc["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado no disco")
    from fastapi.responses import FileResponse

    return FileResponse(
        path,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{doc["name"]}"',
            "Cache-Control": "private, max-age=3600",
        },
    )


def _doc_parts(doc_id: str):
    """Partes de narração do documento (uma por página ou ~1800 chars)."""
    doc = agent.memory.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="documento não encontrado")
    from pathlib import Path as _Path

    from .tools.documents import load_document_text, split_narration

    path = _Path(doc["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="arquivo não encontrado no disco")
    _, text = load_document_text(path)
    return doc, split_narration(text)


@app.get("/api/documents/{doc_id}/audio/plan")
def document_audio_plan(doc_id: str):
    try:
        permissions.require("file_access")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    doc, partes = _doc_parts(doc_id)
    if not partes:
        raise HTTPException(status_code=400, detail="documento sem texto legível")
    kind = "página" if (doc["pages"] or 1) > 1 else "parte"
    return {"total": len(partes), "kind": kind, "name": doc["name"]}


@app.get("/api/documents/{doc_id}/audio")
async def document_audio(doc_id: str, idx: int = 0):
    try:
        permissions.require("file_access")
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    _, partes = _doc_parts(doc_id)
    if not 0 <= idx < len(partes):
        raise HTTPException(status_code=404, detail=f"parte {idx} fora do alcance")
    wav = await run_in_threadpool(text_to_speech.synthesize, partes[idx])
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )

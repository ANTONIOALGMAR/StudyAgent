import base64
import json
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
from .tutor import advanced_profile, automation, export_import, flashcards, gamification, profile, study_plan
from .tutor import stats as tutor_stats
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


class FlashcardGenerateRequest(BaseModel):
    topic: str
    n: int = 10
    level: str = "ensino fundamental"


class FlashcardReviewRequest(BaseModel):
    card_id: str
    difficulty: str


class StudyPlanRequest(BaseModel):
    topic: str
    level: str = "ensino fundamental"


class ProfileRequest(BaseModel):
    name: str = ""
    grade: str = ""
    school: str = ""
    preferences: str = ""


class ActionProposalRequest(BaseModel):
    action_type: str
    params: dict = {}
    description: str = ""


class ProposalRejectRequest(BaseModel):
    reason: str = ""


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
        result = exercises.grade_and_track(exercise_id=req.exercise_id, answers=req.answers)
        return result
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Tutor: Flashcards ──────────────────────────────────────────────────────────


@app.get("/api/flashcards/decks")
def flashcard_deck_list():
    return flashcards.list_decks()


@app.get("/api/flashcards/decks/{deck_id}/stats")
def flashcard_deck_stats(deck_id: str):
    return flashcards.deck_stats(deck_id)


@app.post("/api/flashcards/generate")
def flashcard_generate(req: FlashcardGenerateRequest):
    try:
        return flashcards.generate_deck(
            topic=req.topic, n=req.n, level=req.level,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/flashcards/decks/{deck_id}/due")
def flashcard_due(deck_id: str, limit: int = 20):
    return flashcards.due_cards(deck_id, limit=limit)


@app.post("/api/flashcards/review")
def flashcard_review(req: FlashcardReviewRequest):
    try:
        return flashcards.review_card(req.card_id, req.difficulty)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Tutor: Study Plans ─────────────────────────────────────────────────────────


@app.get("/api/study-plans")
def study_plan_list():
    return study_plan.list_plans()


@app.post("/api/study-plans/generate")
def study_plan_generate(req: StudyPlanRequest):
    try:
        return study_plan.generate_plan(topic=req.topic, level=req.level)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/study-plans/{plan_id}")
def study_plan_get(plan_id: str):
    plan = study_plan.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plan


@app.post("/api/study-plans/items/{item_id}/toggle")
def study_plan_toggle(item_id: int):
    try:
        return study_plan.toggle_item(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Tutor: Stats ───────────────────────────────────────────────────────────────


@app.get("/api/stats/dashboard")
def stats_dashboard():
    return tutor_stats.dashboard()


# ── P6: Perfil do aluno ────────────────────────────────────────────────────────


@app.get("/api/profile")
def profile_get():
    return profile.get_profile() or {"name": "", "grade": "", "school": "", "preferences": ""}


@app.post("/api/profile")
def profile_save(req: ProfileRequest):
    return profile.save_profile(
        name=req.name, grade=req.grade, school=req.school, preferences=req.preferences,
    )


@app.get("/api/profile/insights")
def profile_insights():
    return profile.profile_insights()


@app.get("/api/mastery")
def mastery_list():
    return profile.all_mastery()


@app.get("/api/mastery/{topic}")
def mastery_detail(topic: str):
    result = profile.topic_details(topic)
    if not result:
        raise HTTPException(status_code=404, detail="Tema não encontrado")
    return result


# ── P7: Automação com confirmação ──────────────────────────────────────────────


@app.post("/api/actions/propose")
def action_propose(req: ActionProposalRequest):
    try:
        return automation.create_proposal(req.action_type, req.params, req.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/actions/{proposal_id}/approve")
def action_approve(proposal_id: str):
    try:
        return automation.approve(proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/actions/{proposal_id}/reject")
def action_reject(proposal_id: str, body: ProposalRejectRequest = ProposalRejectRequest()):
    return automation.reject(proposal_id, reason=body.reason)


@app.get("/api/actions/pending")
def action_pending():
    return automation.get_pending()


@app.get("/api/actions/recent")
def action_recent(limit: int = 10):
    return automation.list_recent(limit=limit)


# ── P8: Perfil avançado ────────────────────────────────────────────────────────


class SessionStartRequest(BaseModel):
    session_type: str
    metadata: dict = {}


@app.post("/api/sessions/start")
def session_start(req: SessionStartRequest):
    session_id = advanced_profile.start_session(req.session_type, req.metadata)
    return {"session_id": session_id}


@app.post("/api/sessions/{session_id}/end")
def session_end(session_id: str):
    try:
        return advanced_profile.end_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/stats/time-analytics")
def time_analytics():
    return advanced_profile.time_analytics()


@app.get("/api/recommendations/{minutes}")
def recommendations(minutes: int):
    return advanced_profile.recommend_for_time(minutes)


@app.get("/api/mastery/{topic}/difficulty")
def mastery_difficulty(topic: str):
    return advanced_profile.get_adaptive_difficulty(topic)


@app.post("/api/mastery/{topic}/difficulty")
def mastery_update_difficulty(topic: str):
    topic_data = profile.topic_details(topic)
    if not topic_data:
        raise HTTPException(status_code=404, detail="Tema não encontrado")
    return advanced_profile.update_difficulty(topic, topic_data["avg_percent"])


# ── P9: Gamificação ────────────────────────────────────────────────────────────


@app.get("/api/achievements")
def achievements_list():
    return gamification.list_achievements()


@app.get("/api/achievements/progress")
def achievements_progress():
    return gamification.achievement_progress()


@app.get("/api/achievements/check")
def achievements_check():
    newly = gamification.check_achievements()
    return {"newly_earned": newly}


@app.get("/api/streaks")
def topic_streaks():
    return gamification.topic_streaks()


# ── P10: Export/Import ─────────────────────────────────────────────────────────


@app.get("/api/flashcards/decks/{deck_id}/export/csv")
def flashcard_export_csv(deck_id: str):
    try:
        csv_content = export_import.export_deck_csv(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="deck_{deck_id}.csv"'},
    )


@app.get("/api/flashcards/decks/{deck_id}/export/json")
def flashcard_export_json(deck_id: str):
    try:
        return export_import.export_deck_json(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class FlashcardImportRequest(BaseModel):
    content: str
    topic: str = "Importado"
    title: str = ""


@app.post("/api/flashcards/import")
def flashcard_import(req: FlashcardImportRequest):
    try:
        return export_import.import_deck_csv(req.content, req.topic, req.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/flashcards/import/json")
def flashcard_import_json(req: FlashcardImportRequest):
    try:
        return export_import.import_deck_json(req.content)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/study-plans/{plan_id}/export")
def study_plan_export(plan_id: str):
    try:
        return export_import.export_plan_json(plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/profile/export")
def profile_export():
    return export_import.export_full()


@app.post("/api/profile/import")
async def profile_import(file: UploadFile = File(...)):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="arquivo vazio")
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {exc}") from exc
    try:
        return export_import.import_full(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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

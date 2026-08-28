"""Router: Tutor (flashcards, planos, stats, perfil, automação, gamificação, export)."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..tutor import advanced_profile, automation, export_import, flashcards, gamification, profile, study_plan
from ..tutor import stats as tutor_stats

router = APIRouter(prefix="/api")


# ── Flashcards ─────────────────────────────────────────────────────────────────


@router.get("/flashcards/decks")
def flashcard_deck_list():
    return flashcards.list_decks()


@router.get("/flashcards/decks/{deck_id}/stats")
def flashcard_deck_stats(deck_id: str):
    return flashcards.deck_stats(deck_id)


class FlashcardGenerateRequest(BaseModel):
    topic: str
    n: int = 10
    level: str = "ensino fundamental"


@router.post("/flashcards/generate")
def flashcard_generate(req: FlashcardGenerateRequest):
    try:
        return flashcards.generate_deck(topic=req.topic, n=req.n, level=req.level)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/flashcards/decks/{deck_id}/due")
def flashcard_due(deck_id: str, limit: int = 20):
    return flashcards.due_cards(deck_id, limit=limit)


class FlashcardReviewRequest(BaseModel):
    card_id: str
    difficulty: str


@router.post("/flashcards/review")
def flashcard_review(req: FlashcardReviewRequest):
    try:
        return flashcards.review_card(req.card_id, req.difficulty)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/flashcards/decks/{deck_id}/export/csv")
def flashcard_export_csv(deck_id: str):
    try:
        csv_content = export_import.export_deck_csv(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from fastapi.responses import Response
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="deck_{deck_id}.csv"'},
    )


@router.get("/flashcards/decks/{deck_id}/export/json")
def flashcard_export_json(deck_id: str):
    try:
        return export_import.export_deck_json(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class FlashcardImportRequest(BaseModel):
    content: str
    topic: str = "Importado"
    title: str = ""


@router.post("/flashcards/import")
def flashcard_import(req: FlashcardImportRequest):
    try:
        return export_import.import_deck_csv(req.content, req.topic, req.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/flashcards/import/json")
def flashcard_import_json(req: FlashcardImportRequest):
    try:
        return export_import.import_deck_json(req.content)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Study Plans ────────────────────────────────────────────────────────────────


@router.get("/study-plans")
def study_plan_list():
    return study_plan.list_plans()


class StudyPlanRequest(BaseModel):
    topic: str
    level: str = "ensino fundamental"


@router.post("/study-plans/generate")
def study_plan_generate(req: StudyPlanRequest):
    try:
        return study_plan.generate_plan(topic=req.topic, level=req.level)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/study-plans/{plan_id}")
def study_plan_get(plan_id: str):
    plan = study_plan.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plan


@router.post("/study-plans/items/{item_id}/toggle")
def study_plan_toggle(item_id: int):
    try:
        return study_plan.toggle_item(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/study-plans/{plan_id}/export")
def study_plan_export(plan_id: str):
    try:
        return export_import.export_plan_json(plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Stats ──────────────────────────────────────────────────────────────────────


@router.get("/stats/dashboard")
def stats_dashboard():
    return tutor_stats.dashboard()


@router.get("/stats/dashboard/enhanced")
def stats_enhanced_dashboard():
    return tutor_stats.enhanced_dashboard()


@router.get("/stats/weekly-summary")
def stats_weekly_summary():
    return tutor_stats.weekly_summary()


@router.get("/stats/mastery-by-subject")
def stats_mastery_by_subject():
    return tutor_stats.mastery_by_subject()


@router.get("/stats/time-analytics")
def time_analytics():
    return advanced_profile.time_analytics()


# ── Profile ────────────────────────────────────────────────────────────────────


class ProfileRequest(BaseModel):
    name: str = ""
    grade: str = ""
    school: str = ""
    preferences: str = ""


@router.get("/profile")
def profile_get():
    return profile.get_profile() or {"name": "", "grade": "", "school": "", "preferences": ""}


@router.post("/profile")
def profile_save(req: ProfileRequest):
    return profile.save_profile(
        name=req.name, grade=req.grade, school=req.school, preferences=req.preferences,
    )


@router.get("/profile/insights")
def profile_insights():
    return profile.profile_insights()


@router.get("/profile/export")
def profile_export():
    return export_import.export_full()


@router.post("/profile/import")
async def profile_import(file: UploadFile = File(...)):  # noqa: B008
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


# ── Mastery ────────────────────────────────────────────────────────────────────


@router.get("/mastery")
def mastery_list():
    return profile.all_mastery()


@router.get("/mastery/{topic}")
def mastery_detail(topic: str):
    result = profile.topic_details(topic)
    if not result:
        raise HTTPException(status_code=404, detail="Tema não encontrado")
    return result


@router.get("/mastery/{topic}/difficulty")
def mastery_difficulty(topic: str):
    return advanced_profile.get_adaptive_difficulty(topic)


@router.post("/mastery/{topic}/difficulty")
def mastery_update_difficulty(topic: str):
    topic_data = profile.topic_details(topic)
    if not topic_data:
        raise HTTPException(status_code=404, detail="Tema não encontrado")
    return advanced_profile.update_difficulty(topic, topic_data["avg_percent"])


# ── Recommendations ────────────────────────────────────────────────────────────


@router.get("/recommendations/{minutes}")
def recommendations(minutes: int):
    return advanced_profile.recommend_for_time(minutes)


# ── Automation ─────────────────────────────────────────────────────────────────


class ActionProposalRequest(BaseModel):
    action_type: str
    params: dict = {}
    description: str = ""


class ProposalRejectRequest(BaseModel):
    reason: str = ""


@router.post("/actions/propose")
def action_propose(req: ActionProposalRequest):
    try:
        return automation.create_proposal(req.action_type, req.params, req.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/actions/{proposal_id}/approve")
def action_approve(proposal_id: str):
    try:
        return automation.approve(proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/actions/{proposal_id}/reject")
def action_reject(proposal_id: str, body: ProposalRejectRequest | None = None):  # noqa: B008
    return automation.reject(proposal_id, reason=body.reason if body else "")


@router.get("/actions/pending")
def action_pending():
    return automation.get_pending()


@router.get("/actions/recent")
def action_recent(limit: int = 10):
    return automation.list_recent(limit=limit)


# ── Gamification ───────────────────────────────────────────────────────────────


@router.get("/achievements")
def achievements_list():
    return gamification.list_achievements()


@router.get("/achievements/progress")
def achievements_progress():
    return gamification.achievement_progress()


@router.get("/achievements/check")
def achievements_check():
    newly = gamification.check_achievements()
    return {"newly_earned": newly}


@router.get("/streaks")
def topic_streaks():
    return gamification.topic_streaks()


@router.get("/level")
def level_info():
    return gamification.get_level_info()


@router.get("/leaderboard")
def leaderboard(limit: int = 20):
    return gamification.leaderboard(limit=limit)


# ── Sessions (advanced) ────────────────────────────────────────────────────────


class SessionStartRequest(BaseModel):
    session_type: str
    metadata: dict = {}


@router.post("/sessions/start")
def session_start(req: SessionStartRequest):
    session_id = advanced_profile.start_session(req.session_type, req.metadata)
    return {"session_id": session_id}


@router.post("/sessions/{session_id}/end")
def session_end(session_id: str):
    try:
        return advanced_profile.end_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Permissions V2 ───────────────────────────────────────────────────────────


class PermissionUpdate(BaseModel):
    value: bool
    reason: str = ""


class PermissionGroupUpdate(BaseModel):
    value: bool
    reason: str = ""


class TemporaryPermission(BaseModel):
    duration_seconds: float
    reason: str = ""


@router.get("/permissions")
def get_permissions():
    from ..security.permissions import PermissionManager
    return PermissionManager().all()


@router.put("/permissions/{name}")
def set_permission(name: str, body: PermissionUpdate):
    from ..security.permissions import PermissionManager
    try:
        PermissionManager().set(name, body.value, reason=body.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"permissão desconhecida: {name}") from exc
    return {name: body.value}


@router.put("/permissions/group/{group}")
def set_permission_group(group: str, body: PermissionGroupUpdate):
    from ..security.permissions import PERMISSION_GROUPS, PermissionManager
    if group not in PERMISSION_GROUPS:
        raise HTTPException(status_code=404, detail=f"grupo desconhecido: {group}")
    PermissionManager().set_group(group, body.value, reason=body.reason)
    return {"group": group, "value": body.value, "permissions": PERMISSION_GROUPS[group]}


@router.post("/permissions/{name}/temporary")
def grant_temporary_permission(name: str, body: TemporaryPermission):
    from ..security.permissions import PermissionManager
    try:
        PermissionManager().grant_temporary(name, body.duration_seconds, reason=body.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"permissão desconhecida: {name}") from exc
    return {"name": name, "temporary": True, "duration_seconds": body.duration_seconds}


@router.get("/permissions/audit")
def get_permission_audit(limit: int = 50):
    from ..security.permissions import PermissionManager
    return PermissionManager().audit_log(limit=limit)


# ── Error Notebook ─────────────────────────────────────────────────────────────


@router.get("/errors")
def error_list(topic: str | None = None, include_reviewed: bool = False):
    from ..tutor import error_notebook
    if topic:
        return error_notebook.get_errors_by_topic(topic, include_reviewed=include_reviewed)
    return error_notebook.get_all_errors(include_reviewed=include_reviewed)


@router.get("/errors/stats")
def error_stats():
    from ..tutor import error_notebook
    return error_notebook.error_stats()


@router.post("/errors/{error_id}/review")
def mark_error_reviewed(error_id: int):
    from ..tutor import error_notebook
    error_notebook.mark_reviewed(error_id)
    return {"status": "ok"}


@router.post("/errors/review-topic")
class ReviewTopicRequest(BaseModel):
    topic: str


def review_topic_errors(body: ReviewTopicRequest):
    from ..tutor import error_notebook
    count = error_notebook.mark_topic_reviewed(body.topic)
    return {"reviewed": count}


@router.post("/flashcards/generate-from-errors")
class GenerateFromErrorsRequest(BaseModel):
    topic: str | None = None
    limit: int = 10


def generate_flashcards_from_errors(body: GenerateFromErrorsRequest):
    return flashcards.generate_from_errors(topic=body.topic, limit=body.limit)

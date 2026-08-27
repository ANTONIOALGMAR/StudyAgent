"""Router: Exercícios."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..agent import exercises

router = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)


class ExerciseGenerateRequest(BaseModel):
    topic: str
    n: int = 4
    level: str = "ensino fundamental"


class ExerciseGradeRequest(BaseModel):
    exercise_id: str
    answers: dict[str, str]


@router.post("/exercises/generate")
@limiter.limit("5/minute")
def exercises_generate(request: Request, req: ExerciseGenerateRequest):
    try:
        return exercises.generate(topic=req.topic, n=req.n, level=req.level)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar exercícios: {exc}") from exc


@router.post("/exercises/generate/adaptive")
@limiter.limit("5/minute")
def exercises_generate_adaptive(request: Request, req: ExerciseGenerateRequest):
    try:
        return exercises.generate_adaptive(topic=req.topic, n=req.n)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar exercícios adaptativos: {exc}") from exc


@router.post("/exercises/generate/review")
@limiter.limit("5/minute")
def exercises_generate_review(request: Request, n: int = 4):
    try:
        return exercises.generate_review(n=n)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao gerar revisão: {exc}") from exc


@router.post("/exercises/grade")
@limiter.limit("30/minute")
def exercises_grade(request: Request, req: ExerciseGradeRequest):
    try:
        return exercises.grade_and_track(exercise_id=req.exercise_id, answers=req.answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/calculate")
def calculate(expression: str):
    try:
        from ..tools.calculator import safe_calc
        return {"result": safe_calc(expression)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

"""Router: health checks — GET /api/health"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from ..core.health import full_health_check

router = APIRouter(prefix="/api", tags=["health"])
log = logging.getLogger("studyagent.router.health")


@router.get("/health")
def health_check() -> dict:
    report = full_health_check()
    log.info("[HEALTH] status=%s components=%d", report.status, len(report.components))
    return report.to_dict()

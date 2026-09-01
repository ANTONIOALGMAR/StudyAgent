from __future__ import annotations

from fastapi import APIRouter, HTTPException
from ..db import get_connection

router = APIRouter(prefix="/api/notifications", tags=["notifications"]) 

@router.get("/")
def list_notifications(limit: int = 20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, body, created_at, read FROM inbox_entries ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]

@router.post("/{nid}/read")
def mark_read(nid: str):
    conn = get_connection()
    row = conn.execute("SELECT id FROM inbox_entries WHERE id = ?", (nid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    conn.execute("UPDATE inbox_entries SET read = 1 WHERE id = ?", (nid,))
    conn.commit()
    return {"ok": True, "id": nid}

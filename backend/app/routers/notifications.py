from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException, Request, Depends
from ..auth import get_current_user
from fastapi.responses import StreamingResponse
from ..db import get_connection

router = APIRouter(prefix="/api/notifications", tags=["notifications"]) 

@router.get("/")
def list_notifications(user: str = Depends(get_current_user), limit: int = 20):
    # user is normalized by dependency
    conn = get_connection()
    if user and user != 'default':
        rows = conn.execute(
            "SELECT id, title, body, created_at, read FROM inbox_entries WHERE owner_user_id = ? OR owner_user_id = 'default' ORDER BY created_at DESC LIMIT ?",
            (user, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, body, created_at, read FROM inbox_entries WHERE owner_user_id = 'default' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]

@router.post("/{nid}/read")
def mark_read(nid: str, user: str = Depends(get_current_user)):
    conn = get_connection()
    row = conn.execute("SELECT id, owner_user_id FROM inbox_entries WHERE id = ?", (nid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    owner = (row["owner_user_id"] or "default").strip().lower()
    if owner != 'default' and (not user or user != owner):
        raise HTTPException(status_code=403, detail="acesso negado à notificação")
    conn.execute("UPDATE inbox_entries SET read = 1 WHERE id = ?", (nid,))
    conn.commit()
    return {"ok": True, "id": nid}


# ===== Server-Sent Events stream endpoint =====
@router.get("/stream")
async def notifications_stream(user: str = Depends(get_current_user)):
    """Return an SSE stream of notifications. Each message is JSON in `data:`.

    Clients should open EventSource('/api/notifications/stream') and listen for
    message events. The stream does not replay DB history; clients should GET / to
    retrieve recent items on connect.
    """
    from ..core.notification_pub import subscribe, unsubscribe

    q = await subscribe(owner=user)

    async def event_generator():
        try:
            # keep alive comment every 15s in case proxies close idle connections
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # send a keep-alive comment
                    yield ": keep-alive\n\n"
        finally:
            await unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

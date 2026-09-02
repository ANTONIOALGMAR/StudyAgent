"""
Lightweight in-memory publisher for server-sent events (SSE).

Provides subscribe() -> asyncio.Queue and publish(payload) to broadcast JSON-serializable
objects to all current subscribers.

This is best-effort and kept simple for local deployments. Messages are not persisted
here (DB still stores inbox_entries).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

log = logging.getLogger("studyagent.notifications")

_SUBSCRIBERS: list[dict] = []  # each entry: {"queue": Queue, "owner": str|None}
_LOCK = asyncio.Lock()


async def subscribe(owner: str | None = None) -> asyncio.Queue:
    """Subscribe to notifications. If owner is provided, the subscriber will only receive
    notifications targeted to that owner or public ones.
    """
    q: asyncio.Queue = asyncio.Queue()
    async with _LOCK:
        _SUBSCRIBERS.append({"queue": q, "owner": (owner.lower().replace(" ", "_") if owner else None)})
        log.debug("subscriber added, total=%d", len(_SUBSCRIBERS))
    return q


async def unsubscribe(q: asyncio.Queue) -> None:
    async with _LOCK:
        try:
            # remove any subscriber entry with this queue
            for entry in list(_SUBSCRIBERS):
                if entry.get("queue") is q:
                    _SUBSCRIBERS.remove(entry)
        except ValueError:
            pass
        log.debug("subscriber removed, total=%d", len(_SUBSCRIBERS))


async def publish(obj: Any) -> None:
    """Publish an object to subscribers. If the object contains 'owner_user_id', it will
    only be sent to subscribers whose owner matches or to subscribers with owner=None.
    Public notifications (owner 'default') are broadcast to everyone.
    """
    data = None
    try:
        data = json.dumps(obj, default=str)
    except Exception:
        try:
            data = json.dumps({"payload": str(obj)})
        except Exception:
            data = "{}"
    obj_owner = None
    try:
        if isinstance(obj, dict) and 'owner_user_id' in obj:
            obj_owner = (obj.get('owner_user_id') or 'default').lower().replace(" ", "_")
    except Exception:
        obj_owner = None

    async with _LOCK:
        for entry in list(_SUBSCRIBERS):
            q = entry.get("queue")
            sub_owner = entry.get("owner")
            try:
                # send if subscriber listens to all (None), or object is public, or owner matches
                if sub_owner is None or obj_owner is None or obj_owner == 'default' or sub_owner == obj_owner:
                    q.put_nowait(data)
            except asyncio.QueueFull:
                log.debug("subscriber queue full, skipping")
            except Exception:
                log.exception("failed to publish to subscriber")

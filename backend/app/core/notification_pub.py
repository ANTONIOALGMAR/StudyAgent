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

_SUBSCRIBERS: list[asyncio.Queue] = []
_LOCK = asyncio.Lock()


async def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    async with _LOCK:
        _SUBSCRIBERS.append(q)
        log.debug("subscriber added, total=%d", len(_SUBSCRIBERS))
    return q


async def unsubscribe(q: asyncio.Queue) -> None:
    async with _LOCK:
        try:
            _SUBSCRIBERS.remove(q)
        except ValueError:
            pass
        log.debug("subscriber removed, total=%d", len(_SUBSCRIBERS))


async def publish(obj: Any) -> None:
    data = None
    try:
        data = json.dumps(obj, default=str)
    except Exception:
        try:
            data = json.dumps({"payload": str(obj)})
        except Exception:
            data = "{}"
    async with _LOCK:
        for q in list(_SUBSCRIBERS):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                log.debug("subscriber queue full, skipping")
            except Exception:
                log.exception("failed to publish to subscriber")

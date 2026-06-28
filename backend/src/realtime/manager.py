"""Per-session WebSocket connection manager (research R5).

Tracks live connections per session so the agent loop can push activity events
to the dashboard in real time. One connection per session is the v1 model.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING

from fastapi import WebSocket

from src.models.db import db_session
from src.realtime.store import replay, to_public

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ConnectionManager:
    """session_id -> active WebSocket."""

    def __init__(self) -> None:
        self._conns: dict[uuid.UUID, WebSocket] = {}

    def connect(self, session_id: uuid.UUID, ws: WebSocket) -> None:
        # ponytail: one connection per session; replace any existing.
        if session_id in self._conns:
            try:
                asyncio.get_event_loop().create_task(self._conns[session_id].close())
            except Exception:
                pass
        self._conns[session_id] = ws

    def disconnect(self, session_id: uuid.UUID) -> None:
        self._conns.pop(session_id, None)

    async def send_event(self, session_id: uuid.UUID, event: dict) -> None:
        """Push a persisted activity event to the live connection, if any.

        event is the to_public() dict. Wrap per ws-event-protocol.md:
        {"type": "activity", "seq": N, "event": {...}}.
        """
        ws = self._conns.get(session_id)
        if ws is None:
            return  # run continues; event is persisted for backfill
        try:
            await ws.send_text(
                json.dumps({"type": "activity", "seq": event["seq"], "event": event})
            )
        except Exception:
            logger.exception("failed to push activity to session %s", session_id)

    def is_connected(self, session_id: uuid.UUID) -> bool:
        return session_id in self._conns


manager = ConnectionManager()


async def backfill(ws: WebSocket, session_id: uuid.UUID, last_seen_seq: int) -> None:
    """On reconnect, replay missed persisted events before live streaming (SC-006)."""
    with db_session() as db:
        for ev in replay(db, session_id=session_id, since_seq=last_seen_seq):
            pub = to_public(ev)
            await ws.send_text(
                json.dumps({"type": "activity", "seq": pub["seq"], "event": pub})
            )

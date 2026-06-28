"""T015 — WS event protocol contract test (US1, SC-006).

Proves the guarantees our code enforces (Starlette's WS transport is its own
concern): monotonic per-session seq, tool_call-before-tool_result ordering,
and reconnect backfill by seq with no loss or duplication. Uses a fake
WebSocket against the real store + manager.

A full live end-to-end WS check (connect → chat → 3 events stream with a fake
LLM) is verified by `backend/scripts/smoke_ws.py` (runnable, not pytest-driven,
to avoid the Starlette TestClient WS transport deadlock in this environment).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.models.db import Base, SessionLocal, engine
import src.models.entities  # noqa: F401
from src.models.entities import ActivityType
from src.realtime.manager import ConnectionManager
from src.realtime.store import record, replay, to_public


class _FakeWS:
    """Captures sent activity events in order."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        import json
        self.sent.append(json.loads(text))

    async def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _sid() -> uuid.UUID:
    return uuid.uuid4()


def test_seq_monotonic_and_ordered():
    """Events record with monotonic seq; tool_call precedes tool_result."""
    sid = _sid()
    with SessionLocal() as db:
        record(db, event_type=ActivityType.reasoning, payload={"n": 1}, session_id=sid)
        record(db, event_type=ActivityType.tool_call, payload={"name": "t"}, session_id=sid)
        record(db, event_type=ActivityType.tool_result, payload={"ok": True}, session_id=sid)
        evs = replay(db, session_id=sid, since_seq=0)
    seqs = [e.seq for e in evs]
    types = [e.type.value for e in evs]
    assert seqs == [1, 2, 3], seqs
    assert types.index("tool_call") < types.index("tool_result")


def test_reconnect_backfill_no_loss_no_dup():
    """SC-006: replay by since_seq returns only newer events, exactly once."""
    sid = _sid()
    with SessionLocal() as db:
        for i in range(5):
            record(db, event_type=ActivityType.progress, payload={"i": i}, session_id=sid)

    with SessionLocal() as db:
        # Client saw up to seq 3; reconnect should get only seq>3.
        missed = replay(db, session_id=sid, since_seq=3)
    seqs = [e.seq for e in missed]
    assert seqs == [4, 5], "backfill must return only newer events"
    assert len(seqs) == len(set(seqs)), "no duplicate seqs"

    # A fully caught-up client (since_seq=5) gets nothing — no phantom events.
    with SessionLocal() as db:
        assert replay(db, session_id=sid, since_seq=5) == []


def test_manager_pushes_to_connected_only():
    """Live push goes to the connected ws; disconnected runs persist for backfill."""
    sid = _sid()
    mgr = ConnectionManager()
    ws = _FakeWS()
    mgr.connect(sid, ws)

    async def _run():
        # Simulate the agent loop pushing a persisted event to the live ws.
        with SessionLocal() as db:
            ev = record(db, event_type=ActivityType.llm_call, payload={"model": "m"}, session_id=sid)
        await mgr.send_event(sid, to_public(ev))

    asyncio.run(_run())
    assert len(ws.sent) == 1
    assert ws.sent[0]["type"] == "activity"
    assert ws.sent[0]["seq"] == 1
    assert ws.sent[0]["event"]["type"] == "llm_call"

    # After disconnect, pushes are silently skipped (event still persisted).
    mgr.disconnect(sid)
    asyncio.run(_run())
    assert len(ws.sent) == 1  # no second push

    # But backfill replays the persisted event.
    with SessionLocal() as db:
        assert len(replay(db, session_id=sid, since_seq=1)) == 1

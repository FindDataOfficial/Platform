"""T040 — confirmation gate test (US5, constitution III, FR-010/FR-011).

Proves: a destructive tool can never be auto_run; a trust-boundary tool always
emits a confirmation_request and blocks until resolved; declining returns a
`declined` error. Uses a fake WS manager so no real connection is needed.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.confirm import engine
from src.models.db import Base, SessionLocal, engine as db_engine
import src.models.entities  # noqa: F401
from src.models.entities import ChatSession, LlmModel, LlmProvider, Message, MessageRole, RiskLevel
from src.tools.invoke import invoke
from src.tools.registry import ToolDescriptor, ToolError, register, reset_registry


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.create_all(db_engine)
    yield
    Base.metadata.drop_all(db_engine)


@pytest.fixture(autouse=True)
def _reg():
    reset_registry()
    yield
    reset_registry()


class _CapturingManager:
    def __init__(self):
        self.sent = []

    async def send_event(self, session_id, event):
        self.sent.append((session_id, event))


def _seed_session() -> uuid.UUID:
    with SessionLocal() as db:
        from src.models.entities import User

        u = User(email="g@h.com", password_hash="x")
        p = LlmProvider(owner_id=None, name="p", type="openai_compatible", base_url="http://x", api_key_ciphertext=b"k")
        s = ChatSession(owner_id=None, model_id=None)
        # minimal valid rows
        db.add(u); db.flush()
        p.owner_id = u.id; db.add(p); db.flush()
        m = LlmModel(provider_id=p.id, model_name="m", display_name="M")
        db.add(m); db.flush()
        s.owner_id = u.id; s.model_id = m.id; db.add(s); db.commit()
        return s.id


def test_destructive_tool_can_never_auto_run():
    """FR-011: registering a destructive tool with auto_run=True must raise."""
    with pytest.raises(ToolError):
        register(
            ToolDescriptor(
                name="nuke", description="d", source_type="builtin",
                input_schema={"type": "object"},
                risk_level=RiskLevel.destructive, auto_run=True,
            ),
            lambda a: None,
        )


def test_sensitive_tool_blocks_on_confirmation(monkeypatch):
    """FR-010: a sensitive tool emits a confirmation_request and blocks until approved."""
    sid = _seed_session()
    fake = _CapturingManager()
    monkeypatch.setattr(engine, "manager", fake)

    async def echo(args):
        return {"done": True}

    register(ToolDescriptor(
        name="sensitive_op", description="d", source_type="builtin",
        input_schema={"type": "object"}, risk_level=RiskLevel.sensitive,
        timeout_seconds=30, tool_id=uuid.uuid4(),
    ), echo)

    async def _driver():
        # Start the (blocking) invoke in a task.
        task = asyncio.create_task(invoke("sensitive_op", {}, session_id=sid))
        # Let it reach the await fut point.
        await asyncio.sleep(0.05)
        # A confirmation_request event should have been emitted.
        assert any(ev["type"] == "confirmation_request" for _, ev in fake.sent)
        # Resolve approved.
        cid = uuid.UUID(fake.sent[0][1]["payload"]["confirmation_id"])
        await engine.resolve(cid, True, uuid.uuid4())
        return await task

    res = asyncio.run(_driver())
    assert res["ok"] is True
    assert any(ev["type"] == "confirmation_result" for _, ev in fake.sent)


def test_declined_returns_declined_error(monkeypatch):
    sid = _seed_session()
    fake = _CapturingManager()
    monkeypatch.setattr(engine, "manager", fake)

    async def echo(args):
        return {"done": True}

    register(ToolDescriptor(
        name="sensitive_op2", description="d", source_type="builtin",
        input_schema={"type": "object"}, risk_level=RiskLevel.sensitive,
        timeout_seconds=30, tool_id=uuid.uuid4(),
    ), echo)

    async def _driver():
        task = asyncio.create_task(invoke("sensitive_op2", {}, session_id=sid))
        await asyncio.sleep(0.05)
        cid = uuid.UUID(fake.sent[0][1]["payload"]["confirmation_id"])
        await engine.resolve(cid, False, uuid.uuid4())  # decline
        return await task

    res = asyncio.run(_driver())
    assert res["ok"] is False
    assert res["error"]["code"] == "declined"


def test_none_risk_tool_runs_without_confirmation(monkeypatch):
    """A risk_level=none tool never triggers the gate."""
    sid = _seed_session()
    fake = _CapturingManager()
    monkeypatch.setattr(engine, "manager", fake)

    async def echo(args):
        return {"ok": True}

    register(ToolDescriptor(
        name="safe_op", description="d", source_type="builtin",
        input_schema={"type": "object"}, risk_level=RiskLevel.none,
    ), echo)

    res = asyncio.run(invoke("safe_op", {}, session_id=sid))
    assert res["ok"] is True
    assert fake.sent == []  # no confirmation emitted

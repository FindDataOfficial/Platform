"""T047 — integration tests for reconnect + edge cases (SC-006 + spec edge cases).

Covers: WS reconnect backfill by seq (no loss/dup — SC-006), MCP-server-
unreachable surfaces an error without hanging, and a model disabled mid-session
yields "model unavailable".
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.models.db import Base, SessionLocal, engine as db_engine
import src.models.entities  # noqa: F401
from src.models.entities import ActivityType
from src.realtime.store import record, replay


@pytest.fixture(autouse=True)
def _db():
    Base.metadata.create_all(db_engine)
    yield
    Base.metadata.drop_all(db_engine)


def test_reconnect_backfill_no_loss_no_dup():
    """SC-006: a client that missed events gets exactly the newer ones on replay."""
    sid = uuid.uuid4()
    with SessionLocal() as db:
        for i in range(6):
            record(db, event_type=ActivityType.progress, payload={"i": i}, session_id=sid)

    # Client saw seq 4; reconnect replays only seq>4, exactly once.
    with SessionLocal() as db:
        missed = replay(db, session_id=sid, since_seq=4)
    seqs = [e.seq for e in missed]
    assert seqs == [5, 6]
    assert len(set(seqs)) == len(seqs)


def test_mcp_unreachable_surfaces_error_without_hang():
    """Edge case: invoking an MCP tool against a dead server returns execution_error,
    not a hang. We simulate via a tool whose executor raises."""
    from src.tools.invoke import invoke
    from src.tools.registry import ToolDescriptor, register, reset_registry
    from src.models.entities import RiskLevel

    reset_registry()

    async def dead(args):
        raise RuntimeError("connection refused")

    register(ToolDescriptor(
        name="mcp_dead_ping", description="d", source_type="mcp",
        input_schema={"type": "object"}, risk_level=RiskLevel.none, timeout_seconds=2,
    ), dead)

    res = asyncio.run(invoke("mcp_dead_ping", {}))
    assert res["ok"] is False
    assert res["error"]["code"] == "execution_error"
    assert "connection refused" in res["error"]["message"]


def test_model_disabled_mid_session_yields_unavailable():
    """Edge case: a disabled/missing model surfaces 'model unavailable'."""
    from src.agent.loop import _load_model
    from src.models.entities import LlmModel, LlmProvider, ProviderType, User

    with SessionLocal() as db:
        u = User(email="e@f.com", password_hash="x"); db.add(u); db.flush()
        p = LlmProvider(owner_id=u.id, name="p", type=ProviderType.openai_compatible,
                        base_url="http://x", api_key_ciphertext=b"k"); db.add(p); db.flush()
        m = LlmModel(provider_id=p.id, model_name="m", display_name="M", enabled=False)
        db.add(m); db.commit()
        with pytest.raises(ValueError, match="model unavailable"):
            _load_model(db, m.id)

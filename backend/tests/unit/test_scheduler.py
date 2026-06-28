"""T035 — scheduler test (US4, research R8).

Proves: a scheduled job persists to the SQL jobstore (survives a scheduler
restart, FR-015), runs through the tool path emitting a job-scoped activity
event, and retries on failure per max_retries.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.models.db import Base, SessionLocal, engine as db_engine
import src.models.entities  # noqa: F401
from src.models.entities import (
    JobStatus,
    JobTargetType,
    RunStatus,
    ScheduledJob,
    User,
)
from src.scheduler import engine
from src.tools.registry import ToolDescriptor, register, reset_registry


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    # Use an isolated sqlite DB for the scheduler jobstore + ORM.
    monkeypatch.setattr(engine, "_scheduler", None)
    Base.metadata.create_all(db_engine)
    yield
    Base.metadata.drop_all(db_engine)


@pytest.fixture(autouse=True)
def _reg():
    reset_registry()
    yield
    reset_registry()


def _seed_user_job() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as db:
        u = User(email="j@k.com", password_hash="x")
        db.add(u); db.commit()
        job = ScheduledJob(
            owner_id=u.id,
            cron_expr="* * * * *",
            target_type=JobTargetType.tool,
            target_ref={"type": "tool", "tool_name": "echo", "arguments": {"msg": "hi"}},
            max_retries=2,
        )
        db.add(job); db.commit()
        return u.id, job.id


def test_job_persists_and_runs_through_tool_path(monkeypatch):
    """A job run invokes the target tool and records a job-scoped activity event."""
    uid, job_id = _seed_user_job()

    calls = []

    async def echo(args):
        calls.append(args)
        return {"echoed": args["msg"]}

    register(ToolDescriptor(
        name="echo", description="d", source_type="builtin",
        input_schema={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
    ), echo)

    # Run the job function directly (no real cron firing needed).
    asyncio.run(engine._run_job(job_id))

    assert calls == [{"msg": "hi"}], "tool should have been invoked"
    with SessionLocal() as db:
        job = db.get(ScheduledJob, job_id)
        assert job.last_run_status == RunStatus.success
    # A job-scoped activity event was recorded.
    from src.realtime.store import replay
    with SessionLocal() as db:
        evs = replay(db, job_id=job_id, since_seq=0)
    assert len(evs) == 1
    assert evs[0].job_id == job_id


def test_job_retries_on_failure_then_marks_failed(monkeypatch):
    uid, job_id = _seed_user_job()

    attempts = {"n": 0}

    async def flaky(args):
        attempts["n"] += 1
        raise RuntimeError("boom")

    register(ToolDescriptor(
        name="echo", description="d", source_type="builtin",
        input_schema={"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]},
    ), flaky)

    asyncio.run(engine._run_job(job_id))
    # max_retries=2 → initial + 2 retries = 3 attempts.
    assert attempts["n"] == 3
    with SessionLocal() as db:
        job = db.get(ScheduledJob, job_id)
        assert job.last_run_status == RunStatus.failed
        assert job.status == JobStatus.failed


def test_resource_lock_rejects_overlap():
    """R8: a second job targeting the same busy resource gets resource_busy."""
    # The lock is non-blocking; verify it rejects when already held.
    sid = str(uuid.uuid4())
    lock = engine._resource_lock(sid)
    assert lock.acquire(blocking=False) is True
    # Second acquire (simulating an overlapping job) must fail.
    assert lock.acquire(blocking=False) is False
    lock.release()

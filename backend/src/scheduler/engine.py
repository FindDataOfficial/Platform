"""Cron scheduler (T036/T037, US4, research R8).

APScheduler with a persistent SQL jobstore so jobs survive restarts (FR-015).
Scheduled jobs run through the normal agent/tool path, emitting ActivityEvents
with job_id set (FR-007). A per-resource lock serializes jobs targeting the
same browser/computer session (edge case: concurrent cron on same browser).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

from src.config import get_settings
from src.models.db import db_session
from src.models.entities import (
    ActivityType,
    RunStatus,
    ScheduledJob,
    JobStatus,
    JobTargetType,
)
from src.realtime.store import record, to_public
from src.realtime.manager import manager
from src.tools.invoke import invoke

logger = logging.getLogger(__name__)

# Per-resource lock for browser/computer sessions (R8): serialize overlapping jobs.
_resource_locks: dict[str, threading.Lock] = {}
_resource_locks_guard = threading.Lock()


def _resource_lock(key: str) -> threading.Lock:
    with _resource_locks_guard:
        if key not in _resource_locks:
            _resource_locks[key] = threading.Lock()
        return _resource_locks[key]


_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=get_settings().database_url)},
            timezone="UTC",
        )
    return _scheduler


def _job_id(db_job_id: uuid.UUID) -> str:
    return str(db_job_id)


async def _run_job(db_job_id: uuid.UUID) -> None:
    """Execute a scheduled job through the tool path, emitting activity (FR-007)."""
    with db_session() as db:
        job = db.get(ScheduledJob, db_job_id)
        if job is None or job.status != JobStatus.active:
            return
        job.last_run_at = datetime.now(timezone.utc)
        job.last_run_status = RunStatus.running
        db.commit()
        target = job.target_ref or {}
        max_retries = job.max_retries

    # Per-resource lock if the job targets a browser/computer session.
    res_key = str(target.get("session_id", "")) if target.get("session_id") else ""
    lock = _resource_lock(res_key) if res_key else None

    async def _attempt() -> dict:
        if job_target_type := target.get("target_type"):
            pass
        if target.get("type") == "tool":
            tool_name = target["tool_name"]
            args = target.get("arguments", {})
            res = await invoke(tool_name, args)
            return res
        return {"note": "chat-target jobs not yet supported in v1"}

    attempts = 0
    result: dict = {}
    success = False
    while attempts <= max_retries:
        try:
            if lock:
                # ponytail: non-blocking acquire; if busy, reject with resource_busy (R8).
                if not lock.acquire(blocking=False):
                    result = {"error": {"code": "resource_busy", "message": "session in use"}}
                    break
                try:
                    result = await _attempt()
                finally:
                    lock.release()
            else:
                result = await _attempt()
            if result.get("ok", True) and not result.get("error"):
                success = True
                break
        except Exception as e:  # noqa: BLE001
            result = {"error": {"code": "execution_error", "message": str(e)}}
        attempts += 1
        if attempts <= max_retries:
            await asyncio.sleep(1)

    with db_session() as db:
        job = db.get(ScheduledJob, db_job_id)
        if job is not None:
            job.last_run_status = RunStatus.success if success else RunStatus.failed
            if not success and attempts > max_retries:
                job.status = JobStatus.failed
            db.commit()
        # Emit the run's activity under the job.
        ev = record(
            db,
            event_type=ActivityType.tool_result if target.get("type") == "tool" else ActivityType.reasoning,
            payload=result,
            job_id=db_job_id,
        )
        # Jobs have no live dashboard connection by default; event is persisted.
        await manager.send_event(uuid.UUID("00000000-0000-0000-0000-000000000000"), to_public(ev))


def schedule_job(job: ScheduledJob) -> None:
    """Register an active job with the scheduler."""
    sched = get_scheduler()
    trigger = CronTrigger.from_crontab(job.cron_expr)
    sched.add_job(
        _run_job,
        trigger=trigger,
        args=[job.id],
        id=_job_id(job.id),
        replace_existing=True,
    )


def unschedule_job(job_id: uuid.UUID) -> None:
    sched = get_scheduler()
    try:
        sched.remove_job(_job_id(job_id))
    except Exception:
        pass


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        # Re-register all active jobs from the DB (survives restart, FR-015).
        with db_session() as db:
            from sqlalchemy import select
            for job in db.execute(select(ScheduledJob).where(ScheduledJob.status == JobStatus.active)).scalars():
                schedule_job(job)

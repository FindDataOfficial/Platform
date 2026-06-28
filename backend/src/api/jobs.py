"""Scheduled jobs HTTP API (T038, US4, contracts/http-api.md).

Create/pause/delete cron jobs; list with last_run_status/next_run_at; replay
a job's activity by seq.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import require_user
from src.models.db import get_db
from src.models.entities import JobStatus, JobTargetType, RunStatus, ScheduledJob, User
from src.realtime.store import replay, to_public
from src.scheduler.engine import schedule_job, unschedule_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobIn(BaseModel):
    cron_expr: str
    target_type: JobTargetType
    target_ref: dict
    max_retries: int = 3


class JobPatch(BaseModel):
    status: JobStatus


def _out(j: ScheduledJob) -> dict:
    return {
        "id": str(j.id),
        "cron_expr": j.cron_expr,
        "target_type": j.target_type.value,
        "target_ref": j.target_ref,
        "max_retries": j.max_retries,
        "status": j.status.value,
        "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
        "last_run_status": j.last_run_status.value if j.last_run_status else None,
        "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
    }


def _validate_cron(expr: str) -> None:
    from apscheduler.triggers.cron import CronTrigger
    try:
        CronTrigger.from_crontab(expr)
    except Exception as e:
        raise HTTPException(400, f"invalid cron expression: {e}")


@router.get("")
def list_jobs(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.execute(select(ScheduledJob).where(ScheduledJob.owner_id == user.id)).scalars()
    return [_out(j) for j in rows]


@router.post("")
def create_job(body: JobIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    _validate_cron(body.cron_expr)
    # target_ref for tool: {type:"tool", tool_name, arguments}
    job = ScheduledJob(
        owner_id=user.id,
        cron_expr=body.cron_expr,
        target_type=body.target_type,
        target_ref=body.target_ref,
        max_retries=body.max_retries,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    schedule_job(job)
    return _out(job)


@router.patch("/{job_id}")
def update_job(job_id: uuid.UUID, body: JobPatch, user: User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.get(ScheduledJob, job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(404, "job not found")
    job.status = body.status
    db.commit()
    db.refresh(job)
    if body.status == JobStatus.active:
        schedule_job(job)
    else:
        unschedule_job(job.id)
    return _out(job)


@router.delete("/{job_id}")
def delete_job(job_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.get(ScheduledJob, job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(404, "job not found")
    unschedule_job(job.id)
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.get("/{job_id}/activity")
def job_activity(job_id: uuid.UUID, since_seq: int = Query(0), user: User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.get(ScheduledJob, job_id)
    if job is None or job.owner_id != user.id:
        raise HTTPException(404, "job not found")
    return [to_public(ev) for ev in replay(db, job_id=job_id, since_seq=since_seq)]

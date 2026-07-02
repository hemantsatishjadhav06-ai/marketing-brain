"""Single entry-point for RQ. Dispatches by Job.type to the right agent/orchestrator."""
from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.cost_guard import BudgetExceeded, assert_budget_available
from app.core.db import SessionLocal
from app.models.jobs import Job
from app.workers.events import emit


def _set_running(db, job: Job) -> None:
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()
    emit(job.id, status="running")


def _set_done(db, job: Job, result: dict) -> None:
    job.status = "done"
    job.finished_at = datetime.now(timezone.utc)
    job.result = result
    job.progress = 100
    db.commit()
    emit(job.id, status="done", data={"result": result})


def _set_failed(db, job: Job, err: str) -> None:
    job.status = "failed"
    job.finished_at = datetime.now(timezone.utc)
    job.error = err[:3500]
    db.commit()
    emit(job.id, status="failed", message=err)


def run_job(job_id: str) -> None:
    """Top-level RQ entry. Loads the Job, runs the agent, persists outcome."""
    db = SessionLocal()
    try:
        job = db.get(Job, uuid.UUID(job_id))
        if not job:
            return
        try:
            assert_budget_available(db, job.org_id)
        except BudgetExceeded as e:
            _set_failed(db, job, f"budget_exceeded: {e}")
            return

        _set_running(db, job)

        # dispatch
        try:
            if job.type == "short_video.product_video":
                from app.agents.short_video.agent import run_product_video
                result = run_product_video(db, job)
            elif job.type == "calendar.generate":
                # Phase 1 will land the full calendar agent
                result = {"status": "not_implemented_in_phase_0"}
            elif job.type == "scoring.run":
                result = {"status": "not_implemented_in_phase_0"}
            else:
                raise ValueError(f"Unknown job type: {job.type}")
            _set_done(db, job, result)
        except Exception as e:
            _set_failed(db, job, f"{type(e).__name__}: {e}\n{traceback.format_exc()}")
    finally:
        db.close()

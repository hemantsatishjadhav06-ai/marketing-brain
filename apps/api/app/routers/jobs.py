"""Jobs — list + create + get. Creates enqueue an RQ task; the worker picks it up."""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import require_role, require_user
from app.models.brand import Brand
from app.models.jobs import Job
from app.models.tenancy import User
from app.schemas.jobs import JobCreateIn, JobOut
from app.workers.queue import enqueue_job

router = APIRouter()


@router.get("", response_model=List[JobOut])
def list_jobs(
    status_filter: Optional[str] = None,
    brand_id: Optional[uuid.UUID] = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    q = select(Job).where(Job.org_id == user.org_id)
    if status_filter:
        q = q.where(Job.status == status_filter)
    if brand_id:
        q = q.where(Job.brand_id == brand_id)
    q = q.order_by(Job.created_at.desc()).limit(200)
    return db.execute(q).scalars().all()


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreateIn,
    user: User = Depends(require_role("marketer")),
    db: Session = Depends(get_db),
):
    if payload.brand_id:
        brand = db.get(Brand, payload.brand_id)
        if not brand or brand.org_id != user.org_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    job = Job(
        org_id=user.org_id,
        brand_id=payload.brand_id,
        type=payload.type,
        status="queued",
        payload=payload.payload,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_job(str(job.id))
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job or job.org_id != user.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job

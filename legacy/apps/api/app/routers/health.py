"""Health + version routes."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": "marketing-brain-api", "version": "0.1.0"}


@router.get("/")
def root():
    return {"service": "marketing-brain-api", "docs": "/docs", "health": "/health"}

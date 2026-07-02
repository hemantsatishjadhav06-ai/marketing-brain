"""Swappable storage interface. Local now, R2/S3 later."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Protocol

from app.core.config import settings


class Storage(Protocol):
    def write_bytes(self, key: str, data: bytes) -> str: ...
    def write_file(self, key: str, src_path: str) -> str: ...
    def url_for(self, key: str) -> str: ...


class LocalStorage:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.STORAGE_LOCAL_PATH)
        self.root.mkdir(parents=True, exist_ok=True)
        self.public_base = settings.PUBLIC_BASE_URL.rstrip("/")

    def _full(self, key: str) -> Path:
        p = self.root / key.lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def write_bytes(self, key: str, data: bytes) -> str:
        p = self._full(key)
        p.write_bytes(data)
        return self.url_for(key)

    def write_file(self, key: str, src_path: str) -> str:
        p = self._full(key)
        shutil.copyfile(src_path, p)
        return self.url_for(key)

    def url_for(self, key: str) -> str:
        return f"{self.public_base}/storage/{key.lstrip('/')}"


def get_storage() -> Storage:
    backend = settings.STORAGE_BACKEND.lower()
    if backend in ("s3", "r2"):
        try:
            from app.pipeline.storage_s3 import S3Storage
            return S3Storage()
        except Exception:
            # graceful fallback to local — keeps dev unblocked when keys are missing
            return LocalStorage()
    return LocalStorage()


def new_key(brand_id: uuid.UUID | str, kind: str, ext: str) -> str:
    return f"{kind}/{brand_id}/{uuid.uuid4().hex}.{ext.lstrip('.')}"

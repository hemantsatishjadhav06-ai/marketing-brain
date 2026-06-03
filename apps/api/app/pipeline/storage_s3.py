"""S3 / R2 storage backend implementing the Storage Protocol.

Selected when settings.STORAGE_BACKEND in ("s3", "r2"). Falls back to local
storage when AWS / R2 credentials are missing, so dev still works without keys.

This file imports boto3 lazily to keep the local-only deploy lightweight.
"""
from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from app.core.config import settings


class S3Storage:
    """Works for AWS S3 and Cloudflare R2.

    R2 requires `S3_ENDPOINT_URL` like
        https://<accountid>.r2.cloudflarestorage.com
    and `S3_REGION="auto"`.
    """

    def __init__(self) -> None:
        try:
            import boto3  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "boto3 is not installed — add it to requirements.txt to use s3/r2 storage"
            ) from e
        self.bucket = settings.S3_BUCKET
        if not self.bucket:
            raise RuntimeError("S3_BUCKET is not configured")
        self.client = boto3.client(
            "s3",
            region_name=settings.S3_REGION or "auto",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY or None,
            aws_secret_access_key=settings.S3_SECRET_KEY or None,
        )
        self.public_base = (settings.S3_PUBLIC_BASE_URL or "").rstrip("/")

    def _content_type(self, key: str) -> str:
        ct, _ = mimetypes.guess_type(key)
        return ct or "application/octet-stream"

    def write_bytes(self, key: str, data: bytes) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key.lstrip("/"),
            Body=data,
            ContentType=self._content_type(key),
            ACL="public-read",
        )
        return self.url_for(key)

    def write_file(self, key: str, src_path: str) -> str:
        with open(src_path, "rb") as f:
            return self.write_bytes(key, f.read())

    def url_for(self, key: str) -> str:
        key = key.lstrip("/")
        if self.public_base:
            return f"{self.public_base}/{key}"
        # presigned fallback (1 hour)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=3600,
        )

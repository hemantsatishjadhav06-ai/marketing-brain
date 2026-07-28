"""Small, testable Airtable REST client used by the content orchestrator."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable
from urllib.parse import quote

import httpx


AIRTABLE_API_URL = "https://api.airtable.com/v0"
MAX_RECORDS_PER_WRITE = 10


class AirtableError(RuntimeError):
    """A sanitized Airtable failure safe to surface through the API."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail[:500]
        super().__init__(self.detail)


@dataclass(frozen=True)
class AirtableConfig:
    token: str
    webhook_secret: str
    base_id: str
    content_table_id: str
    slides_table_id: str
    claims_table_id: str
    projects_table_id: str
    brand_rules_table_id: str
    runs_table_id: str
    approvals_table_id: str

    @classmethod
    def from_env(cls) -> "AirtableConfig":
        return cls(
            token=os.environ.get("AIRTABLE_TOKEN", "").strip(),
            webhook_secret=os.environ.get("AIRTABLE_WEBHOOK_SECRET", "").strip(),
            base_id=os.environ.get("AIRTABLE_BASE_ID", "appvpMfpbNQDkUGeF").strip(),
            content_table_id=os.environ.get("AIRTABLE_CONTENT_TABLE_ID", "tblWu3YzDoasrj0OG").strip(),
            slides_table_id=os.environ.get("AIRTABLE_SLIDES_TABLE_ID", "tblAbMcwp6DipTQqu").strip(),
            claims_table_id=os.environ.get("AIRTABLE_CLAIMS_TABLE_ID", "tbluMV1yECqSjpY0S").strip(),
            projects_table_id=os.environ.get("AIRTABLE_PROJECTS_TABLE_ID", "tblXdFUMM6E6qSKLF").strip(),
            brand_rules_table_id=os.environ.get("AIRTABLE_BRAND_RULES_TABLE_ID", "tblP2Gqh59vI79IqW").strip(),
            runs_table_id=os.environ.get("AIRTABLE_RUNS_TABLE_ID", "tblir6QJU0Vo4qBeP").strip(),
            approvals_table_id=os.environ.get("AIRTABLE_APPROVALS_TABLE_ID", "tbl7C6O77DDf6zd9D").strip(),
        )

    @property
    def api_configured(self) -> bool:
        return all(
            (
                self.token,
                self.base_id,
                self.content_table_id,
                self.slides_table_id,
                self.claims_table_id,
                self.projects_table_id,
                self.brand_rules_table_id,
                self.runs_table_id,
                self.approvals_table_id,
            )
        )

    @property
    def webhook_configured(self) -> bool:
        return bool(self.webhook_secret)


class AirtableClient:
    """Airtable API adapter with bounded retries and ten-record write chunks."""

    def __init__(
        self,
        config: AirtableConfig,
        *,
        timeout: float = 20.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not config.token:
            raise AirtableError(503, "AIRTABLE_TOKEN is not configured")
        self.config = config
        self.max_retries = max(0, max_retries)
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=AIRTABLE_API_URL,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
                "User-Agent": "marketing-brain-airtable/1.0",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AirtableClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _path(self, table_id: str, record_id: str | None = None) -> str:
        base = quote(self.config.base_id, safe="")
        table = quote(table_id, safe="")
        path = f"/{base}/{table}"
        return f"{path}/{quote(record_id, safe='')}" if record_id else path

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
            error = payload.get("error", payload) if isinstance(payload, dict) else {}
            if isinstance(error, dict):
                code = str(error.get("type") or error.get("error") or "").strip()
                message = str(error.get("message") or "").strip()
                joined = ": ".join(part for part in (code, message) if part)
                if joined:
                    return joined
        except Exception:
            pass
        return f"Airtable request failed with HTTP {response.status_code}"

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                if attempt < self.max_retries:
                    self._sleep(0.25 * (2**attempt))
                    continue
                raise AirtableError(502, f"Airtable network error: {exc.__class__.__name__}") from exc

            retryable = response.status_code == 429 or 500 <= response.status_code < 600
            if retryable and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    delay = min(max(float(retry_after), 0.0), 5.0)
                except ValueError:
                    delay = 0.25 * (2**attempt)
                self._sleep(delay)
                continue
            if response.status_code >= 400:
                raise AirtableError(response.status_code, self._error_detail(response))
            try:
                payload = response.json()
            except ValueError as exc:
                raise AirtableError(502, "Airtable returned an invalid JSON response") from exc
            if not isinstance(payload, dict):
                raise AirtableError(502, "Airtable returned an unexpected response")
            return payload
        raise AirtableError(502, "Airtable retry limit exceeded")

    def get_record(self, table_id: str, record_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            self._path(table_id, record_id),
            params={"returnFieldsByFieldId": "true"},
        )

    def update_record(self, table_id: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "PATCH",
            self._path(table_id, record_id),
            params={"returnFieldsByFieldId": "true"},
            json={"fields": fields, "typecast": False},
        )

    def create_record(self, table_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        records = self.create_records(table_id, [fields])
        if not records:
            raise AirtableError(502, "Airtable did not return the created record")
        return records[0]

    def create_records(
        self,
        table_id: str,
        rows: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        items = list(rows)
        created: list[dict[str, Any]] = []
        for start in range(0, len(items), MAX_RECORDS_PER_WRITE):
            chunk = items[start : start + MAX_RECORDS_PER_WRITE]
            payload = self._request(
                "POST",
                self._path(table_id),
                params={"returnFieldsByFieldId": "true"},
                json={"records": [{"fields": row} for row in chunk], "typecast": False},
            )
            records = payload.get("records", [])
            if not isinstance(records, list):
                raise AirtableError(502, "Airtable returned an invalid record batch")
            created.extend(record for record in records if isinstance(record, dict))
        return created

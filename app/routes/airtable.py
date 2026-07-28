"""Airtable content-operations webhook routes."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException

from ..ai import engine as ai_engine
from ..schemas import AirtableApprovalIn, AirtableRunIn
from ..services.airtable import AirtableClient, AirtableConfig, AirtableError
from ..services.airtable_orchestrator import AirtableOrchestrator, WorkflowError

router = APIRouter(prefix="/api/airtable", tags=["airtable"])


def _require_webhook_secret(
    x_marketing_brain_secret: str = Header(default="", alias="X-Marketing-Brain-Secret"),
) -> AirtableConfig:
    config = AirtableConfig.from_env()
    if not config.webhook_configured:
        raise HTTPException(503, "AIRTABLE_WEBHOOK_SECRET is not configured")
    if not secrets.compare_digest(x_marketing_brain_secret, config.webhook_secret):
        raise HTTPException(401, "Invalid Airtable webhook secret")
    if not config.api_configured:
        raise HTTPException(503, "Airtable API connection is not configured")
    return config


def _build_orchestrator(config: AirtableConfig) -> AirtableOrchestrator:
    client = AirtableClient(config)
    return AirtableOrchestrator(client, config, ai_engine)


@router.get("/health")
def airtable_health(
    x_marketing_brain_secret: str = Header(default="", alias="X-Marketing-Brain-Secret"),
):
    config = _require_webhook_secret(x_marketing_brain_secret)
    return {
        "ok": True,
        "configuration_ready": True,
        "connectivity_checked": False,
        "message": "Airtable credentials and table mappings are configured; use a dry run to verify connectivity.",
    }


@router.post("/content/{record_id}/run")
def run_airtable_content(
    record_id: str,
    body: AirtableRunIn,
    x_marketing_brain_secret: str = Header(default="", alias="X-Marketing-Brain-Secret"),
):
    config = _require_webhook_secret(x_marketing_brain_secret)
    orchestrator = _build_orchestrator(config)
    try:
        return orchestrator.run(
            record_id,
            requested_stage=body.stage,
            dry_run=body.dry_run,
            idempotency_key=body.idempotency_key[:120],
        )
    except WorkflowError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    except AirtableError as exc:
        if exc.status_code == 404:
            raise HTTPException(404, "Airtable record not found") from exc
        raise HTTPException(502, f"Airtable upstream error: {exc.detail}") from exc
    except Exception as exc:
        raise HTTPException(502, f"Content workflow failed: {exc.__class__.__name__}") from exc
    finally:
        close = getattr(orchestrator.client, "close", None)
        if callable(close):
            close()


@router.post("/content/{record_id}/approval")
def record_airtable_approval(
    record_id: str,
    body: AirtableApprovalIn,
    x_marketing_brain_secret: str = Header(default="", alias="X-Marketing-Brain-Secret"),
):
    config = _require_webhook_secret(x_marketing_brain_secret)
    orchestrator = _build_orchestrator(config)
    try:
        return orchestrator.record_approval(
            record_id,
            stage=body.stage,
            decision=body.decision,
            comment=body.comment,
            approved_by=body.approved_by,
        )
    except WorkflowError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    except AirtableError as exc:
        if exc.status_code == 404:
            raise HTTPException(404, "Airtable record not found") from exc
        raise HTTPException(502, f"Airtable upstream error: {exc.detail}") from exc
    finally:
        close = getattr(orchestrator.client, "close", None)
        if callable(close):
            close()

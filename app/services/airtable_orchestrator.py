"""Source-locked Airtable → AI → Airtable content workflow."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .airtable import AirtableClient, AirtableConfig


CONTENT = {
    "content_id": "fldqC1JF7C7UZZoSO",
    "brand": "fldieKw3Yjch0vvnl",
    "publish_date": "fldKaYONKCIIe92pg",
    "format": "fldWwvwm3BNUF7jV6",
    "template": "fldOAFQeMpz67Drky",
    "status": "fldX6UiqBgM40oHAH",
    "priority": "fldZS20AKxP0t3n2E",
    "topic": "fldyaJTwGmQ1ZKWjV",
    "perspective": "fldwiWijkMbQ3ajxA",
    "selected_concept": "fldFLYgamr9H9725I",
    "platforms": "fldEG57bc66PSOLLB",
    "concept_a": "fld3R0zQpGwfJ5UbE",
    "concept_b": "fldd3LCYuQAVJcsMb",
    "concept_c": "fldDeuuMEztfPzPQP",
    "caption": "fldZBzeD9z8M9hdMa",
    "hashtags": "flddAMXql9rW5wPYa",
    "cta": "fldRYFUHZDVtuG972",
    "image_prompt": "fldypoCN3Qsbl7aaz",
    "trigger": "fldcAjd1ibCwvFEkl",
    "approve_design": "fld7c83iBvI14ySHh",
    "qa_status": "fldzBesSqdXLXibTL",
    "backend_job_id": "fldNd3222reuwZpR8",
    "backend_status": "fldlpyz41tT5a3gdQ",
    "backend_response": "fldmFMy0KULUk2MjS",
    "error_log": "fldFvM32SqWVeUA8E",
    "scheduled_at": "fldawHX3uu0MKeUJf",
    "brand_profile": "fldY1bzXJMCUD6gsS",
    "slides": "fld71vYohgfjGWtJb",
    "claims": "fldeC8ASJcUUcX4xW",
    "projects": "fldlkPcyx5w127HQo",
}

BRAND = {
    "name": "fld4qhOeswbxWyPhx",
    "website": "fldjxOs3lSDEZkumK",
    "instagram": "fldYlDtO84I6kK7RC",
    "contact": "fldgQLj4lxCSME2vp",
    "tone": "fldzvYoNtKG0TjsFt",
    "audience": "fldxJ1ZxdJIxgqU4J",
    "visual": "fld3AuWN2IMZRz4cq",
    "cta": "fldSytlsUdMPvykko",
    "forbidden": "fldR7XX10PhEK0TTV",
    "active": "fldmXWoI0BNNNglX4",
}

CLAIM = {
    "brand": "fldUiQQmGdNhYGxqr",
    "subject": "fldbt8zWZKfvj90sI",
    "claim": "fldRAzG2Da0bNf945",
    "source_url": "fldBF8Lk1rtoSHPDH",
    "source_date": "fldSsgWsOnAdvxKjN",
    "verification": "fldaifYyqIZ6wq8nf",
    "last_verified": "fldf8dSP45vTu2ktA",
}

PROJECT = {
    "name": "fldy6ZXo18NmyELo1",
    "brand": "fldfQrS9OoPVwKjsb",
    "developer": "fld8huzMD8lBP9XLw",
    "location": "fldmoMWK3Djd9fiwS",
    "registration": "fld1GorCfkuUQ1qUU",
    "price": "fldgVtcyxAYSlG9SQ",
    "configurations": "fldfSnggVL1F5xqUi",
    "source_url": "fld2uzM8U1f3yggWv",
    "verified_date": "fldYwNQLqs61NuLpi",
    "active": "fld0PMjoNQ5x1Ao53",
}

RUN = {
    "run_id": "fldP9K8pdgkUbH3Z3",
    "stage": "fldeCiltj967TstHY",
    "status": "fldXXszcTDMxe90AJ",
    "started_at": "fldvMAgCWl6Cahmpu",
    "completed_at": "fldjo9kNdv8DAqwcI",
    "backend_job_id": "fldDDtjuhJPkAqwoj",
    "git_sha": "fld5zg8Hpo1W6nSdp",
    "model": "fld0yuYxvqfyD5t73",
    "request": "fldGNaSXDLHvDp3mD",
    "response": "fldb9PUkwhKyZIygp",
    "error": "fldveVABdQR3ESlJT",
    "content": "fldRd9B4tHA0lx4Rh",
}

SLIDE = {
    "slide_id": "fldEvvao5R4Z0sTqu",
    "number": "fldX4Dz0Apvt8wKB9",
    "headline": "fldHPKPE9ktSGy5vg",
    "body": "fldMYSRqLGAPskSqD",
    "visual": "fldtg2MliqMUkOT13",
    "image_prompt": "fldEw5zeQnaXCuVJB",
    "qa_status": "fld3p012XGuAaX8tp",
    "content": "fldeKdOJFbrNwjShl",
}

APPROVAL = {
    "approval_id": "fldHEkRD76gOInMV0",
    "stage": "fldBOHIQACRxjTOBH",
    "decision": "fldL48oKRQ8p3adnp",
    "comment": "fldvENq0yi9kKCsCy",
    "approved_by": "fldTWvSKU4jgrlHB8",
    "decision_at": "fldYAJupSySPAPsEG",
    "content": "fldAwZzy5h8HGxuaM",
}

FACT_TEMPLATES = {
    "Market Intelligence",
    "Project Spotlight",
    "Location & Investment Story",
}
FACT_TERMS = {
    "price",
    "cost",
    "roi",
    "return",
    "rera",
    "tgrera",
    "registration",
    "distance",
    "km",
    "metro",
    "airport",
    "highway",
    "investment",
    "appreciation",
    "infrastructure",
}

_RECORD_LOCKS: dict[str, threading.Lock] = {}
_RECORD_LOCKS_GUARD = threading.Lock()


class WorkflowError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _git_sha() -> str:
    """The deployed commit, whichever host we are on.

    Each platform exposes it under its own name; GIT_SHA is the manual escape
    hatch for hosts that expose none.
    """
    for var in ("RAILWAY_GIT_COMMIT_SHA", "RENDER_GIT_COMMIT", "GIT_SHA"):
        sha = os.environ.get(var, "").strip()
        if sha:
            return sha
    return ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("name", "")
    return str(value).strip()


def _links(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and item.get("id"):
            result.append(str(item["id"]))
    return result


def _json(value: Any, limit: int = 50_000) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:limit]


def _record_lock(record_id: str) -> threading.Lock:
    with _RECORD_LOCKS_GUARD:
        return _RECORD_LOCKS.setdefault(record_id, threading.Lock())


class AirtableOrchestrator:
    """Executes one idempotent content stage; n8n remains the retry scheduler."""

    def __init__(
        self,
        client: AirtableClient,
        config: AirtableConfig,
        ai_engine: Any,
    ):
        self.client = client
        self.config = config
        self.ai = ai_engine

    def run(
        self,
        record_id: str,
        *,
        requested_stage: str = "auto",
        dry_run: bool = False,
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        with _record_lock(record_id):
            return self._run_locked(
                record_id,
                requested_stage=requested_stage,
                dry_run=dry_run,
                idempotency_key=idempotency_key,
            )

    def _run_locked(
        self,
        record_id: str,
        *,
        requested_stage: str,
        dry_run: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        idempotency_key = idempotency_key.strip()
        record = self.client.get_record(self.config.content_table_id, record_id)
        fields = record.get("fields") or {}
        if not isinstance(fields, dict):
            raise WorkflowError(422, "Content Master record has no readable fields")

        previous_job = _text(fields.get(CONTENT["backend_job_id"]))
        previous_status = _text(fields.get(CONTENT["backend_status"]))
        if idempotency_key and previous_job == idempotency_key and previous_status == "Succeeded":
            stored: dict[str, Any] = {}
            try:
                decoded = json.loads(_text(fields.get(CONTENT["backend_response"])))
                if isinstance(decoded, dict):
                    stored = decoded
            except (TypeError, ValueError):
                pass
            return {
                **stored,
                "ok": True,
                "idempotent": True,
                "record_id": record_id,
                "job_id": previous_job,
                "status": stored.get("status") or _text(fields.get(CONTENT["status"])),
            }
        if previous_status == "Running":
            raise WorkflowError(409, "This content item already has a running backend job")

        topic = _text(fields.get(CONTENT["topic"]))
        brand_name = _text(fields.get(CONTENT["brand"]))
        if not topic:
            raise WorkflowError(422, "Topic is required in Content Master")
        if not brand_name:
            raise WorkflowError(422, "Brand is required in Content Master")

        stage = self._choose_stage(requested_stage, fields)
        brand = self._load_brand(fields, brand_name)
        evidence = self._load_evidence(fields, brand_name)
        needs_evidence = self._requires_evidence(fields)
        research_gap = self._research_gap_reason(stage, fields, brand, evidence, needs_evidence)

        plan = {
            "record_id": record_id,
            "content_id": _text(fields.get(CONTENT["content_id"])),
            "stage": stage,
            "brand": brand_name,
            "format": _text(fields.get(CONTENT["format"])),
            "requires_verified_evidence": needs_evidence,
            "verified_source_count": len(evidence),
            "research_gap": research_gap,
        }
        if dry_run:
            return {"ok": True, "dry_run": True, "plan": plan}

        job_id = idempotency_key or f"job-{uuid.uuid4().hex}"
        self.client.update_record(
            self.config.content_table_id,
            record_id,
            {
                CONTENT["trigger"]: False,
                CONTENT["backend_job_id"]: job_id,
                CONTENT["backend_status"]: "Running",
                CONTENT["backend_response"]: "",
                CONTENT["error_log"]: "",
            },
        )

        run_record_id = ""
        try:
            run_record_id = self._start_run(record_id, job_id, stage, plan)
            if research_gap:
                result = {
                    "ok": True,
                    "record_id": record_id,
                    "job_id": job_id,
                    "stage": stage,
                    "status": "NEEDS_RESEARCH",
                    "reason": research_gap,
                }
                self.client.update_record(
                    self.config.content_table_id,
                    record_id,
                    {
                        CONTENT["status"]: "NEEDS_RESEARCH",
                        CONTENT["backend_status"]: "Succeeded",
                        CONTENT["backend_response"]: _json(result),
                        CONTENT["error_log"]: "",
                    },
                )
                self._finish_run(run_record_id, "Succeeded", result)
                return result

            if stage == "concepts":
                result = self._run_concepts(record_id, job_id, fields, brand, evidence)
            elif stage == "package":
                result = self._run_package(record_id, job_id, fields, brand, evidence)
            else:
                result = self._run_qa(record_id, job_id, fields, brand, evidence)
            self._finish_run(run_record_id, "Succeeded", result)
            return result
        except Exception as exc:
            detail = self._safe_error(exc)
            try:
                self.client.update_record(
                    self.config.content_table_id,
                    record_id,
                    {
                        CONTENT["status"]: "Failed",
                        CONTENT["backend_status"]: "Failed",
                        CONTENT["error_log"]: detail,
                    },
                )
            except Exception:
                pass
            if run_record_id:
                try:
                    self.client.update_record(
                        self.config.runs_table_id,
                        run_record_id,
                        {
                            RUN["status"]: "Failed",
                            RUN["completed_at"]: _now(),
                            RUN["error"]: detail,
                        },
                    )
                except Exception:
                    pass
            raise

    def record_approval(
        self,
        record_id: str,
        *,
        stage: str,
        decision: str,
        comment: str = "",
        approved_by: str = "",
    ) -> dict[str, Any]:
        with _record_lock(record_id):
            record = self.client.get_record(self.config.content_table_id, record_id)
            fields = record.get("fields") or {}
            current = _text(fields.get(CONTENT["status"]))
            expected = {
                "Direction": {"Concepts Ready"},
                "Copy": {"Copy Ready"},
                "Design": {"Design Approved"},
                "Final": {"Final Approval"},
            }
            if current not in expected[stage]:
                allowed = ", ".join(sorted(expected[stage]))
                raise WorkflowError(409, f"{stage} approval requires Status: {allowed}")
            if stage == "Direction" and decision == "Approved":
                if not _text(fields.get(CONTENT["selected_concept"])):
                    raise WorkflowError(409, "Select a concept before approving direction")

            if decision == "Approved":
                next_status = {
                    "Direction": "Direction Selected",
                    "Copy": "Design Approved",
                    "Design": "QA Review",
                    "Final": "Scheduled" if fields.get(CONTENT["scheduled_at"]) else "Final Approval",
                }[stage]
            elif decision == "Changes Requested":
                next_status = {
                    "Direction": "Concepts Ready",
                    "Copy": "Direction Selected",
                    "Design": "Copy Ready",
                    "Final": "QA Review",
                }[stage]
            else:
                next_status = current

            approval_id = f"approval-{uuid.uuid4().hex}"
            approval = self.client.create_record(
                self.config.approvals_table_id,
                {
                    APPROVAL["approval_id"]: approval_id,
                    APPROVAL["stage"]: stage,
                    APPROVAL["decision"]: decision,
                    APPROVAL["comment"]: comment[:5_000],
                    APPROVAL["approved_by"]: approved_by[:200],
                    APPROVAL["decision_at"]: _now(),
                    APPROVAL["content"]: [record_id],
                },
            )
            result = {
                "ok": True,
                "record_id": record_id,
                "approval_record_id": _text(approval.get("id")),
                "stage": stage,
                "decision": decision,
                "status": next_status,
                "schedule_required": stage == "Final" and decision == "Approved" and next_status != "Scheduled",
            }
            updates: dict[str, Any] = {
                CONTENT["status"]: next_status,
                CONTENT["backend_response"]: _json(result),
                CONTENT["error_log"]: "",
            }
            if stage == "Design" and decision == "Approved":
                updates[CONTENT["approve_design"]] = True
            self.client.update_record(self.config.content_table_id, record_id, updates)
            return result

    def _choose_stage(self, requested: str, fields: dict[str, Any]) -> str:
        allowed = {"auto", "concepts", "package", "qa"}
        if requested not in allowed:
            raise WorkflowError(422, f"stage must be one of: {', '.join(sorted(allowed))}")
        status = _text(fields.get(CONTENT["status"]))
        if requested != "auto":
            stage = requested
        else:
            selected = _text(fields.get(CONTENT["selected_concept"]))
            if status in {"New", "Researching", "NEEDS_RESEARCH"}:
                stage = "concepts"
            elif status == "Direction Selected" or (status == "Concepts Ready" and selected):
                stage = "package"
            elif status == "QA Review":
                stage = "qa"
            else:
                raise WorkflowError(
                    409,
                    "No automatic stage is valid for the current Status. "
                    "Use New/Researching for concepts, select a direction for package, or use QA Review for QA.",
                )

        allowed_statuses = {
            "concepts": {"New", "Researching", "NEEDS_RESEARCH"},
            "package": {"Concepts Ready", "Direction Selected"},
            "qa": {"QA Review"},
        }
        if status not in allowed_statuses[stage]:
            expected = ", ".join(sorted(allowed_statuses[stage]))
            raise WorkflowError(409, f"{stage} cannot run from Status '{status}'. Expected one of: {expected}")
        if stage == "package" and not _text(fields.get(CONTENT["selected_concept"])):
            raise WorkflowError(409, "Select a concept before running the production package")
        if stage == "qa" and not _text(fields.get(CONTENT["caption"])):
            raise WorkflowError(409, "A production package with a caption is required before QA")
        return stage

    def _load_brand(self, fields: dict[str, Any], expected_name: str) -> dict[str, Any]:
        profile_ids = _links(fields.get(CONTENT["brand_profile"]))
        if len(profile_ids) != 1:
            raise WorkflowError(422, "Link exactly one active Brand Rules record in Brand Profile")
        record = self.client.get_record(self.config.brand_rules_table_id, profile_ids[0])
        rules = record.get("fields") or {}
        actual_name = _text(rules.get(BRAND["name"]))
        if actual_name.casefold() != expected_name.casefold():
            raise WorkflowError(422, "Content Master Brand does not match the linked Brand Profile")
        if rules.get(BRAND["active"]) is not True:
            raise WorkflowError(422, "The linked Brand Profile is not active")

        channels = fields.get(CONTENT["platforms"]) or ["Instagram"]
        if not isinstance(channels, list):
            channels = [channels]
        return {
            "name": actual_name,
            "website": _text(rules.get(BRAND["website"])),
            "profile": {
                "brand_voice": {
                    "tone": _text(rules.get(BRAND["tone"])),
                    "words_we_avoid": [_text(rules.get(BRAND["forbidden"]))],
                },
                "target_audience": [{"persona": _text(rules.get(BRAND["audience"]))}],
                "positioning": _text(rules.get(BRAND["tone"])),
                "brand_kit": {"style": _text(rules.get(BRAND["visual"]))},
            },
            "setup": {"channels": [_text(channel).lower() for channel in channels if _text(channel)]},
            "airtable_rules": {
                "required_cta": _text(rules.get(BRAND["cta"])),
                "forbidden_claims": _text(rules.get(BRAND["forbidden"])),
                "instagram": _text(rules.get(BRAND["instagram"])),
                "contact": _text(rules.get(BRAND["contact"])),
            },
        }

    def _load_evidence(self, fields: dict[str, Any], expected_brand: str) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for record_id in _links(fields.get(CONTENT["claims"])):
            record = self.client.get_record(self.config.claims_table_id, record_id)
            claim = record.get("fields") or {}
            claim_brand = _text(claim.get(CLAIM["brand"]))
            if claim_brand.casefold() != expected_brand.casefold():
                raise WorkflowError(422, "A linked Verified Claim belongs to a different brand")
            if _text(claim.get(CLAIM["verification"])) != "Verified":
                continue
            if not _text(claim.get(CLAIM["source_url"])):
                continue
            evidence.append(
                {
                    "kind": "verified_claim",
                    "subject": _text(claim.get(CLAIM["subject"])),
                    "claim": _text(claim.get(CLAIM["claim"])),
                    "source_url": _text(claim.get(CLAIM["source_url"])),
                    "source_date": _text(claim.get(CLAIM["source_date"])),
                    "verified_at": _text(claim.get(CLAIM["last_verified"])),
                }
            )
        for record_id in _links(fields.get(CONTENT["projects"])):
            record = self.client.get_record(self.config.projects_table_id, record_id)
            project = record.get("fields") or {}
            project_brand = _text(project.get(PROJECT["brand"]))
            if project_brand.casefold() != expected_brand.casefold():
                raise WorkflowError(422, "A linked Project or Location belongs to a different brand")
            if project.get(PROJECT["active"]) is not True:
                continue
            if not _text(project.get(PROJECT["source_url"])) or not _text(project.get(PROJECT["verified_date"])):
                continue
            evidence.append(
                {
                    "kind": "verified_project",
                    "name": _text(project.get(PROJECT["name"])),
                    "developer": _text(project.get(PROJECT["developer"])),
                    "location": _text(project.get(PROJECT["location"])),
                    "registration": _text(project.get(PROJECT["registration"])),
                    "price_from": project.get(PROJECT["price"]),
                    "configurations": _text(project.get(PROJECT["configurations"])),
                    "source_url": _text(project.get(PROJECT["source_url"])),
                    "verified_at": _text(project.get(PROJECT["verified_date"])),
                }
            )
        return evidence

    @staticmethod
    def _requires_evidence(fields: dict[str, Any]) -> bool:
        template = _text(fields.get(CONTENT["template"]))
        factual_fields = (
            "topic",
            "perspective",
            "selected_concept",
            "concept_a",
            "concept_b",
            "concept_c",
            "caption",
            "cta",
            "image_prompt",
        )
        text = "\n".join(_text(fields.get(CONTENT[name])) for name in factual_fields).casefold()
        return template in FACT_TEMPLATES or any(
            re.search(rf"\b{re.escape(term)}\b", text) for term in FACT_TERMS
        )

    @staticmethod
    def _research_gap_reason(
        stage: str,
        fields: dict[str, Any],
        brand: dict[str, Any],
        evidence: list[dict[str, Any]],
        needs_evidence: bool,
    ) -> str:
        if needs_evidence and not evidence:
            return "No linked, same-brand Verified Claims or active sourced Projects & Locations were found."
        if stage != "qa":
            return ""
        generated = "\n".join(
            _text(fields.get(CONTENT[name]))
            for name in ("selected_concept", "caption", "cta", "image_prompt")
        )
        generated_numbers = set(re.findall(r"(?<![\w])\d+(?:[.,]\d+)?%?", generated.casefold()))
        if not generated_numbers:
            return ""
        source_text = _json(
            {"evidence": evidence, "brand_rules": brand.get("airtable_rules", {})},
            20_000,
        ).casefold()
        source_numbers = set(re.findall(r"(?<![\w])\d+(?:[.,]\d+)?%?", source_text))
        unsupported = sorted(generated_numbers - source_numbers)
        if unsupported:
            return "Generated copy contains numbers not present in verified evidence: " + ", ".join(unsupported)
        return ""

    def _start_run(
        self,
        record_id: str,
        job_id: str,
        stage: str,
        plan: dict[str, Any],
    ) -> str:
        run_id = f"run-{uuid.uuid4().hex}"
        if stage == "package":
            stage_name = "Storyboard" if plan.get("format") in {"Carousel", "Reel Motion Lite"} else "Copy"
        else:
            stage_name = {"concepts": "Concepts", "qa": "QA"}[stage]
        record = self.client.create_record(
            self.config.runs_table_id,
            {
                RUN["run_id"]: run_id,
                RUN["stage"]: stage_name,
                RUN["status"]: "Running",
                RUN["started_at"]: _now(),
                RUN["backend_job_id"]: job_id,
                RUN["git_sha"]: _git_sha()[:80],
                RUN["model"]: os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")[:120],
                RUN["request"]: _json(plan),
                RUN["content"]: [record_id],
            },
        )
        return _text(record.get("id"))

    def _finish_run(self, run_record_id: str, status: str, result: dict[str, Any]) -> None:
        if not run_record_id:
            return
        self.client.update_record(
            self.config.runs_table_id,
            run_record_id,
            {
                RUN["status"]: status,
                RUN["completed_at"]: _now(),
                RUN["response"]: _json(result),
                RUN["error"]: "",
            },
        )

    def _run_concepts(
        self,
        record_id: str,
        job_id: str,
        fields: dict[str, Any],
        brand: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        fmt = self._engine_format(fields)
        channel = self._channel(fields)
        options = {
            "topic": _text(fields.get(CONTENT["topic"])),
            "formats": [fmt],
            "instructions": "Follow the source lock and brand rules supplied in the dedicated evidence block.",
            "source_evidence": self._source_payload(fields, brand, evidence),
        }
        ideas = self.ai.generate_ideas(brand, channel, count=3, options=options)
        if not isinstance(ideas, list) or len(ideas) < 3:
            raise RuntimeError("AI returned fewer than three concepts")
        concept_text = [self._concept_text(idea) for idea in ideas[:3]]
        result = {
            "ok": True,
            "record_id": record_id,
            "job_id": job_id,
            "stage": "concepts",
            "status": "Concepts Ready",
            "concept_count": 3,
        }
        self.client.update_record(
            self.config.content_table_id,
            record_id,
            {
                CONTENT["concept_a"]: concept_text[0],
                CONTENT["concept_b"]: concept_text[1],
                CONTENT["concept_c"]: concept_text[2],
                CONTENT["status"]: "Concepts Ready",
                CONTENT["backend_status"]: "Succeeded",
                CONTENT["backend_response"]: _json(result),
                CONTENT["error_log"]: "",
            },
        )
        return result

    def _run_package(
        self,
        record_id: str,
        job_id: str,
        fields: dict[str, Any],
        brand: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        fmt = self._engine_format(fields)
        selected = _text(fields.get(CONTENT["selected_concept"]))
        idea = {
            "title": selected.splitlines()[0][:160],
            "format": fmt,
            "hook": selected.splitlines()[0][:300],
            "concept": f"{selected}\n\n{self._source_lock(fields, brand, evidence)}",
            "cta": brand["airtable_rules"]["required_cta"],
        }
        creative = self.ai.produce_creative(
            brand,
            idea,
            self._channel(fields),
            source_evidence=self._source_payload(fields, brand, evidence),
        )
        if not isinstance(creative, dict):
            raise RuntimeError("AI returned an invalid production package")
        slide_rows = self._slide_rows(record_id, fields, creative, fmt)
        created_frames, updated_frames = self._sync_slide_rows(fields, slide_rows)
        result = {
            "ok": True,
            "record_id": record_id,
            "job_id": job_id,
            "stage": "package",
            "status": "Copy Ready",
            "frame_count": len(slide_rows),
            "created_frames": created_frames,
            "updated_frames": updated_frames,
        }
        self.client.update_record(
            self.config.content_table_id,
            record_id,
            {
                CONTENT["caption"]: _text(creative.get("caption")),
                CONTENT["hashtags"]: self._hashtags(creative.get("hashtags")),
                CONTENT["cta"]: _text(creative.get("cta")) or brand["airtable_rules"]["required_cta"],
                CONTENT["image_prompt"]: _text(creative.get("image_prompt")),
                CONTENT["status"]: "Copy Ready",
                CONTENT["backend_status"]: "Succeeded",
                CONTENT["backend_response"]: _json(result),
                CONTENT["error_log"]: "",
            },
        )
        return result

    def _run_qa(
        self,
        record_id: str,
        job_id: str,
        fields: dict[str, Any],
        brand: dict[str, Any],
        _evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        payload = {
            "title": _text(fields.get(CONTENT["topic"])),
            "format": self._engine_format(fields),
            "caption": _text(fields.get(CONTENT["caption"])),
            "hashtags": _text(fields.get(CONTENT["hashtags"])),
            "cta": _text(fields.get(CONTENT["cta"])),
            "image_prompt": _text(fields.get(CONTENT["image_prompt"])),
        }
        audit = self.ai.algo_audit(
            brand,
            payload,
            source_evidence=self._source_payload(fields, brand, _evidence),
        )
        if not isinstance(audit, dict):
            raise RuntimeError("AI returned an invalid QA audit")
        try:
            score = int(audit.get("algo_score", 0))
        except (TypeError, ValueError):
            score = 0
        unsupported_claims = audit.get("unsupported_claims") or []
        if not isinstance(unsupported_claims, list):
            unsupported_claims = [_text(unsupported_claims)]
        source_lock_pass = audit.get("source_lock_pass") is True and not unsupported_claims
        passed = score >= 70 and source_lock_pass
        status = "Final Approval" if passed else ("NEEDS_RESEARCH" if not source_lock_pass else "QA Review")
        qa_status = "Passed" if passed else "Failed"
        result = {
            "ok": True,
            "record_id": record_id,
            "job_id": job_id,
            "stage": "qa",
            "status": status,
            "qa_status": qa_status,
            "algo_score": score,
            "source_lock_pass": source_lock_pass,
            "unsupported_claims": unsupported_claims,
            "audit": audit,
        }
        self.client.update_record(
            self.config.content_table_id,
            record_id,
            {
                CONTENT["qa_status"]: qa_status,
                CONTENT["status"]: status,
                CONTENT["backend_status"]: "Succeeded",
                CONTENT["backend_response"]: _json(result),
                CONTENT["error_log"]: "",
            },
        )
        return result

    @staticmethod
    def _source_payload(
        fields: dict[str, Any],
        brand: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "verified_evidence": evidence,
            "brand_rules": brand.get("airtable_rules", {}),
            "perspective": _text(fields.get(CONTENT["perspective"])),
        }

    def _source_lock(
        self,
        fields: dict[str, Any],
        brand: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> str:
        return (
            "SOURCE LOCK: Use only the verified evidence below for factual claims. "
            "Do not invent prices, returns, registrations, distances, infrastructure dates, scarcity, "
            "product specifications, or testimonials. If a needed fact is absent, write NEEDS_RESEARCH. "
            f"Authoritative context: {_json(self._source_payload(fields, brand, evidence), 12_000)}"
        )

    @staticmethod
    def _engine_format(fields: dict[str, Any]) -> str:
        return {
            "Static Post": "post",
            "Carousel": "carousel",
            "Reel Motion Lite": "reel",
        }.get(_text(fields.get(CONTENT["format"])), "post")

    @staticmethod
    def _channel(fields: dict[str, Any]) -> str:
        platforms = fields.get(CONTENT["platforms"]) or ["Instagram"]
        if not isinstance(platforms, list):
            platforms = [platforms]
        return (_text(platforms[0]) or "Instagram").lower()

    @staticmethod
    def _concept_text(idea: Any) -> str:
        if not isinstance(idea, dict):
            return _text(idea)
        parts = [
            _text(idea.get("title")),
            f"Hook: {_text(idea.get('hook'))}",
            f"Concept: {_text(idea.get('concept'))}",
            f"CTA: {_text(idea.get('cta'))}",
        ]
        return "\n".join(part for part in parts if part and not part.endswith(": "))

    @staticmethod
    def _hashtags(value: Any) -> str:
        if isinstance(value, dict):
            tags = []
            for items in value.values():
                if isinstance(items, list):
                    tags.extend(_text(item) for item in items)
            return " ".join(tag if tag.startswith("#") else f"#{tag}" for tag in tags if tag)
        if isinstance(value, list):
            return " ".join(_text(item) for item in value)
        return _text(value)

    def _sync_slide_rows(
        self,
        fields: dict[str, Any],
        rows: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Upsert frames by sequence so retries cannot duplicate a storyboard."""
        if not rows:
            return 0, 0
        existing_by_number: dict[int, str] = {}
        for record_id in _links(fields.get(CONTENT["slides"])):
            record = self.client.get_record(self.config.slides_table_id, record_id)
            record_fields = record.get("fields") or {}
            try:
                number = int(record_fields.get(SLIDE["number"]))
            except (TypeError, ValueError):
                continue
            existing_by_number.setdefault(number, record_id)

        create_rows = []
        updated = 0
        for row in rows:
            number = int(row[SLIDE["number"]])
            existing_id = existing_by_number.get(number)
            if existing_id:
                self.client.update_record(self.config.slides_table_id, existing_id, row)
                updated += 1
            else:
                create_rows.append(row)
        if create_rows:
            self.client.create_records(self.config.slides_table_id, create_rows)
        return len(create_rows), updated

    @staticmethod
    def _slide_rows(
        record_id: str,
        fields: dict[str, Any],
        creative: dict[str, Any],
        fmt: str,
    ) -> list[dict[str, Any]]:
        content_id = _text(fields.get(CONTENT["content_id"])) or record_id
        source: list[dict[str, Any]]
        if fmt == "carousel":
            source = [row for row in (creative.get("slides") or []) if isinstance(row, dict)][:10]
        elif fmt == "reel":
            shots = ((creative.get("script") or {}).get("shots") or [])[:2]
            source = []
            for number, shot in enumerate(shots, start=1):
                if not isinstance(shot, dict):
                    continue
                source.append(
                    {
                        "n": number,
                        "headline": shot.get("on_screen_text", ""),
                        "body": shot.get("dialogue_or_vo", ""),
                        "visual_direction": " | ".join(
                            _text(shot.get(key)) for key in ("camera", "action", "broll") if _text(shot.get(key))
                        ),
                        "image_prompt": shot.get("action", ""),
                    }
                )
        else:
            source = []

        rows = []
        for index, item in enumerate(source, start=1):
            number = item.get("n", index)
            try:
                number = int(number)
            except (TypeError, ValueError):
                number = index
            rows.append(
                {
                    SLIDE["slide_id"]: f"{content_id}-F{number:02d}",
                    SLIDE["number"]: number,
                    SLIDE["headline"]: _text(item.get("headline") or item.get("on_screen_text")),
                    SLIDE["body"]: _text(item.get("body") or item.get("dialogue_or_vo")),
                    SLIDE["visual"]: _text(item.get("visual_direction") or item.get("design_notes")),
                    SLIDE["image_prompt"]: _text(item.get("image_prompt") or item.get("visual_direction")),
                    SLIDE["qa_status"]: "Pending",
                    SLIDE["content"]: [record_id],
                }
            )
        return rows

    def _safe_error(self, exc: Exception) -> str:
        detail = getattr(exc, "detail", str(exc)) or exc.__class__.__name__
        for secret in (self.config.token, self.config.webhook_secret):
            if secret:
                detail = detail.replace(secret, "[redacted]")
        return detail[:1_000]

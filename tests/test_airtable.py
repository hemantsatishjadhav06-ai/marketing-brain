"""Offline tests for the Airtable client, webhook, and content state machine."""
from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import engine
from app.main import app
from app.routes import airtable as airtable_route
from app.services.airtable import AirtableClient, AirtableConfig
from app.services.airtable_orchestrator import (
    APPROVAL,
    BRAND,
    CLAIM,
    CONTENT,
    RUN,
    SLIDE,
    AirtableOrchestrator,
    WorkflowError,
)


def config() -> AirtableConfig:
    return AirtableConfig(
        token="pat-test",
        webhook_secret="webhook-test",
        base_id="appvpMfpbNQDkUGeF",
        content_table_id="tblWu3YzDoasrj0OG",
        slides_table_id="tblAbMcwp6DipTQqu",
        claims_table_id="tbluMV1yECqSjpY0S",
        projects_table_id="tblXdFUMM6E6qSKLF",
        brand_rules_table_id="tblP2Gqh59vI79IqW",
        runs_table_id="tblir6QJU0Vo4qBeP",
        approvals_table_id="tbl7C6O77DDf6zd9D",
    )


def base_records(**overrides):
    fields = {
        CONTENT["content_id"]: "TEST-001",
        CONTENT["brand"]: "Neopolis Infra",
        CONTENT["format"]: "Carousel",
        CONTENT["template"]: "Buyer Education",
        CONTENT["status"]: "New",
        CONTENT["topic"]: "Five questions to ask before a site visit",
        CONTENT["platforms"]: ["Instagram", "Facebook"],
        CONTENT["brand_profile"]: ["rec-brand"],
    }
    fields.update(overrides)
    return {
        ("tblWu3YzDoasrj0OG", "rec-content"): {"id": "rec-content", "fields": fields},
        ("tblP2Gqh59vI79IqW", "rec-brand"): {
            "id": "rec-brand",
            "fields": {
                BRAND["name"]: "Neopolis Infra",
                BRAND["tone"]: "Evidence-first and locally informed",
                BRAND["audience"]: "West Hyderabad property buyers",
                BRAND["visual"]: "Premium editorial",
                BRAND["cta"]: "Contact the approved Neopolis channel",
                BRAND["forbidden"]: "No invented prices or guarantees",
                BRAND["active"]: True,
            },
        },
    }


class FakeClient:
    def __init__(self, records):
        self.records = deepcopy(records)
        self.updates = []
        self.created = []
        self.closed = False
        self._next = 0

    def get_record(self, table_id, record_id):
        try:
            return deepcopy(self.records[(table_id, record_id)])
        except KeyError as exc:
            raise AssertionError(f"Unexpected read: {table_id}/{record_id}") from exc

    def update_record(self, table_id, record_id, fields):
        self.updates.append((table_id, record_id, deepcopy(fields)))
        record = self.records.setdefault((table_id, record_id), {"id": record_id, "fields": {}})
        record["fields"].update(deepcopy(fields))
        return deepcopy(record)

    def create_record(self, table_id, fields):
        self._next += 1
        record_id = f"rec-created-{self._next}"
        record = {"id": record_id, "fields": deepcopy(fields)}
        self.records[(table_id, record_id)] = record
        self.created.append((table_id, [deepcopy(fields)]))
        return deepcopy(record)

    def create_records(self, table_id, rows):
        rows = deepcopy(list(rows))
        self.created.append((table_id, rows))
        result = []
        for fields in rows:
            self._next += 1
            record_id = f"rec-created-{self._next}"
            record = {"id": record_id, "fields": fields}
            self.records[(table_id, record_id)] = record
            result.append(deepcopy(record))
        return result

    def close(self):
        self.closed = True


class FakeAI:
    def __init__(self):
        self.idea_calls = 0
        self.package_calls = 0
        self.qa_calls = 0

    def generate_ideas(self, _brand, _channel, count, options):
        self.idea_calls += 1
        assert count == 3
        assert options["source_evidence"]["brand_rules"]
        return [
            {"title": f"Concept {n}", "hook": f"Hook {n}", "concept": f"Body {n}", "cta": "Verify first"}
            for n in range(1, 4)
        ]

    def produce_creative(self, _brand, idea, _channel, source_evidence=None):
        self.package_calls += 1
        assert "SOURCE LOCK" in idea["concept"]
        assert source_evidence["brand_rules"]
        return {
            "caption": "A source-safe caption",
            "hashtags": {"niche": ["hyderabad", "#buyerchecklist"]},
            "cta": "Book a verified consultation",
            "image_prompt": "Clean evidence-first carousel cover",
            "slides": [
                {
                    "n": n,
                    "headline": f"Slide {n}",
                    "body": f"Body {n}",
                    "visual_direction": f"Visual {n}",
                }
                for n in range(1, 13)
            ],
        }

    def algo_audit(self, _brand, payload, source_evidence=None):
        self.qa_calls += 1
        assert payload["caption"]
        assert source_evidence["brand_rules"]
        return {
            "algo_score": 82,
            "source_lock_pass": True,
            "unsupported_claims": [],
            "verdict": "Ready for human final approval",
        }


def orchestrator(records):
    client = FakeClient(records)
    ai = FakeAI()
    return AirtableOrchestrator(client, config(), ai), client, ai


def test_client_sends_bearer_token_and_field_ids():
    seen = {}

    def handler(request: httpx.Request):
        seen["authorization"] = request.headers["Authorization"]
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"id": "rec-content", "fields": {}})

    client = AirtableClient(config(), transport=httpx.MockTransport(handler), sleep=lambda _seconds: None)
    try:
        assert client.get_record(config().content_table_id, "rec-content")["id"] == "rec-content"
    finally:
        client.close()
    assert seen["authorization"] == "Bearer pat-test"
    assert seen["params"]["returnFieldsByFieldId"] == "true"


def test_client_retries_429_and_chunks_writes_at_ten():
    calls = {"retry": 0, "batches": []}

    def handler(request: httpx.Request):
        if request.method == "GET":
            calls["retry"] += 1
            if calls["retry"] == 1:
                return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": {"type": "RATE_LIMIT"}})
            return httpx.Response(200, json={"id": "rec-content", "fields": {}})
        body = json.loads(request.content)
        calls["batches"].append(len(body["records"]))
        return httpx.Response(
            200,
            json={"records": [{"id": f"rec-{i}", "fields": row["fields"]} for i, row in enumerate(body["records"])]},
        )

    client = AirtableClient(
        config(),
        transport=httpx.MockTransport(handler),
        max_retries=1,
        sleep=lambda _seconds: None,
    )
    try:
        client.get_record(config().content_table_id, "rec-content")
        created = client.create_records(config().slides_table_id, [{"field": n} for n in range(23)])
    finally:
        client.close()
    assert calls["retry"] == 2
    assert calls["batches"] == [10, 10, 3]
    assert len(created) == 23


def test_dry_run_performs_no_writes_or_generation():
    workflow, client, ai = orchestrator(base_records())
    result = workflow.run("rec-content", dry_run=True)
    assert result["dry_run"] is True
    assert result["plan"]["stage"] == "concepts"
    assert client.updates == []
    assert client.created == []
    assert ai.idea_calls == 0


def test_missing_verified_evidence_stops_before_ai():
    workflow, client, ai = orchestrator(
        base_records(
            **{
                CONTENT["template"]: "Market Intelligence",
                CONTENT["topic"]: "Infrastructure investment outlook",
            }
        )
    )
    result = workflow.run("rec-content")
    final_fields = client.records[(config().content_table_id, "rec-content")]["fields"]
    assert result["status"] == "NEEDS_RESEARCH"
    assert final_fields[CONTENT["status"]] == "NEEDS_RESEARCH"
    assert final_fields[CONTENT["backend_status"]] == "Succeeded"
    assert ai.idea_calls == 0
    assert any(table == config().runs_table_id for table, _rows in client.created)


def test_concepts_map_exactly_to_a_b_c():
    workflow, client, ai = orchestrator(base_records())
    result = workflow.run("rec-content", idempotency_key="automation-1")
    fields = client.records[(config().content_table_id, "rec-content")]["fields"]
    assert result["status"] == "Concepts Ready"
    assert fields[CONTENT["concept_a"]].startswith("Concept 1")
    assert fields[CONTENT["concept_b"]].startswith("Concept 2")
    assert fields[CONTENT["concept_c"]].startswith("Concept 3")
    assert fields[CONTENT["backend_job_id"]] == "automation-1"
    assert ai.idea_calls == 1


@pytest.mark.parametrize(
    ("overrides", "counter"),
    [
        ({CONTENT["status"]: "New"}, "idea_calls"),
        (
            {
                CONTENT["status"]: "Direction Selected",
                CONTENT["selected_concept"]: "Evidence-first buyer checklist",
            },
            "package_calls",
        ),
        (
            {
                CONTENT["status"]: "QA Review",
                CONTENT["caption"]: "Finished caption",
            },
            "qa_calls",
        ),
    ],
)
def test_successful_retry_returns_stored_result_before_status_routing(overrides, counter):
    workflow, _client, ai = orchestrator(base_records(**overrides))
    first = workflow.run("rec-content", idempotency_key="same-automation-run")
    calls_after_first = getattr(ai, counter)
    second = workflow.run("rec-content", idempotency_key="same-automation-run")
    assert first["status"] == second["status"]
    assert second["idempotent"] is True
    assert getattr(ai, counter) == calls_after_first == 1


def test_duplicate_running_request_returns_conflict():
    records = base_records(**{CONTENT["backend_status"]: "Running"})
    workflow, client, ai = orchestrator(records)
    with pytest.raises(WorkflowError) as exc:
        workflow.run("rec-content")
    assert exc.value.status_code == 409
    assert client.updates == []
    assert ai.idea_calls == 0


def test_explicit_stage_cannot_move_a_published_item_backwards():
    records = base_records(**{CONTENT["status"]: "Published"})
    workflow, client, ai = orchestrator(records)
    with pytest.raises(WorkflowError) as exc:
        workflow.run("rec-content", requested_stage="concepts")
    assert exc.value.status_code == 409
    assert client.updates == []
    assert ai.idea_calls == 0


def test_cross_brand_evidence_is_rejected_before_ai():
    records = base_records(
        **{
            CONTENT["template"]: "Market Intelligence",
            CONTENT["claims"]: ["rec-claim"],
        }
    )
    records[(config().claims_table_id, "rec-claim")] = {
        "id": "rec-claim",
        "fields": {
            CLAIM["brand"]: "MoreSpace",
            CLAIM["claim"]: "A fact from another tenant",
            CLAIM["source_url"]: "https://example.com/source",
            CLAIM["verification"]: "Verified",
        },
    }
    workflow, client, ai = orchestrator(records)
    with pytest.raises(WorkflowError) as exc:
        workflow.run("rec-content")
    assert exc.value.status_code == 422
    assert client.updates == []
    assert ai.idea_calls == 0


def test_package_creates_at_most_ten_linked_carousel_slides():
    records = base_records(
        **{
            CONTENT["status"]: "Direction Selected",
            CONTENT["selected_concept"]: "Evidence-first buyer checklist",
        }
    )
    workflow, client, ai = orchestrator(records)
    result = workflow.run("rec-content")
    slide_batches = [rows for table, rows in client.created if table == config().slides_table_id]
    fields = client.records[(config().content_table_id, "rec-content")]["fields"]
    assert result["frame_count"] == 10
    assert len(slide_batches) == 1
    assert len(slide_batches[0]) == 10
    assert slide_batches[0][0][SLIDE["content"]] == ["rec-content"]
    assert fields[CONTENT["status"]] == "Copy Ready"
    assert "#hyderabad" in fields[CONTENT["hashtags"]]
    assert ai.package_calls == 1


def test_package_retry_updates_existing_frame_instead_of_duplicating_it():
    records = base_records(
        **{
            CONTENT["status"]: "Direction Selected",
            CONTENT["selected_concept"]: "Evidence-first buyer checklist",
            CONTENT["slides"]: ["rec-slide-1"],
        }
    )
    records[(config().slides_table_id, "rec-slide-1")] = {
        "id": "rec-slide-1",
        "fields": {
            SLIDE["slide_id"]: "TEST-001-F01",
            SLIDE["number"]: 1,
            SLIDE["headline"]: "Old headline",
            SLIDE["content"]: ["rec-content"],
        },
    }
    workflow, client, _ai = orchestrator(records)
    result = workflow.run("rec-content")
    slide_batches = [rows for table, rows in client.created if table == config().slides_table_id]
    slide_updates = [
        row
        for table, record_id, row in client.updates
        if table == config().slides_table_id and record_id == "rec-slide-1"
    ]
    assert result["created_frames"] == 9
    assert result["updated_frames"] == 1
    assert len(slide_batches[0]) == 9
    assert slide_updates[-1][SLIDE["headline"]] == "Slide 1"


def test_qa_passes_to_human_final_approval():
    records = base_records(
        **{
            CONTENT["status"]: "QA Review",
            CONTENT["caption"]: "Finished caption",
            CONTENT["hashtags"]: "#buyerchecklist",
            CONTENT["cta"]: "Verify before deciding",
        }
    )
    workflow, client, ai = orchestrator(records)
    result = workflow.run("rec-content")
    fields = client.records[(config().content_table_id, "rec-content")]["fields"]
    assert result["qa_status"] == "Passed"
    assert fields[CONTENT["qa_status"]] == "Passed"
    assert fields[CONTENT["status"]] == "Final Approval"
    assert ai.qa_calls == 1


def test_qa_blocks_a_number_missing_from_verified_evidence():
    records = base_records(
        **{
            CONTENT["status"]: "QA Review",
            CONTENT["caption"]: "This project guarantees a 25% return.",
            CONTENT["claims"]: ["rec-claim"],
        }
    )
    records[(config().claims_table_id, "rec-claim")] = {
        "id": "rec-claim",
        "fields": {
            CLAIM["brand"]: "Neopolis Infra",
            CLAIM["claim"]: "The project includes a clubhouse.",
            CLAIM["source_url"]: "https://example.com/clubhouse",
            CLAIM["verification"]: "Verified",
        },
    }
    workflow, client, ai = orchestrator(records)
    result = workflow.run("rec-content")
    fields = client.records[(config().content_table_id, "rec-content")]["fields"]
    assert result["status"] == "NEEDS_RESEARCH"
    assert "25%" in result["reason"]
    assert fields[CONTENT["status"]] == "NEEDS_RESEARCH"
    assert ai.qa_calls == 0


def test_direction_approval_is_logged_and_advances_the_master_record():
    records = base_records(
        **{
            CONTENT["status"]: "Concepts Ready",
            CONTENT["selected_concept"]: "Selected evidence-first direction",
        }
    )
    workflow, client, _ai = orchestrator(records)
    result = workflow.record_approval(
        "rec-content",
        stage="Direction",
        decision="Approved",
        comment="Proceed with this direction",
        approved_by="content-lead",
    )
    approval_rows = [rows for table, rows in client.created if table == config().approvals_table_id]
    fields = client.records[(config().content_table_id, "rec-content")]["fields"]
    assert result["status"] == "Direction Selected"
    assert fields[CONTENT["status"]] == "Direction Selected"
    assert approval_rows[0][0][APPROVAL["decision"]] == "Approved"
    assert approval_rows[0][0][APPROVAL["content"]] == ["rec-content"]


def test_run_failure_marks_master_and_generation_run_failed():
    records = base_records()
    workflow, client, ai = orchestrator(records)

    def fail(*_args, **_kwargs):
        raise RuntimeError("upstream token pat-test must stay hidden")

    ai.generate_ideas = fail
    with pytest.raises(RuntimeError):
        workflow.run("rec-content")
    fields = client.records[(config().content_table_id, "rec-content")]["fields"]
    assert fields[CONTENT["status"]] == "Failed"
    assert fields[CONTENT["backend_status"]] == "Failed"
    assert "pat-test" not in fields[CONTENT["error_log"]]
    run_updates = [row for table, _record, row in client.updates if table == config().runs_table_id]
    assert run_updates[-1][RUN["status"]] == "Failed"


def test_large_source_evidence_reaches_idea_and_package_prompts(monkeypatch):
    prompts = []

    def fake_json_chat(_system, user, **_kwargs):
        prompts.append(user)
        return {"ideas": []} if "Generate 1 distinct" in user else {"caption": "ok"}

    monkeypatch.setattr(engine, "_json_chat", fake_json_chat)
    brand = {"name": "Test Brand"}
    source = {
        "verified_evidence": [
            {"claim": "x" * 2_000},
            {"claim": "TAIL-EVIDENCE-MARKER"},
        ]
    }
    engine.generate_ideas(
        brand,
        "instagram",
        count=1,
        options={"instructions": "y" * 2_000, "source_evidence": source},
    )
    engine.produce_creative(
        brand,
        {"title": "Test", "format": "post", "concept": "z" * 2_000},
        "instagram",
        source_evidence=source,
    )
    assert len(prompts) == 2
    assert all("TAIL-EVIDENCE-MARKER" in prompt for prompt in prompts)


def test_webhook_secret_and_route_contract(monkeypatch):
    monkeypatch.setenv("AIRTABLE_TOKEN", "pat-route")
    monkeypatch.setenv("AIRTABLE_WEBHOOK_SECRET", "route-secret")
    client = TestClient(app)

    denied = client.post(
        "/api/airtable/content/rec-content/run",
        headers={"X-Marketing-Brain-Secret": "wrong"},
        json={"dry_run": True},
    )
    assert denied.status_code == 401

    stub_client = SimpleNamespace(closed=False)
    stub_client.close = lambda: setattr(stub_client, "closed", True)
    stub = SimpleNamespace(
        client=stub_client,
        run=lambda record_id, **kwargs: {"ok": True, "record_id": record_id, **kwargs},
    )
    monkeypatch.setattr(airtable_route, "_build_orchestrator", lambda _config: stub)
    response = client.post(
        "/api/airtable/content/rec-content/run",
        headers={"X-Marketing-Brain-Secret": "route-secret"},
        json={"stage": "concepts", "dry_run": True, "idempotency_key": "route-1"},
    )
    assert response.status_code == 200
    assert response.json()["record_id"] == "rec-content"
    assert response.json()["requested_stage"] == "concepts"
    assert stub_client.closed is True

    health = client.get(
        "/api/airtable/health",
        headers={"X-Marketing-Brain-Secret": "route-secret"},
    )
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["connectivity_checked"] is False
    assert "/api/airtable/content/{record_id}/run" in client.get("/openapi.json").json()["paths"]

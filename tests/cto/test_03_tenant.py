"""03 MULTI-TENANT (BLOCKER) + IDOR — Org B (dental clinic) must never read or mutate
Org A (real-estate). Every brand-scoped resource, the workspace file server, and the
by-id sub-resources are attempted with B's token."""
from __future__ import annotations

import json

import pytest

from app.core import database as db
from app.routes import _shared
from app.services import memory as mem, workspace as ws

from .conftest import client, hdr, make_client_user, png_bytes, seed_creative, seed_idea, u


@pytest.fixture
def orgs(org_a, org_b):
    A, B = org_a["brand_id"], org_b["brand_id"]
    a_idea = seed_idea(A, title="A private idea")
    a_cre = seed_creative(A, title="A private creative")
    a_mem = mem.remember(A, "A's secret rule.", kind="rule")
    a_comp = db.insert_doc("competitors", A, {"gaps_we_can_own": []}, name="A rival", url="https://rival.invalid")
    from app.services import inbox
    convo, msg = inbox.record_inbound(A, "whatsapp", "+911111", "A customer message", "Cust")
    db.set_connector(A, "instagram", {"access_token": "A-TOKEN", "ig_user_id": "1"})
    db.insert_doc("metrics", A, {"views": 9}, channel="instagram", post_ref="p1")
    db.insert_doc("calendar_items", A, {"title": "A slot"}, channel="instagram", date="2030-01-01", time="10:00")
    db.insert_doc("publish_queue", A, {"simulated": True}, creative_id=a_cre, channel="instagram", mode="simulated", status="published")
    ws.write_text(org_a["brand"]["slug"], "instagram/creatives/secret.md", "A-SECRET-CONTENT")
    return {"A": A, "B": B, "a": org_a, "b": org_b, "a_idea": a_idea, "a_cre": a_cre, "a_mem": a_mem,
            "a_comp": a_comp, "a_convo": convo["id"], "a_msg": msg["id"], "a_slug": org_a["brand"]["slug"]}


def _snapshot(bid):
    out = {"brand": json.dumps(db.get_brand(bid), sort_keys=True)}
    for t in ("ideas", "creatives", "calendar_items", "publish_queue", "metrics", "competitors",
              "brand_memory", "conversations", "messages", "invites", "agent_runs"):
        out[t] = json.dumps(db.list_docs(t, bid), sort_keys=True)
    out["connectors"] = json.dumps(db.get_connectors(bid), sort_keys=True)
    return out


# ------------------------------------------------------------ reads

READS = ["", "/ideas", "/creatives", "/calendar", "/memory", "/inbox", "/competitors", "/metrics",
         "/publish", "/connectors", "/profile", "/history", "/invites", "/mode"]


@pytest.mark.parametrize("suffix", READS, ids=[s or "/brand" for s in READS])
def TENANT_cross_company_read_blocked(orgs, suffix):
    r = client.get(f"/api/brands/{orgs['A']}{suffix}", headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 403, f"B read A{suffix}: {r.status_code}"
    assert "A private" not in r.text and "A-TOKEN" not in r.text and "secret" not in r.text.lower()


@pytest.mark.parametrize("suffix", READS, ids=[s or "/brand" for s in READS])
def TENANT_cross_company_read_blocked_for_client_role(orgs, suffix):
    cb = make_client_user(orgs["B"])
    r = client.get(f"/api/brands/{orgs['A']}{suffix}", headers=hdr(cb["token"]))
    assert r.status_code == 403


def TENANT_own_reads_still_work(orgs):
    for suffix in READS:
        r = client.get(f"/api/brands/{orgs['A']}{suffix}", headers=hdr(orgs["a"]["token"]))
        assert r.status_code == 200, f"owner blocked from own {suffix}: {r.status_code} {r.text[:100]}"


def TENANT_inbox_conversation_by_id_blocked(orgs):
    r = client.get(f"/api/brands/{orgs['A']}/inbox/{orgs['a_convo']}", headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 403
    r = client.get(f"/api/brands/{orgs['B']}/inbox/{orgs['a_convo']}", headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404 and "A customer message" not in r.text


def TENANT_aggregate_views_never_include_other_org(orgs):
    B = hdr(orgs["b"]["token"])
    for path in ("/api/approvals", "/api/digest", "/api/activity", "/api/profiles", "/api/autopilot/status", "/api/brands"):
        r = client.get(path, headers=B)
        assert r.status_code == 200, path
        assert orgs["A"] not in r.text and "A private" not in r.text, f"{path} leaked org A data"


def TENANT_companies_overview_admin_only(orgs):
    assert client.get("/api/companies", headers=hdr(orgs["b"]["token"])).status_code == 403


# ------------------------------------------------------------ workspace file server

def TENANT_workspace_file_requires_auth(orgs):
    assert client.get(f"/workspaces/{orgs['a_slug']}/instagram/creatives/secret.md").status_code == 401


def TENANT_workspace_file_readable_by_owner(orgs):
    r = client.get(f"/workspaces/{orgs['a_slug']}/instagram/creatives/secret.md", headers=hdr(orgs["a"]["token"]))
    assert r.status_code == 200 and r.text == "A-SECRET-CONTENT"


@pytest.mark.defect
def TENANT_workspace_file_blocked_for_other_org(orgs):
    """DEFECT: app/main.py _workspace_router checks *that* the caller is logged in, not
    *which* brand the path belongs to. Any authenticated user can read any tenant's
    workspace (creatives, calendars, scraped data, uploaded logos)."""
    r = client.get(f"/workspaces/{orgs['a_slug']}/instagram/creatives/secret.md", headers=hdr(orgs["b"]["token"]))
    assert r.status_code in (403, 404), f"org B read org A's workspace file: {r.status_code}"
    assert "A-SECRET-CONTENT" not in r.text


# ------------------------------------------------------------ mutations

def _mutations(o):
    A = o["A"]
    return [
        ("POST", f"/api/brands/{A}/ideas", {"channels": ["instagram"], "count": 1}),
        ("POST", f"/api/brands/{A}/ideas/{o['a_idea']}/state", {"state": "approved"}),
        ("POST", f"/api/brands/{A}/calendar", {"days": 7}),
        ("POST", f"/api/brands/{A}/creatives", {"idea_id": o["a_idea"]}),
        ("POST", f"/api/brands/{A}/images", {"creative_id": o["a_cre"]}),
        ("POST", f"/api/brands/{A}/creatives/{o['a_cre']}/approval", {"state": "approved"}),
        ("POST", f"/api/brands/{A}/creatives/{o['a_cre']}/revise", {"instruction": "change"}),
        ("POST", f"/api/brands/{A}/creatives/{o['a_cre']}/proceed", None),
        ("POST", f"/api/brands/{A}/creatives/{o['a_cre']}/slides", None),
        ("POST", f"/api/brands/{A}/creatives/{o['a_cre']}/voiceover", None),
        ("POST", f"/api/brands/{A}/creatives/{o['a_cre']}/algo-audit", None),
        ("POST", f"/api/brands/{A}/publish", {"creative_id": o["a_cre"], "mode": "simulated"}),
        ("POST", f"/api/brands/{A}/publish", {"creative_id": o["a_cre"], "mode": "live"}),
        ("POST", f"/api/brands/{A}/connectors", {"platform": "instagram", "credentials": {"access_token": "B", "ig_user_id": "9"}}),
        ("POST", f"/api/brands/{A}/metrics", {"channel": "instagram", "metrics": {"views": 1}}),
        ("POST", f"/api/brands/{A}/insights", None),
        ("POST", f"/api/brands/{A}/memory", {"content": "B's rule", "kind": "rule"}),
        ("DELETE", f"/api/brands/{A}/memory/{o['a_mem']}", None),
        ("POST", f"/api/brands/{A}/competitors", {"url": "https://1.1.1.1"}),
        ("DELETE", f"/api/brands/{A}/competitors/{o['a_comp']}", None),
        ("POST", f"/api/brands/{A}/competitors/discover", None),
        ("POST", f"/api/brands/{A}/inbox/inbound", {"channel": "whatsapp", "contact_ref": "+2", "text": "hi"}),
        ("POST", f"/api/brands/{A}/inbox/{o['a_convo']}/draft", None),
        ("POST", f"/api/brands/{A}/inbox/messages/{o['a_msg']}/send", {"text": "x"}),
        ("DELETE", f"/api/brands/{A}/inbox/messages/{o['a_msg']}", None),
        ("POST", f"/api/brands/{A}/invites", {"email": "x@x.test", "role": "client"}),
        ("POST", f"/api/brands/{A}/mode", {"mode": "manual"}),
        ("POST", f"/api/brands/{A}/setup", {"channels": ["instagram"]}),
        ("POST", f"/api/brands/{A}/kit", {"colors": ["#111111"], "style": "x"}),
        ("POST", f"/api/brands/{A}/scrape", None),
        ("POST", f"/api/brands/{A}/scrape/import", {"scrape": {"ok": True, "meta": {"title": "pwned"}}}),
        ("POST", f"/api/brands/{A}/analyze", None),
        ("POST", f"/api/brands/{A}/blueprint", {"topic": "t"}),
        ("POST", f"/api/brands/{A}/reel-studio", {"prompt": "a long enough video idea"}),
        ("POST", f"/api/brands/{A}/autopilot", {"ideas_per_channel": 1}),
        ("POST", f"/api/brands/{A}/blog", {"topic": "t"}),
        ("POST", f"/api/brands/{A}/email", {"topic": "t"}),
        ("POST", f"/api/brands/{A}/playbook", None),
        ("POST", f"/api/brands/{A}/playbook/run", {"system": "s", "prompt": "p"}),
        ("POST", f"/api/brands/{A}/chat", {"message": "hi"}),
        ("POST", f"/api/brands/{A}/repurpose", {"source": "x" * 300}),
        ("POST", f"/api/brands/{A}/seo", {"topic": "t"}),
        ("POST", f"/api/brands/{A}/trends", {"keywords": ["k"]}),
        ("POST", f"/api/brands/{A}/score", {"kind": "creative", "id": o["a_cre"]}),
        ("POST", f"/api/brands/{A}/studio/moodboard", {"topic": "t"}),
        ("POST", f"/api/brands/{A}/studio/image", {"prompt": "p"}),
        ("POST", f"/api/brands/{A}/studio/carousel", {"prompts": ["p"]}),
        ("POST", f"/api/brands/{A}/studio/save", {"title": "B wrote this"}),
    ]


def TENANT_cross_company_mutations_blocked_and_nothing_changes(orgs):
    before = _snapshot(orgs["A"])
    B = hdr(orgs["b"]["token"])
    failures = []
    for method, path, body in _mutations(orgs):
        r = client.request(method, path, json=body, headers=B)
        if r.status_code != 403:
            failures.append(f"{method} {path} -> {r.status_code}")
    logo = client.post(f"/api/brands/{orgs['A']}/logo", files={"file": ("l.png", png_bytes(), "image/png")}, headers=B)
    if logo.status_code != 403:
        failures.append(f"POST logo -> {logo.status_code}")
    assert not failures, "org B was not refused on:\n" + "\n".join(failures)
    import time; time.sleep(0.3)  # let any wrongly-started background thread land
    after = _snapshot(orgs["A"])
    changed = [k for k in before if before[k] != after[k]]
    assert not changed, f"org A data mutated by org B: {changed}"


def TENANT_cross_company_mutations_401_without_token(orgs):
    bad = [f"{m} {p} -> {client.request(m, p, json=b).status_code}"
           for m, p, b in _mutations(orgs) if client.request(m, p, json=b).status_code != 401]
    assert not bad, "\n".join(bad)


# ------------------------------------------------------------ IDOR: right brand in URL, foreign id in path/body

@pytest.mark.defect
def IDOR_idea_state_cross_brand_blocked(orgs):
    """DEFECT (app/routes/pipeline.py idea_state): only the brand is checked; the idea id
    is updated unscoped, so B can flip the state of any idea in the system."""
    r = client.post(f"/api/brands/{orgs['B']}/ideas/{orgs['a_idea']}/state", json={"state": "rejected-by-B"},
                    headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404, f"B mutated A's idea via its own brand URL: {r.status_code} {r.text[:120]}"
    assert db.get_doc("ideas", orgs["a_idea"])["state"] == "proposed"


def IDOR_idea_state_with_A_bid_and_B_token_blocked(orgs):
    r = client.post(f"/api/brands/{orgs['A']}/ideas/{orgs['a_idea']}/state", json={"state": "approved"},
                    headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 403
    assert db.get_doc("ideas", orgs["a_idea"])["state"] == "proposed"


@pytest.mark.defect
def IDOR_idea_state_admin_url_mismatch_blocked(orgs, admin):
    """Even the admin must not be able to mutate idea X through brand Y's URL (audit trail)."""
    r = client.post(f"/api/brands/{orgs['B']}/ideas/{orgs['a_idea']}/state", json={"state": "approved"},
                    headers=hdr(admin["token"]))
    assert r.status_code == 404
    assert db.get_doc("ideas", orgs["a_idea"])["state"] == "proposed"


@pytest.mark.defect
def IDOR_creative_from_other_brands_idea_blocked(orgs, fake_ai):
    """DEFECT (app/routes/_shared.py _produce_creative): the idea is fetched by raw id, so B
    can produce a creative from A's idea AND flip A's idea to 'produced'."""
    r = client.post(f"/api/brands/{orgs['B']}/creatives", json={"idea_id": orgs["a_idea"]},
                    headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404, f"B produced from A's idea: {r.status_code}"
    assert db.get_doc("ideas", orgs["a_idea"])["state"] == "proposed"
    assert db.list_docs("creatives", orgs["B"]) == []


@pytest.mark.defect
def IDOR_image_for_other_brands_creative_blocked(orgs, fake_ai):
    """DEFECT (app/routes/_shared.py _generate_image): creative fetched by raw id — B can
    spend on an image for A's creative and overwrite A's asset_path."""
    r = client.post(f"/api/brands/{orgs['B']}/images", json={"creative_id": orgs["a_cre"]},
                    headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404, f"B generated an image for A's creative: {r.status_code}"
    assert db.get_doc("creatives", orgs["a_cre"]).get("asset_path") is None
    assert fake_ai.image_calls == []


@pytest.mark.parametrize("suffix,body", [
    ("/creatives/CID/approval", {"state": "approved"}),
    ("/creatives/CID/revise", {"instruction": "x"}),
    ("/creatives/CID/proceed", None),
    ("/creatives/CID/slides", None),
    ("/creatives/CID/voiceover", None),
    ("/creatives/CID/algo-audit", None),
    ("/publish", {"creative_id": "CID"}),
    ("/score", {"kind": "creative", "id": "CID"}),
    ("/reel-studio", {"creative_id": "CID"}),
])
def IDOR_creative_subresources_scoped_to_brand(orgs, suffix, body):
    path = f"/api/brands/{orgs['B']}{suffix}".replace("CID", orgs["a_cre"])
    if body:
        body = {k: (orgs["a_cre"] if v == "CID" else v) for k, v in body.items()}
    r = client.post(path, json=body, headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404, f"{suffix}: {r.status_code} {r.text[:100]}"
    assert (db.get_doc("creatives", orgs["a_cre"])["payload"].get("approval")) is None


def IDOR_score_other_brands_idea_blocked(orgs):
    r = client.post(f"/api/brands/{orgs['B']}/score", json={"kind": "idea", "id": orgs["a_idea"]},
                    headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404


def IDOR_memory_delete_cross_brand_blocked(orgs):
    r = client.delete(f"/api/brands/{orgs['B']}/memory/{orgs['a_mem']}", headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404 and len(mem.recall(orgs["A"])) == 1


def IDOR_competitor_delete_cross_brand_noop(orgs):
    r = client.delete(f"/api/brands/{orgs['B']}/competitors/{orgs['a_comp']}", headers=hdr(orgs["b"]["token"]))
    assert r.status_code in (200, 404)
    assert db.get_doc("competitors", orgs["a_comp"]) is not None


@pytest.mark.parametrize("suffix", ["/inbox/CONVO/draft", "/inbox/messages/MSG/send"])
def IDOR_inbox_cross_brand_blocked(orgs, suffix):
    path = f"/api/brands/{orgs['B']}{suffix}".replace("CONVO", orgs["a_convo"]).replace("MSG", orgs["a_msg"])
    r = client.post(path, json={"text": "x"}, headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404


def IDOR_inbox_message_delete_cross_brand_blocked(orgs):
    r = client.delete(f"/api/brands/{orgs['B']}/inbox/messages/{orgs['a_msg']}", headers=hdr(orgs["b"]["token"]))
    assert r.status_code == 404 and db.get_doc("messages", orgs["a_msg"]) is not None


def IDOR_reel_job_of_other_brand_blocked(orgs):
    _shared._reel_set("job-tenant-" + u(), state="done", creative_id=orgs["a_cre"], brand_id=orgs["A"])
    key = [k for k in _shared.REEL_JOBS if k.startswith("job-tenant-")][-1]
    assert client.get(f"/api/reel-studio/jobs/{key}", headers=hdr(orgs["b"]["token"])).status_code == 403


def IDOR_invite_for_other_brand_cannot_be_listed_or_created(orgs):
    B = hdr(orgs["b"]["token"])
    assert client.get(f"/api/brands/{orgs['A']}/invites", headers=B).status_code == 403
    assert client.post(f"/api/brands/{orgs['A']}/invites", json={"email": "z@z.test"}, headers=B).status_code == 403
    assert db.list_docs("invites", orgs["A"]) == []

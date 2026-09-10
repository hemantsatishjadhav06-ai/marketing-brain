"""02 AUTHZ — role matrix (admin / owner / client) on every mutating endpoint.
Enforcement must be server-side: no token -> 401, wrong role -> 403."""
from __future__ import annotations

import pytest

from app.core import database as db

from .conftest import client, hdr, make_client_user, seed_creative, signup_org


@pytest.fixture
def world(admin):
    a = signup_org("Neopolis Realty")
    b = signup_org("BrightSmile Dental")
    ca = make_client_user(a["brand_id"])
    return {"admin": admin, "owner_a": a, "owner_b": b, "client_a": ca, "A": a["brand_id"], "B": b["brand_id"]}


# ------------------------------------------------------------ admin-only endpoints

ADMIN_ONLY = [
    ("POST", "/api/brands", {"name": "Zed", "website": "https://z.invalid"}),
    ("GET", "/api/users", None),
    ("POST", "/api/users", {"email": "n@n.test", "password": "longenough1", "role": "client", "brand_id": "x"}),
    ("DELETE", "/api/users/does-not-matter", None),
    ("POST", "/api/autopilot/all", {"ideas_per_channel": 1}),
    ("GET", "/api/companies", None),
]


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY, ids=[f"{m} {p}" for m, p, _ in ADMIN_ONLY])
@pytest.mark.parametrize("who", ["owner_a", "client_a"])
def AUTHZ_non_admin_blocked_from_admin_endpoints(world, who, method, path, body):
    r = client.request(method, path, json=body, headers=hdr(world[who]["token"]))
    assert r.status_code == 403, f"{who} got {r.status_code} on {method} {path}: {r.text[:120]}"


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY, ids=[f"{m} {p}" for m, p, _ in ADMIN_ONLY])
def AUTHZ_admin_endpoints_401_without_token(world, method, path, body):
    r = client.request(method, path, json=body)
    assert r.status_code == 401


def AUTHZ_non_admin_cannot_delete_any_brand(world):
    for who in ("owner_a", "client_a"):
        for bid in (world["A"], world["B"]):
            r = client.delete(f"/api/brands/{bid}", headers=hdr(world[who]["token"]))
            assert r.status_code == 403, f"{who} deleted brand {bid}: {r.status_code}"
            assert db.get_brand(bid) is not None


def AUTHZ_admin_can_delete_brand(world):
    r = client.delete(f"/api/brands/{world['B']}", headers=hdr(world["admin"]["token"]))
    assert r.status_code == 200 and db.get_brand(world["B"]) is None


def AUTHZ_non_admin_cannot_create_brand_side_effect_free(world):
    before = len(db.list_brands())
    client.post("/api/brands", json={"name": "Sneak", "website": "https://s.invalid"}, headers=hdr(world["client_a"]["token"]))
    client.post("/api/brands", json={"name": "Sneak", "website": "https://s.invalid"}, headers=hdr(world["owner_a"]["token"]))
    assert len(db.list_brands()) == before


def AUTHZ_non_admin_cannot_create_users(world):
    r = client.post("/api/users", headers=hdr(world["owner_a"]["token"]),
                    json={"email": "escalate@n.test", "password": "longenough1", "role": "admin"})
    assert r.status_code == 403 and db.get_user_by_email("escalate@n.test") is None


def AUTHZ_non_admin_cannot_delete_users(world):
    r = client.delete(f"/api/users/{world['owner_b']['user_id']}", headers=hdr(world["owner_a"]["token"]))
    assert r.status_code == 403 and db.get_user_by_email(world["owner_b"]["email"]) is not None


def AUTHZ_client_cannot_invite_even_own_brand(world):
    r = client.post(f"/api/brands/{world['A']}/invites", headers=hdr(world["client_a"]["token"]),
                    json={"email": "friend@n.test", "role": "owner"})
    assert r.status_code == 403
    assert client.get(f"/api/brands/{world['A']}/invites", headers=hdr(world["client_a"]["token"])).status_code == 403


def AUTHZ_owner_can_invite_own_brand_only(world):
    ok = client.post(f"/api/brands/{world['A']}/invites", headers=hdr(world["owner_a"]["token"]),
                     json={"email": "mate@n.test", "role": "client"})
    assert ok.status_code == 200
    no = client.post(f"/api/brands/{world['B']}/invites", headers=hdr(world["owner_a"]["token"]),
                     json={"email": "mate2@n.test", "role": "client"})
    assert no.status_code == 403


def AUTHZ_invite_cannot_grant_admin_role(world):
    r = client.post(f"/api/brands/{world['A']}/invites", headers=hdr(world["owner_a"]["token"]),
                    json={"email": "root@n.test", "role": "admin"})
    assert r.status_code == 400


def AUTHZ_brand_listing_scoped_by_role(world):
    adm = {b["id"] for b in client.get("/api/brands", headers=hdr(world["admin"]["token"])).json()}
    assert {world["A"], world["B"]} <= adm
    own = [b["id"] for b in client.get("/api/brands", headers=hdr(world["owner_a"]["token"])).json()]
    cli = [b["id"] for b in client.get("/api/brands", headers=hdr(world["client_a"]["token"])).json()]
    assert own == [world["A"]] and cli == [world["A"]]


# ------------------------------------------------------------ brand-scoped mutations across roles

BRAND_MUTATIONS = [
    ("POST", "/mode", {"mode": "manual"}),
    ("POST", "/connectors", {"platform": "instagram", "credentials": {"access_token": "t", "ig_user_id": "1"}}),
    ("POST", "/publish", {"creative_id": "CID", "mode": "simulated"}),
    ("POST", "/memory", {"content": "rule", "kind": "rule"}),
    ("POST", "/metrics", {"channel": "instagram", "metrics": {"views": 1}}),
    ("POST", "/kit", {"colors": ["#000000"], "style": "s"}),
    ("POST", "/setup", {"channels": ["instagram"]}),
    ("POST", "/inbox/inbound", {"channel": "whatsapp", "contact_ref": "+1", "text": "hi"}),
    ("POST", "/scrape/import", {"scrape": {"ok": True}}),
]


@pytest.mark.parametrize("method,suffix,body", BRAND_MUTATIONS, ids=[s for _, s, _ in BRAND_MUTATIONS])
def AUTHZ_brand_mutation_requires_token(world, method, suffix, body):
    cid = seed_creative(world["A"])
    body = {k: (cid if v == "CID" else v) for k, v in body.items()}
    assert client.request(method, f"/api/brands/{world['A']}{suffix}", json=body).status_code == 401


@pytest.mark.parametrize("method,suffix,body", BRAND_MUTATIONS, ids=[s for _, s, _ in BRAND_MUTATIONS])
def AUTHZ_brand_mutation_blocked_for_other_org(world, method, suffix, body):
    cid = seed_creative(world["A"])
    body = {k: (cid if v == "CID" else v) for k, v in body.items()}
    r = client.request(method, f"/api/brands/{world['A']}{suffix}", json=body, headers=hdr(world["owner_b"]["token"]))
    assert r.status_code == 403, f"org B mutated org A via {suffix}: {r.status_code} {r.text[:100]}"


@pytest.mark.parametrize("who", ["admin", "owner_a", "client_a"])
def AUTHZ_mode_switch_allowed_for_own_brand_roles(world, who):
    """Observation (not a defect per spec): a 'client' can flip the brand's operating mode."""
    r = client.post(f"/api/brands/{world['A']}/mode", json={"mode": "manual"}, headers=hdr(world[who]["token"]))
    assert r.status_code == 200


def AUTHZ_client_can_store_connector_credentials(world):
    """Observation: role 'client' (an individual, non-owner) may overwrite the brand's
    platform credentials. Flagged for product review; no role model forbids it today."""
    r = client.post(f"/api/brands/{world['A']}/connectors", headers=hdr(world["client_a"]["token"]),
                    json={"platform": "facebook", "credentials": {"access_token": "t", "page_id": "p"}})
    assert r.status_code == 200
    assert "facebook" in db.get_connectors(world["A"])


def AUTHZ_connector_credentials_never_echoed(world):
    client.post(f"/api/brands/{world['A']}/connectors", headers=hdr(world["owner_a"]["token"]),
                json={"platform": "linkedin", "credentials": {"access_token": "SECRET-TOKEN-XYZ", "author_urn": "u"}})
    r = client.get(f"/api/brands/{world['A']}/connectors", headers=hdr(world["owner_a"]["token"]))
    assert r.status_code == 200 and "SECRET-TOKEN-XYZ" not in r.text
    prof = client.get(f"/api/brands/{world['A']}/profile", headers=hdr(world["owner_a"]["token"]))
    assert "SECRET-TOKEN-XYZ" not in prof.text


def AUTHZ_cron_without_key_does_nothing(world):
    r = client.get("/api/cron?key=wrong")
    assert r.status_code == 200 and "cycled" not in r.json()


def AUTHZ_reel_job_status_scoped(world):
    from app.routes import _shared
    _shared._reel_set("job-authz-a", state="done", creative_id=None, brand_id=world["A"])
    assert client.get("/api/reel-studio/jobs/job-authz-a", headers=hdr(world["owner_b"]["token"])).status_code == 403
    assert client.get("/api/reel-studio/jobs/job-authz-a", headers=hdr(world["owner_a"]["token"])).status_code == 200
    assert client.get("/api/reel-studio/jobs/job-authz-a").status_code == 401

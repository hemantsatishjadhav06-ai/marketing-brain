"""45 API CONTRACT — validation, auth, wrong-org and abusive payloads on key POST endpoints."""
from __future__ import annotations

import json

import pytest

from app.core import database as db

from .conftest import client, client_no_raise, hdr, seed_creative, signup_org


@pytest.fixture
def org():
    return signup_org("Acme Widgets")


@pytest.fixture
def other():
    return signup_org("Other Dental")


# (suffix, valid body, [invalid bodies that must 422])
CASES = [
    ("/memory", {"content": "rule", "kind": "rule"}, [{}, {"content": "x", "weight": "heavy"}, {"content": ["x"]}]),
    ("/ideas", {"count": 1}, [{"count": "six"}, {"channels": "instagram"}, {"count": 1.5}]),
    ("/publish", {"creative_id": "CID"}, [{}, {"creative_id": 123}, {"creative_id": "CID", "mode": 7}]),
    ("/connectors", {"platform": "instagram", "credentials": {"a": "b"}}, [{"platform": "instagram", "credentials": "str"}, {"credentials": {}}]),
    ("/metrics", {"channel": "instagram", "metrics": {"views": 1}}, [{"channel": "instagram", "metrics": [1]}, {"metrics": {}}]),
    ("/inbox/inbound", {"channel": "whatsapp", "contact_ref": "+1", "text": "hi"}, [{"channel": "whatsapp", "contact_ref": "+1"}, {"channel": 1, "contact_ref": "+1", "text": "x"}]),
    ("/competitors", {"url": "https://1.1.1.1"}, [{}, {"url": ["x"]}]),
    ("/calendar", {"days": 7}, [{"days": "thirty"}, {"start": 5}]),
    ("/invites", {"email": "x@x.test", "role": "client"}, [{}, {"email": 5}]),
    ("/mode", {"mode": "manual"}, [{}, {"mode": 1}]),
    ("/setup", {"channels": ["instagram"]}, [{}, {"channels": "instagram"}]),
    ("/kit", {"colors": ["#000000"]}, [{"colors": "#000"}, {"style": 5}]),
]


@pytest.mark.parametrize("suffix,valid,invalids", CASES, ids=[c[0] for c in CASES])
def API_invalid_bodies_422(org, suffix, valid, invalids):
    for body in invalids:
        r = client.post(f"/api/brands/{org['brand_id']}{suffix}", json=body, headers=hdr(org["token"]))
        assert r.status_code == 422, f"{suffix} {body} -> {r.status_code} {r.text[:120]}"


@pytest.mark.parametrize("suffix,valid,invalids", CASES, ids=[c[0] for c in CASES])
def API_unauthenticated_401(org, suffix, valid, invalids):
    cid = seed_creative(org["brand_id"])
    body = {k: (cid if v == "CID" else v) for k, v in valid.items()}
    assert client.post(f"/api/brands/{org['brand_id']}{suffix}", json=body).status_code == 401


@pytest.mark.parametrize("suffix,valid,invalids", CASES, ids=[c[0] for c in CASES])
def API_wrong_org_403(org, other, suffix, valid, invalids):
    cid = seed_creative(org["brand_id"])
    body = {k: (cid if v == "CID" else v) for k, v in valid.items()}
    assert client.post(f"/api/brands/{org['brand_id']}{suffix}", json=body, headers=hdr(other["token"])).status_code == 403


def API_unknown_brand_404_for_admin_403_for_client(admin, org):
    assert client.get("/api/brands/does-not-exist/ideas", headers=hdr(admin["token"])).status_code == 404
    r = client.get("/api/brands/does-not-exist/ideas", headers=hdr(org["token"]))
    assert r.status_code in (403, 404)


@pytest.mark.parametrize("body", [{}, {"name": "x"}, {"name": 5, "website": "w"}, {"name": "x", "website": "w", "socials": "no"}])
def API_create_brand_invalid_422(admin, body):
    assert client.post("/api/brands", json=body, headers=hdr(admin["token"])).status_code == 422


@pytest.mark.parametrize("body", [{}, {"email": "a@b.c"}, {"email": "a@b.c", "password": 5}, {"email": "a@b.c", "password": "x", "role": []}])
def API_create_user_invalid_422(admin, body):
    assert client.post("/api/users", json=body, headers=hdr(admin["token"])).status_code == 422


@pytest.mark.parametrize("body", [{"email": 5, "password": "x"}, {"email": None, "password": "x"}, {"email": "a@b.c", "password": None}])
def API_login_invalid_422(body):
    assert client.post("/api/auth/login", json=body).status_code == 422


def API_non_json_body_422(org):
    r = client.post(f"/api/brands/{org['brand_id']}/memory", content=b"content=rule",
                    headers={**hdr(org["token"]), "Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 422
    r = client.post(f"/api/brands/{org['brand_id']}/memory", content=b"{not json",
                    headers={**hdr(org["token"]), "Content-Type": "application/json"})
    assert r.status_code == 422


def API_unknown_fields_ignored_not_stored(admin):
    r = client.post("/api/brands", json={"name": "Extra", "website": "https://e.invalid", "status": "ready", "id": "hijack"},
                    headers=hdr(admin["token"]))
    assert r.status_code == 200 and r.json()["status"] == "new" and r.json()["id"] != "hijack"


# ------------------------------------------------------------ abusive payloads

@pytest.mark.defect
def API_5mb_payload_rejected(admin):
    """DEFECT: no request-size limit anywhere (no middleware, no field max_length). A 5 MB
    brand name is accepted and written to the DB and echoed on every /api/brands list."""
    big = "A" * (5 * 1024 * 1024)
    r = client_no_raise.post("/api/brands", json={"name": big, "website": "https://big.invalid"}, headers=hdr(admin["token"]))
    if r.status_code == 200:
        db.delete_brand(r.json()["id"])  # keep the shared DB usable for later tests
    assert r.status_code in (413, 422), f"5 MB brand name accepted: {r.status_code}"


@pytest.mark.defect
def API_5mb_memory_note_rejected(org):
    big = "B" * (5 * 1024 * 1024)
    r = client_no_raise.post(f"/api/brands/{org['brand_id']}/memory", json={"content": big, "kind": "rule"}, headers=hdr(org["token"]))
    assert r.status_code in (413, 422), f"5 MB memory note accepted: {r.status_code}"


def API_nested_json_bomb_handled(admin):
    """A 100k-deep JSON body must come back as a 4xx, never a 500/RecursionError."""
    depth = 100_000
    bomb = "[" * depth + "]" * depth
    body = '{"name":"x","website":"w","socials":' + bomb + "}"
    r = client_no_raise.post("/api/brands", content=body.encode(),
                             headers={**hdr(admin["token"]), "Content-Type": "application/json"})
    assert r.status_code in (400, 413, 422), f"JSON bomb -> {r.status_code}"


def API_error_bodies_never_contain_tracebacks(admin, org):
    for r in (client.get("/api/brands/nope", headers=hdr(admin["token"])),
              client.post("/api/brands", json={}, headers=hdr(admin["token"])),
              client.post("/api/auth/login", json={"email": "x@y.z", "password": "n"})):
        assert "Traceback" not in r.text and "File \"" not in r.text

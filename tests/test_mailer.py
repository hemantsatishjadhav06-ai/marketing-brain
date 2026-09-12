"""Built-in mailer — contacts, segments, drafts, rendering, tracking, approval-gated
sending with a daily cap and warm-up, sequences that advance on the cron tick.
SMTP and AI are faked; no mail leaves the process."""
from __future__ import annotations

import os
import tempfile
import time
import uuid

import pytest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "mail.db"))
os.environ.setdefault("WORKSPACES_ROOT", tempfile.mkdtemp())
os.environ["BG_SYNC"] = "1"
os.environ.pop("DIRECT_ACCESS", None)

from fastapi.testclient import TestClient  # noqa: E402

from app.core import auth, database as db  # noqa: E402
from app.main import app  # noqa: E402
from app.routes import mail as mail_routes  # noqa: E402
from app.services import mailer, workspace as ws  # noqa: E402

client = TestClient(app)
SMTP = {"host": "smtp.example", "port": 587, "username": "u", "password": "p", "from_email": "hello@neopolis.example", "from_name": "Neopolis"}


class FakeSMTP:
    sent = []
    fail_for = set()

    def __init__(self, host, port, timeout=30):
        self.host = host
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def ehlo(self): pass
    def starttls(self): pass
    def login(self, u, p): pass
    def send_message(self, msg):
        to = msg["To"]
        if any(f in to for f in FakeSMTP.fail_for):
            raise RuntimeError("550 recipient rejected")
        FakeSMTP.sent.append({"to": to, "subject": msg["Subject"], "html": msg.get_body(("html",)).get_content(),
                              "text": msg.get_body(("plain",)).get_content(), "unsub": msg["List-Unsubscribe"]})


@pytest.fixture(autouse=True)
def _fakes(monkeypatch):
    FakeSMTP.sent = []; FakeSMTP.fail_for = set()
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(mail_routes.ai_engine, "_json_chat", lambda s, u, **k: (
        {"steps": [{"delay_days": 0, "subject": "Quick one, {{first_name}}", "text": "Hi {{first_name}},\nStill looking in Kokapet?"},
                   {"delay_days": 2, "subject": "Re: quick one", "text": "Bumping this."}]} if "SEQUENCES" in s else
        {"subject": "Site-visit weekend, {{first_name}}", "subject_alt": "Kokapet this weekend?", "preview": "Two days, direct from landowners",
         "html": "<h1>Site-visit weekend</h1><p>Hi {{first_name}}, join us.</p><p><a href=\"https://www.neopolisinfra.com/visit\">Book a slot</a></p>",
         "text": "Hi {{first_name}}, join us. https://www.neopolisinfra.com/visit"}))
    yield


def _brand(smtp=True):
    slug = "ml" + uuid.uuid4().hex[:6]
    bid = db.create_brand("Neopolis " + slug, slug, "https://www.neopolisinfra.com", {}, "")
    ws.create_workspace(slug, ["email"])
    if smtp:
        db.set_connector(bid, "smtp", dict(SMTP))
    return bid


def _admin():
    uid = db.create_user(f"a-{uuid.uuid4().hex[:6]}@t.local", auth.hash_pw("pw12345678"), role="admin")
    return {"Authorization": "Bearer " + auth.make_token(uid, "admin", "")}


def _seed(bid, n=3, tag="enquiry"):
    return mailer.add_contacts(bid, [{"email": f"p{i}-{uuid.uuid4().hex[:4]}@example.com", "name": f"Priya {i}", "tags": [tag]} for i in range(n)])


# ---------------- contacts ----------------

def test_CONTACTS_import_csv_upsert_and_segments():
    bid = _brand()
    r = mailer.import_csv(bid, "Email,Name,Tags,City\nPRIYA@Example.com,Priya Sharma,\"enquiry, kokapet\",Hyderabad\nbad-email,,,\n", tags=["csv-2026"])
    assert r == {"added": 1, "updated": 0, "skipped": 1}
    c = mailer.list_contacts(bid)[0]
    assert c["email"] == "priya@example.com" and c["tags"] == ["csv-2026", "enquiry", "kokapet"] and c["payload"]["fields"]["city"] == "Hyderabad"
    assert c["payload"]["first_name"] == "Priya"
    r2 = mailer.add_contacts(bid, [{"email": "priya@example.com", "tags": ["nri"]}])
    assert r2["updated"] == 1 and "nri" in mailer.list_contacts(bid)[0]["tags"] and len(mailer.list_contacts(bid)) == 1
    _seed(bid, 2, "other")
    assert len(mailer.segment(bid, {"tags": ["kokapet"]})) == 1 and len(mailer.segment(bid, {})) == 3
    assert len(mailer.segment(bid, {"tags": ["other"], "exclude": ["nri"]})) == 2
    assert mailer.unsubscribe(bid, mailer.list_contacts(bid)[0]["id"])
    assert len(mailer.segment(bid, {})) == 2


def test_ROUTES_contacts_and_role_gate():
    bid = _brand(); h = _admin()
    r = client.post(f"/api/brands/{bid}/mail/contacts", json={"csv": "email\na@example.com\nb@example.com", "tags": ["list-a"]}, headers=h)
    assert r.status_code == 200 and r.json()["added"] == 2
    g = client.get(f"/api/brands/{bid}/mail/contacts?tag=list-a", headers=h).json()
    assert g["count"] == 2 and g["tags"] == ["list-a"]
    uid = db.create_user(f"c-{uuid.uuid4().hex[:6]}@t.local", auth.hash_pw("pw12345678"), role="client", brand_id=bid)
    ch = {"Authorization": "Bearer " + auth.make_token(uid, "client", bid)}
    assert client.get(f"/api/brands/{bid}/mail/contacts", headers=ch).status_code == 200
    assert client.post(f"/api/brands/{bid}/mail/contacts", json={"contacts": [{"email": "x@example.com"}]}, headers=ch).status_code == 403


# ---------------- drafting + rendering ----------------

def test_DRAFT_broadcast_and_render_with_tracking():
    bid = _brand(); h = _admin(); _seed(bid, 2)
    r = client.post(f"/api/brands/{bid}/mail/draft", json={"goal": "site visit weekend", "segment": {"tags": ["enquiry"]}}, headers=h)
    assert r.status_code == 200, r.text
    c = r.json()["campaign"]
    assert c["status"] == "draft" and c["kind"] == "broadcast" and r.json()["campaign"]["audience_size"] == 2
    b = db.get_brand(bid); contact = mailer.list_contacts(bid)[0]
    subject, html, text = mailer.render_html(b, c, contact, 0, "https://mb.example")
    assert "Priya" in subject and "{{" not in html
    assert "https://mb.example/m/u/" in html and "https://mb.example/m/o/" in html and "https://mb.example/m/c/" in html
    assert "neopolisinfra.com/visit" not in html and "Unsubscribe:" in text
    # preview route renders for the operator with a sample recipient
    pv = client.get(f"/api/brands/{bid}/mail/campaigns/{c['id']}/preview", headers=h)
    assert pv.status_code == 200 and "Priya" in pv.text and pv.headers["x-subject"].startswith("Site-visit weekend")


def test_TRACKING_tokens_signed_and_events_recorded():
    bid = _brand(); _seed(bid, 1); contact = mailer.list_contacts(bid)[0]
    camp = mailer.create_campaign(bid, "broadcast", {"subject": "s", "html": "<p><a href=\"https://www.neopolisinfra.com/x\">x</a></p>"}, {})
    o = mailer.sign("o", bid, camp["id"], contact["id"], 0)
    assert client.get(f"/m/o/{o}.gif").status_code == 200
    assert mailer.stats(bid, camp["id"])["opens"] == 1
    c = mailer.sign("c", bid, camp["id"], contact["id"], 0, extra="https://www.neopolisinfra.com/x")
    r = client.get(f"/m/c/{c}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://www.neopolisinfra.com/x"
    assert mailer.stats(bid, camp["id"])["clicks"] == 1
    tampered = c[:-3] + "abc"
    assert client.get(f"/m/c/{tampered}", follow_redirects=False).status_code == 404
    bad = mailer.sign("c", bid, camp["id"], contact["id"], 0, extra="http://127.0.0.1/admin")
    assert client.get(f"/m/c/{bad}", follow_redirects=False).status_code == 400
    u = mailer.sign("u", bid, camp["id"], contact["id"], 0)
    assert "unsubscribed" in client.get(f"/m/u/{u}").text
    assert db.get_doc("mail_contacts", contact["id"])["status"] == "unsubscribed"
    assert client.get("/m/u/garbage").status_code == 404


# ---------------- sending ----------------

def test_SEND_requires_approval_smtp_and_audience():
    bid = _brand(smtp=False); h = _admin()
    camp = mailer.create_campaign(bid, "broadcast", {"subject": "s", "html": "<p>x</p>"}, {})
    r = client.post(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/approve", json={"approve": False}, headers=h)
    assert r.status_code == 403
    r = client.post(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/approve", json={"approve": True}, headers=h)
    assert r.status_code == 400 and "SMTP" in r.json()["detail"]
    db.set_connector(bid, "smtp", dict(SMTP))
    r = client.post(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/approve", json={"approve": True}, headers=h)
    assert r.status_code == 400 and "contacts" in r.json()["detail"]
    assert FakeSMTP.sent == []


def test_SEND_broadcast_within_cap_and_idempotent():
    bid = _brand(); h = _admin(); _seed(bid, 3)
    camp = mailer.create_campaign(bid, "broadcast", {"subject": "Hello {{first_name}}", "html": "<p>Hi {{first_name}}</p>"}, {})
    r = client.post(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/approve", json={"approve": True}, headers=h)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    assert res["sent"] == 3 and res["complete"] and res["cap_today"] == 20   # warm-up day 1
    assert len(FakeSMTP.sent) == 3 and FakeSMTP.sent[0]["subject"].startswith("Hello Priya") and "<mailto:" in FakeSMTP.sent[0]["unsub"]
    assert db.get_doc("mail_campaigns", camp["id"])["status"] == "sent"
    # a finished campaign refuses to send again; re-approving it still sends nothing (per contact+step idempotency)
    with pytest.raises(RuntimeError):
        mailer.send_batch(bid, camp["id"], "https://mb.example")
    db.update_doc("mail_campaigns", camp["id"], status="approved")
    r2 = mailer.send_batch(bid, camp["id"], "https://mb.example")
    assert r2["sent"] == 0 and len(FakeSMTP.sent) == 3
    st = client.get(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/stats", headers=h).json()
    assert st["sent"] == 3 and st["open_rate"] == 0.0


def test_SEND_daily_cap_and_warmup_enforced():
    bid = _brand(); _seed(bid, 25)
    camp = mailer.create_campaign(bid, "broadcast", {"subject": "s", "html": "<p>x</p>"}, {})
    db.update_doc("mail_campaigns", camp["id"], status="approved")
    r = mailer.send_batch(bid, camp["id"])
    assert r["sent"] == 20 and r["remaining_today"] == 0 and not r["complete"]
    assert db.get_doc("mail_campaigns", camp["id"])["status"] == "sending"
    r2 = mailer.send_batch(bid, camp["id"])
    assert r2["sent"] == 0  # cap reached for today
    # a mailbox that has been sending for a week gets the configured cap
    creds = mailer.smtp_creds(bid); creds["_first_send"] = time.time() - 10 * 86400; db.set_connector(bid, "smtp", creds)
    assert mailer.daily_cap(bid, creds) == 200


def test_SEND_bounce_marks_contact_and_unsub_skips():
    bid = _brand(); _seed(bid, 3)
    cs = mailer.list_contacts(bid)
    FakeSMTP.fail_for = {cs[0]["email"]}
    mailer.unsubscribe(bid, cs[1]["id"])
    camp = mailer.create_campaign(bid, "broadcast", {"subject": "s", "html": "<p>x</p>"}, {})
    db.update_doc("mail_campaigns", camp["id"], status="approved")
    r = mailer.send_batch(bid, camp["id"])
    assert r["sent"] == 1 and r["failed"] == 1
    assert db.get_doc("mail_contacts", cs[0]["id"])["status"] == "bounced"
    assert mailer.stats(bid, camp["id"])["bounces"] == 1


def test_SEQUENCE_advances_on_tick_and_stops_on_unsubscribe(monkeypatch):
    bid = _brand(); h = _admin(); _seed(bid, 2)
    r = client.post(f"/api/brands/{bid}/mail/draft", json={"goal": "re-engage", "kind": "sequence"}, headers=h)
    camp = r.json()["campaign"]
    assert camp["kind"] == "sequence" and len(camp["payload"]["steps"]) == 2
    r = client.post(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/approve", json={"approve": True}, headers=h).json()
    assert r["result"]["sent"] == 2 and not r["result"]["complete"]
    assert all("[TEST]" not in m["subject"] for m in FakeSMTP.sent) and "Priya" in FakeSMTP.sent[0]["subject"]
    # nothing more today: step 2 is due in 2 days
    assert mailer.send_batch(bid, camp["id"])["sent"] == 0
    # jump 2 days ahead: the cron tick sends step 2 to everyone still subscribed
    cs = mailer.list_contacts(bid); mailer.unsubscribe(bid, cs[0]["id"])
    real_time = time.time
    monkeypatch.setattr(mailer.time, "time", lambda: real_time() + 2 * 86400 + 60)
    t = mailer.tick("https://mb.example")   # ticks every brand in the shared test DB
    mine = [m for m in FakeSMTP.sent if m["subject"] == "Re: quick one"]
    assert t["sent"] >= 1 and len(mine) == 1
    assert db.get_doc("mail_campaigns", camp["id"])["status"] == "sent"


def test_SCHEDULE_waits_for_time_then_cron_sends(monkeypatch):
    bid = _brand(); h = _admin(); _seed(bid, 1)
    camp = mailer.create_campaign(bid, "broadcast", {"subject": "later", "html": "<p>x</p>"}, {})
    at = time.time() + 3600
    r = client.post(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/approve", json={"approve": True, "schedule_at": at}, headers=h).json()
    assert r["status"] == "scheduled" and FakeSMTP.sent == []
    assert mailer.tick()["sent"] == 0
    real_time = time.time
    monkeypatch.setattr(mailer.time, "time", lambda: real_time() + 3700)
    assert mailer.tick("https://mb.example")["sent"] == 1


def test_EDIT_resets_approval_and_blocks_after_send():
    bid = _brand(); h = _admin(); _seed(bid, 1)
    camp = mailer.create_campaign(bid, "broadcast", {"subject": "a", "html": "<p>x</p>"}, {})
    db.update_doc("mail_campaigns", camp["id"], status="approved")
    r = client.put(f"/api/brands/{bid}/mail/campaigns/{camp['id']}", json={"subject": "b"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "draft" and r.json()["subject"] == "b"
    db.update_doc("mail_campaigns", camp["id"], status="sent")
    assert client.put(f"/api/brands/{bid}/mail/campaigns/{camp['id']}", json={"subject": "c"}, headers=h).status_code == 409


def test_TEST_SEND_marks_subject_and_needs_smtp():
    bid = _brand(); h = _admin()
    camp = mailer.create_campaign(bid, "broadcast", {"subject": "s", "html": "<p>x</p>"}, {})
    r = client.post(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/test", json={"to": "me@example.com"}, headers=h)
    assert r.status_code == 200 and FakeSMTP.sent[0]["subject"] == "[TEST] s"
    assert client.post(f"/api/brands/{bid}/mail/campaigns/{camp['id']}/test", json={"to": "nope"}, headers=h).status_code == 400
    assert mailer.stats(bid, camp["id"])["sent"] == 0  # tests never count as sends


def test_CRON_route_ticks_mailer(monkeypatch):
    monkeypatch.setenv("CRON_KEY", "k")
    r = client.get("/api/cron?key=k").json()
    assert "mail" in r and isinstance(r["mail"], dict)


def test_DELETE_brand_cascades_mail_tables():
    bid = _brand(); _seed(bid, 2); h = _admin()
    mailer.create_campaign(bid, "broadcast", {"subject": "s", "html": "x"}, {})
    assert client.delete(f"/api/brands/{bid}", headers=h).status_code == 200
    assert db.list_docs("mail_contacts", bid) == [] and db.list_docs("mail_campaigns", bid) == []

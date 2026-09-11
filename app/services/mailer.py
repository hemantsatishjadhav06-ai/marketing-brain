"""Built-in email marketing — the parts of Mailchimp and Smartlead a marketing
team actually uses, inside the product, sending through the client's own mailbox.

From Mailchimp: audiences with tags and segments, broadcast campaigns with a
branded HTML template, preview text, a test send, scheduling, open/click
stats, one-click unsubscribe and a suppression list that is honoured forever.
From Smartlead: multi-step sequences with day delays and {{first_name}}
merge fields, a daily send cap that ramps a fresh mailbox, plain-text-first
copy, and per-contact stop rules (a reply, an unsubscribe, a bounce).

Deliberately NOT built: our own sending infrastructure. Mail goes out through
SMTP credentials the client connects (Google Workspace, Zoho, SES, Brevo…) so
reputation stays with the client's domain. Nothing is sent without an approval,
every message carries an unsubscribe link, and the daily cap is enforced in
code, not in a setting a model can change.

Tracking: an open pixel and click redirects signed with the app secret — no
third-party beacon, no PII in URLs.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import html as _html
import io
import json
import os
import re
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr

from ..core import database as db
from . import brand_config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
STATUSES = ("draft", "approved", "scheduled", "sending", "sent", "paused", "failed")
DEFAULT_DAILY_CAP = 200
WARMUP = [20, 40, 80, 120, 160]       # day 1..5 caps for a fresh SMTP connection, then DEFAULT_DAILY_CAP


# ---------------- signing (open pixel, click redirects, unsubscribe) ----------------

def _secret():
    from ..core import auth
    return (os.environ.get("SECRET_KEY") or auth.DEFAULT_SECRET).encode()


def sign(kind: str, brand_id: str, campaign_id: str, contact_id: str, step: int = 0, extra: str = "") -> str:
    body = f"{kind}|{brand_id}|{campaign_id}|{contact_id}|{step}|{extra}"
    mac = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()[:20]
    return base64.urlsafe_b64encode(f"{body}|{mac}".encode()).decode().rstrip("=")


def verify(token: str):
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        *parts, mac = raw.split("|")
        body = "|".join(parts)
        if not hmac.compare_digest(hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()[:20], mac):
            return None
        kind, brand_id, campaign_id, contact_id, step, extra = parts
        return {"kind": kind, "brand_id": brand_id, "campaign_id": campaign_id, "contact_id": contact_id,
                "step": int(step or 0), "extra": extra}
    except Exception:
        return None


# ---------------- contacts ----------------

def _norm_tags(tags):
    if isinstance(tags, str):
        tags = tags.split(",")
    return sorted({str(t).strip().lower() for t in (tags or []) if str(t).strip()})


def add_contacts(bid: str, rows: list, source: str = "import") -> dict:
    """Upsert by email. rows: [{email, name?, first_name?, tags?, fields?}]"""
    existing = {c["email"]: c for c in list_contacts(bid)}
    added = updated = skipped = 0
    for r in rows:
        email = str(r.get("email") or "").strip().lower()
        if not EMAIL_RE.match(email):
            skipped += 1
            continue
        name = str(r.get("name") or "").strip()
        first = str(r.get("first_name") or (name.split(" ")[0] if name else "")).strip()
        tags = _norm_tags(r.get("tags"))
        fields = {k: v for k, v in (r.get("fields") or {}).items() if isinstance(k, str)}
        ex = existing.get(email)
        if ex:
            merged_tags = sorted(set(_norm_tags(ex.get("tags"))) | set(tags))
            p = dict(ex.get("payload") or {})
            p.update({k: v for k, v in {"name": name, "first_name": first}.items() if v})
            p.setdefault("fields", {}).update(fields)
            db.update_doc("mail_contacts", ex["id"], tags=",".join(merged_tags), payload=p)
            updated += 1
        else:
            db.insert_doc("mail_contacts", bid, {"name": name, "first_name": first, "fields": fields, "source": source},
                          email=email, status="subscribed", tags=",".join(tags))
            added += 1
    return {"added": added, "updated": updated, "skipped": skipped}


def import_csv(bid: str, text: str, tags=None) -> dict:
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for r in reader:
        low = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
        email = low.get("email") or low.get("e-mail") or low.get("email address")
        if not email:
            continue
        name = low.get("name") or (" ".join(x for x in (low.get("first name") or low.get("first_name") or "", low.get("last name") or low.get("last_name") or "") if x)).strip()
        rows.append({"email": email, "name": name, "first_name": low.get("first name") or low.get("first_name") or "",
                     "tags": _norm_tags(tags) + _norm_tags(low.get("tags")),
                     "fields": {k: v for k, v in low.items() if k not in ("email", "e-mail", "email address", "name", "first name", "first_name", "last name", "last_name", "tags")}})
    return add_contacts(bid, rows, source="csv")


def list_contacts(bid: str, tag: str | None = None, status: str | None = None) -> list:
    rows = db.list_docs("mail_contacts", bid)
    out = []
    for r in rows:
        r["tags"] = _norm_tags(r.get("tags"))
        if tag and tag.lower() not in r["tags"]:
            continue
        if status and r.get("status") != status:
            continue
        out.append(r)
    return out


def unsubscribe(bid: str, contact_id: str, reason: str = "link") -> bool:
    c = db.get_doc("mail_contacts", contact_id)
    if not c or c.get("brand_id") != bid:
        return False
    if c.get("status") != "unsubscribed":
        db.update_doc("mail_contacts", contact_id, status="unsubscribed")
        db.insert_doc("mail_events", bid, {"reason": reason}, campaign_id="", contact_id=contact_id, kind="unsubscribe")
    return True


def segment(bid: str, seg: dict | None) -> list:
    """Subscribed contacts matching the campaign segment {tags:[any of], exclude:[none of]}."""
    seg = seg or {}
    want = set(_norm_tags(seg.get("tags")))
    block = set(_norm_tags(seg.get("exclude")))
    out = []
    for c in list_contacts(bid, status="subscribed"):
        t = set(c["tags"])
        if want and not (t & want):
            continue
        if block and (t & block):
            continue
        out.append(c)
    return out


# ---------------- campaigns ----------------

def create_campaign(bid: str, kind: str, content: dict, segment_spec: dict | None = None, goal: str = "") -> dict:
    kind = "sequence" if kind == "sequence" else "broadcast"
    payload = {"goal": goal[:400], "segment": segment_spec or {}, "stats": {}}
    if kind == "broadcast":
        payload.update({"subject": str(content.get("subject") or "")[:200], "preview": str(content.get("preview") or "")[:200],
                        "html": str(content.get("html") or ""), "text": str(content.get("text") or ""),
                        "subject_alt": str(content.get("subject_alt") or "")[:200]})
        subj = payload["subject"]
    else:
        steps = []
        for i, st in enumerate(content.get("steps") or []):
            if not isinstance(st, dict):
                continue
            steps.append({"n": i + 1, "delay_days": max(0, int(st.get("delay_days") or st.get("seq_delay_in_days") or (0 if i == 0 else 2))),
                          "subject": str(st.get("subject") or "")[:200], "text": str(st.get("text") or st.get("email_body") or "")})
        payload["steps"] = steps[:8]
        subj = steps[0]["subject"] if steps else ""
    cid = db.insert_doc("mail_campaigns", bid, payload, kind=kind, status="draft", subject=subj)
    return db.get_doc("mail_campaigns", cid)


def render_html(brand, campaign: dict, contact: dict, step: int = 0, base_url: str = "") -> tuple[str, str, str]:
    """(subject, html, text) for one recipient: merge fields, brand frame, tracking, unsubscribe."""
    p = campaign["payload"]
    kit = ((brand.get("profile") or {}).get("brand_kit") or {})
    colors = kit.get("colors") or ((brand.get("scrape") or {}).get("colors") or [])
    accent = next((c for c in colors if re.match(r"^#[0-9a-fA-F]{6}$", str(c))), "#0a2540")
    first = (contact.get("payload") or {}).get("first_name") or "there"
    name = (contact.get("payload") or {}).get("name") or first
    cfg = brand_config.get(brand)
    contact_line = (cfg.get("cta") or {}).get("contact") or ""
    def merge(s):
        return (s or "").replace("{{first_name}}", first).replace("{{name}}", name).replace("{{brand}}", brand.get("name", ""))
    unsub = f"{base_url}/m/u/{sign('u', brand['id'], campaign['id'], contact['id'], step)}"
    pixel = f"{base_url}/m/o/{sign('o', brand['id'], campaign['id'], contact['id'], step)}.gif"
    if campaign.get("kind") == "sequence":
        st = p["steps"][step]
        subject = merge(st["subject"])
        body_text = merge(st["text"])
        body_html = "".join(f"<p>{_html.escape(x)}</p>" for x in body_text.split("\n") if x.strip())
        frame = False   # sequences read like a person wrote them: no template chrome
    else:
        subject = merge(p.get("subject"))
        body_html = merge(p.get("html")) or "".join(f"<p>{_html.escape(x)}</p>" for x in merge(p.get("text")).split("\n") if x.strip())
        body_text = merge(p.get("text")) or re.sub(r"<[^>]+>", "", body_html)
        frame = True
    # click tracking: rewrite http(s) links
    def track(m):
        url = m.group(1)
        if url.startswith(("http://", "https://")) and "/m/u/" not in url:
            tok = sign("c", brand["id"], campaign["id"], contact["id"], step, extra=url)
            return f'href="{base_url}/m/c/{tok}"'
        return m.group(0)
    body_html = re.sub(r'href="([^"]+)"', track, body_html)
    logo = ((brand.get("scrape") or {}).get("logo") or "")
    preview = _html.escape(merge(p.get("preview") or ""))
    if frame:
        html_out = f"""<!doctype html><html><body style="margin:0;background:#f4f5f7;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#1a1a1a">
<span style="display:none;max-height:0;overflow:hidden">{preview}</span>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="600" style="max-width:600px;background:#fff;border-radius:12px;overflow:hidden">
<tr><td style="background:{accent};padding:18px 24px;color:#fff;font-weight:700;font-size:18px">{('<img src="' + _html.escape(logo) + '" alt="" style="height:32px;vertical-align:middle;margin-right:10px">') if logo.startswith('http') else ''}{_html.escape(brand.get('name', ''))}</td></tr>
<tr><td style="padding:24px;font-size:15px;line-height:1.55">{body_html}</td></tr>
<tr><td style="padding:16px 24px;font-size:12px;color:#6b7280;border-top:1px solid #eee">{_html.escape(brand.get('name', ''))}{(' · ' + _html.escape(contact_line)) if contact_line else ''}<br>
You are receiving this because you asked to hear from us. <a href="{unsub}" style="color:#6b7280">Unsubscribe</a></td></tr>
</table></td></tr></table><img src="{pixel}" width="1" height="1" alt="" style="display:block"></body></html>"""
    else:
        html_out = f"""<!doctype html><html><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:15px;line-height:1.55;color:#1a1a1a">{body_html}
<p style="font-size:12px;color:#6b7280">{_html.escape(brand.get('name', ''))}{(' · ' + _html.escape(contact_line)) if contact_line else ''} · <a href="{unsub}" style="color:#6b7280">unsubscribe</a></p><img src="{pixel}" width="1" height="1" alt="" style="display:block"></body></html>"""
    text_out = body_text + f"\n\n--\n{brand.get('name', '')}\nUnsubscribe: {unsub}\n"
    return subject, html_out, text_out


# ---------------- sending ----------------

def smtp_creds(bid: str) -> dict:
    return db.get_connectors(bid).get("smtp") or {}


def configured(creds: dict) -> bool:
    return bool(creds and creds.get("host") and creds.get("username") and creds.get("password") and creds.get("from_email"))


def daily_cap(bid: str, creds: dict) -> int:
    cfg = brand_config.get(db.get_brand(bid))
    cap = int((cfg.get("caps") or {}).get("mail_daily") or DEFAULT_DAILY_CAP)
    first = float(creds.get("_first_send") or 0)
    if first:
        day = int((time.time() - first) // 86400)
        if day < len(WARMUP):
            cap = min(cap, WARMUP[day])
    else:
        cap = min(cap, WARMUP[0])
    return cap


def sent_today(bid: str) -> int:
    since = time.time() - 86400
    return sum(1 for e in db.list_docs("mail_events", bid, kind="sent") if (e.get("created_at") or 0) >= since)


def _deliver(creds: dict, to_email: str, to_name: str, subject: str, html_body: str, text_body: str) -> dict:
    msg = EmailMessage()
    msg["From"] = formataddr((creds.get("from_name") or "", creds["from_email"]))
    msg["To"] = formataddr((to_name or "", to_email))
    msg["Subject"] = subject
    if creds.get("reply_to"):
        msg["Reply-To"] = creds["reply_to"]
    msg["List-Unsubscribe"] = f"<mailto:{creds.get('reply_to') or creds['from_email']}?subject=unsubscribe>"
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    port = int(creds.get("port") or 587)
    if str(creds.get("security") or "starttls").lower() == "ssl" or port == 465:
        with smtplib.SMTP_SSL(creds["host"], port, timeout=30) as s:
            s.login(creds["username"], creds["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(creds["host"], port, timeout=30) as s:
            s.ehlo()
            s.starttls()
            s.login(creds["username"], creds["password"])
            s.send_message(msg)
    return {"ok": True}


def send_test(bid: str, campaign_id: str, to_email: str, base_url: str = "") -> dict:
    brand = db.get_brand(bid)
    camp = db.get_doc("mail_campaigns", campaign_id)
    creds = smtp_creds(bid)
    if not configured(creds):
        raise RuntimeError("SMTP is not connected for this client (Settings → Connections → SMTP)")
    fake_contact = {"id": "test", "email": to_email, "payload": {"first_name": "Test", "name": "Test Recipient"}}
    subject, html_body, text_body = render_html(brand, camp, fake_contact, 0, base_url)
    _deliver(creds, to_email, "Test", "[TEST] " + subject, html_body, text_body)
    db.insert_doc("mail_events", bid, {"to": to_email}, campaign_id=campaign_id, contact_id="", kind="test")
    return {"ok": True, "to": to_email}


def _already(bid, campaign_id, contact_id, step):
    return any(e.get("contact_id") == contact_id and int(e.get("step") or 0) == step
               for e in db.list_docs("mail_events", bid, campaign_id=campaign_id, kind="sent"))


def send_batch(bid: str, campaign_id: str, base_url: str = "", limit: int | None = None, log=None) -> dict:
    """Send what is due for a campaign, within today's cap. Idempotent per contact+step."""
    brand = db.get_brand(bid)
    camp = db.get_doc("mail_campaigns", campaign_id)
    if not camp or camp.get("brand_id") != bid:
        raise RuntimeError("Campaign not found")
    if camp.get("status") not in ("approved", "scheduled", "sending"):
        raise RuntimeError(f"Campaign is {camp.get('status')} — approve it first")
    creds = smtp_creds(bid)
    if not configured(creds):
        raise RuntimeError("SMTP is not connected for this client")
    cap = daily_cap(bid, creds)
    room = max(0, cap - sent_today(bid))
    if limit is not None:
        room = min(room, limit)
    if not creds.get("_first_send"):
        creds["_first_send"] = time.time()
        db.set_connector(bid, "smtp", creds)
    recipients = segment(bid, camp["payload"].get("segment"))
    started = float((camp["payload"].get("started_at") or time.time()))
    if not camp["payload"].get("started_at"):
        db.merge_payload("mail_campaigns", campaign_id, {"started_at": started})
    db.update_doc("mail_campaigns", campaign_id, status="sending")
    sent = failed = skipped = 0
    for c in recipients:
        if room <= 0:
            break
        steps = camp["payload"].get("steps") if camp.get("kind") == "sequence" else [None]
        for i, st in enumerate(steps):
            if _already(bid, campaign_id, c["id"], i):
                continue
            if st is not None:
                due = started + st["delay_days"] * 86400
                if time.time() < due:
                    break   # later steps are later still
                if i > 0 and not _already(bid, campaign_id, c["id"], i - 1):
                    break
            if any(e.get("contact_id") == c["id"] and e.get("kind") in ("unsubscribe", "bounce", "reply")
                   for e in db.list_docs("mail_events", bid, campaign_id=campaign_id)):
                skipped += 1
                break
            try:
                subject, html_body, text_body = render_html(brand, camp, c, i, base_url)
                _deliver(creds, c["email"], (c.get("payload") or {}).get("name") or "", subject, html_body, text_body)
                db.insert_doc("mail_events", bid, {"subject": subject}, campaign_id=campaign_id, contact_id=c["id"], kind="sent", step=i)
                sent += 1
                room -= 1
                if log:
                    log(f"sent step {i + 1} to {c['email']}")
            except Exception as e:
                db.insert_doc("mail_events", bid, {"error": str(e)[:300]}, campaign_id=campaign_id, contact_id=c["id"], kind="fail", step=i)
                failed += 1
                if "550" in str(e) or "recipient" in str(e).lower():
                    db.update_doc("mail_contacts", c["id"], status="bounced")
                    db.insert_doc("mail_events", bid, {"error": str(e)[:200]}, campaign_id=campaign_id, contact_id=c["id"], kind="bounce", step=i)
            break  # one message per contact per batch (sequences advance next tick)
    done = _campaign_complete(bid, camp, recipients)
    db.update_doc("mail_campaigns", campaign_id, status="sent" if done else "sending")
    st = stats(bid, campaign_id)
    db.merge_payload("mail_campaigns", campaign_id, {"stats": st})
    return {"ok": True, "sent": sent, "failed": failed, "skipped": skipped, "cap_today": cap, "remaining_today": room, "complete": done, "stats": st}


def _campaign_complete(bid, camp, recipients):
    if camp.get("kind") == "sequence":
        last = len(camp["payload"].get("steps") or []) - 1
        if last < 0:
            return True
        evs = db.list_docs("mail_events", bid, campaign_id=camp["id"])
        stopped = {e["contact_id"] for e in evs if e.get("kind") in ("unsubscribe", "bounce", "reply", "fail")}
        done = {e["contact_id"] for e in evs if e.get("kind") == "sent" and int(e.get("step") or 0) == last}
        return all((c["id"] in done) or (c["id"] in stopped) for c in recipients)
    evs = db.list_docs("mail_events", bid, campaign_id=camp["id"])
    touched = {e["contact_id"] for e in evs if e.get("kind") in ("sent", "fail", "bounce")}
    return all(c["id"] in touched for c in recipients)


def stats(bid: str, campaign_id: str) -> dict:
    evs = db.list_docs("mail_events", bid, campaign_id=campaign_id)
    by = {}
    for e in evs:
        by[e.get("kind")] = by.get(e.get("kind"), 0) + 1
    sent = by.get("sent", 0)
    opens = len({e["contact_id"] for e in evs if e.get("kind") == "open"})
    clicks = len({e["contact_id"] for e in evs if e.get("kind") == "click"})
    return {"sent": sent, "opens": opens, "clicks": clicks, "unsubscribes": by.get("unsubscribe", 0), "bounces": by.get("bounce", 0),
            "failed": by.get("fail", 0), "open_rate": round(100 * opens / sent, 1) if sent else 0.0,
            "click_rate": round(100 * clicks / sent, 1) if sent else 0.0}


def record_event(token: str, kind: str, meta: dict | None = None):
    t = verify(token)
    if not t or t["kind"] != {"open": "o", "click": "c", "unsubscribe": "u"}[kind]:
        return None
    if kind == "unsubscribe":
        unsubscribe(t["brand_id"], t["contact_id"], reason="link")
        return t
    if t["contact_id"] == "test":
        return t
    db.insert_doc("mail_events", t["brand_id"], meta or {}, campaign_id=t["campaign_id"], contact_id=t["contact_id"], kind=kind, step=t["step"])
    return t


def tick(base_url: str = "", log=None) -> dict:
    """Cron hook: advance every sending/scheduled campaign across all brands."""
    out = {"campaigns": 0, "sent": 0}
    for b in db.list_brands():
        for camp in db.list_docs("mail_campaigns", b["id"]):
            if camp.get("status") == "scheduled":
                at = float((camp["payload"] or {}).get("schedule_at") or 0)
                if at and time.time() < at:
                    continue
            if camp.get("status") in ("scheduled", "sending"):
                try:
                    r = send_batch(b["id"], camp["id"], base_url, log=log)
                    out["campaigns"] += 1
                    out["sent"] += r["sent"]
                except Exception as e:
                    if log:
                        log(f"{b['name']}: {e}")
    return out


PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")

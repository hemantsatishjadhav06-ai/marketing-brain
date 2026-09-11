"""Monthly client report — numbers from the DB, a short narrative from the model,
rendered as a white-labelled HTML page the agency can send as-is.

The narrative is optional: when the model is unavailable the report still
renders with the numbers, because a report that fails to generate on the 1st of
the month is the kind of thing that gets an agency fired.
"""
from __future__ import annotations

import calendar
import html
import time
from datetime import datetime, timezone

from ..core import database as db
from . import agency_settings

TABLE = "reports"


def period_bounds(period: str):
    """'YYYY-MM' → (start_ts, end_ts) in UTC."""
    y, m = (int(x) for x in period.split("-"))
    start = datetime(y, m, 1, tzinfo=timezone.utc).timestamp()
    last = calendar.monthrange(y, m)[1]
    end = datetime(y, m, last, 23, 59, 59, tzinfo=timezone.utc).timestamp()
    return start, end


def _in(row, lo, hi):
    t = row.get("created_at") or 0
    return lo <= t <= hi


def aggregate(b, period):
    bid = b["id"]
    lo, hi = period_bounds(period)
    ideas = [r for r in db.list_docs("ideas", bid) if _in(r, lo, hi)]
    creatives = [r for r in db.list_docs("creatives", bid) if _in(r, lo, hi)]
    pubs = [r for r in db.list_docs("publish_queue", bid) if _in(r, lo, hi)]
    metrics = [r for r in db.list_docs("metrics", bid) if _in(r, lo, hi)]
    campaigns = [r for r in db.list_docs("campaigns", bid) if _in(r, lo, hi)]
    emails = [r for r in db.list_docs("email_campaigns", bid) if _in(r, lo, hi)]
    audits = [r for r in db.list_docs("seo_audits", bid) if _in(r, lo, hi)]
    spend = [r for r in db.list_docs("spend_log", bid) if _in(r, lo, hi)]
    convos = [r for r in db.list_docs("conversations", bid) if _in(r, lo, hi)]
    by_channel = {}
    for p in pubs:
        if p.get("status") == "published":
            by_channel[p.get("channel") or "?"] = by_channel.get(p.get("channel") or "?", 0) + 1
    totals = {}
    for m in metrics:
        for k, v in (m.get("payload") or {}).items():
            try:
                totals[k] = totals.get(k, 0) + float(v)
            except (TypeError, ValueError):
                pass
    top = sorted(creatives, key=lambda c: -(((c.get("payload") or {}).get("virality") or {}).get("score") or 0))[:3]
    return {
        "ideas": len(ideas),
        "creatives": len(creatives),
        "approved": sum(1 for c in creatives if ((c.get("payload") or {}).get("approval") or {}).get("state") == "approved"),
        "published": sum(by_channel.values()), "published_by_channel": by_channel,
        "simulated": sum(1 for p in pubs if p.get("status") == "simulated"),
        "metrics_logged": len(metrics), "metric_totals": {k: round(v, 1) for k, v in totals.items()},
        "ad_campaigns": len(campaigns), "ad_spend_actions": len(spend),
        "ad_spend_total": round(sum(float(s.get("amount") or 0) for s in spend), 2),
        "email_campaigns": len(emails), "seo_audits": len(audits),
        "seo_best_score": max((a.get("score") or 0) for a in audits) if audits else None,
        "conversations": len(convos),
        "top_creatives": [{"id": c["id"], "title": (c.get("payload") or {}).get("title"),
                           "channel": c.get("channel"), "format": c.get("format")} for c in top],
    }


def narrative(b, period, agg):
    from ..ai import engine
    try:
        msgs = [{"role": "system", "content": "You write short, honest monthly marketing reports for a client. "
                 "Plain language, 3 short paragraphs: what we did, what it produced, what we recommend next. "
                 "Use ONLY the numbers given. No hype, no invented metrics. " + engine.ANTI_INJECTION},
                {"role": "user", "content": f"Client: {b['name']}\nPeriod: {period}\nNumbers (JSON): {agg}"}]
        return (engine._chat(msgs, max_tokens=600, temperature=0.4) or "").strip()
    except Exception:
        return ""


def build(b, period, by=""):
    agg = aggregate(b, period)
    text = narrative(b, period, agg)
    payload = {"period": period, "brand": b["name"], "numbers": agg, "narrative": text,
               "generated_at": time.time(), "by": by, "branding": agency_settings.branding()}
    rid = db.insert_doc(TABLE, b["id"], payload, period=period, kind="monthly")
    return db.get_doc(TABLE, rid)


def list_for(bid):
    return [{"id": r["id"], "period": r.get("period"), "kind": r.get("kind"), "created_at": r.get("created_at")}
            for r in db.list_docs(TABLE, bid)]


def render_html(report, branding=None) -> str:
    p = report.get("payload") or {}
    br = branding or p.get("branding") or agency_settings.branding()
    n = p.get("numbers") or {}
    e = html.escape
    rows = "".join(f"<tr><th>{e(str(k).replace('_', ' '))}</th><td>{e(str(v))}</td></tr>"
                   for k, v in n.items() if not isinstance(v, (dict, list)))
    chan = "".join(f"<li>{e(str(k))}: {v}</li>" for k, v in (n.get("published_by_channel") or {}).items())
    tops = "".join(f"<li>{e(str(t.get('title') or ''))} <small>({e(str(t.get('channel') or ''))})</small></li>"
                   for t in (n.get("top_creatives") or []))
    paras = "".join(f"<p>{e(x.strip())}</p>" for x in (p.get("narrative") or "").split("\n") if x.strip())
    logo = f'<img src="{e(br.get("logo_url"))}" alt="" style="height:36px">' if br.get("logo_url") else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{e(p.get('brand', ''))} — {e(p.get('period', ''))}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#1a1a1a}}
h1{{font-size:26px;margin:0}}.hd{{display:flex;align-items:center;gap:14px;border-bottom:3px solid {e(br.get('accent') or '#6d5dfc')};padding-bottom:14px;margin-bottom:24px}}
table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #eee}}th{{width:55%;font-weight:500;color:#555;text-transform:capitalize}}
.acc{{color:{e(br.get('accent') or '#6d5dfc')}}}footer{{margin-top:36px;color:#777;font-size:13px}}</style></head><body>
<div class="hd">{logo}<div><div class="acc" style="font-weight:600">{e(br.get('agency_name') or '')}</div><h1>{e(p.get('brand', ''))} · {e(p.get('period', ''))}</h1></div></div>
<p>{e(br.get('report_intro') or '')}</p>
{paras or '<p><em>Numbers only this month.</em></p>'}
<h2>By the numbers</h2><table>{rows}</table>
{('<h3>Published by channel</h3><ul>' + chan + '</ul>') if chan else ''}
{('<h3>Top creatives</h3><ul>' + tops + '</ul>') if tops else ''}
<footer>{e(br.get('footer') or '')}{(' · ' + e(br.get('support_email'))) if br.get('support_email') else ''}</footer>
</body></html>"""

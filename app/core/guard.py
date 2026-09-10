"""Safety guards: SSRF-safe URL checks, a lightweight in-process rate limiter,
and a generation kill-switch + per-brand daily budget.

These close concrete holes the audit found:
  * server-side fetches (competitor scrape) could hit internal/link-local hosts;
  * login and generation were unthrottled;
  * nothing bounded fal.ai / OpenRouter spend, and there was no kill switch.

Kept dependency-free (stdlib only) so it is safe to import anywhere.
"""
from __future__ import annotations

import ipaddress
import logging
import os
import socket
import time
from urllib.parse import urlparse

log = logging.getLogger("marketing_brain")
if not log.handlers:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")


# ---------- SSRF-safe URL check ----------

def url_is_safe(url: str):
    """(ok, reason). Rejects non-http(s) schemes and hosts that resolve to any
    private, loopback, link-local, reserved or multicast address — the classic
    SSRF targets (localhost, 169.254.169.254 metadata, 10/172/192.168, etc.)."""
    try:
        u = urlparse(url if "://" in (url or "") else "https://" + (url or ""))
    except Exception:
        return False, "unparseable url"
    if u.scheme not in ("http", "https"):
        return False, f"scheme '{u.scheme}' not allowed"
    host = u.hostname
    if not host:
        return False, "no host"
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False, "host does not resolve"
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr.split("%")[0])
        except ValueError:
            continue
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False, f"host resolves to a non-public address ({ip})"
    return True, ""


# ---------- in-process rate limiter (per worker) ----------

_hits: dict[str, list[float]] = {}


def rate_ok(key: str, limit: int, window_s: int) -> bool:
    """Sliding-window limiter. In-process (per worker) — a real improvement over
    nothing; a shared store (Redis) is the eventual home."""
    now = time.time()
    bucket = [t for t in _hits.get(key, []) if now - t < window_s]
    if len(bucket) >= limit:
        _hits[key] = bucket
        return False
    bucket.append(now)
    _hits[key] = bucket
    return True


def client_ip(request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        # The RIGHTMOST hop is the one appended by our own edge proxy; the first
        # hop is whatever the client chose to send, so keying on it made the
        # limiter bypassable with a rotating header.
        return xff.split(",")[-1].strip()
    return getattr(getattr(request, "client", None), "host", "") or "unknown"


# ---------- generation kill-switch + daily budget ----------

def generation_enabled() -> bool:
    return os.environ.get("GENERATION_DISABLED", "").strip().lower() not in {"1", "true", "yes", "on"}


def daily_cap() -> int:
    try:
        return int(os.environ.get("GEN_DAILY_CAP", "300"))
    except ValueError:
        return 300


def check_generation(brand_id: str):
    """Call before a paid generation. Returns (ok, message). Enforces the global
    kill-switch and a per-brand daily cap (best-effort; skipped if the counter
    backend is unavailable)."""
    if not generation_enabled():
        return False, "Generation is temporarily disabled (GENERATION_DISABLED)."
    cap = daily_cap()
    if cap <= 0:
        return True, ""
    try:
        from . import database as db
        day = time.strftime("%Y-%m-%d", time.gmtime())
        count = db.bump_gen_usage(brand_id or "?", day)
        if count is not None and count > cap:
            return False, f"Daily generation limit reached for this brand ({cap}/day)."
    except Exception as e:  # never let the guard's own failure block generation
        log.warning("generation budget check skipped: %s", e)
    return True, ""

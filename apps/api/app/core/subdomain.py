"""Subdomain → org resolver middleware.

For white-label deploys: `acme.marketing-brain.app` resolves to the Org whose
settings.subdomain == "acme". The resolved org_id is attached to `request.state`
so downstream handlers can render the right theme + scope brand lookups.

For the cockpit subdomain (the default), this is a no-op.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.db import SessionLocal
from app.models.tenancy import Org


# subdomains that should NOT be treated as tenant slugs
RESERVED = {"www", "api", "app", "admin", "cockpit", "docs", "status", "auth", ""}


class SubdomainMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        host = (request.headers.get("host") or "").split(":")[0].lower()
        parts = host.split(".")
        # foo.bar.baz → subdomain candidate = "foo"
        sub = parts[0] if len(parts) >= 3 else ""
        request.state.subdomain = ""
        request.state.tenant_org_id = None
        if sub and sub not in RESERVED:
            db = SessionLocal()
            try:
                org = db.execute(
                    select(Org).where(Org.settings["subdomain"].astext == sub)
                ).scalar_one_or_none()
                if org:
                    request.state.subdomain = sub
                    request.state.tenant_org_id = org.id
            except Exception:
                # any DB hiccup → just fall through; the middleware never blocks
                pass
            finally:
                db.close()
        return await call_next(request)

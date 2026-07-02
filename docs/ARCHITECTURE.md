# Architecture

## Request flow
`web/` (static SPA) → `app/routes/*` (domain routers) → `app/services/*` &
`app/ai/engine.py` → `app/core/*` (SQLite/Postgres, auth, storage) →
per-brand folders under `WORKSPACES_ROOT`.

## Layers
- **routes/** — HTTP only. Each router imports shared deps/state/helpers from
  `routes/_shared.py` and Pydantic models from `schemas.py`.
- **ai/engine.py** — OpenRouter chat + image generation and every pipeline
  function (analyze, ideas, calendar, creatives, reels, blog, email, SEO,
  trends, competitors, scoring, coaching, playbooks, studio).
- **services/** — non-AI capabilities: web scraper, trend scanner, workspace
  filesystem, projects registry, publish connectors, playbook catalog.
- **core/** — database (SQLite/Postgres), auth (JWT + hashing), storage
  (local / S3-style).

## The pipeline (per brand)
input → `/scrape` → `/analyze` → `/setup` → `/ideas` → `/calendar` →
`/creatives` → `/images` → `/publish` → `/metrics` → `/insights`, with an
`/autopilot` runner that chains them unattended.

## Adding a route
Add the handler to the matching `app/routes/<group>.py` (use `@router.<method>`),
put any request model in `app/schemas.py`, and shared helpers in
`app/routes/_shared.py`. No factory changes needed.

# marketing-brain

An AI Marketing Content Operating System for racket-sport e-commerce brands.
Decides, generates, reviews, schedules, and tracks marketing content across
Instagram, YouTube, Facebook, X, Pinterest, Blog, Email, WhatsApp, GBP, and
Quora — with **fully isolated** verticals per sport (tennis, padel,
pickleball, badminton, squash). No cross-sport content, ever.

The previous `tennisoutlet-video-agent` (V1) is absorbed here as the
**Short Video Agent → `product_video` sub-type** — roughly 5 % of the product.

> **Always read `AGENTS.md` first** if you are an AI agent (Codex, Claude
> Code, etc.) touching this repo.

## Phase 0 — what's in this commit

- Monorepo skeleton (`apps/api`, `apps/web`, `docs/`, `packages/shared`)
- Docker Compose: `postgres`, `redis`, `api` (FastAPI), `worker` (RQ), `web` (Next.js 15)
- FastAPI app factory with auth + orgs + brands + users + brand-brain routers
- SQLAlchemy 2.0 (sync) models for the tenancy + content tables (Section 14 of the spec)
- Alembic initial migration
- JWT auth + RBAC (`owner`, `admin`, `growth_head`, `marketer`, `intern`, `viewer`)
- `no_cross_brand` guard middleware + passing pytest
- Cost guard middleware (`org.monthly_cost_cap_usd` vs MTD `cost_ledger`)
- OpenRouter LLM gateway (cost-logged) + swappable media-provider interface
- V1 video code moved into `apps/api/app/agents/short_video/` + shared `pipeline/render`
- Orchestrator + Calendar + Creative Critic agent stubs (interface-only; bodies land in Phase 1)
- Next.js 15 shell: login, dashboard, brand selector, top bar (brand/platform/content-type),
  cost meter, sidebar to all 13 routes, dark command-center theme
- The 8 docs in `docs/` (per spec § 27)

## Run it

```bash
cp .env.example .env
# Fill in JWT_SECRET, OPENROUTER_API_KEY, FAL_KEY at minimum
docker compose up -d --build
open http://localhost:3006      # UI
open http://localhost:8001/docs # Swagger
```

Default owner login: `owner@marketing-brain.local` / `changeme` (override
via `.env`). The seed CLI creates one org, one owner, and one tennis brand.

Host ports (set to avoid clashes with the V1 stack on the same machine):

| Service  | Host | Container |
| -------- | ---- | --------- |
| web      | 3006 | 3000      |
| api      | 8001 | 8000      |
| postgres | 5434 | 5432      |
| redis    | 6381 | 6379      |

## What's next (Phase 1 — MVP)

Per spec § 28 / § 32:

1. Wire up the V1 video pipeline as an actual queued job through the
   Orchestrator (not just stub'd).
2. Build the Product Demand Score + Content Score functions (`apps/api/app/scoring/`).
3. Implement `Calendar Agent` and the `POST /brands/{id}/calendar/generate` endpoint.
4. Build `/calendar` UI with the 30-day grid, AI-reason tooltips, drag-drop.
5. Add Static Post Agent + Blog Agent so the Critic has more than one format to gate.
6. Reviews/approvals UI; Asset Library.

## Docs

- [`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md) — what we're building and why
- [`docs/AGENT_ARCHITECTURE.md`](docs/AGENT_ARCHITECTURE.md) — the 14 agents + Orchestrator
- [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) — services, queue, data flow
- [`docs/CONTENT_CALENDAR_ENGINE.md`](docs/CONTENT_CALENDAR_ENGINE.md) — scoring → calendar
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) — every table + index
- [`docs/UI_UX_BLUEPRINT.md`](docs/UI_UX_BLUEPRINT.md) — design system
- [`docs/ENGINEERING_ROADMAP.md`](docs/ENGINEERING_ROADMAP.md) — phases 0–3
- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) — V1 summary + what's left
- [`AGENTS.md`](AGENTS.md) — onboarding for any AI agent editing this repo

## License

Internal. Not open source.

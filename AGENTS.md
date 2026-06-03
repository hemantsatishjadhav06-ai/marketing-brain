# AGENTS.md — Onboarding for Codex / Claude Code / any AI coding agent

Read this top-to-bottom before touching the repo. Then read the spec at
[`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md) and the roadmap at
[`docs/ENGINEERING_ROADMAP.md`](docs/ENGINEERING_ROADMAP.md). If you change
something that contradicts this file, **update this file in the same commit.**

---

## 1. What this product is

`marketing-brain` is an AI Marketing Content Operating System for racket-sport
e-commerce brands. It decides, generates, reviews, schedules, and tracks
marketing content across every platform a brand uses, with **fully isolated**
verticals per sport (tennis, padel, pickleball, badminton, squash).

The previous `tennisoutlet-video-agent` (V1) is absorbed here as the
**Short Video Agent → `product_video` sub-type** — roughly **5 %** of the product.

## 2. THE HARDEST RULE — no cross-sport content

Read [`docs/PRODUCT_VISION.md` § "non-negotiable"](docs/PRODUCT_VISION.md).
This rule is enforced at three layers (data, prompt, critic). Every agent
prompt must include `CROSS_SPORT_CLAUSE`. Every brand-scoped query must
pass through `assert_single_brand`. The Critic auto-rejects cross-sport
phrases via regex. There is a pytest at
`apps/api/app/tests/test_no_cross_brand.py` that runs before every change.

If your change weakens any of these layers — **you have introduced a bug.**

## 3. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI 0.115 + Uvicorn | typed, fast, OpenAPI free |
| ORM | SQLAlchemy 2.0 sync | pipeline is IO+CPU mixed; sync reads simpler |
| DB | Postgres 16 | JSONB everywhere, real FKs, indexes |
| Queue | Redis 7 + RQ 2.0 | Python-native, single-binary |
| LLM | Claude Sonnet 4.5 (reasoning) + Haiku 4.5 (drafting), via OpenRouter | one gateway, easy swap |
| Media | fal.ai (`nano-banana/edit`, `kling v2.1`, `elevenlabs tts`) | best-quality hosted models; provider is swappable |
| Renderer | Pillow + ffmpeg | $0, deterministic, no second runtime |
| Auth | JWT (HS256, 30-day) + bcrypt | localStorage in browser — internal cockpit |
| Frontend | Next.js 15 + React 19 + Tailwind 3 + SWR | latest stable |
| Migrations | Alembic | required from Phase 0; no `create_all()` in prod |
| Deploy | Docker Compose now; Render/Railway/Fly in Phase 3 | |

## 4. Repo layout

```
marketing-brain/
├─ docker-compose.yml          5 services: postgres, redis, api, worker, web
├─ .env.example
├─ AGENTS.md                   this file
├─ README.md
├─ docs/                       PRODUCT_VISION, AGENT_ARCHITECTURE, SYSTEM_DESIGN,
│                              CONTENT_CALENDAR_ENGINE, DATABASE_SCHEMA, UI_UX_BLUEPRINT,
│                              ENGINEERING_ROADMAP, CURRENT_STATE
├─ apps/
│  ├─ api/                     FastAPI + worker
│  │  ├─ Dockerfile · requirements.txt · alembic.ini
│  │  ├─ alembic/              env.py + versions/001_initial.py
│  │  └─ app/
│  │     ├─ main.py · cli.py
│  │     ├─ core/              config, db, security, cost_guard
│  │     ├─ models/            tenancy, brand, products, intelligence, content,
│  │     │                     jobs, assets, publishing, cost
│  │     ├─ schemas/           pydantic for every router
│  │     ├─ routers/           auth, orgs, brands, brand_brain, products, jobs,
│  │     │                     sse, scoring, calendar, content, health
│  │     ├─ guards/            no_cross_brand
│  │     ├─ pipeline/          llm_gateway, media_gateway, storage, render
│  │     ├─ workers/           queue, worker, events, job_handlers
│  │     ├─ agents/
│  │     │  ├─ base.py         Agent interface + CROSS_SPORT_CLAUSE
│  │     │  ├─ orchestrator.py · calendar.py · critic.py · repurpose.py
│  │     │  ├─ stubs.py        the other 9 agents as one-line stubs
│  │     │  └─ short_video/    V1 absorbed: agent.py · script_writer.py · prompts.py
│  │     ├─ scoring/           demand, content, trend, audience, weights
│  │     ├─ data_sources/      Phase 2 (cached + TTL'd)
│  │     ├─ repos/             Phase 1 (brand-scoped repository layer)
│  │     └─ tests/             test_no_cross_brand · test_health
│  └─ web/                     Next.js 15 App Router
│     ├─ Dockerfile · next.config.mjs · tailwind.config.ts
│     ├─ app/                  login + 15 cockpit routes
│     ├─ components/           AppShell, BrandSelector, CostMeter, ui
│     └─ lib/                  api, brandStore, types
└─ packages/shared/            shared TS types (Phase 1)
```

## 5. The job state machine

```
queued → running → done
   │        │
   │        └── (cross-sport rejected by Critic) → failed
   └── budget cap hit → failed("budget_exceeded")
```

Worker dispatches by `job.type`:

| `type` | Handler |
|---|---|
| `short_video.product_video` | `agents.short_video.agent.run_product_video` (full E2E in Phase 0) |
| `calendar.generate` | Phase 1 |
| `scoring.run` | Phase 1 |
| `content.<agent>.draft` | Phase 1+ per agent |

Every state transition emits a Redis pub/sub event via `workers.events.emit`,
forwarded to the UI as SSE.

## 6. Conventions (the non-obvious ones)

1. **Sync SQLAlchemy 2.0.** Don't `await session.execute`. Use `with SessionLocal() as s:`.
2. **One agent = one prompt = one LLM call = strict JSON.** No agent makes multiple LLM calls. The pipeline orchestrates.
3. **All LLM calls go through `pipeline/llm_gateway.py`** — cost-logged, retried, tier-aware (`REASONING` vs `DRAFTING`).
4. **All media calls go through `pipeline/media_gateway.py`** — same reason. Swap providers via the `MediaProvider` Protocol.
5. **All storage writes go through `pipeline/storage.py`**.
6. **Brand bible is read at job start.** Editing it affects the next queued job, not the running one.
7. **Critic runs BEFORE media spend.** Script rejection costs $0.03; video rejection costs $0.30. Don't move the gate.
8. **Cost guard runs BEFORE every job** in `workers.job_handlers.run_job`. If `cost_ledger` MTD ≥ `org.monthly_cost_cap_usd`, the job is `failed("budget_exceeded")` immediately.
9. **EventSource can't send headers.** SSE uses `?token=...` query string; `routers/sse.py` decodes.
10. **Migrations: real Alembic, no `create_all`.** New table = new revision.
11. **JWT in localStorage** — fine for internal tool; move to httpOnly cookies before public exposure.
12. **Next.js rewrites** in `next.config.mjs` proxy `/api/*` + `/storage/*` to the backend — zero CORS in dev.

## 7. Run it

```bash
cd marketing-brain
cp .env.example .env       # fill JWT_SECRET, OPENROUTER_API_KEY, FAL_KEY
docker compose up -d --build
open http://localhost:3006     # cockpit
open http://localhost:8001/docs
docker compose exec api pytest app/tests
```

Default login: `owner@marketing-brain.local` / `changeme` (override via `.env`).

Host ports: web **3006**, api **8001**, postgres **5434**, redis **6381**
(non-default to avoid clashing with the V1 stack).

## 8. Common change recipes

### Add a new agent
1. New file in `apps/api/app/agents/<your_agent>.py` exposing a `run()` callable.
2. Prompt lives next to the agent or in `<your_agent>/prompts.py` — must include `CROSS_SPORT_CLAUSE`.
3. Wire into `workers.job_handlers.run_job` dispatch (add a new `job.type`).
4. Front-end: pick a page from `apps/web/app/` to surface its output.

### Add an API route
1. New file in `apps/api/app/routers/your_thing.py`.
2. Add `app.include_router(...)` in `apps/api/app/main.py`.
3. Schemas in `apps/api/app/schemas/your_thing.py`.
4. Typed fetch wrapper in `apps/web/lib/api.ts` and a page under `apps/web/app/`.

### Add a DB table
1. Model in `apps/api/app/models/your_table.py` + re-export from `models/__init__.py`.
2. New Alembic revision (`docker compose exec api alembic revision -m "..."` then hand-edit).
3. Index the columns you actually query.

### Add a new sport vertical
1. Add to `models.brand.Sport` enum.
2. Add accent color to `routers/brands.py::ACCENT_DEFAULTS` and `tailwind.config.ts`.
3. **Do not add any cross-sport content elsewhere.** New sport is a new brand row, nothing shared.

## 9. Environment variables (canonical)

See `.env.example`. Hot ones:

| Var | Required | Default |
|---|---|---|
| `JWT_SECRET` | yes | dev stub — replace |
| `OPENROUTER_API_KEY` | for any LLM work | empty (gateway returns stub) |
| `FAL_KEY` | for any media work | empty (provider returns stub) |
| `DATABASE_URL` | yes | compose default |
| `REDIS_URL` | yes | compose default |
| `STORAGE_BACKEND` | no | `local` |
| `CORS_ORIGINS` | yes | `http://localhost:3006,...` |
| `DEFAULT_OWNER_EMAIL` / `_PASSWORD` | no | seed defaults |
| `DEFAULT_MONTHLY_COST_CAP_USD` | no | 200 |

## 10. Definition of "done" for a change (Phase 0+)

1. `docker compose build` clean
2. `docker compose up -d` reaches healthy
3. `pytest app/tests` passes
4. New env var → in `.env.example` + this file
5. Touched a doc → grep'd for inconsistencies elsewhere
6. Committed + pushed

## 11. Quick links

- Spec: [the master build spec is the source-of-truth for all behavioral decisions]
- Live cockpit (after `docker compose up`): http://localhost:3006
- Swagger: http://localhost:8001/docs
- Vision: [`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md)
- Agents: [`docs/AGENT_ARCHITECTURE.md`](docs/AGENT_ARCHITECTURE.md)
- System: [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md)
- Calendar: [`docs/CONTENT_CALENDAR_ENGINE.md`](docs/CONTENT_CALENDAR_ENGINE.md)
- Schema: [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md)
- UI: [`docs/UI_UX_BLUEPRINT.md`](docs/UI_UX_BLUEPRINT.md)
- Roadmap: [`docs/ENGINEERING_ROADMAP.md`](docs/ENGINEERING_ROADMAP.md)
- Today's state: [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)

— If you're an AI: start with §§ 1, 2, 4, 5. That's enough to make safe edits.
Read the rest before larger changes.

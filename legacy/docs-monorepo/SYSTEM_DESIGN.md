# System Design

## Runtime topology

```
┌──────────────────────────────┐
│        Next.js Web (3006)    │  apps/web · App Router · SWR · SSE consumer
└────────────────┬─────────────┘
                 │ /api/* and /storage/* (next.config rewrites)
┌────────────────▼─────────────┐
│        FastAPI API (8001)    │  apps/api/app · sync SQLAlchemy 2.0
│  auth · brands · products    │
│  brand-brain · jobs · sse    │  + cost guard middleware
│  scoring · calendar · content│
└──┬──────┬───────────┬────────┘
   │      │           │
┌──▼──┐ ┌─▼─────┐ ┌───▼──────────┐
│ PG  │ │ Redis │ │ Object store │
│5434 │ │ 6381  │ │ local → R2/S3│
└─────┘ └───┬───┘ └──────────────┘
            │ RQ jobs
   ┌────────▼─────────────────┐
   │   Worker pool             │  apps/api/app/workers · RQ Worker
   │   orchestrator + agents   │
   │   + critic + render       │
   └──┬──────┬─────────────────┘
      │      │
┌─────▼──┐ ┌─▼─────────────┐
│OpenRtr │ │ fal.ai +      │
│(all    │ │ swappable     │
│ LLMs)  │ │ media interface│
└────────┘ └───────────────┘
```

All five services run via `docker compose up` (see project root `docker-compose.yml`).

## Process model

| Container | Process | Notes |
|---|---|---|
| `postgres` | postgres:16-alpine | host port 5434 |
| `redis` | redis:7-alpine | host port 6381 |
| `api` | uvicorn `app.main:app` | host port 8001; runs `wait-db → alembic upgrade → seed-defaults → uvicorn` on boot |
| `worker` | `python -m app.workers.worker` | RQ worker, `WORKER_CONCURRENCY` jobs |
| `web` | next standalone server | host port 3006 |

Host ports are non-standard (5434, 6381, 8001, 3006) to avoid clashes with the V1 `tennisoutlet-video-agent` stack on the same machine.

## Request paths

1. **UI calls the API:** `/api/auth/login` → `next.config.mjs` rewrite → `http://api:8000/auth/login`. No CORS issues in dev because the browser sees one origin.
2. **UI streams a job:** `/api/sse/jobs/<id>?token=<jwt>` — EventSource can't send headers; JWT goes via query.
3. **API enqueues work:** `enqueue_job(job_id)` pushes to RQ; the worker picks it up and runs through `workers.job_handlers.run_job → agents.<agent>.run`.
4. **Worker emits progress:** `workers.events.emit(job_id, status=..., message=...)` publishes to Redis channel `jobs.<id>`; SSE forwards.

## Brand isolation enforcement

Spec § 3.1, 3-layer guard:

| Layer | File | What it does |
|---|---|---|
| Data | `apps/api/app/guards/no_cross_brand.py` | `assert_single_brand(rows, brand_id)` — pytest in `app/tests/test_no_cross_brand.py` |
| Prompt | `apps/api/app/agents/base.py::CROSS_SPORT_CLAUSE` | Every agent prompt includes it |
| Critic | `apps/api/app/agents/critic.py::hard_cross_sport_check` | Regex auto-reject; the LLM rubric (Phase 1) reinforces it |

A unit test boots before every change: `pytest app/tests/test_no_cross_brand.py` — proves the data + critic layers reject cross-brand input.

## Cost guard

`apps/api/app/core/cost_guard.py`:

- `assert_budget_available(db, org_id)` runs **before every job** in `workers.job_handlers.run_job`. If `cost_ledger` MTD ≥ `org.monthly_cost_cap_usd`, the job fails immediately with `failed("budget_exceeded")`.
- Every LLM call from `pipeline/llm_gateway.py` and every fal call from `pipeline/media_gateway.py` lands a row in `cost_ledger`.
- The `/orgs/me/cost` endpoint powers the live cost-meter in the top bar.

## Storage

`apps/api/app/pipeline/storage.py` — interface `Storage`. Concretes: `LocalStorage` (Phase 0, ships now), `R2Storage` (Phase 3). Worker writes via `get_storage().write_file(key, src_path)`; API mounts `/storage/*` as a static directory for the local backend.

Keys: `videos/<brand_id>/<uuid>.mp4`, `images/<brand_id>/<uuid>.jpg`, etc. — see `pipeline.storage.new_key`.

## Choices that were rejected

| Choice | Why rejected |
|---|---|
| Celery | RQ is simpler, single-binary, plenty for ~2k SKUs |
| Async SQLAlchemy | Pipeline code is IO+CPU mixed; sync reads better |
| Multiple LLM providers | One gateway (OpenRouter); easy model swap via env |
| Direct fal-only render | Render stays as ffmpeg+Pillow (V1); Remotion migration documented but not adopted in Phase 0 |
| WebSocket for live jobs | SSE works through proxies, is simpler, no bidirectional traffic needed |
| Per-app frontend repos | One monorepo; shared types in `packages/shared` |

## Deploy plan

- **Dev:** `docker compose up -d --build` brings up everything.
- **Stage/Prod (Phase 3):** Render/Railway/Fly for api+worker+web; managed Postgres + Redis; R2/S3 for assets; secrets via env; CI runs lint + tests + alembic check; health endpoints + basic uptime alerting.

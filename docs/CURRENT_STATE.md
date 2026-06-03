# Current State

## V1 (`tennisoutlet-video-agent`) — what we absorbed

V1 was a single-purpose tool: one tennis SKU in, one 9:16 vertical product video out (1080×1920 @ 30 fps, ~25-35 s, with voiceover and on-screen text). It runs at <https://github.com/hemantsatishjadhav06-ai/tennisoutlet-video-agent> and is currently live on the dev machine at `http://localhost:3005`.

**What V1 had:**

- FastAPI 0.115 backend, sync SQLAlchemy 2.0
- Postgres + Redis + RQ worker
- One LLM agent: script writer (Claude Sonnet 4.5 via OpenRouter)
- One critic: 6-criterion rubric, hard cross-sport check, banned-phrase gate
- Media: fal.ai (`nano-banana/edit`, `kling-video v2.1`, `elevenlabs tts`)
- Renderer: Pillow + ffmpeg compositing to MP4
- Brand bible editable in the UI (admin-only) — voice / tone / banned phrases / cta / platform rules
- JWT auth + RBAC
- Next.js 15 cockpit with dashboard, products, jobs (live SSE), videos, settings/brand
- Docker Compose deploy with seeded admin

**What V1 was NOT:** multi-brand, multi-agent, calendar-aware, scored, trend-aware, audience-aware, scheduled, repurposed, or platform-diverse. It was the **`Short Video Agent → product_video` sub-type**, full stop. By the spec's accounting that's roughly **5 %** of the eventual product.

## What's in this Phase 0 commit

| Area | Status | Where |
|---|---|---|
| Monorepo skeleton | ✓ | `marketing-brain/` |
| Docker Compose (postgres · redis · api · worker · web) | ✓ | `docker-compose.yml` |
| Postgres schema, all spec § 14 tables | ✓ | `apps/api/alembic/versions/001_initial.py` |
| SQLAlchemy models (every table) | ✓ | `apps/api/app/models/` |
| JWT auth + RBAC + dependencies | ✓ | `apps/api/app/core/security.py` |
| Org + brand + brand-brain + products + jobs routes | ✓ | `apps/api/app/routers/` |
| Cross-brand guard + pytest | ✓ | `apps/api/app/guards/no_cross_brand.py` + `app/tests/test_no_cross_brand.py` |
| Cost guard (MTD vs org cap) | ✓ | `apps/api/app/core/cost_guard.py` |
| LLM gateway (OpenRouter, cost-logged) | ✓ | `apps/api/app/pipeline/llm_gateway.py` |
| Media interface + fal provider | ✓ | `apps/api/app/pipeline/media_gateway.py` |
| Storage interface (local now) | ✓ | `apps/api/app/pipeline/storage.py` |
| V1 renderer absorbed | ✓ | `apps/api/app/pipeline/render.py` |
| V1 script writer + critic absorbed | ✓ | `apps/api/app/agents/short_video/` |
| Orchestrator + Calendar + Critic + Repurpose interfaces | ✓ stubs | `apps/api/app/agents/` |
| Other 9 agents (long_video, carousel, static, blog, …) | ✓ class stubs | `apps/api/app/agents/stubs.py` |
| Scoring weights + Demand/Content scoring functions | ✓ functions, real signals are Phase 1 | `apps/api/app/scoring/` |
| Worker + queue + events | ✓ | `apps/api/app/workers/` |
| Next.js 15 cockpit with 15 routes | ✓ shell, page bodies Phase 1+ | `apps/web/app/` |
| Cost meter + Brand selector live in top bar | ✓ | `apps/web/components/` |
| 8 docs + `AGENTS.md` | ✓ | `docs/` + `AGENTS.md` |

## What's NOT in Phase 0 (intentionally)

- Real scoring numbers (Phase 1)
- Calendar generation (Phase 1)
- Static / Blog / other 8 agent bodies (Phase 1 / 2)
- LLM-backed critic rubric (Phase 0 ships regex hard gate only)
- Trend / audience data sources (Phase 2)
- Analytics import + feedback loop (Phase 2)
- Platform API publishing (Phase 3)
- R2/S3 storage, better-auth, Remotion render (Phase 3)

## How to verify Phase 0

```bash
cd marketing-brain
cp .env.example .env
# fill JWT_SECRET, OPENROUTER_API_KEY, FAL_KEY (FAL/LLM keys optional in Phase 0)
docker compose up -d --build
open http://localhost:3006        # cockpit, log in with owner@marketing-brain.local / changeme
open http://localhost:8001/docs   # Swagger
docker compose exec api pytest app/tests   # cross-brand guard + health
```

Expected:
- API `/health` → 200
- Web login works; dashboard renders with 4 KPI cards + "Phase 0 — what's live" panel
- BrandSelector shows the seeded tennis brand
- Cost meter shows 0 / cap
- Pytest passes 6/6 (cross-brand + health smoke)

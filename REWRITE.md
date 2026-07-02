# Rewrite & Restructure

The repo previously held **two parallel products** (`apps/` FastAPI+Next.js
monorepo and `marketing-brain-v2/`) plus scattered extras (`landing/`, `video/`,
`supabase/`, `docs/`, `.claude/`). Per direction, **`marketing-brain-v2` is the
source of truth** and has been **fully rewritten into a clean, modular package**;
everything else is archived under `legacy/`.

## What changed

- **Monoliths split.** `backend/main.py` (1,389 lines, 62 routes) and
  `backend/ai_engine.py` (857 lines) were broken into a proper package with an
  app factory, domain routers, and clear layers.
- **Frontend split.** `frontend/index.html` (1,433 lines) → a thin shell plus
  external `css/` and `js/` (dynamic brand theming preserved).
- **Tooling added.** `pyproject.toml`, smoke `tests/`, `.gitignore`; `run.sh`
  and `render.yaml` now target `app.main:app`.
- **Behavior preserved** (logic ported, not reinvented). Verified: app boots,
  `GET /api/health` → 200, 52 OpenAPI paths, all smoke tests pass.
- **Legacy archived** under `legacy/` (nothing deleted).

## Old → New map

| Old (`marketing-brain-v2/`) | New |
|---|---|
| `backend/main.py` (routes + schemas + helpers + state) | `app/main.py` (factory) · `app/routes/*.py` (9 domain routers) · `app/schemas.py` · `app/routes/_shared.py` (deps/state/helpers) |
| `backend/ai_engine.py` | `app/ai/engine.py` |
| `backend/database.py` · `auth.py` · `storage.py` | `app/core/` |
| `backend/scraper.py` | `app/services/scraper.py` |
| `backend/trend_scanner.py` | `app/services/trends.py` |
| `backend/workspace.py` · `projects.py` · `connectors.py` · `playbook.py` | `app/services/` |
| `frontend/index.html` | `web/index.html` + `web/css/styles.css` + `web/js/app.js` + `web/js/boot.js` |
| `requirements.txt` · `render.yaml` · `run.sh` · `.env.example` | root equivalents, updated |

Route groups: `auth` (5) · `brands` (5) · `pipeline` (13) · `growth` (10) ·
`competitors` (4) · `studio` (10) · `autopilot` (6) · `publishing` (7) · `misc` (2).

## Applying this rewrite

**Option A — git bundle (full history + branch):**
```bash
git clone marketing-brain-rewrite.bundle marketing-brain
# or into an existing clone:
git fetch ../marketing-brain-rewrite.bundle rewrite/clean-architecture:rewrite/clean-architecture
git checkout rewrite/clean-architecture
```

**Option B — patch series:**
```bash
git checkout -b rewrite/clean-architecture
git am 0001-*.patch 0002-*.patch
```

Both land two commits on `rewrite/clean-architecture`: (1) archive legacy, (2)
the clean rewrite. Review, then merge to `main` and push.

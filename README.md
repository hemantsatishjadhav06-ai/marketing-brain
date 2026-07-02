# Marketing Brain

An AI marketing team in a box. Give it a company name + website; it scans the
brand's online presence, proposes a full social strategy, spins up a per-brand
workspace, generates ideas → a 30-day calendar → deep creative packages (reel
scripts, carousels, posts, emails, blogs), generates visuals, publishes
(simulated or live via official APIs), and learns from performance data.

> This repository was **restructured from a monolith into a clean, modular
> package**. See [`REWRITE.md`](REWRITE.md) for the full old→new map. The
> previous implementations are archived under [`legacy/`](legacy/).

## Architecture

```
app/                     FastAPI application (Python package)
├── main.py              app factory: create_app(), router wiring, static mounts
├── config.py            env-driven settings
├── core/                database · auth · storage
├── ai/engine.py         OpenRouter LLM + image generation + pipeline functions
├── services/            scraper · trends · workspace · projects · connectors · playbook
├── schemas.py           all Pydantic request models
└── routes/              domain routers (auth, brands, pipeline, growth,
                         competitors, studio, autopilot, publishing, misc)
                         + _shared.py (deps, state, helpers)
web/                     frontend  (index.html + css/ + js/)
tests/                   smoke tests
legacy/                  previous implementations, archived (not run)
```

## Run locally

```bash
cp .env.example .env      # add your OPENROUTER_API_KEY
./run.sh                  # installs deps + starts uvicorn on :8000
# open http://localhost:8000   (Swagger at /docs)
```

## Deploy (Render)

`render.yaml` is a one-click blueprint. New → Blueprint → pick the repo, set
`OPENROUTER_API_KEY`. Start command: `uvicorn app.main:app`.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Required. Powers all generation. |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Text model (any OpenRouter id). |
| `OPENROUTER_IMAGE_MODEL` | `openai/gpt-image-1` | Image model. |
| `DB_PATH` | `data/marketing_brain.db` | SQLite location (or Postgres URL). |
| `WORKSPACES_ROOT` | `workspaces/` | Per-brand output folders. |
| `PUBLIC_BASE_URL` | — | Needed for IG image publishing. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | — | Auto-creates an admin on boot. |

## Tests

```bash
pip install pytest && pytest -q
```

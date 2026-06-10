# 🧠 Marketing Brain v2

A one-stop AI marketing team in a box. Give it a company name and website; it scans the company's online presence, proposes a full social strategy, creates a per-brand multi-channel workspace, generates content ideas, builds a 30-day posting calendar, produces ready-to-shoot creative packages (reel scripts with shot lists, carousels slide-by-slide, post copy variants), generates visuals, publishes (simulated or live via official APIs), and learns from your performance data.

## The pipeline

1. **Step 1 — Company input.** Name + website (social handles optional).
2. **Step 2 — Presence scan.** Crawls the website + key internal pages, extracts brand description, headings, colors, logo, and discovers social profiles.
3. **Step 3 — Strategy setup.** AI builds a brand profile: voice, audience personas, positioning, content pillars, recommended channels with priorities and cadence. You review and confirm.
4. **Workspace.** A folder per brand is created at `workspaces/<brand>/` with subfolders per channel (`ideas/ calendar/ creatives/ assets/ published/`). Everything generated is saved there as JSON + readable markdown — you own your content.
5. **Ideas.** Per-channel idea batches with hook, concept, funnel stage, and "why it works". Approve/reject.
6. **Calendar.** 30-day schedule at platform-optimal times, sequenced by funnel stage.
7. **Creatives.** Deep production packages per format:
   - **Reels/Shorts:** 3 hook options, shot-by-shot script (time, camera, action, VO, on-screen text), audio style, loop trick, filming + CapCut editing guide, thumbnail concept.
   - **Carousels:** slide-by-slide headline/body/visual direction.
   - **Posts:** A/B copy variants + visual direction. **Stories:** frame sequence with interactive stickers. **Threads**, **Articles** (SEO outline) too.
   - Every package includes publish-ready caption, tiered hashtags (broad/niche/branded), CTA, best time, alt-text, and KPIs to watch.
8. **Visuals.** Text-to-image generation (via OpenRouter image models) saved into the brand's assets folder.
9. **Publish.** *Simulated mode* (default): renders the exact post + a step-by-step manual publishing checklist. *Live mode*: real posting through official APIs (Meta Graph for Instagram/Facebook, LinkedIn UGC) once you save credentials — in-app setup guides included.
10. **Analytics loop.** Log post metrics; the analyst model grades channels, finds what works/fails, and those insights automatically bias the next idea batch.

## Run locally

```bash
cp .env.example .env        # put your OpenRouter key in .env
./run.sh                    # or: pip install -r requirements.txt && uvicorn backend.main:app --port 8000
# open http://localhost:8000
```

## Deploy to Render

1. Push this folder to a GitHub repo.
2. Render dashboard → New → Blueprint → pick the repo (`render.yaml` is auto-detected).
3. Set `OPENROUTER_API_KEY` in the environment settings.
4. (Optional, for Instagram live publishing) set `PUBLIC_BASE_URL` to your Render URL so generated images are publicly fetchable.

Note: `render.yaml` uses a 1 GB persistent disk for the SQLite DB and workspaces. Disks aren't available on Render's free plan — either upgrade to Starter, or remove the `disk:` block and accept that data resets on redeploys.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Required. Powers all generation. |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Text model (any OpenRouter model id). |
| `OPENROUTER_IMAGE_MODEL` | `google/gemini-2.5-flash-image` | Image model. |
| `DB_PATH` | `data/marketing_brain.db` | SQLite location. |
| `WORKSPACES_ROOT` | `workspaces/` | Where brand folders are created. |
| `PUBLIC_BASE_URL` | — | Public URL of this app (needed for IG image publishing). |

## API surface

`POST /api/brands` → `POST /{id}/scrape` → `POST /{id}/analyze` → `POST /{id}/setup` →
`POST /{id}/ideas` → `POST /{id}/calendar` → `POST /{id}/creatives` → `POST /{id}/images` →
`POST /{id}/publish` → `POST /{id}/metrics` → `POST /{id}/insights`. Interactive docs at `/docs`.

## Honest limits (read this)

- **Social scraping:** platforms block anonymous scraping; the scanner discovers handles and public metadata, not full feeds. Deep social data arrives via the analytics loop or official APIs.
- **Live auto-posting** requires platform developer apps only the account owner can create (guides are built into the Connectors tab). X/Twitter posting requires their paid API tier. Until then, simulated mode gives you the exact post + checklist, which takes ~60 seconds to execute manually.
- AI output quality scales with the model — set `OPENROUTER_MODEL` to a stronger model (e.g. `anthropic/claude-sonnet-4.5`) for better strategy and scripts.

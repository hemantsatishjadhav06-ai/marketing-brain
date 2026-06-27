# Update — OpenRouter GPT Image 1 image generation + fixes

## What changed
**backend/ai_engine.py — image engine rewritten**
- Image generation now calls OpenRouter's dedicated **Images API** (`/api/v1/images`),
  which is the correct endpoint for **GPT Image 1** and other dedicated image models.
  The old code only used chat-completions `modalities`, which works for Gemini but
  NOT for `openai/gpt-image-1` — so simply switching the model would have failed.
- New `_art_direct()` builds a designer-grade brief (brand palette, cinematic composition,
  negative space, and a hard "no text/logo in pixels" rule since the logo is composited on).
- Robust: tries the Images API first, falls back to the chat-image path for Gemini models.
  Always returns image bytes or `None` (never throws into the request).

**Config — default model is now GPT Image 1**
- `render.yaml` and `.env.example`: `OPENROUTER_IMAGE_MODEL = openai/gpt-image-1`.
- Code default matches. Override per-deploy via the env var (e.g. back to
  `google/gemini-2.5-flash-image` for cheaper runs).

**frontend/index.html — UI/UX fixes**
- Added `alt` text to all brand logos, generated visuals, slide images and storyboard
  scenes (accessibility / screen-reader + graceful broken-image text).
- `loading="lazy"` on generated/slide/scene images (faster creatives tab).
- App icon gradient now uses the brand tokens (`--yel`→`--grn`) instead of a hardcoded
  purple, so the chrome matches the rest of the brand-adaptive UI.

## Deploy
1. Set `OPENROUTER_API_KEY` in the Render dashboard (use a freshly rotated key).
2. `OPENROUTER_IMAGE_MODEL` already defaults to `openai/gpt-image-1` — no action needed.
3. Push to `main`; Render auto-deploys (`autoDeploy: true`).

## Automation review
The autopilot/orchestrator runs agents through `_chat` (unchanged) and, when
`generate_images=true`, calls `generate_image` — which was the broken link for GPT Image 1
and is now fixed, so the autopilot image step works too. Other agents were left intact.

## Reminders
- Rotate the OpenRouter key and the GitHub token that were shared in chat.
- Set the repo back to **private** once you've pushed.

## Update 2 — All projects in the chatbot, voice & a master directory
- `backend/projects.py`: structured directory of every MoreSpace project — Neopolis (Kokapet),
  Rajendra Nagar, Manchirevula/Narsingi, and Soul of Earth (Kukatpally) — each with area,
  corridor, configs, sizes, price, highlights and its morespace.ai link. morespace.ai is set
  as the MASTER website for all projects.
- AI coach chatbot (`/api/brands/{id}/chat`) now answers property/area/budget questions with the
  exact project link + in-depth details, combining corridor + developer info, and never invents prices.
- Voice/reel scripts and every generator (ideas, calendar, creatives) are project-aware via a short
  pointer injected into the shared brand context — so spoken/voiceover content references real projects.
- New public endpoint `GET /api/projects` and a "Projects" tab in the app = the master directory with links.

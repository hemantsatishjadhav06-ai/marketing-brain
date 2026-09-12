# Cinematic Storyboard Film — storyboard first, video second

A creative style that directs a **cut-by-cut cinematic storyboard** before any
video renders. Inspired by storyboard-first film tools (Viora Studio): the
director writes a complete production plan you review, edit and reorder; nothing
is generated until a human approves the storyboard.

## The idea

> Storyboard first, video second. No video is generated until you have edited
> every cut and approved the plan.

A film is a normal creative (`format = "film"`), so it flows through the same
approval queue, portfolio counts, memory and tenancy as every other creative.
Its editable production plan lives at `creative.payload.film`.

## A cut

Each cut is a director's card:

| Field | Example |
|---|---|
| `duration_s` (clamped 3–15) | `4` |
| `t_in` / `t_out` (computed) | `0` → `4` |
| `camera` (lens + move) | `35mm, slow dolly-in` |
| `lighting` | `controlled golden hour, soft key` |
| `vo_line` + `vo_tone` | "Most buyers overpay." · `calm, confident` |
| `on_screen_text` (≤6 words) | `Overpaying?` |
| `visual` (text-free frame) | keys on a table, warm grade, 9:16 |
| `transition` (into next cut) | `match cut` |
| `negatives` | `no text, no logos, no stock-photo look` |
| `asset` (after render) | the reference frame |

The looks are graded film presets (`warm-neutral-premium`, `teal-orange-cinematic`,
`golden-hour`, `bright-airy`, `moody-noir`, `documentary-natural`, `product-studio`,
`editorial-mono`). Default format is 9:16, ~30s, 6 cuts.

## Two invariants the code owns (never the model)

1. **Timecodes.** Every edit renumbers cuts, clamps each duration to 3–15s and
   recomputes `t_in`/`t_out` and the total from the durations (`film_studio.recompute`).
2. **The gate.** `render` refuses unless the creative is human-approved. Any edit
   (a cut change, reorder, add/remove) clears a prior render **and its approval**,
   so a changed storyboard must be re-approved before it can render again.

## Flow

```
plan  → storyboard creative (no render)         POST /api/brands/{id}/film/plan   (pool job)
edit  → update / reorder / add / remove cuts    PUT/POST/DELETE …/film/{cid}/cut…
approve (the storyboard)                        POST …/creatives/{cid}/approval
render → reference frames + voiceover           POST …/film/{cid}/render          (pool job, gated)
```

Both long operations run in the bounded pool; poll `GET /api/agency/jobs/{job_id}`.
Client logins can review and approve a storyboard but cannot plan, edit or render
it — the agency directs, the client signs off.

## Where

- Backend: `app/ai/engine.py` (`FILM_LOOKS`, `film_storyboard`), `app/services/film_studio.py`, `app/routes/film.py`.
- Per-client default look/aspect/cuts/duration: `brand.profile.config.film`.
- Brand app: **Content → 🎬 Film studio** — the storyboard board with per-cut
  cards, reorder, inline edit, the "no video generated yet" banner, the approval
  gate and render.
- Tests: `tests/test_film_studio.py`.

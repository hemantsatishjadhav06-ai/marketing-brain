# Competitor notes — OpusClip & vidIQ (June 2026)

## OpusClip (agent.opus.pro)
What they are: AI video clipping. Long video in → scored short clips out, captions + reframing applied.

Key features worth learning from:
- **Virality Score (0–99)** per clip, judged on Hook / Flow / Trend fit, trained on millions of viral videos. Pro-tier exclusive — it's their stickiest feature.
- **ClipAnything**: clips any video type (talking-head, vlog, sports, low-dialogue) using visual/audio/sentiment cues.
- AI captions, auto-reframe to vertical, AI b-roll, voice dubbing, multi-speaker detection.
- Positioned in 2026 as a "content intelligence engine", not a clipper.
- Weakness (per reviews): ~40% of generated clips get discarded; quality varies; expensive at scale.

## vidIQ (vidiq.com)
What they are: YouTube growth/SEO copilot.

Key features worth learning from:
- **Keyword research** with volume/competition estimates (tracks within ~20-25% of YT internal data).
- **Daily Ideas**: 3–5 personalized video ideas/day from channel data + niche trends + competitor gaps.
- **AI Coach**: chat assistant with access to channel data + keyword DB.
- **Trending detection**: flags rising keywords ~3–5 days before peak.
- Title/thumbnail optimization, SEO score, best-time-to-post.
- Pricing: free tier limited; Boost $39/mo.

## What we adopted into Marketing Brain (Growth Engine)
| Their feature | Ours | Notes |
|---|---|---|
| OpusClip Virality Score | `POST /brands/{id}/score` + auto-score on idea generation (0–99 hook/flow/trend/brand-fit/share-trigger) | honest scoring prompt; badge in UI |
| ClipAnything | `POST /brands/{id}/repurpose` — paste transcript/article → best moments → scored short scripts, saved as Ideas | text-level clipping (no video processing in this stack) |
| vidIQ keyword research | `POST /brands/{id}/seo` — keywords w/ intent + opportunity, titles, tags, description, thumbnail text | volumes are AI estimates, labelled |
| vidIQ trending | `POST /brands/{id}/trends` — niche trend hypotheses with brand-specific angles | AI-inferred, confidence-labelled |
| vidIQ competitor gaps | `POST /brands/{id}/competitors` — scrape competitor site → battlecard (strengths, weaknesses, gaps to own) | grounded in our scraper |

## Our differentiation vs both
- They are single-channel point tools; we run the **whole pipeline** (strategy → ideas → calendar → production packages → publish → analytics loop) across **multiple brands with client logins**.
- Honest gaps remaining vs them: no actual video processing (OpusClip), no live search-volume data (vidIQ). Both would need external APIs/services.

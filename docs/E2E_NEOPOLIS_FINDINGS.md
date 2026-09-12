# Neopolis Infra — live end-to-end run findings

Run: `out/e2e-neopolis/20260817-041313` · 2026-08-17
Models: `openai/gpt-4o-mini` (text) · `fal-ai/nano-banana-pro` @ 4:5 (image)
Command: `python -m scripts.e2e_neopolis all`

All three stages completed. 8 images rendered (928×1152, correct 4:5), a 423-word
blog with 3 FAQs, full blueprints saved. The pipeline **works**. What follows is
what the output revealed.

---

## 1. Brand logo is not composited on the Brain path — invented brands ship

`app/routes/brain.py::_run_proceed` calls `brain.fal_image(..., logo_url=...)` and
saves the result directly. It never composites the real logo file.

Every other image route does composite: `studio.py:44`, `studio.py:130`,
`studio.py:146`, `growth.py:157`, `_shared.py:176`, `_shared.py:262`. The fal path
is the only one that doesn't — and `brain.py` itself warns about this:

> "The model may still reinterpret it, so the caller should composite the real logo
> file over that tile for guaranteed fidelity."

The caller doesn't. In one run, four different **invented** brands appeared in the
top-left logo tile of Neopolis marketing assets:

| Asset | Logo rendered |
|---|---|
| `post-creative.png` | Neopolis Infra ✅ (correct, by luck) |
| `carousel-slide1.png` | **SKYLINE REALTY** ❌ |
| `carousel-slide3.png` | **ELEVATE — by The Indian Luxury** ❌ |
| `carousel-slide6.png` | **JADE HEIGHTS** ❌ |
| `blog-hero.png` | generic **REAL ESTATE** clip-art ❌ |

These read as competitor brands on the brand's own creatives. The fix is the
existing `_composite_logo` helper, applied after `fal_image` as everywhere else.

## 2. The project knowledge base never reaches the prompt for this brand

`projects.py::pointer()` is gated on `is_morespace(brand_name)`, which is a
substring test for `"morespace"`:

```python
def is_morespace(brand_name=""):
    return "morespace" in (brand_name or "").lower().replace(" ", "")
```

The brand is **"Neopolis Infra"**, so `is_morespace()` returns `False` and
`pointer()` returns `""`. No project facts — and, notably, not even the
`"never invent prices"` instruction — reach the model.

The result is that every regulated or commercial fact on the creative is invented.
Three stages of the same run produced three different prices for the same project:

| Stage | Price stated | `projects.py` says |
|---|---|---|
| post | Rs 2.7 Cr | ₹2.7 Cr onwards ✅ |
| carousel | **₹5.5 Crores** | ❌ |
| blog | **₹3.5–4.5 crore** | ❌ |

Other invented facts on `post-creative.png`:

| Field on image | Rendered | Reality |
|---|---|---|
| Sizes | 2500–3000 sq.ft | 2850 / 3303 / 3850 sq.ft |
| Possession | Q1 2025 | in the past — run date is Aug 2026 |
| RERA No | `P1234567890` | placeholder; RERA numbers are legally mandatory in Indian property advertising |
| Phone | +91 98765 43210 | +91 73965 06318 |
| Homes available | "Only 30 Homes Available" | not in any source |

The blog also asserts *"Recent surveys indicate a 25% increase in demand"* — no such
survey is in the source data.

Note that `context_block()` **does** hold the full price/size/RERA directory, but it
is only wired into the AI-coach chatbot, not the creative pipeline. Even a correctly
named brand would only get project *names* from `pointer()`, never the numbers.

## 3. The scraper cannot reach the source site

`scrape_company()` returns `ok: False` for every morespace.ai URL. Two independent
causes, both real (the code itself is fine — `scrape_company('https://example.com')`
returns `ok: True`):

**a. Bot challenge.** morespace.ai is served by Hostinger CDN (`server: hcdn`), which
returns **403 + "Checking your browser before accessing"** to the httpx client while
letting curl through. This is a TLS/client-fingerprint check, so the deployed Render
server will hit it identically.

**b. The domain no longer hosts the brand.** `https://morespace.ai/` now serves
**"Janaki Ram Arts One Gram Jewellery"** — an e-commerce jewellery store. Zero
occurrences of *morespace*, *neopolis*, *kokapet*, *hyderabad*, *apartment* or *BHK*
in the HTML. All three URLs in `projects.py` are dead:

```
404  https://morespace.ai/httpsmorespaceailuxury-apartments-neopolis
404  https://morespace.ai/httpsmorespaceailuxury-residential-projects-hyderabad
404  https://morespace.ai/property-buying-contact
```

The dead Neopolis URL is nonetheless printed in the footer of `post-creative.png`.

## 4. Slide headlines are truncated mid-word

`studio.py:35` and the harness both apply `headline[:40]`. Slide 1 rendered
*"Discover the Pinnacle of Ultra-Luxury Li"* — cut mid-word, baked into the image.
The truncation happens before the prompt is written, so the model faithfully renders
the broken string.

## 5. Slide imagery is not India-anchored

`carousel-slide1.png` is plainly a New York interior — Central Park visible through
the window — on a Hyderabad property carousel. The per-slide prompt built in
`studio.py:36-39` carries `visual_direction` and `design_notes` but no locality, and
unlike the Brain path it attaches no style reference.

---

## Reproducing

```bash
export OPENROUTER_API_KEY=...   # text
export FAL_KEY=...              # images
python -m scripts.e2e_neopolis all
```

Roughly 5 minutes and ~24s per fal image. `--check` preflights without spending;
`--no-images` runs text only.

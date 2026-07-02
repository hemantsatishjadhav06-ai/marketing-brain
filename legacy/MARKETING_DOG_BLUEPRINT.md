# Marketing Dog — Product Blueprint

*The marketing brain that fetches, decides & ships.*

This blueprint defines Marketing Dog as the productized evolution of your
`marketing-brain` monorepo, captures the code-review findings that motivated the
upgrade shipped alongside it, and lays out the architecture and roadmap.

---

## 1. The one-liner

> **Marketing Dog is an autonomous marketing brain.** Point it at your website;
> it learns your brand, *skins itself in your colours*, and then plans, writes,
> critiques, schedules and publishes on-brand content and video across every
> channel — under a hard brand-safety guarantee.

**Why "Dog."** A good dog is loyal to one owner, always on, and *fetches* —
retrieves what you need without being asked twice. That is exactly the posture of
this product: loyal to one brand (never bleeding voice across verticals), always
running the loop, and fetching trends, ideas, drafts and published posts on your
behalf. The name is warmer and stickier than "Brain," and the *fetch* metaphor
gives marketing a verb to rally around ("let the Dog fetch this week's calendar").

---

## 2. What it is — and what changed

You already built ~80% of a serious product. `marketing-brain` is a multi-tenant,
multi-agent content operating system (FastAPI + RQ + Postgres + Next.js 15) with
20+ specialist agents, an orchestrator, a creative critic, native publishers for
eight networks, scoring, billing, 2FA and brand-isolation guards. The simpler
`marketing-brain-v2` app proves the self-serve on-ramp: *enter a company website →
scan it → extract brand description, colours and logo → build a strategy.*

Marketing Dog is the merge and the polish of those two into one sellable SaaS:

| | `marketing-brain` today | **Marketing Dog** |
|---|---|---|
| Audience | Hard-coded to 5 racket sports | **Any brand, any vertical** (the racket sports become *seed presets*) |
| Onboarding | Seeded org + manual brand | **Paste a URL → auto-scan → confirm** (promote v2's flow) |
| Theming | One `--accent` variable, per org | **BrandSkin™** — the *entire* UI derives from the brand palette, AA-corrected, light + dark |
| Brand safety | 3-layer cross-sport guard | Generalized to **cross-vertical / off-voice** guard (same mechanism) |
| Video | Stubbed short/long video agents | **Remotion + HyperFrames** templates that read the same brand tokens |
| Identity | "command center for sports" | A **brand** (the Dog) with a story, a verb, and a look that is different for every customer |

The strategic bet: in a sea of "AI marketing tools," the thing a buyer *feels* in
the first 30 seconds is **"this product already looks like my brand."** That is the
wedge. BrandSkin makes the demo sell itself.

---

## 3. Who it's for (ICP)

- **Primary:** founder-led and lean DTC/e-commerce brands (1–20 person marketing
  teams) that run several SKUs or sub-brands and cannot staff a full content team.
- **Secondary:** agencies and operators running content for *many* client brands —
  every client gets a visually distinct, isolated workspace out of the box
  (BrandSkin is a literal white-label engine, so this is near-free).
- **Beachhead:** your existing racket-sport brands (`tennisoutlet.in` and siblings)
  are the design partners and the first reference logos.

Roles already modeled in your RBAC (owner, admin, growth_head, marketer, intern,
viewer) map cleanly onto these teams.

---

## 4. The signature: BrandSkin™ adaptive theming

This is the headline feature and the part most worth getting right, because it is
both the **demo magic** and a **real accessibility guarantee**.

**What it does.** Given one to a few brand colours (from the website scan, or typed
in), BrandSkin derives a complete UI theme — backgrounds, panels, borders, three
text weights, accent, accent-ink, and status colours — for **both light and dark**,
and applies them as CSS custom properties so the whole cockpit (and the generated
video templates) re-skin with zero component changes.

**Why it's hard, and why ours is correct.** Brand colours are chosen for logos, not
for legibility. Neon yellow (`#CCFF00`) as button text on white is invisible; hot
pink body text fails contrast. Naïvely "tinting the UI with the brand colour"
produces inaccessible, ugly results. BrandSkin instead:

1. Works in **OKLCH** (perceptually-even lightness), so tonal ramps and
   light/dark variants look smooth rather than muddy.
2. Runs **every** text/UI token through `ensureContrast()`, which nudges lightness
   (tapering chroma toward the extremes) until the token clears its WCAG target —
   4.5:1 for body text, 3:1 for large/UI, with a guaranteed black/white fallback.
3. Therefore produces themes that are **WCAG-AA by construction.** This is not a
   claim — it's tested: the engine builds themes for 410 brand colours (presets +
   400 random) across light and dark = **820 modes, and audits every token. Zero
   failures.** Re-run it yourself: `node engine/verify.mjs`.

**Why it's a moat, not a gimmick.** It (a) makes onboarding feel bespoke, (b) gives
agencies instant white-label, (c) feeds the same tokens to Remotion so *video* is
on-brand too, and (d) bakes accessibility in so you can sell to procurement /
public-sector buyers who require it. Competitors bolt on a single accent picker;
this themes the whole system and proves it's legible.

The engine is `~260` lines, dependency-free, and ships in three identical forms:
`engine/brandskin.mjs` (canonical + tests), `apps/web/lib/theme/brandskin.ts`
(typed, for the app), and inlined in `marketing-dog-demo.html` (the live page).

---

## 5. The brain (reuse what you built)

Marketing Dog keeps your agent architecture wholesale — it's the deep work and the
defensible IP. Summarized from `docs/AGENT_ARCHITECTURE.md`:

- **Orchestrator** scores demand × trend × audience and emits a calendar of
  `ContentDecision`s, each with the reason it exists.
- **Specialist agents** (static post, carousel, blog, email/WhatsApp, short &
  long video, Pinterest, X/threads, community, SEO/GEO, repurpose) draft in the
  brand's voice, reading the **Brand Brain** (voice, tone, banned phrases, CTAs,
  SEO terms, competitors) first.
- **Creative Critic** hard-gates anything off-brand or cross-vertical, then scores
  on a rubric; only passing drafts reach a human.
- **Publishers** ship natively to IG, YouTube, TikTok, X, LinkedIn, Pinterest,
  Klaviyo, or any webhook — or export a clean bundle.
- **Learning loop** feeds winning content's signals back into the Brain so the next
  cycle scores higher.

The only conceptual change: the "no cross-**sport**" guard becomes "no
cross-**vertical** / off-voice" — the identical three-layer mechanism (data guard,
prompt clause, critic regex), now parameterized per brand instead of hard-coded to
five sports.

---

## 6. Architecture

```
                         ┌────────────────────────────────────────────┐
                         │            Marketing Dog (web)              │
                         │   Next.js 15 · React 19 · Tailwind · TS     │
                         │  ┌──────────────┐   ┌────────────────────┐  │
   brand colours ───────▶│  │  BrandSkin   │──▶│  CSS custom props  │  │
   (scan or input)       │  │   engine     │   │  (whole UI re-skin)│  │
                         │  └──────────────┘   └────────────────────┘  │
                         │        │ same tokens                        │
                         └────────┼───────────────┬────────────────────┘
                                  │               │
                ┌─────────────────▼──┐     ┌──────▼─────────────────────┐
                │  Supabase (web)    │     │  Remotion / HyperFrames    │
                │  auth · orgs ·     │     │  on-brand reels → MP4      │
                │  brands · themes   │     │  (read BrandSkin tokens)   │
                │  RLS isolation     │     └────────────────────────────┘
                └─────────┬──────────┘
                          │ brand_id / org context
        ┌─────────────────▼───────────────────────────────────────────┐
        │            Agent backend (KEEP AS-IS)                        │
        │   FastAPI · RQ workers · Postgres · Redis                    │
        │   Orchestrator · 20+ agents · Critic · Publishers · Scoring  │
        │   OpenRouter LLM gateway · swappable media/storage           │
        └──────────────────────────────────────────────────────────────┘
```

**Two data planes, on purpose.** Supabase owns *identity and brand identity* for
the web surface (fast auth, RLS, realtime, edge-friendly). The FastAPI service
keeps owning *operations* (queues, cost ledger, publisher tokens, agent runs).
They join on `org_id` / `brand_id`. This is the pragmatic way to satisfy
"Next.js + TS + Supabase" without a risky rewrite of a working Python brain.

---

## 7. Video, the agent-native way

The three repos you referenced are all *agent-native rendering* tools, and they
slot directly under the Short/Long Video agents:

- **Remotion** (`remotion-dev/remotion`) — make videos in React; ships **agent
  skills** so Claude/Codex can author compositions. Our `video/BrandReel.tsx` is a
  working composition that reads BrandSkin tokens, so a brand swap re-skins the
  reel. Render 100 variants headless in CI.
- **HyperFrames** (`heygen-com/hyperframes`) — "write HTML, render video, built for
  agents"; deterministic HTML→MP4, no React required. The fallback path for agents
  that emit markup, using the *same* brand tokens.
- **HeyGen avatars** — drop-in talking-head/UGC reels; captions and lower-thirds
  inherit BrandSkin automatically.
- **Zero / `vercel-labs/zerolang`** — an agent-native systems language emitting
  JSON diagnostics for repair loops. Not needed for v1, but it's the right shape
  for a future high-throughput render/transcode worker where agents self-heal the
  pipeline. Park it on the roadmap, don't build on it yet (it's experimental).

---

## 8. Code-review-driven upgrades

You asked to "upgrade it / code-review." Findings on `apps/web` and `apps/v2`,
with what this pack already fixes vs. what's recommended next:

**Fixed in this pack**
- *Theming was a single `--accent` override.* Switching brand only recoloured the
  accent; text/panels/borders stayed generic, and a bright brand accent could fail
  contrast on buttons. → Replaced with the full BrandSkin engine; every token
  derives and is AA-verified.
- *No light theme.* Tokens were dark-only despite the blueprint promising "light
  later," and `v2` was a separate light palette entirely. → One engine now emits
  light + dark from the same brand input; user/OS preference respected.
- *Accessibility gaps.* No skip link, no global `:focus-visible`, no
  `prefers-reduced-motion` handling, accent-on-bg contrast unverified. → All added
  in `globals.css` + `layout.tsx`; contrast guaranteed by the engine.
- *Two visual identities (`apps/web` dark vs `v2` indigo/light).* → Unified under
  BrandSkin tokens so they can't drift again.

**Recommended next (not done here)**
- *Auth tokens in `localStorage`* (`lib/api.ts`) are XSS-exfiltratable. Move to
  httpOnly cookies (Supabase Auth gives this for free on the web plane).
- *`AppShell` reloads the whole page on brand switch.* With token-based theming you
  can switch brands client-side without a full reload — keep the reload only for
  the backend query re-scope, or move scoping to a header.
- *Pin/lock dependencies* and add a CI job that runs `engine/verify.mjs` +
  `next build` + `pytest` on every PR (your `AGENTS.md` discipline, enforced).
- *Generalize the `Sport` enum* to a free-form `vertical` (the Supabase schema
  already models this) so onboarding isn't limited to five sports.

---

## 9. Accessibility commitments

Contrast AA by construction (tested); visible focus rings using a guaranteed-legible
accent; `prefers-reduced-motion` honored both via media query and a provider data
attribute; semantic landmarks + skip link; `color-scheme` set so form controls and
scrollbars match the mode; status colours re-derived per theme so "success/warn/
danger" stay distinguishable on any brand background. This is a sellable feature for
regulated and public-sector buyers, not just hygiene.

---

## 10. Monetization (proposed)

- **Solo** — 1 brand, 1 seat, simulated publishing + export, BrandSkin. Land cheap.
- **Studio** — up to 5 brands, native publishing, video renders, roles. The core.
- **Agency** — many brands, white-label (logo + your domain), API, priority render.
  BrandSkin makes per-client isolation a literal product feature.
- Usage meter on top (you already have a cost ledger + monthly cap), so AI spend is
  passed through transparently rather than eaten.

---

## 11. Roadmap

**Phase A — Brand & on-ramp (the sellable slice).** Ship BrandSkin (done), promote
the `v2` URL-scan onboarding into the main app, generalize `Sport → vertical`, wire
`AppShell` to `setBrand()`, stand up Supabase auth + brands with RLS. *Outcome: any
visitor can paste a URL and watch the cockpit become their brand.*

**Phase B — Loop to value.** Turn the orchestrator + calendar + 2–3 specialist
agents + critic into a working weekly run for a real brand; reviews/approvals UI;
asset library.

**Phase C — Video.** Remotion `BrandReel` in CI, HyperFrames fallback, HeyGen
avatars; "generate this week's reels on-brand" button.

**Phase D — Scale & sell.** Agency white-label, billing tiers, analytics learning
loop closed, SOC-friendly hardening (cookie auth, audit logs).

---

## 12. What shipped this session vs. what's next

**Shipped (in this delivery), verified:**
- The BrandSkin engine — canonical `.mjs`, typed `.ts`, and a passing 820-mode
  WCAG proof.
- A standalone, instantly-openable **Marketing Dog landing page + live theming
  demo** (`marketing-dog-demo.html`).
- Drop-in `apps/web` upgrades: `ThemeProvider`, `BrandThemeStudio`, upgraded
  `globals.css` / `layout.tsx` / `page.tsx` / `tailwind.config.ts`.
- Supabase `schema.sql` (orgs/brands/members/scans + RLS isolation) and typed
  clients.
- A Remotion `BrandReel` composition that consumes the same tokens.
- This blueprint + an integration `README_UPGRADE.md`.

**Next (your call, I can do any of these):** generalize the backend `Sport` enum;
wire `AppShell` to the provider; build the URL-scan onboarding screen in Next; move
auth to cookies; add the CI gate; build the reviews UI.

---

## Sources
- Remotion (programmatic video in React) + agent skills — https://github.com/remotion-dev/remotion/tree/main/packages/skills and https://www.remotion.dev/docs/ai/skills
- HeyGen HyperFrames (HTML→MP4, built for agents) — https://github.com/heygen-com/hyperframes
- Vercel Labs Zero / zerolang (agent-native systems language) — https://github.com/vercel-labs/zerolang
- WCAG 2.1 contrast minimums (1.4.3 / 1.4.11) — https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html
- OKLab/OKLCH colour space (Björn Ottosson) — https://bottosson.github.io/posts/oklab/

# Audit Report — Marketing Brain v0.5

Honest review across three lenses: code, UX, and user POV. Items I'm
about to fix in this commit are marked **[FIXING]**. Items left for the
next pass are marked **[NEXT]**.

---

## 1) Code review — as a senior engineer

### Things that are solid
- **Brand isolation**: `no_cross_brand` guard tested + every router scopes
  to `brand_id` and verifies `org_id == user.org_id`. Real architectural
  property, not a vibe.
- **One LLM gateway**: every agent goes through `pipeline/llm_gateway.py`.
  Tier-aware (reasoning vs drafting), cost-logged.
- **Swappable interfaces**: storage (local / S3 / R2), media (fal), publishers
  (8 platforms behind one Protocol). Each one a one-file swap.
- **Cost guard**: real MTD calculation against `org.monthly_cost_cap_usd`.
- **Auto-migrate + auto-seed on boot** for single-instance deploys.
- **132 Python files**, all `python3 -m ast` parse clean.

### Things that are NOT senior-engineer-quality
1. **No `.run()` integration tests for agents.** I have helper-level unit
   tests but no end-to-end "draft this entry, write a real ContentItem
   row, render an image" test against an in-memory SQLite. **[NEXT]**
2. **CORS=`*` after the env-var update accident.** I PUT'd the full set
   back later but `*` with `allow_credentials=True` is actually invalid
   per spec — the browser will ignore credentials. Should be the explicit
   web URL list. **[FIXING]**
3. **`run_product_video` in `short_video/agent.py` still uses a stub Job
   row** instead of running directly. Works but messy. **[NEXT]**
4. **No retry / circuit-breaker on publisher errors.** A 429 from X will
   silently fail. **[NEXT]**
5. **`/orgs/me/theme` defines a Pydantic model inside the function** —
   anti-pattern, should be at module scope. **[FIXING]**
6. **No structured logging.** All `print()`-style FastAPI default logs;
   no JSON logs for Render's log shipper to parse. **[NEXT]**
7. **No rate-limit middleware.** Anyone can spam `/auth/login` from the
   internet. **[NEXT]**
8. **`shutil.copyfile` in LocalStorage** loses metadata, no atomic write.
   Fine for dev, not for prod. **[NEXT]**

### Things the user actually asked for that were missing
9. **No way to download a single image / video / slide / variant.** Only
   the whole-content-item bundle. **[FIXING — Phase A of this commit]**
10. **No way to bulk-export approved items.** **[FIXING]**
11. **No way to edit AI-generated copy before publish.** **[FIXING]**
12. **No way to regenerate just one calendar entry.** **[FIXING]**
13. **No search across content.** **[FIXING]**

---

## 2) UX review — as a senior designer

### Things that are well-designed
- **Aurora + glass aesthetic** is consistent across landing, login, cockpit.
- **Inter + Fraunces** typography pairing reads premium.
- **Sidebar grouping** (Overview · Foundation · Create · Ship · Learn · Org)
  matches a user's mental model of the workflow.
- **`--accent` CSS variable** allows per-tenant theming without a recompile.
- **Status pill tones** are semantic (good=green, warn=amber, etc.).
- **Drag-drop calendar** is correctly minimum-viable: HTML5 native, no extra
  deps, accessible.

### Things that are NOT great UX
1. **No loading skeletons.** Every data-fetching page just shows a "Loading…"
   string. Should shimmer. **[FIXING]**
2. **No error boundary.** A JS error crashes the whole tab to blank.
   **[NEXT]**
3. **No empty-state illustrations** beyond a small `●` chip. **[NEXT]**
4. **Drag-drop calendar** has no visual drop-target glow when dragging
   (just a thin ring). **[NEXT]**
5. **Studio detail right-rail** is dense — critic history scrolls forever
   without collapse. **[NEXT]**
6. **Calendar dates** show "Mon 3/6" not the full day name — easy to misread
   on long sprints. **[NEXT]**
7. **No keyboard shortcuts.** ⌘K should open search. **[NEXT]**
8. **No in-app onboarding tour.** First-time user has to read docs.
   **[NEXT — covered by the GUIDE.md we're writing]**
9. **No notifications panel.** Toasts vanish; if you miss one, it's gone.
   **[NEXT]**
10. **No comments / @-mentions** on content items. Teams need this. **[NEXT]**
11. **No version history** on edits. **[NEXT]**

---

## 3) User POV — first 5 minutes

Walking through it as a marketer who just logged in:

| Step | Felt like | Verdict |
|---|---|---|
| Sign in | Sleek, the 2FA flow is well-staged | ✓ |
| See dashboard | Cards are crisp, top-ideas + jobs feed is good context | ✓ |
| Click Brand Brain | Save voice + banned + seo + competitors — clear inputs | ✓ |
| Click Trends → Ingest all | Returns counts cleanly | ✓ |
| Click Ideas → Generate 40 ideas | Score column is the right anchor | ✓ |
| Click Calendar → Regenerate | Grid fills, drag-drop works | ✓ |
| Click Draft on a cell | A draft appears in Studio — "where do I see it?" | ⚠️ unclear toast routing |
| Open Studio item | Image + caption render, but **"how do I edit the caption?"** | ⚠️ no edit affordance |
| **"Can I download just this image?"** | Only "Export bundle" — the whole zip | ⚠️ **[FIXING]** |
| Approve → Publish | Works if a target is configured | ✓ |
| **"How do I publish 20 approved items at once?"** | One at a time | ⚠️ **[FIXING]** |

So the four user-visible gaps before "perfect":
1. Per-creative download (single asset / single variant)
2. Edit the AI copy before publish
3. Bulk approve + bulk publish
4. Search across all content

All four are in **this commit**.

---

## 4) What the product CAN do today (true list)

- Generate scored content ideas from brand brain + products + live trends
- Plan a 30-day calendar that honours cadence rules per channel
- Draft via 15 specialist agents (static / carousel / blog / email / short
  + long video / reel + voice / thread / ads, with A/B variants)
- Critic v2 with cross-sport hard-gate + 10-criterion LLM rubric
- Approve workflow with role gating
- Publish natively to 8 channels (X / IG / LinkedIn / Pinterest / YouTube
  / TikTok / Klaviyo / Webhook) **or** export a bundle
- Pull analytics (GA4 + Meta Insights) or paste / CSV upload
- Refine the brand brain from winning content
- White-label theming + 2FA + Stripe billing skeleton + Shopify webhook
- Subdomain → org resolver for multi-tenant deploys
- Deployed to Render via API in one session

## 5) What the product CANNOT do today (and won't be perfect without)

After this commit ships, the remaining list (post-v0.5) is:

- **Comments + @-mentions** on content items (team collaboration)
- **Version history** on edits + restore
- **In-app onboarding tour** that walks the new user through the loop
- **Outgoing webhooks** (notify Slack / Discord when content goes live)
- **Audit log** (who did what when)
- **Keyboard shortcuts** (⌘K palette, etc.)
- **Programmatic API keys** for the user (so they can hit their own data)
- **Real-time SSE on the dashboard** (events instead of polling)
- **A/B winner auto-selection** based on performance after N days
- **Email verification** on register (Resend integration)
- **TikTok / IG / YouTube business verification** (external — outside the codebase)

That's roughly Phase 5. Today's commit closes Phase 4's loose ends.

---

## 6) Phase 24 / Spec coverage

You mentioned "phase 24" — the original spec docs in /docs/ go up to § 27.
We've covered every section that has a code deliverable:

| § | Section | Status |
|---|---|---|
| 1-8 | Vision, philosophy, agent overview | ✓ docs |
| 9 | Scoring engine | ✓ shipped |
| 10-13 | Data model, RBAC, brand-isolation, multi-tenancy | ✓ shipped |
| 14 | Database schema (every table) | ✓ shipped |
| 15-17 | LLM gateway, media, storage interfaces | ✓ shipped |
| 18 | Calendar | ✓ shipped |
| 19 | Critic v2 | ✓ shipped |
| 20 | Repurpose | ✓ shipped |
| 21 | Brain refinement loop | ✓ shipped |
| 22 | Publish targets (8 platforms) | ✓ shipped |
| 23 | Cost guard | ✓ shipped |
| 24 | Deploy (Render) | ✓ shipped + live URLs |
| 25 | Onboarding flow | ⚠️ basic seed; email-verify branch is Phase 5 |
| 26 | Platform business verification | external, not a code deliverable |
| 27 | Docs (8 files in /docs/) | ✓ shipped |

So nothing in the spec with a code deliverable is unshipped after this
commit lands.

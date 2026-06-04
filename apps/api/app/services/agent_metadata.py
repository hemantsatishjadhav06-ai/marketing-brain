"""Per-agent metadata — what each agent does + which inputs the user-facing
form should show. The /create UI reads this to render generically.

This is the agency-mode source of truth: a marketer can stand up a creative
for any agent without going through the calendar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


FieldKind = Literal["text", "textarea", "select", "number", "product", "switch"]


@dataclass
class AgentField:
    key: str
    label: str
    kind: FieldKind
    required: bool = False
    placeholder: str = ""
    help: str = ""
    options: list[str] = field(default_factory=list)
    default: str = ""


@dataclass
class AgentMeta:
    name: str
    title: str
    group: str                       # display group on the /create rail
    description: str
    default_platform: str
    default_content_type: str
    icon: str                        # lucide-react icon name
    accent: str                      # tailwind colour class
    fields: list[AgentField]


# ─── canonical platform & content options ────────────────────────────────────
PLATFORMS = ["instagram", "youtube", "tiktok", "x", "linkedin", "pinterest", "blog", "email", "whatsapp", "quora", "reddit", "meta_ads", "google_ads"]


def _common_fields(default_platform: str, default_content_type: str, *, allow_multi_product: bool = False) -> list[AgentField]:
    """Standard input fields for every agent. Some agents (carousel, ads,
    comparison blog) accept multi-product selection."""
    fields = [
        AgentField(
            "angle", "Angle / brief", "textarea", required=True,
            placeholder="e.g. How to choose grip size in 60 seconds",
            help="The thesis of the post. Be specific — vague briefs make vague drafts.",
        ),
        AgentField(
            "platform", "Platform", "select", required=True,
            options=PLATFORMS, default=default_platform,
        ),
        AgentField(
            "content_type", "Content type", "text", required=True,
            default=default_content_type,
        ),
        AgentField(
            "category_id", "Category (Magento) — filters products below", "category",
            help="Pick a Magento category to narrow the product dropdown. Optional.",
        ),
    ]
    if allow_multi_product:
        fields.append(AgentField(
            "product_ids", "Featured products (1-5, for comparison)", "product_multi",
            help="Pick up to 5 SKUs. Carousel / Ads / Blog will compare them side-by-side; other agents use the first.",
        ))
    else:
        fields.append(AgentField(
            "product_id", "Featured product (optional)", "product",
            help="Attach a product to ground the AI's claims in real specs / price.",
        ))
    return fields


# Each override block is read by the agent at LLM-call time.
OVERRIDE_FIELDS = [
    AgentField("override_tone", "Tone override (optional)", "text",
               placeholder="e.g. punchy, sceptical, expert",
               help="Merges with brand voice. Leave blank to use the brand default."),
    AgentField("override_length", "Length", "select",
               options=["short", "medium", "long"], default="medium",
               help="Maps to max_tokens. Long ≈ 2× short."),
    AgentField("override_model", "Model tier", "select",
               options=["auto", "drafting", "reasoning"], default="auto",
               help="Auto picks based on agent. Reasoning = stronger model, higher cost."),
    AgentField("override_custom_instructions", "Custom instructions (optional)", "textarea",
               placeholder="e.g. End with a poll. Lead with a stat.",
               help="Appended verbatim to the agent's system prompt."),
]


AGENT_METADATA: dict[str, AgentMeta] = {
    # ── Visual ───────────────────────────────────────────────────────────────
    "static_post": AgentMeta(
        name="static_post", title="Static Post", group="Visual",
        description="Single image + caption + hashtags + CTA. Pillow render over your brand accent. Ships A + B variants.",
        default_platform="instagram", default_content_type="static_post",
        icon="Image", accent="text-pink-300",
        fields=_common_fields("instagram", "static_post") + OVERRIDE_FIELDS,
    ),
    "carousel": AgentMeta(
        name="carousel", title="Carousel", group="Visual",
        description="Multi-slide IG / LinkedIn carousel. Default 6 slides — page counter, hook, body, swipe to CTA. Pick 2-5 products for a side-by-side comparison carousel.",
        default_platform="instagram", default_content_type="carousel",
        icon="Layers", accent="text-pink-300",
        fields=_common_fields("instagram", "carousel", allow_multi_product=True) + [
            AgentField("slide_count", "Slide count", "number", default="6",
                       help="3–10 supported. 6 is the sweet spot for IG."),
        ] + OVERRIDE_FIELDS,
    ),
    "pinterest": AgentMeta(
        name="pinterest", title="Pinterest Pin", group="Visual",
        description="Vertical 1000×1500 pin with keyword-rich title + description + alt text + board suggestion.",
        default_platform="pinterest", default_content_type="pin",
        icon="Pin", accent="text-rose-300",
        fields=_common_fields("pinterest", "pin") + OVERRIDE_FIELDS,
    ),
    # ── Video ────────────────────────────────────────────────────────────────
    "short_video": AgentMeta(
        name="short_video", title="Short Video (product)", group="Video",
        description="V1 product-video pipeline. 9:16, ~25-35s, voiceover + on-screen text. Requires a featured product.",
        default_platform="instagram", default_content_type="reel",
        icon="Video", accent="text-fuchsia-300",
        fields=_common_fields("instagram", "reel") + OVERRIDE_FIELDS,
    ),
    "reel_voice": AgentMeta(
        name="reel_voice", title="Reel + Voice", group="Video",
        description="9:16 vertical reel — pattern-break hook in first 2s + 3-5 beats + CTA. TTS voiceover anchored to scene 0.",
        default_platform="instagram", default_content_type="reel",
        icon="Mic", accent="text-fuchsia-300",
        fields=_common_fields("instagram", "reel") + OVERRIDE_FIELDS,
    ),
    "long_video": AgentMeta(
        name="long_video", title="Long Video (chapters)", group="Video",
        description="90-180s chaptered video: intro + 4-6 chapters with timestamps + outro CTA. Exports paste-ready YouTube chapter timestamps.",
        default_platform="youtube", default_content_type="youtube_long",
        icon="Film", accent="text-red-300",
        fields=_common_fields("youtube", "youtube_long") + OVERRIDE_FIELDS,
    ),
    # ── Long-form ────────────────────────────────────────────────────────────
    "blog": AgentMeta(
        name="blog", title="Blog Post", group="Long-form",
        description="700-1000 word SEO post: title + meta + 4-6 sections + CTA. Ships A + B title variants. Pick 2-5 products for a comparison blog.",
        default_platform="blog", default_content_type="blog",
        icon="FileText", accent="text-amber-300",
        fields=_common_fields("blog", "blog", allow_multi_product=True) + OVERRIDE_FIELDS,
    ),
    "seo_geo": AgentMeta(
        name="seo_geo", title="SEO + GEO Head", group="Long-form",
        description="Title + slug + meta + headers + schema.org JSON-LD + GEO answer block + queries. So ChatGPT / Gemini / Perplexity surface you.",
        default_platform="blog", default_content_type="seo_geo",
        icon="Search", accent="text-amber-300",
        fields=_common_fields("blog", "seo_geo") + OVERRIDE_FIELDS,
    ),
    "community": AgentMeta(
        name="community", title="Community Answer", group="Long-form",
        description="Quora / Reddit / FAQ long-form answer (250-600 words). Expertise-first, links back to brand naturally.",
        default_platform="quora", default_content_type="answer",
        icon="MessagesSquare", accent="text-orange-300",
        fields=_common_fields("quora", "answer") + OVERRIDE_FIELDS,
    ),
    # ── Social (short-form text) ─────────────────────────────────────────────
    "x_post": AgentMeta(
        name="x_post", title="X / Twitter Post", group="Social",
        description="Single tweet ≤ 270 chars. Optional poll. Pattern: trend reaction · drop · fact · reply.",
        default_platform="x", default_content_type="post",
        icon="Twitter", accent="text-zinc-300",
        fields=_common_fields("x", "post") + OVERRIDE_FIELDS,
    ),
    "thread_post": AgentMeta(
        name="thread_post", title="Thread (X / LinkedIn)", group="Social",
        description="5-9 connected posts with HOOK + body + CTA flags. X publisher chains them as reply tweets.",
        default_platform="x", default_content_type="thread",
        icon="ListOrdered", accent="text-zinc-300",
        fields=_common_fields("x", "thread") + OVERRIDE_FIELDS,
    ),
    # ── Paid ─────────────────────────────────────────────────────────────────
    "ads": AgentMeta(
        name="ads", title="Ads (Meta / Google)", group="Paid",
        description="3 A/B/C variants per item. Char-budgeted per format. Pick multiple products to spin a comparison ad set.",
        default_platform="meta_ads", default_content_type="ad",
        icon="Megaphone", accent="text-violet-300",
        fields=_common_fields("meta_ads", "ad", allow_multi_product=True) + OVERRIDE_FIELDS,
    ),
    # ── Direct ───────────────────────────────────────────────────────────────
    "email": AgentMeta(
        name="email", title="Email Broadcast", group="Direct",
        description="Subject + preheader + blocks + CTA. Ships A + B subject-line variants for CTR testing.",
        default_platform="email", default_content_type="email",
        icon="Mail", accent="text-sky-300",
        fields=_common_fields("email", "email") + OVERRIDE_FIELDS,
    ),
    "whatsapp": AgentMeta(
        name="whatsapp", title="WhatsApp Template", group="Direct",
        description="WA Business message template ≤ 1024 chars. Header + body + footer + URL/quick-reply buttons. Opt-in only.",
        default_platform="whatsapp", default_content_type="broadcast",
        icon="MessageCircle", accent="text-emerald-300",
        fields=_common_fields("whatsapp", "broadcast") + OVERRIDE_FIELDS,
    ),
}


GROUP_ORDER = ["Visual", "Video", "Long-form", "Social", "Paid", "Direct"]


def list_metadata() -> list[dict]:
    """Serializable list ordered by group, then by title."""
    out = []
    for g in GROUP_ORDER:
        for name, m in AGENT_METADATA.items():
            if m.group != g:
                continue
            out.append({
                "name": m.name,
                "title": m.title,
                "group": m.group,
                "description": m.description,
                "default_platform": m.default_platform,
                "default_content_type": m.default_content_type,
                "icon": m.icon,
                "accent": m.accent,
                "fields": [
                    {
                        "key": f.key, "label": f.label, "kind": f.kind,
                        "required": f.required, "placeholder": f.placeholder,
                        "help": f.help, "options": f.options, "default": f.default,
                    } for f in m.fields
                ],
            })
    return out

"""Pydantic request models."""
from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    password: str


class UserIn(BaseModel):
    email: str
    password: str
    role: str = "client"
    brand_id: str = ""


class BrandIn(BaseModel):
    name: str
    website: str
    socials: dict = {}
    group: str = ""


class SetupIn(BaseModel):
    channels: list[str]
    goals: list[str] = []
    cadence: str = "4 posts/week"
    language: str = "English"
    profile_overrides: dict = {}


class KitIn(BaseModel):
    colors: list[str] = []
    style: str = ""


class IdeasIn(BaseModel):
    channels: list[str] = []
    count: int = 6
    # advanced customization (all optional — defaults keep the one-click flow)
    formats: list[str] = []
    funnel_stage: str = ""
    pillar: str = ""
    topic: str = ""
    tone: str = ""
    instructions: str = ""


class ChatIn(BaseModel):
    message: str
    history: list = []


class CalendarIn(BaseModel):
    days: int = 30
    start: str | None = None


class CreativeIn(BaseModel):
    idea_id: str


class ImageIn(BaseModel):
    creative_id: str
    prompt_override: str | None = None


class PublishIn(BaseModel):
    creative_id: str
    channel: str | None = None
    scheduled_for: str | None = None
    mode: str = "simulated"


class MetricsIn(BaseModel):
    channel: str
    post_ref: str = ""
    metrics: dict


class ConnectorIn(BaseModel):
    platform: str
    credentials: dict


class ScrapeImportIn(BaseModel):
    scrape: dict


class RepurposeIn(BaseModel):
    source: str
    count: int = 5
    platform: str = "instagram"


class SeoIn(BaseModel):
    topic: str
    platform: str = "youtube"


class ScoreIn(BaseModel):
    kind: str = "idea"  # idea|creative
    id: str


class CompetitorIn(BaseModel):
    url: str
    name: str = ""


class AutopilotIn(BaseModel):
    ideas_per_channel: int = 4
    creatives_per_channel: int = 1
    generate_images: bool = False
    calendar_days: int = 30


class BlogIn(BaseModel):
    topic: str
    keyword: str = ""


class EmailIn(BaseModel):
    etype: str = "newsletter"   # newsletter|promo|welcome|nurture|winback|launch
    topic: str = ""
    email_count: int = 1        # >1 builds a sequence


class PlaybookIn(BaseModel):
    pass


class TrendsIn(BaseModel):
    keywords: list[str] = []
    live: bool = True  # scrape real signals via Apify when a token is configured


class ReelStudioIn(BaseModel):
    prompt: str = ""           # describe the video idea (Idea-to-Video)
    creative_id: str = ""      # or start from an existing reel creative (Script-to-Video)
    style: str = "cinematic"
    voice: str = "alloy"
    scenes: int = 4


class ApprovalIn(BaseModel):
    state: str  # approved|changes_requested
    comment: str = ""


class PlaybookRunIn(BaseModel):
    system: str
    prompt: str
    inputs: dict | None = None


class StudioMoodIn(BaseModel):
    topic: str = ""
    format: str = "post"


class StudioImageIn(BaseModel):
    prompt: str
    reference: str | None = None


class StudioCarouselIn(BaseModel):
    prompts: list = []


class StudioSaveIn(BaseModel):
    title: str = "Untitled post"
    caption: str = ""
    asset_path: str | None = None
    format: str = "post"


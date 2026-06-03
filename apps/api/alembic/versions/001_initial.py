"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-03
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _ts():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    # orgs
    op.create_table(
        "orgs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("monthly_cost_cap_usd", sa.Numeric(10, 2), nullable=False, server_default="200"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        *_ts(),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.create_index("ix_users_org_id", "users", ["org_id"])

    # api_keys
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("key_encrypted", sa.String(2048), nullable=False),
        sa.Column("label", sa.String(128), nullable=False, server_default="default"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_ts(),
        sa.UniqueConstraint("org_id", "provider", "label", name="uq_api_key"),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])

    # brands
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sport", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("website_url", sa.String(255), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("accent_color", sa.String(16), nullable=False, server_default="#CCFF00"),
        *_ts(),
        sa.UniqueConstraint("org_id", "sport", name="uq_brand_sport"),
    )
    op.create_index("ix_brands_org_id", "brands", ["org_id"])

    # brand_brain
    op.create_table(
        "brand_brain",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("voice", sa.String(2000), nullable=False, server_default=""),
        sa.Column("tone", sa.String(2000), nullable=False, server_default=""),
        sa.Column("banned_phrases", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("visual_rules", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("cta_rules", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("platform_rules", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("seo_keywords", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("geo_prompts", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("competitors", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("content_templates", postgresql.JSONB, nullable=False, server_default="{}"),
        *_ts(),
    )

    # audiences
    op.create_table(
        "audiences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("profile", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("affinity_scores", postgresql.JSONB, nullable=False, server_default="{}"),
        *_ts(),
    )
    op.create_index("ix_audiences_brand_id", "audiences", ["brand_id"])

    # products
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(8000), nullable=False, server_default=""),
        sa.Column("category", sa.String(120), nullable=False, server_default=""),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("margin", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("image_urls", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("is_new", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_bestseller", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_dead_stock", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_discounted", sa.Boolean, nullable=False, server_default=sa.false()),
        *_ts(),
        sa.UniqueConstraint("brand_id", "sku", name="uq_product_sku_per_brand"),
    )
    op.create_index("ix_products_brand_id", "products", ["brand_id"])

    # inventory_snapshots
    op.create_table(
        "inventory_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_qty", sa.Integer, nullable=False, server_default="0"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        *_ts(),
    )
    op.create_index("ix_inventory_snapshots_product_id", "inventory_snapshots", ["product_id"])

    # trends
    op.create_table(
        "trends",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("keyword", sa.String(255), nullable=False, server_default=""),
        sa.Column("signal_strength", sa.Numeric(6, 3), nullable=False, server_default="0"),
        sa.Column("slope", sa.Numeric(6, 3), nullable=False, server_default="0"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ttl_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
    )
    op.create_index("ix_trends_brand_id", "trends", ["brand_id"])

    # scoring_runs
    op.create_table(
        "scoring_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score_type", sa.String(32), nullable=False),
        sa.Column("total", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("breakdown", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("inputs", postgresql.JSONB, nullable=False, server_default="{}"),
        *_ts(),
    )
    op.create_index("ix_scoring_runs_brand_id", "scoring_runs", ["brand_id"])
    op.create_index("ix_scoring_runs_subject_id", "scoring_runs", ["subject_id"])

    # content_ideas
    op.create_table(
        "content_ideas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("angle", sa.String(255), nullable=False, server_default=""),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("product_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("score", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(2000), nullable=False, server_default=""),
        sa.Column("source", sa.String(16), nullable=False, server_default="ai"),
        sa.Column("status", sa.String(32), nullable=False, server_default="idea"),
        *_ts(),
    )
    op.create_index("ix_content_ideas_brand_id", "content_ideas", ["brand_id"])

    # content_items
    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idea_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_ideas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("angle", sa.String(255), nullable=False, server_default=""),
        sa.Column("product_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="idea"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(2000), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(16), nullable=False, server_default="ai"),
        sa.Column("agent_name", sa.String(64), nullable=False, server_default=""),
        *_ts(),
    )
    op.create_index("ix_content_items_brand_id", "content_items", ["brand_id"])
    op.create_index("ix_content_items_status", "content_items", ["status"])

    # content_variants
    op.create_table(
        "content_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        *_ts(),
    )
    op.create_index("ix_content_variants_content_item_id", "content_variants", ["content_item_id"])

    # critic_reviews
    op.create_table(
        "critic_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scores", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("weighted_total", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("blocking_issues", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("fixes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("reviewer", sa.String(16), nullable=False, server_default="ai"),
        *_ts(),
    )
    op.create_index("ix_critic_reviews_content_item_id", "critic_reviews", ["content_item_id"])

    # calendar_entries
    op.create_table(
        "calendar_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("product_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("angle", sa.String(255), nullable=False, server_default=""),
        sa.Column("agent_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("score", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(2000), nullable=False, server_default=""),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="idea"),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_calendar_entries_brand_id", "calendar_entries", ["brand_id"])
    op.create_index("ix_calendar_entries_date", "calendar_entries", ["date"])

    # jobs
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("result", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("error", sa.String(4000), nullable=False, server_default=""),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_jobs_org_id", "jobs", ["org_id"])
    op.create_index("ix_jobs_brand_id", "jobs", ["brand_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_type", "jobs", ["type"])

    # assets
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("mime", sa.String(120), nullable=False, server_default=""),
        sa.Column("width", sa.Integer, nullable=False, server_default="0"),
        sa.Column("height", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duration_s", sa.Numeric(8, 2), nullable=False, server_default="0"),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default="{}"),
        *_ts(),
    )
    op.create_index("ix_assets_brand_id", "assets", ["brand_id"])

    # publish_targets
    op.create_table(
        "publish_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False, server_default="export"),
        sa.Column("credentials_ref", sa.String(255), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        *_ts(),
    )
    op.create_index("ix_publish_targets_brand_id", "publish_targets", ["brand_id"])

    # publish_logs
    op.create_table(
        "publish_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("response", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        *_ts(),
    )
    op.create_index("ix_publish_logs_content_item_id", "publish_logs", ["content_item_id"])

    # analytics_events
    op.create_table(
        "analytics_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform", sa.String(64), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("value", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        *_ts(),
    )
    op.create_index("ix_analytics_events_brand_id", "analytics_events", ["brand_id"])

    # content_performance
    op.create_table(
        "content_performance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("impressions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("engagements", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("conversions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("score", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("period", sa.String(16), nullable=False, server_default="rolling_7d"),
        *_ts(),
    )
    op.create_index("ix_content_performance_content_item_id", "content_performance", ["content_item_id"])

    # cost_ledger
    op.create_table(
        "cost_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        *_ts(),
    )
    op.create_index("ix_cost_ledger_org_id", "cost_ledger", ["org_id"])
    op.create_index("ix_cost_ledger_brand_id", "cost_ledger", ["brand_id"])
    op.create_index("ix_cost_ledger_job_id", "cost_ledger", ["job_id"])


def downgrade() -> None:
    for t in [
        "cost_ledger", "content_performance", "analytics_events", "publish_logs",
        "publish_targets", "assets", "jobs", "calendar_entries", "critic_reviews",
        "content_variants", "content_items", "content_ideas", "scoring_runs", "trends",
        "inventory_snapshots", "products", "audiences", "brand_brain", "brands",
        "api_keys", "users", "orgs",
    ]:
        op.drop_table(t)

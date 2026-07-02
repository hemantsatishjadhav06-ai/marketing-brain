"""Central settings (env-driven)."""
import os


class Settings:
    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")
    openrouter_model = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    openrouter_image_model = os.environ.get("OPENROUTER_IMAGE_MODEL", "openai/gpt-image-1")
    db_path = os.environ.get("DB_PATH", "data/marketing_brain.db")
    workspaces_root = os.environ.get("WORKSPACES_ROOT", "workspaces/")
    public_base_url = os.environ.get("PUBLIC_BASE_URL", "")


settings = Settings()

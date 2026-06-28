"""Backend environment configuration.

Reads DATABASE_URL and AGENT_PLATFORM_SECRET_KEY (Fernet master key, research R4).
"""

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    database_url: str
    secret_key: str  # Fernet master key for API-key encryption at rest (R4)
    skills_dir: str
    browser_profile_root: str

    def __init__(self) -> None:
        self.database_url = os.environ.get(
            "DATABASE_URL", "sqlite:///./agent.db"
        )
        self.secret_key = os.environ.get("AGENT_PLATFORM_SECRET_KEY", "")
        self.skills_dir = os.environ.get("SKILLS_DIR", "skills")
        self.browser_profile_root = os.environ.get(
            "BROWSER_PROFILE_ROOT", "/tmp/agent-platform-profiles"
        )
        if not self.secret_key:
            # ponytail: dev-only fallback so local runs don't crash; prod MUST set env.
            self.secret_key = "dev-only-insecure-key-do-not-use-in-prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Settings read from environment variables (and a .env file for local work)."""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./leadflow.db"
    # Empty means the admin area is switched off, not open.
    admin_password: str = ""
    # Signs admin tokens. A random value per process is fine for one server.
    secret: str = ""
    anthropic_api_key: str = ""
    model: str = "claude-haiku-5-5"
    # Hard ceiling on Claude calls per day so a public demo cannot run up a bill.
    ai_daily_limit: int = 200
    notify_webhook_url: str = ""
    notify_attempts: int = 4
    notify_backoff_seconds: float = 1.0
    clinic_name: str = "Brightside Dental & Physio"
    clinic_phone: str = "01234 567890"
    allowed_origins: tuple[str, ...] = ("*",)
    trust_proxy: bool = False
    chat_per_minute: int = 20
    leads_per_hour: int = 6
    login_per_minute: int = 5
    max_messages_per_conversation: int = 60
    seed_demo: bool = False


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv()
        env = os.environ
    d = Settings()
    origins = tuple(o.strip() for o in env.get("LEADFLOW_ALLOWED_ORIGINS", "").split(",") if o.strip())
    return Settings(
        database_url=env.get("DATABASE_URL", d.database_url).strip() or d.database_url,
        admin_password=env.get("LEADFLOW_ADMIN_PASSWORD", "").strip(),
        secret=env.get("LEADFLOW_SECRET", "").strip() or secrets.token_urlsafe(32),
        anthropic_api_key=env.get("ANTHROPIC_API_KEY", "").strip(),
        model=env.get("LEADFLOW_MODEL", d.model).strip() or d.model,
        ai_daily_limit=_int(env, "LEADFLOW_AI_DAILY_LIMIT", d.ai_daily_limit),
        notify_webhook_url=env.get("LEADFLOW_NOTIFY_WEBHOOK_URL", "").strip(),
        notify_attempts=max(1, _int(env, "LEADFLOW_NOTIFY_ATTEMPTS", d.notify_attempts)),
        clinic_name=env.get("LEADFLOW_CLINIC_NAME", d.clinic_name).strip() or d.clinic_name,
        clinic_phone=env.get("LEADFLOW_CLINIC_PHONE", d.clinic_phone).strip() or d.clinic_phone,
        allowed_origins=origins or d.allowed_origins,
        trust_proxy=env.get("LEADFLOW_TRUST_PROXY", "").strip().lower() in {"1", "true", "yes"},
        chat_per_minute=_int(env, "LEADFLOW_CHAT_PER_MINUTE", d.chat_per_minute),
        leads_per_hour=_int(env, "LEADFLOW_LEADS_PER_HOUR", d.leads_per_hour),
        seed_demo=env.get("LEADFLOW_SEED_DEMO", "").strip().lower() in {"1", "true", "yes"},
    )

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv()


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _integer(value: str | None, default: int) -> int:
    if not value:
        return default

    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    telegram_allowed_chat_id: str | None
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    imap_folder: str
    email_poll_seconds: int
    email_mark_seen: bool
    openai_api_key: str
    openai_model: str
    default_weather_location: str
    agents_db_path: Path
    worker_poll_seconds: int
    daily_report_hour: int | None

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def has_email(self) -> bool:
        return bool(self.imap_host and self.imap_user and self.imap_password)

    @property
    def has_llm(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)

    def ensure_storage(self) -> None:
        self.agents_db_path.parent.mkdir(parents=True, exist_ok=True)


def format_config_status(config: AppConfig) -> str:
    def line(label: str, ready: bool, detail: str) -> str:
        status = "ready" if ready else "missing"
        return f"- {label}: {status} ({detail})"

    report_detail = (
        f"daily at {config.daily_report_hour}:00 UTC"
        if config.daily_report_hour is not None
        else "optional; set DAILY_REPORT_HOUR=0-23 in .env"
    )

    return "\n".join(
        [
            "Configuration status:",
            line(
                "Telegram bot",
                config.has_telegram,
                "set TELEGRAM_BOT_TOKEN in .env",
            ),
            line(
                "Telegram chat lock",
                bool(config.telegram_allowed_chat_id),
                "optional; set TELEGRAM_ALLOWED_CHAT_ID to restrict access",
            ),
            line(
                "Email monitoring",
                config.has_email,
                "set IMAP_HOST, IMAP_USER, and IMAP_PASSWORD in .env",
            ),
            line(
                "OpenAI reasoning",
                config.has_llm,
                "set OPENAI_API_KEY; OPENAI_MODEL defaults to gpt-4.1-mini",
            ),
            line(
                "Default weather location",
                bool(config.default_weather_location),
                "optional; set WEATHER_DEFAULT_LOCATION in .env",
            ),
            f"- Daily report: {report_detail}",
            f"- Database: {config.agents_db_path}",
            f"- Worker poll: {config.worker_poll_seconds}s",
            f"- Email poll: {config.email_poll_seconds}s",
            "",
            "Diagnostics:",
            "- personal-agents setup-telegram",
            "- personal-agents chat",
            "- personal-agents test-email",
            "- personal-agents test-llm",
        ]
    )


def load_config() -> AppConfig:
    _load_dotenv_if_available()

    db_path = Path(os.getenv("AGENTS_DB_PATH", "data/agents.sqlite3"))
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "").strip()
    if openai_api_key and not openai_model:
        openai_model = "gpt-4.1-mini"

    daily_report_raw = os.getenv("DAILY_REPORT_HOUR", "").strip()
    daily_report_hour: int | None
    if not daily_report_raw:
        daily_report_hour = None
    else:
        hour = _integer(daily_report_raw, -1)
        daily_report_hour = hour if 0 <= hour <= 23 else None

    return AppConfig(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_allowed_chat_id=os.getenv("TELEGRAM_ALLOWED_CHAT_ID", "").strip() or None,
        imap_host=os.getenv("IMAP_HOST", "").strip(),
        imap_port=_integer(os.getenv("IMAP_PORT"), 993),
        imap_user=os.getenv("IMAP_USER", "").strip(),
        imap_password=os.getenv("IMAP_PASSWORD", "").strip(),
        imap_folder=os.getenv("IMAP_FOLDER", "INBOX").strip() or "INBOX",
        email_poll_seconds=_integer(os.getenv("EMAIL_POLL_SECONDS"), 120),
        email_mark_seen=_truthy(os.getenv("EMAIL_MARK_SEEN"), False),
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        default_weather_location=os.getenv("WEATHER_DEFAULT_LOCATION", "").strip(),
        agents_db_path=db_path,
        worker_poll_seconds=_integer(os.getenv("WORKER_POLL_SECONDS"), 3),
        daily_report_hour=daily_report_hour,
    )

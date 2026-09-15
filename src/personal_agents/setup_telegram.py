from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from personal_agents.env_file import project_env_path, upsert_env_values


def setup_telegram_interactive(*, env_path: Path | None = None) -> None:
    path = env_path or project_env_path()

    print(
        "\n".join(
            [
                "Telegram setup",
                "--------------",
                "1. Open Telegram and message @BotFather",
                "2. Send /newbot (or /token if you already have a bot)",
                "3. Copy the bot token BotFather gives you",
                "4. Optional but recommended: message @userinfobot to get your chat id",
                "",
                f"Values will be saved to: {path.resolve()}",
                "",
            ]
        )
    )

    token = input("Paste TELEGRAM_BOT_TOKEN (or press Enter to cancel): ").strip()
    if not token:
        print("Cancelled. No changes were written.")
        return

    if ":" not in token or len(token) < 30:
        print("That does not look like a Telegram bot token. Example shape: 123456:AA...")
        confirm = input("Save it anyway? [y/N]: ").strip().lower()
        if confirm not in {"y", "yes"}:
            print("Cancelled. No changes were written.")
            return

    ok, detail = validate_bot_token(token)
    if ok:
        print(f"Token looks valid. Bot: {detail}")
    else:
        print(f"Warning: could not verify token with Telegram ({detail}).")
        confirm = input("Save it anyway? [y/N]: ").strip().lower()
        if confirm not in {"y", "yes"}:
            print("Cancelled. No changes were written.")
            return

    chat_id = input(
        "Paste TELEGRAM_ALLOWED_CHAT_ID (recommended; Enter to leave empty): "
    ).strip()

    upsert_env_values(
        path,
        {
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_ALLOWED_CHAT_ID": chat_id,
        },
    )

    print(
        "\n".join(
            [
                "",
                f"Saved Telegram settings to {path.resolve()}",
                "Next:",
                "  python -m personal_agents.cli check-config",
                "  python -m personal_agents.cli run-bot",
                "",
                "Until Telegram is ready, you can use local chat:",
                "  python -m personal_agents.cli chat",
            ]
        )
    )


def validate_bot_token(token: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{token}/getMe"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - surface any network/parse issue
        return False, str(exc)

    if not payload.get("ok"):
        return False, str(payload.get("description") or "Telegram rejected the token")

    result = payload.get("result") or {}
    username = str(result.get("username") or result.get("first_name") or "unknown")
    if username.startswith("@"):
        return True, username
    if result.get("username"):
        return True, f"@{username}"
    return True, username

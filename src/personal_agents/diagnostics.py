from __future__ import annotations

import imaplib

from personal_agents.config import AppConfig
from personal_agents.llm import LLMClient


def test_email_connection(config: AppConfig) -> str:
    if not config.has_email:
        return (
            "Email is not configured.\n"
            "Set IMAP_HOST, IMAP_USER, and IMAP_PASSWORD in .env.\n"
            "For Gmail: enable 2FA, create an app password, and use imap.gmail.com."
        )

    mailbox = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
    try:
        mailbox.login(config.imap_user, config.imap_password)
        status, data = mailbox.select(config.imap_folder)
        if status != "OK":
            return f"Connected, but could not open folder {config.imap_folder}: {status}"

        message_count = data[0].decode("ascii", errors="ignore") if data else "unknown"
        status, unseen = mailbox.search(None, "UNSEEN")
        unseen_count = len(unseen[0].split()) if status == "OK" and unseen and unseen[0] else 0

        return (
            f"Email connection OK.\n"
            f"Account: {config.imap_user}\n"
            f"Folder: {config.imap_folder}\n"
            f"Messages: {message_count}\n"
            f"Unread: {unseen_count}"
        )
    except imaplib.IMAP4.error as exc:
        return (
            f"Email login failed: {exc}\n"
            "For Gmail, use an app password instead of your normal password."
        )
    except OSError as exc:
        return f"Could not reach mail server {config.imap_host}:{config.imap_port}: {exc}"
    finally:
        try:
            mailbox.logout()
        except imaplib.IMAP4.error:
            pass


def test_llm_connection(config: AppConfig) -> str:
    if not config.has_llm:
        return (
            "OpenAI is not configured.\n"
            "Set OPENAI_API_KEY and OPENAI_MODEL in .env."
        )

    client = LLMClient(config)
    reply = client.complete(
        system="Reply with exactly: Personal agents online.",
        user="Health check.",
    )
    if not reply:
        return "OpenAI request failed. Check your API key, model name, and billing."

    return f"OpenAI connection OK.\nModel: {config.openai_model}\nReply: {reply[:120]}"

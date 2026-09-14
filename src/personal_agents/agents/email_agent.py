from __future__ import annotations

import asyncio
import email
import imaplib
import re
import time
from email.header import decode_header
from email.message import Message
from typing import Any

from personal_agents.agents.base import BaseAgent
from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig
from personal_agents.models import AgentName, MessageKind, Task


ASSIGNMENT_KEYWORDS = (
    "assignment",
    "homework",
    "coursework",
    "task",
    "deadline",
    "due date",
    "submit",
    "submission",
    "project",
    "action required",
    "to do",
    "todo",
    "deliverable",
)


class EmailAgent(BaseAgent):
    def __init__(self, *, bus: AgentBus, config: AppConfig) -> None:
        super().__init__(name=AgentName.EMAIL.value, bus=bus, config=config)

    async def run_forever(self) -> None:
        last_scan = 0.0
        while True:
            await self.run_once()

            if time.monotonic() - last_scan >= self.config.email_poll_seconds:
                findings = self.scan_inbox()
                self.notify_findings(findings)
                last_scan = time.monotonic()

            await asyncio.sleep(self.config.worker_poll_seconds)

    async def handle_task(self, task: Task) -> dict[str, Any]:
        if task.kind != "check_email_now":
            return {
                "title": "Email Agent",
                "summary": f"I do not know how to handle task type: {task.kind}",
            }

        if not self.config.has_email:
            return {
                "title": "Email Agent",
                "summary": "Email settings are not configured yet. Fill IMAP_HOST, IMAP_USER, and IMAP_PASSWORD in .env.",
            }

        findings = self.scan_inbox()
        self.notify_findings(findings)
        if not findings:
            return {
                "title": "Email Agent",
                "summary": "I checked the inbox and did not find new assignment-style emails.",
            }

        return {
            "title": "Email Agent",
            "summary": f"I found {len(findings)} possible assignment email(s).",
        }

    def notify_findings(self, findings: list[dict[str, str]]) -> None:
        for finding in findings:
            self.bus.send_message(
                from_agent=AgentName.EMAIL.value,
                to_agent=AgentName.MAIN.value,
                kind=MessageKind.NOTIFICATION.value,
                body={
                    "title": "Email assignment found",
                    "detail": format_assignment_alert(finding),
                    "finding": finding,
                },
            )

    def scan_inbox(self) -> list[dict[str, str]]:
        if not self.config.has_email:
            return []

        processed_uids = set(
            self.bus.get_state(
                agent=AgentName.EMAIL.value,
                key="processed_uids",
                default=[],
            )
        )
        mailbox = imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_port)
        try:
            mailbox.login(self.config.imap_user, self.config.imap_password)
            mailbox.select(self.config.imap_folder)
            status, data = mailbox.uid("search", None, "UNSEEN")
            if status != "OK" or not data:
                return []

            findings: list[dict[str, str]] = []
            seen_this_scan: list[str] = []
            for message_uid in data[0].split():
                uid = message_uid.decode("ascii", errors="ignore")
                if uid in processed_uids:
                    continue

                status, message_data = mailbox.uid("fetch", message_uid, "(RFC822)")
                if status != "OK":
                    continue

                raw_message = next(
                    (part[1] for part in message_data if isinstance(part, tuple)),
                    None,
                )
                if raw_message is None:
                    continue

                parsed = email.message_from_bytes(raw_message)
                subject = decode_header_value(parsed.get("Subject", "No subject"))
                sender = decode_header_value(parsed.get("From", "Unknown sender"))
                body = extract_text(parsed)
                stable_id = parsed.get("Message-ID", uid).strip() or uid

                if looks_like_assignment(subject, body):
                    findings.append(
                        {
                            "id": stable_id,
                            "subject": subject,
                            "from": sender,
                            "snippet": body[:600],
                            "due": extract_due_hint(body),
                        }
                    )

                seen_this_scan.append(uid)
                if not self.config.email_mark_seen:
                    mailbox.uid("store", message_uid, "-FLAGS", "\\Seen")

            if seen_this_scan:
                updated = list((processed_uids | set(seen_this_scan)))[-500:]
                self.bus.set_state(
                    agent=AgentName.EMAIL.value,
                    key="processed_uids",
                    value=updated,
                )
            return findings
        finally:
            try:
                mailbox.logout()
            except imaplib.IMAP4.error:
                pass


def looks_like_assignment(subject: str, body: str) -> bool:
    haystack = f"{subject}\n{body}".lower()
    return any(keyword in haystack for keyword in ASSIGNMENT_KEYWORDS)


def extract_due_hint(body: str) -> str:
    patterns = [
        r"\bdue\s+(?:on|by)?\s*([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
        r"\bdeadline\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
        r"\bby\s+(\d{1,2}/\d{1,2}/\d{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def format_assignment_alert(finding: dict[str, str]) -> str:
    due = f"\nDue: {finding['due']}" if finding.get("due") else ""
    return (
        f"From: {finding.get('from', 'Unknown')}\n"
        f"Subject: {finding.get('subject', 'No subject')}{due}\n\n"
        f"{finding.get('snippet', '').strip()}"
    ).strip()


def decode_header_value(value: str) -> str:
    decoded_parts = decode_header(value)
    chunks: list[str] = []
    for content, charset in decoded_parts:
        if isinstance(content, bytes):
            chunks.append(content.decode(charset or "utf-8", errors="ignore"))
        else:
            chunks.append(content)
    return "".join(chunks).strip()


def extract_text(message: Message) -> str:
    if message.is_multipart():
        parts = []
        for part in message.walk():
            content_type = part.get_content_type()
            disposition = part.get("Content-Disposition", "")
            if content_type == "text/plain" and "attachment" not in disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="ignore"))
        return "\n".join(parts)

    payload = message.get_payload(decode=True)
    if not payload:
        return ""

    return payload.decode(message.get_content_charset() or "utf-8", errors="ignore")

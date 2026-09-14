from __future__ import annotations

import json
import re
from dataclasses import dataclass

from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig
from personal_agents.llm import LLMClient
from personal_agents.models import AgentMessage, AgentName, MessageKind
from personal_agents.reports import build_activity_report


@dataclass(frozen=True)
class RoutedTask:
    agent: AgentName
    kind: str
    reason: str


AGENT_KINDS = {
    AgentName.EMAIL: "check_email_now",
    AgentName.RESEARCH: "deep_research",
    AgentName.BUSINESS: "business_support",
}


class MainAgent:
    def __init__(self, *, bus: AgentBus, config: AppConfig) -> None:
        self.bus = bus
        self.config = config
        self.llm = LLMClient(config)

    def delegate_user_message(self, text: str) -> tuple[RoutedTask, str]:
        route = route_user_text(text, llm=self.llm if self.llm.enabled else None)
        task_id = self.bus.enqueue_task(
            from_agent=AgentName.MAIN.value,
            to_agent=route.agent.value,
            kind=route.kind,
            payload={"request": text},
        )
        return route, task_id

    def request_email_scan(self) -> str:
        return self.bus.enqueue_task(
            from_agent=AgentName.MAIN.value,
            to_agent=AgentName.EMAIL.value,
            kind="check_email_now",
            payload={"request": "Scan the inbox now and report assignments."},
        )

    def fetch_updates(self) -> list[str]:
        messages = self.bus.fetch_messages(to_agent=AgentName.MAIN.value, limit=50)
        return [format_main_message(message) for message in messages]

    def recent_status(self) -> str:
        tasks = self.bus.recent_tasks(limit=10)
        if not tasks:
            return "No tasks yet."

        lines = ["Recent tasks:"]
        for task in tasks:
            lines.append(
                f"- {task.id[:8]} | {task.to_agent} | {task.status} | {task.kind}"
            )
        return "\n".join(lines)

    def activity_report(self) -> str:
        return build_activity_report(self.bus)


def route_user_text(text: str, *, llm: LLMClient | None = None) -> RoutedTask:
    if llm and llm.enabled:
        llm_route = route_user_text_with_llm(text, llm)
        if llm_route is not None:
            return llm_route

    return route_user_text_keywords(text)


def route_user_text_keywords(text: str) -> RoutedTask:
    lower = text.lower()

    email_words = {
        "email",
        "emails",
        "inbox",
        "mail",
        "gmail",
        "assignment",
        "homework",
        "deadline",
    }
    research_words = {
        "research",
        "find",
        "investigate",
        "search",
        "collect",
        "information",
        "dig",
        "study",
        "sources",
    }
    business_words = {
        "business",
        "startup",
        "company",
        "idea",
        "ideas",
        "sales",
        "profit",
        "marketing",
        "customer",
        "customers",
        "requirements",
        "manage",
        "plan",
    }

    if any(word in lower for word in email_words):
        return RoutedTask(
            agent=AgentName.EMAIL,
            kind=AGENT_KINDS[AgentName.EMAIL],
            reason="This sounds like email or assignment monitoring.",
        )

    if any(word in lower for word in research_words):
        return RoutedTask(
            agent=AgentName.RESEARCH,
            kind=AGENT_KINDS[AgentName.RESEARCH],
            reason="This asks for deeper information collection.",
        )

    if any(word in lower for word in business_words):
        return RoutedTask(
            agent=AgentName.BUSINESS,
            kind=AGENT_KINDS[AgentName.BUSINESS],
            reason="This asks for business ideas, plans, or requirements.",
        )

    return RoutedTask(
        agent=AgentName.BUSINESS,
        kind=AGENT_KINDS[AgentName.BUSINESS],
        reason="Defaulting to business support because no specialist keyword was clear.",
    )


def route_user_text_with_llm(text: str, llm: LLMClient) -> RoutedTask | None:
    reply = llm.complete(
        system=(
            "You route user requests to one specialist agent. "
            "Reply with JSON only: "
            '{"agent":"email|research|business","reason":"short reason"}'
        ),
        user=text,
    )
    if not reply:
        return None

    payload = parse_routing_json(reply)
    if payload is None:
        return None

    agent_name = payload.get("agent", "").strip().lower()
    reason = payload.get("reason", "Routed by AI.").strip() or "Routed by AI."

    try:
        agent = AgentName(agent_name)
    except ValueError:
        return None

    if agent == AgentName.MAIN:
        return None

    return RoutedTask(
        agent=agent,
        kind=AGENT_KINDS[agent],
        reason=reason,
    )


def parse_routing_json(reply: str) -> dict[str, str] | None:
    match = re.search(r"\{.*\}", reply, flags=re.DOTALL)
    if not match:
        return None

    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    return {str(key): str(value) for key, value in payload.items()}


def format_main_message(message: AgentMessage) -> str:
    if message.kind == MessageKind.NOTIFICATION.value:
        title = message.body.get("title", "Notification")
        detail = message.body.get("detail", "")
        return f"{title}\n{detail}".strip()

    if message.kind == MessageKind.RESULT.value:
        result = message.body.get("result")
        error = message.body.get("error")
        task_id = message.body.get("task_id", message.task_id)

        if error:
            return f"Task {str(task_id)[:8]} failed:\n{error}"

        if isinstance(result, dict):
            title = result.get("title", f"Task {str(task_id)[:8]} completed")
            body = result.get("summary") or result.get("message") or str(result)
            sources = result.get("sources") or []
            if sources:
                source_lines = "\n".join(f"- {source}" for source in sources[:5])
                return f"{title}\n\n{body}\n\nSources:\n{source_lines}".strip()
            return f"{title}\n\n{body}".strip()

        return f"Task {str(task_id)[:8]} completed:\n{result}"

    return f"{message.from_agent}: {message.body}"

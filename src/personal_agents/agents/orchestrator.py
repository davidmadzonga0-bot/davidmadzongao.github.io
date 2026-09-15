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
    AgentName.WEATHER: "weather_forecast",
    AgentName.BUSINESS: "business_support",
    AgentName.PROJECTS: "project_support",
}

SPECIALIST_AGENTS = {
    AgentName.EMAIL,
    AgentName.RESEARCH,
    AgentName.WEATHER,
    AgentName.BUSINESS,
    AgentName.PROJECTS,
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
            payload={"request": "Scan the inbox now and report needed information."},
        )

    def request_weather_forecast(self, text: str = "Weather forecast for tomorrow, this week, and this month") -> str:
        return self.bus.enqueue_task(
            from_agent=AgentName.MAIN.value,
            to_agent=AgentName.WEATHER.value,
            kind="weather_forecast",
            payload={"request": text},
        )

    def fetch_updates(self) -> list[str]:
        messages = self.bus.fetch_messages(to_agent=AgentName.MAIN.value, limit=50)
        updates: list[str] = []
        for message in messages:
            if message.kind == MessageKind.RESULT.value:
                updates.append(self.review_and_format_result(message))
            else:
                updates.append(format_main_message(message))
        return updates

    def review_and_format_result(self, message: AgentMessage) -> str:
        base = format_main_message(message)
        error = message.body.get("error")
        result = message.body.get("result")
        if error or not isinstance(result, dict):
            return base

        original_request = ""
        task_id = message.body.get("task_id") or message.task_id
        if task_id:
            task = self.bus.get_task(str(task_id))
            if task is not None:
                original_request = str(task.payload.get("request") or "")

        review = self.quality_review(
            from_agent=message.from_agent,
            request=original_request,
            result=result,
        )
        if not review:
            return base

        quality = review.get("quality", "unknown")
        notes = review.get("notes", "")
        lines = [base, "", f"Main Agent quality check: {quality}"]
        if notes:
            lines.append(notes)

        if quality == "needs_improvement" and review.get("follow_up"):
            follow_up = str(review["follow_up"])
            try:
                agent = AgentName(message.from_agent)
            except ValueError:
                agent = None

            if agent in SPECIALIST_AGENTS:
                task_id = self.bus.enqueue_task(
                    from_agent=AgentName.MAIN.value,
                    to_agent=agent.value,
                    kind=AGENT_KINDS[agent],
                    payload={"request": follow_up},
                )
                lines.append(f"Re-assigned follow-up task {task_id[:8]} to improve the result.")

        return "\n".join(lines).strip()

    def quality_review(
        self,
        *,
        from_agent: str,
        request: str,
        result: dict,
    ) -> dict[str, str] | None:
        summary = str(result.get("summary") or result.get("message") or "")
        if not summary:
            return {
                "quality": "needs_improvement",
                "notes": "The specialist returned an empty result.",
                "follow_up": request or "Please redo the previous request with a complete answer.",
            }

        if not self.llm.enabled:
            if len(summary) < 80:
                return {
                    "quality": "needs_improvement",
                    "notes": "Result looks too short. Asking the specialist to expand.",
                    "follow_up": (
                        f"{request}\n\nPlease provide a fuller answer with clear steps and details."
                        if request
                        else "Please expand the previous answer with clearer steps and details."
                    ),
                }
            return {
                "quality": "accepted",
                "notes": "Accepted without AI review (OPENAI_API_KEY not set).",
            }

        reply = self.llm.complete(
            system=(
                "You are the Main Agent quality checker. Decide if a specialist result is useful. "
                'Reply with JSON only: {"quality":"accepted|needs_improvement",'
                '"notes":"short note","follow_up":"optional improved task text"}'
            ),
            user=(
                f"Specialist: {from_agent}\n"
                f"Original request: {request or '(not stored)'}\n"
                f"Result summary:\n{summary[:3500]}"
            ),
        )
        if not reply:
            return {
                "quality": "accepted",
                "notes": "Could not run AI quality review; forwarding the result as-is.",
            }

        payload = parse_routing_json(reply)
        if payload is None:
            return {
                "quality": "accepted",
                "notes": "Quality review response was unclear; forwarding the result as-is.",
            }

        quality = payload.get("quality", "accepted").strip().lower()
        if quality not in {"accepted", "needs_improvement"}:
            quality = "accepted"

        return {
            "quality": quality,
            "notes": payload.get("notes", "").strip(),
            "follow_up": payload.get("follow_up", "").strip(),
        }

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
    }
    weather_words = {
        "weather",
        "forecast",
        "temperature",
        "rain",
        "sunny",
        "climate",
    }
    project_words = {
        "project",
        "projects",
        "milestone",
        "milestones",
        "roadmap",
        "prototype",
        "capstone",
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
        "assignment",
        "homework",
        "coursework",
        "explain",
        "solution",
        "solve",
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
            reason="This sounds like email monitoring or inbox information.",
        )

    if any(word in lower for word in weather_words):
        return RoutedTask(
            agent=AgentName.WEATHER,
            kind=AGENT_KINDS[AgentName.WEATHER],
            reason="This asks for a weather forecast.",
        )

    if any(word in lower for word in project_words):
        return RoutedTask(
            agent=AgentName.PROJECTS,
            kind=AGENT_KINDS[AgentName.PROJECTS],
            reason="This asks for personal or school project help.",
        )

    if any(word in lower for word in research_words):
        return RoutedTask(
            agent=AgentName.RESEARCH,
            kind=AGENT_KINDS[AgentName.RESEARCH],
            reason="This asks for study help, research, or assignment support.",
        )

    if any(word in lower for word in business_words):
        return RoutedTask(
            agent=AgentName.BUSINESS,
            kind=AGENT_KINDS[AgentName.BUSINESS],
            reason="This asks for business ideas, plans, or requirements.",
        )

    return RoutedTask(
        agent=AgentName.RESEARCH,
        kind=AGENT_KINDS[AgentName.RESEARCH],
        reason="Defaulting to study/research support because no specialist keyword was clear.",
    )


def route_user_text_with_llm(text: str, llm: LLMClient) -> RoutedTask | None:
    reply = llm.complete(
        system=(
            "You route user requests to one specialist agent. "
            "Reply with JSON only: "
            '{"agent":"email|research|weather|business|projects","reason":"short reason"} '
            "Use research for school study, research, homework solutions, and assignment help. "
            "Use projects for personal/school project planning and execution. "
            "Use weather for forecasts. Use email for inbox checks. Use business for business work."
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

    if agent not in SPECIALIST_AGENTS:
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

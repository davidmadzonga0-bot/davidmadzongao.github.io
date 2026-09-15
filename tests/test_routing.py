from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import tests._path  # noqa: F401
from personal_agents.agents.orchestrator import (
    MainAgent,
    parse_routing_json,
    route_user_text,
    route_user_text_keywords,
)
from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig
from personal_agents.models import AgentName
from personal_agents.reports import build_activity_report


def make_config(db_path: Path) -> AppConfig:
    return AppConfig(
        telegram_bot_token="",
        telegram_allowed_chat_id=None,
        imap_host="",
        imap_port=993,
        imap_user="",
        imap_password="",
        imap_folder="INBOX",
        email_poll_seconds=120,
        email_mark_seen=False,
        openai_api_key="",
        openai_model="",
        default_weather_location="Harare",
        agents_db_path=db_path,
        worker_poll_seconds=3,
        daily_report_hour=None,
    )


class RoutingTest(unittest.TestCase):
    def test_routes_email_requests(self) -> None:
        route = route_user_text_keywords("Check my inbox email for needed information")
        self.assertEqual(route.agent, AgentName.EMAIL)

    def test_routes_study_assignment_requests(self) -> None:
        route = route_user_text_keywords("Help me solve this homework assignment on algebra")
        self.assertEqual(route.agent, AgentName.RESEARCH)

    def test_routes_research_requests(self) -> None:
        route = route_user_text_keywords("Research solar pump suppliers and collect information")
        self.assertEqual(route.agent, AgentName.RESEARCH)

    def test_routes_weather_requests(self) -> None:
        route = route_user_text_keywords("What is the weather forecast for tomorrow and this week")
        self.assertEqual(route.agent, AgentName.WEATHER)

    def test_routes_project_requests(self) -> None:
        route = route_user_text_keywords("Help me plan my school science fair project milestones")
        self.assertEqual(route.agent, AgentName.PROJECTS)

    def test_routes_business_requests(self) -> None:
        route = route_user_text_keywords("Give me a business plan and startup requirements")
        self.assertEqual(route.agent, AgentName.BUSINESS)

    def test_llm_routing_when_available(self) -> None:
        llm = MagicMock()
        llm.enabled = True
        llm.complete.return_value = '{"agent":"weather","reason":"Needs a forecast."}'

        route = route_user_text("Weather in Harare this month", llm=llm)
        self.assertEqual(route.agent, AgentName.WEATHER)
        self.assertEqual(route.reason, "Needs a forecast.")

    def test_llm_routing_falls_back_to_keywords(self) -> None:
        llm = MagicMock()
        llm.enabled = True
        llm.complete.return_value = None

        route = route_user_text("Check my inbox for deadlines", llm=llm)
        self.assertEqual(route.agent, AgentName.EMAIL)


class RoutingJsonTest(unittest.TestCase):
    def test_parse_routing_json(self) -> None:
        payload = parse_routing_json('Here you go: {"agent":"business","reason":"Planning work."}')
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["agent"], "business")
        self.assertEqual(payload["reason"], "Planning work.")


class QualityReviewTest(unittest.TestCase):
    def test_flags_short_results_without_llm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "agents.sqlite3"
            bus = AgentBus(db_path)
            main = MainAgent(bus=bus, config=make_config(db_path))
            task_id = bus.enqueue_task(
                from_agent="main",
                to_agent="research",
                kind="deep_research",
                payload={"request": "Explain photosynthesis"},
            )
            bus.complete_task(
                task_id,
                {"title": "Study", "summary": "Too short"},
            )
            updates = main.fetch_updates()
            self.assertTrue(any("quality check" in update.lower() for update in updates))


class ReportTest(unittest.TestCase):
    def test_build_activity_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bus = AgentBus(Path(directory) / "agents.sqlite3")
            bus.enqueue_task(
                from_agent="main",
                to_agent="business",
                kind="business_support",
                payload={"request": "plan a shop"},
            )

            report = build_activity_report(bus)
            self.assertIn("Activity report", report)
            self.assertIn("business", report)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import tests._path  # noqa: F401
from personal_agents.agents.orchestrator import (
    parse_routing_json,
    route_user_text,
    route_user_text_keywords,
)
from personal_agents.bus import AgentBus
from personal_agents.models import AgentName
from personal_agents.reports import build_activity_report


class RoutingTest(unittest.TestCase):
    def test_routes_email_assignment_requests(self) -> None:
        route = route_user_text_keywords("Check if I have any email assignment deadlines")
        self.assertEqual(route.agent, AgentName.EMAIL)

    def test_routes_research_requests(self) -> None:
        route = route_user_text_keywords("Research solar pump suppliers and collect information")
        self.assertEqual(route.agent, AgentName.RESEARCH)

    def test_routes_business_requests(self) -> None:
        route = route_user_text_keywords("Give me a business plan and startup requirements")
        self.assertEqual(route.agent, AgentName.BUSINESS)

    def test_llm_routing_when_available(self) -> None:
        llm = MagicMock()
        llm.enabled = True
        llm.complete.return_value = '{"agent":"research","reason":"Needs web research."}'

        route = route_user_text("Compare solar inverter brands", llm=llm)
        self.assertEqual(route.agent, AgentName.RESEARCH)
        self.assertEqual(route.reason, "Needs web research.")

    def test_llm_routing_falls_back_to_keywords(self) -> None:
        llm = MagicMock()
        llm.enabled = True
        llm.complete.return_value = None

        route = route_user_text("Check my inbox for homework deadlines", llm=llm)
        self.assertEqual(route.agent, AgentName.EMAIL)


class RoutingJsonTest(unittest.TestCase):
    def test_parse_routing_json(self) -> None:
        payload = parse_routing_json('Here you go: {"agent":"business","reason":"Planning work."}')
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["agent"], "business")
        self.assertEqual(payload["reason"], "Planning work.")


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

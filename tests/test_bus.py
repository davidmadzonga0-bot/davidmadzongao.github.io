from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import tests._path  # noqa: F401
from personal_agents.bus import AgentBus
from personal_agents.models import MessageKind, TaskStatus


class AgentBusTest(unittest.TestCase):
    def test_task_lifecycle_and_result_message(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bus = AgentBus(Path(directory) / "agents.sqlite3")

            task_id = bus.enqueue_task(
                from_agent="main",
                to_agent="research",
                kind="deep_research",
                payload={"request": "test"},
            )

            task = bus.claim_next_task("research")
            self.assertIsNotNone(task)
            self.assertEqual(task.id, task_id)
            self.assertEqual(task.status, TaskStatus.RUNNING.value)

            bus.complete_task(task_id, {"title": "Done", "summary": "ok"})
            completed = bus.get_task(task_id)
            self.assertIsNotNone(completed)
            self.assertEqual(completed.status, TaskStatus.COMPLETED.value)

            messages = bus.fetch_messages(to_agent="main")
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0].kind, MessageKind.RESULT.value)

    def test_agent_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bus = AgentBus(Path(directory) / "agents.sqlite3")
            self.assertEqual(bus.get_state(agent="email", key="uids", default=[]), [])

            bus.set_state(agent="email", key="uids", value=["1", "2"])
            self.assertEqual(
                bus.get_state(agent="email", key="uids", default=[]),
                ["1", "2"],
            )


if __name__ == "__main__":
    unittest.main()

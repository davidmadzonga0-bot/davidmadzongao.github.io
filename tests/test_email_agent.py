from __future__ import annotations

import unittest

import tests._path  # noqa: F401
from personal_agents.agents.email_agent import extract_due_hint, looks_like_assignment


class EmailAgentTest(unittest.TestCase):
    def test_assignment_detection(self) -> None:
        self.assertTrue(
            looks_like_assignment(
                "Course update",
                "Your assignment is due on August 12. Please submit it online.",
            )
        )

    def test_assignment_detection_ignores_normal_mail(self) -> None:
        self.assertFalse(
            looks_like_assignment(
                "Lunch",
                "Are you available tomorrow afternoon?",
            )
        )

    def test_due_hint_extraction(self) -> None:
        self.assertEqual(
            extract_due_hint("The final task is due by September 3, 2026."),
            "September 3, 2026",
        )


if __name__ == "__main__":
    unittest.main()

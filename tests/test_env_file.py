from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import tests._path  # noqa: F401
from personal_agents.env_file import upsert_env_values


class EnvFileTest(unittest.TestCase):
    def test_upsert_creates_and_updates_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# Telegram\nTELEGRAM_BOT_TOKEN=\nOTHER=keep\n",
                encoding="utf-8",
            )

            upsert_env_values(
                path,
                {
                    "TELEGRAM_BOT_TOKEN": "123:abc",
                    "TELEGRAM_ALLOWED_CHAT_ID": "99",
                },
            )

            text = path.read_text(encoding="utf-8")
            self.assertIn("TELEGRAM_BOT_TOKEN=123:abc", text)
            self.assertIn("TELEGRAM_ALLOWED_CHAT_ID=99", text)
            self.assertIn("OTHER=keep", text)
            self.assertIn("# Telegram", text)


if __name__ == "__main__":
    unittest.main()

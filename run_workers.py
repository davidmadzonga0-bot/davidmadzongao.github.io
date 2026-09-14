from __future__ import annotations

import asyncio
import logging
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from personal_agents.config import load_config  # noqa: E402
from personal_agents.telegram_bot import run_workers  # noqa: E402


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_workers(load_config()))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_dir = ROOT / "logs"
        log_dir.mkdir(exist_ok=True)
        (log_dir / "workers-crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise

from __future__ import annotations

import argparse
import asyncio
import logging

from personal_agents.agents.orchestrator import MainAgent
from personal_agents.bus import AgentBus
from personal_agents.config import format_config_status, load_config
from personal_agents.diagnostics import test_email_connection, test_llm_connection
from personal_agents.telegram_bot import agent_summary, run_telegram_bot, run_workers


def main() -> None:
    parser = argparse.ArgumentParser(description="Run your personal agent system.")
    parser.add_argument(
        "command",
        choices=[
            "init-db",
            "run-bot",
            "run-workers",
            "agents",
            "status",
            "report",
            "assign",
            "check-config",
            "test-email",
            "test-llm",
        ],
    )
    parser.add_argument("text", nargs="*", help="Text for the assign command.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()
    config.ensure_storage()

    if args.command == "init-db":
        AgentBus(config.agents_db_path)
        print(f"Initialized agent database: {config.agents_db_path}")
        return

    if args.command == "agents":
        print(agent_summary())
        return

    if args.command == "check-config":
        print(format_config_status(config))
        return

    if args.command == "test-email":
        print(test_email_connection(config))
        return

    if args.command == "test-llm":
        print(test_llm_connection(config))
        return

    if args.command == "status":
        bus = AgentBus(config.agents_db_path)
        main_agent = MainAgent(bus=bus, config=config)
        print(main_agent.recent_status())
        return

    if args.command == "report":
        bus = AgentBus(config.agents_db_path)
        main_agent = MainAgent(bus=bus, config=config)
        print(main_agent.activity_report())
        return

    if args.command == "assign":
        text = " ".join(args.text).strip()
        if not text:
            parser.error("assign requires text, for example: personal-agents assign research solar business")

        bus = AgentBus(config.agents_db_path)
        main_agent = MainAgent(bus=bus, config=config)
        route, task_id = main_agent.delegate_user_message(text)
        print(f"Assigned task {task_id} to {route.agent.value}: {route.reason}")
        return

    if args.command == "run-workers":
        asyncio.run(run_workers(config))
        return

    if args.command == "run-bot":
        run_telegram_bot(config)
        return


if __name__ == "__main__":
    main()

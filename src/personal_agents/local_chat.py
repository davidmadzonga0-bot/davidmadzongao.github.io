from __future__ import annotations

import asyncio
import logging

from personal_agents.agents.orchestrator import MainAgent
from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig, format_config_status
from personal_agents.telegram_bot import agent_summary, build_workers, display_agent_name


LOGGER = logging.getLogger(__name__)


async def run_local_chat(config: AppConfig) -> None:
    config.ensure_storage()
    bus = AgentBus(config.agents_db_path)
    main_agent = MainAgent(bus=bus, config=config)
    workers = build_workers(bus=bus, config=config)

    worker_tasks = [asyncio.create_task(worker.run_forever()) for worker in workers]
    update_task = asyncio.create_task(_drain_updates(main_agent, config))

    print(
        "\n".join(
            [
                "Local personal-agents chat",
                "Type a request and specialists will work in the background.",
                "Commands: /help /agents /status /report /config /weather /check_email /quit",
                "",
            ]
        )
    )

    try:
        while True:
            try:
                text = await asyncio.to_thread(input, "you> ")
            except EOFError:
                print()
                break

            text = text.strip()
            if not text:
                continue

            if text.lower() in {"/quit", "/exit", "quit", "exit"}:
                break

            reply = await handle_local_command(text, main_agent=main_agent, config=config)
            if reply is not None:
                print(reply)
                print()
                continue

            route, task_id = main_agent.delegate_user_message(text)
            print(
                f"Assigned to {display_agent_name(route.agent)}. "
                f"Task: {task_id[:8]}. Reason: {route.reason}"
            )
            print()
    finally:
        update_task.cancel()
        for task in worker_tasks:
            task.cancel()
        await asyncio.gather(update_task, *worker_tasks, return_exceptions=True)
        print("Local chat stopped.")


async def handle_local_command(
    text: str,
    *,
    main_agent: MainAgent,
    config: AppConfig,
) -> str | None:
    lower = text.lower().strip()
    if lower in {"/help", "help"}:
        return "\n".join(
            [
                "Local Main Agent commands:",
                "/agents - show specialists",
                "/status - recent tasks",
                "/report - activity summary",
                "/config - setup status",
                "/check_email - scan inbox now",
                "/weather [city] - forecast now",
                "/quit - leave local chat",
                "",
                "Or just type a normal request.",
            ]
        )

    if lower in {"/agents", "agents"}:
        return agent_summary()

    if lower in {"/status", "status"}:
        return main_agent.recent_status()

    if lower in {"/report", "report"}:
        return main_agent.activity_report()

    if lower in {"/config", "config"}:
        return format_config_status(config)

    if lower.startswith("/check_email") or lower == "check email":
        task_id = main_agent.request_email_scan()
        return f"Email Agent assigned. Task: {task_id[:8]}"

    if lower.startswith("/weather"):
        extra = text[len("/weather") :].strip()
        request = extra or "Weather forecast for tomorrow, this week, and this month"
        task_id = main_agent.request_weather_forecast(request)
        return f"Weather Agent assigned. Task: {task_id[:8]}"

    return None


async def _drain_updates(main_agent: MainAgent, config: AppConfig) -> None:
    while True:
        updates = main_agent.fetch_updates()
        for update in updates:
            print("\n--- agent result ---")
            print(update[:4000])
            print("--- end ---\n")
        await asyncio.sleep(config.worker_poll_seconds)

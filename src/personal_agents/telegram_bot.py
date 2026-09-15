from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from personal_agents.agents.business_agent import BusinessAgent
from personal_agents.agents.email_agent import EmailAgent
from personal_agents.agents.orchestrator import MainAgent
from personal_agents.agents.projects_agent import ProjectsAgent
from personal_agents.agents.research_agent import ResearchAgent
from personal_agents.agents.weather_agent import WeatherAgent
from personal_agents.bus import AgentBus
from personal_agents.config import AppConfig, format_config_status
from personal_agents.models import AgentName


LOGGER = logging.getLogger(__name__)


def build_workers(*, bus: AgentBus, config: AppConfig) -> list:
    return [
        EmailAgent(bus=bus, config=config),
        ResearchAgent(bus=bus, config=config),
        WeatherAgent(bus=bus, config=config),
        BusinessAgent(bus=bus, config=config),
        ProjectsAgent(bus=bus, config=config),
    ]


def run_telegram_bot(config: AppConfig) -> None:
    if not config.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the Telegram bot.")

    try:
        from telegram import Update
        from telegram.ext import (
            Application,
            ApplicationBuilder,
            CommandHandler,
            ContextTypes,
            MessageHandler,
            filters,
        )
    except ImportError as exc:
        raise RuntimeError(
            "python-telegram-bot is not installed. Run: pip install -e ."
        ) from exc

    config.ensure_storage()
    bus = AgentBus(config.agents_db_path)
    main_agent = MainAgent(bus=bus, config=config)
    workers = build_workers(bus=bus, config=config)
    notification_chat_id: dict[str, str | None] = {
        "value": config.telegram_allowed_chat_id
    }

    def allowed(update: Update) -> bool:
        if not config.telegram_allowed_chat_id:
            if update.effective_chat:
                notification_chat_id["value"] = str(update.effective_chat.id)
            return True

        chat_id = update.effective_chat.id if update.effective_chat else None
        return str(chat_id) == config.telegram_allowed_chat_id

    async def reject_if_needed(update: Update) -> bool:
        if allowed(update):
            return False

        if update.effective_message:
            await update.effective_message.reply_text("This bot is private.")
        return True

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await reject_if_needed(update):
            return

        await update.effective_message.reply_text(
            "\n".join(
                [
                    "I am your Main Agent. Send me work and I assign it to specialists,",
                    "check the results, and bring everything back here.",
                    "",
                    "/agents - show specialists",
                    "/status - show recent tasks",
                    "/report - activity summary",
                    "/config - show setup status",
                    "/check_email - scan the inbox now",
                    "/weather - weather for tomorrow, week, and month outlook",
                ]
            )
        )

    async def agents_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await reject_if_needed(update):
            return

        await update.effective_message.reply_text(agent_summary())

    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await reject_if_needed(update):
            return

        await update.effective_message.reply_text(main_agent.recent_status())

    async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await reject_if_needed(update):
            return

        await update.effective_message.reply_text(main_agent.activity_report())

    async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await reject_if_needed(update):
            return

        await update.effective_message.reply_text(format_config_status(config))

    async def check_email_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await reject_if_needed(update):
            return

        task_id = main_agent.request_email_scan()
        await update.effective_message.reply_text(
            f"Email Agent assigned. Task: {task_id[:8]}"
        )

    async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await reject_if_needed(update):
            return

        extra = " ".join(context.args).strip() if context.args else ""
        request = extra or "Weather forecast for tomorrow, this week, and this month"
        task_id = main_agent.request_weather_forecast(request)
        await update.effective_message.reply_text(
            f"Weather Agent assigned. Task: {task_id[:8]}"
        )

    async def user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if await reject_if_needed(update):
            return

        text = update.effective_message.text or ""
        route, task_id = main_agent.delegate_user_message(text)
        await update.effective_message.reply_text(
            (
                f"Assigned to {display_agent_name(route.agent)}.\n"
                f"Task: {task_id[:8]}\n"
                f"Reason: {route.reason}"
            )
        )

    async def post_init(application: Application) -> None:
        for worker in workers:
            application.create_task(worker.run_forever())

        application.create_task(
            send_agent_updates(application, main_agent, notification_chat_id, config)
        )
        application.create_task(
            send_daily_report_if_due(
                application,
                bus,
                main_agent,
                notification_chat_id,
                config,
            )
        )
        LOGGER.info("Personal agents are running.")

    application = (
        ApplicationBuilder()
        .token(config.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("start", help_command))
    application.add_handler(CommandHandler("agents", agents_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("config", config_command))
    application.add_handler(CommandHandler("check_email", check_email_command))
    application.add_handler(CommandHandler("weather", weather_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_message))

    application.run_polling()


async def send_agent_updates(
    application: "Application",
    main_agent: MainAgent,
    notification_chat_id: dict[str, str | None],
    config: AppConfig,
) -> None:
    while True:
        chat_id = notification_chat_id["value"]
        if not chat_id:
            await asyncio.sleep(config.worker_poll_seconds)
            continue

        updates = main_agent.fetch_updates()
        for update in updates:
            await application.bot.send_message(
                chat_id=chat_id,
                text=update[:4000],
            )
        await asyncio.sleep(config.worker_poll_seconds)


async def send_daily_report_if_due(
    application: "Application",
    bus: AgentBus,
    main_agent: MainAgent,
    notification_chat_id: dict[str, str | None],
    config: AppConfig,
) -> None:
    if config.daily_report_hour is None:
        return

    while True:
        chat_id = notification_chat_id["value"]
        now = datetime.now(UTC)
        today = now.date().isoformat()

        if chat_id and now.hour == config.daily_report_hour:
            last_sent = bus.get_state(
                agent=AgentName.MAIN.value,
                key="last_daily_report_date",
                default="",
            )
            if last_sent != today:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=main_agent.activity_report()[:4000],
                )
                bus.set_state(
                    agent=AgentName.MAIN.value,
                    key="last_daily_report_date",
                    value=today,
                )

        await asyncio.sleep(60)


async def run_workers(config: AppConfig) -> None:
    config.ensure_storage()
    bus = AgentBus(config.agents_db_path)
    workers = build_workers(bus=bus, config=config)
    await asyncio.gather(*(worker.run_forever() for worker in workers))


def display_agent_name(agent: AgentName) -> str:
    labels = {
        AgentName.MAIN: "Main Agent",
        AgentName.EMAIL: "Email Agent",
        AgentName.RESEARCH: "Study & Research Agent",
        AgentName.WEATHER: "Weather Agent",
        AgentName.BUSINESS: "Business Agent",
        AgentName.PROJECTS: "Projects Agent",
    }
    return labels.get(agent, f"{agent.value.title()} Agent")


def agent_summary() -> str:
    return "\n".join(
        [
            "Available agents:",
            "- Main Agent: Telegram commander; assigns work, checks quality, returns all results",
            "- Email Agent: checks your inbox and extracts needed information",
            "- Study & Research Agent: researches topics and helps with school assignments",
            "- Weather Agent: tomorrow, weekly, and monthly outlook forecasts",
            "- Business Agent: business ideas, plans, and operations help",
            "- Projects Agent: personal and school project planning and execution",
        ]
    )

# My Personal Agents

A local multi-agent assistant you talk to on Telegram. One Main Agent manages specialists, checks their work, and sends you every result.

## Agents

| Agent | Role |
| --- | --- |
| **Main Agent** | Your only Telegram contact. Routes work, reviews quality, re-assigns weak results, and delivers all outcomes. |
| **Email Agent** | Checks your inbox and surfaces needed information, assignments, and deadlines. |
| **Study & Research Agent** | Researches topics and helps with school assignments and solutions. |
| **Weather Agent** | Forecast for tomorrow, the next week, and a month-style outlook. |
| **Business Agent** | Business ideas, plans, requirements, and next actions. |
| **Projects Agent** | Personal and school project planning, milestones, and execution help. |

Agents communicate through a shared SQLite task and message bus.

## Project Layout

```text
src/personal_agents/
  agents/
    orchestrator.py      # Telegram-facing main agent + quality checks
    email_agent.py       # Inbox monitor
    research_agent.py    # Study and research worker
    weather_agent.py     # Forecast worker
    business_agent.py    # Business planning worker
    projects_agent.py    # Personal/school projects worker
  bus.py                 # SQLite task/message bus
  config.py              # Environment configuration
  weather.py             # Open-Meteo forecast helper
  telegram_bot.py        # Telegram runtime
```

## Setup

1. Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install the project:

```powershell
pip install -e .
```

3. Copy the environment file:

```powershell
Copy-Item .env.example .env
```

4. Fill in `.env`.

Required for Telegram:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ALLOWED_CHAT_ID=your_telegram_chat_id
```

Required for email monitoring:

```env
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@example.com
IMAP_PASSWORD=your_gmail_app_password
```

For Gmail:

1. Turn on 2-step verification.
2. Create an app password at https://myaccount.google.com/apppasswords
3. Use that 16-character password as `IMAP_PASSWORD`.

Optional weather default city:

```env
WEATHER_DEFAULT_LOCATION=Harare
```

Optional for stronger reasoning, smarter routing, and quality checks:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
```

If `OPENAI_API_KEY` is not set, agents still work with keyword routing and template responses.

Optional daily Telegram summary:

```env
DAILY_REPORT_HOUR=8
```

Uses UTC. Leave blank to disable.

## Running

```powershell
python -m personal_agents.cli init-db
python -m personal_agents.cli check-config
python -m personal_agents.cli run-bot
```

Or use `.\run_bot.cmd`.

## Telegram Commands

- `/help` — commands
- `/agents` — specialists
- `/status` — recent tasks
- `/report` — activity summary
- `/config` — setup status
- `/check_email` — scan inbox now
- `/weather` — forecast now (optional city: `/weather Bulawayo`)

Normal messages are routed automatically.

Examples:

- “Help me solve this chemistry homework on molarity” → Study & Research
- “Check my email for needed information” → Email
- “Weather for Harare tomorrow and this week” → Weather
- “Business plan for a cleaning company” → Business
- “Plan my school science fair project” → Projects

## Notes

- Keep `.env` private.
- Weather uses the free Open-Meteo API (no key). Full-month detail is limited to about 16 days; the agent summarizes the longest available outlook.
- Study help is for learning support. Use it to understand and work through assignments, not as a substitute for academic integrity rules at your school.

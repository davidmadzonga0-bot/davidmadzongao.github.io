# My Personal Agents

A local multi-agent assistant system with one Telegram-facing main agent and three specialist sub-agents:

- **Main Agent**: the only agent you talk to on Telegram. It receives your requests, delegates work, and sends you updates.
- **Email Agent**: watches your inbox for assignments, deadlines, action items, and tasks, then alerts you through the Main Agent.
- **Research Agent**: collects deeper information from the web and summarizes findings with sources.
- **Business Agent**: helps run and grow your business by preparing ideas, requirements, plans, and next actions.

The agents communicate through a shared SQLite task and message bus. That lets one agent assign work to another and lets results flow back to the Main Agent.

## Project Layout

```text
src/personal_agents/
  agents/
    orchestrator.py      # Telegram-facing main agent logic
    email_agent.py       # Inbox monitor and assignment detector
    research_agent.py    # Research worker
    business_agent.py    # Business planning worker
  bus.py                 # SQLite task/message bus
  config.py              # Environment configuration
  diagnostics.py         # Email and OpenAI connection checks
  llm.py                 # Optional OpenAI helper
  reports.py             # Activity summaries
  telegram_bot.py        # Telegram runtime
  web_search.py          # Lightweight web search/fetch helper
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

1. Turn on 2-step verification for your Google account.
2. Create an app password at https://myaccount.google.com/apppasswords
3. Use that 16-character password as `IMAP_PASSWORD`.

Optional for stronger reasoning and smarter routing:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini
```

If `OPENAI_API_KEY` is not set, the agents still work with keyword routing and template responses.

Optional daily Telegram summary:

```env
DAILY_REPORT_HOUR=8
```

Uses UTC. Leave blank to disable.

## Running

Initialize the local database:

```powershell
python -m personal_agents.cli init-db
```

Check configuration:

```powershell
python -m personal_agents.cli check-config
python -m personal_agents.cli test-email
python -m personal_agents.cli test-llm
```

Run the Telegram bot and all sub-agents:

```powershell
python -m personal_agents.cli run-bot
```

Run workers without Telegram:

```powershell
python -m personal_agents.cli run-workers
```

## CLI Commands

- `init-db` creates the SQLite database.
- `check-config` shows which integrations are ready.
- `test-email` verifies Gmail/IMAP login.
- `test-llm` verifies OpenAI access.
- `report` prints an activity summary.
- `assign <text>` queues work without Telegram.
- `status` shows recent tasks.

## Telegram Commands

- `/help` shows commands.
- `/agents` shows available agents.
- `/status` shows recent tasks.
- `/report` shows an activity summary.
- `/config` shows setup status.
- `/check_email` asks the Email Agent to scan the inbox now.

Normal messages are routed automatically. When OpenAI is configured, the Main Agent uses AI routing first and falls back to keyword routing if needed.

Examples:

- “Research profitable poultry farming in Zimbabwe” goes to the Research Agent.
- “Give me a business plan for a cleaning company” goes to the Business Agent.
- “Check my email for assignments” goes to the Email Agent.

## Notes

- Keep `.env` private. It contains your Telegram token, email password, and optional AI key.
- For Gmail, use an app password instead of your normal account password.
- The email monitor reads unseen emails by default and looks for assignment/deadline language.
- The web research helper uses normal web requests, so research quality depends on network access and the pages available.

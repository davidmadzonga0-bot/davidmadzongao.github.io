@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)
"%PYTHON%" -m personal_agents.cli run-bot > logs\bot.log 2>&1

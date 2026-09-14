$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }
$LogDir = Join-Path $ProjectRoot "logs"
$LogFile = Join-Path $LogDir "bot.log"

Set-Location $ProjectRoot
New-Item -ItemType Directory -Force $LogDir | Out-Null
& $Python -m personal_agents.cli run-bot *> $LogFile

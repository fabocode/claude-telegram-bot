# install.ps1 — Windows setup for Claude Telegram Bridge
# Run from the repo root: .\install.ps1

$ErrorActionPreference = "Stop"

$appDir  = "$env:USERPROFILE\.claude-telegram"
$venvDir = "$appDir\.venv"
$repoDir = $PSScriptRoot

Write-Host "=== Claude Telegram Bridge — Windows Setup ===" -ForegroundColor Cyan

# 1. Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python not found. Install Python 3.10+ from https://python.org and re-run." -ForegroundColor Red
    exit 1
}
$pyVersion = python --version
Write-Host "Found $pyVersion" -ForegroundColor Green

# 2. Create directories
New-Item -ItemType Directory -Force -Path "$appDir\approvals" | Out-Null
Write-Host "Created $appDir\approvals" -ForegroundColor Green

# 3. Create virtual environment
if (-not (Test-Path "$venvDir\Scripts\python.exe")) {
    Write-Host "Creating virtual environment at $venvDir ..." -ForegroundColor Yellow
    python -m venv $venvDir
} else {
    Write-Host "Virtual environment already exists at $venvDir" -ForegroundColor Green
}

# 4. Install dependencies
Write-Host "Installing dependencies ..." -ForegroundColor Yellow
& "$venvDir\Scripts\pip.exe" install --quiet --upgrade pip
& "$venvDir\Scripts\pip.exe" install --quiet "requests>=2.31.0"
Write-Host "Dependencies installed." -ForegroundColor Green

# 5. Copy example config if no config present
$configDst = "$appDir\config.json"
$configSrc = "$repoDir\config.example.json"
if (-not (Test-Path $configDst)) {
    Copy-Item $configSrc $configDst
    Write-Host "Copied config.example.json -> $configDst" -ForegroundColor Green
    Write-Host "  >>> Edit $configDst and set your token, chat_id, and project paths." -ForegroundColor Yellow
} else {
    Write-Host "Config already exists at $configDst — not overwritten." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Setup complete! Next steps ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Edit your config:"
Write-Host "   notepad $configDst"
Write-Host ""
Write-Host "2. Copy hooks/claude_settings.json into your Claude settings file"
Write-Host "   (merge into %APPDATA%\Claude\claude_desktop_config.json or equivalent)."
Write-Host ""
Write-Host "3. Test imports:"
Write-Host "   $venvDir\Scripts\python.exe -c `"from bot.telegram_client import TelegramBot; from sessions.manager import SessionManager; print('imports ok')`""
Write-Host ""
Write-Host "4. Start the bot (run from the repo root):"
Write-Host "   $venvDir\Scripts\python.exe main.py"
Write-Host ""

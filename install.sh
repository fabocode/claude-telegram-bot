#!/bin/bash
set -e

echo "=== Claude Telegram Bridge — WSL Setup ==="
echo ""

# 1. Install system dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq tmux python3 python3-pip python3-venv > /dev/null

# 2. Create directory structure
echo "[2/5] Creating directory structure..."
mkdir -p ~/.claude-telegram/approvals

# 3. Detect Windows repo path and create symlink
WINDOWS_REPO="/mnt/c/Users/fabia/code/projects/claude-telegram-bot"
SYMLINK_PATH="$HOME/claude-telegram"

if [ -d "$WINDOWS_REPO" ]; then
    if [ -L "$SYMLINK_PATH" ]; then
        echo "  Symlink already exists: $SYMLINK_PATH -> $(readlink "$SYMLINK_PATH")"
    elif [ -d "$SYMLINK_PATH" ]; then
        echo "  WARNING: $SYMLINK_PATH exists and is a directory. Skipping symlink."
    else
        ln -s "$WINDOWS_REPO" "$SYMLINK_PATH"
        echo "  Created symlink: $SYMLINK_PATH -> $WINDOWS_REPO"
    fi
else
    echo "  WARNING: Windows repo not found at $WINDOWS_REPO"
    echo "  You'll need to create the symlink manually:"
    echo "    ln -s /mnt/c/path/to/claude-telegram-bot ~/claude-telegram"
fi

# 4. Create venv and install Python dependencies
echo "[3/5] Creating virtual environment and installing dependencies..."
VENV="$HOME/.claude-telegram/.venv"
if [ ! -d "$VENV" ]; then
    python3 -m venv "$VENV"
    echo "  Created venv at $VENV"
else
    echo "  Venv already exists at $VENV"
fi
"$VENV/bin/pip" install -r "$SYMLINK_PATH/requirements.txt" --quiet

# 5. Copy config template if config doesn't exist
echo "[4/5] Setting up configuration..."
CONFIG_FILE="$HOME/.claude-telegram/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    cp "$SYMLINK_PATH/config.example.json" "$CONFIG_FILE"
    echo "  Config template copied to $CONFIG_FILE"
    echo "  ** You need to edit this file with your Telegram credentials **"
else
    echo "  Config already exists at $CONFIG_FILE"
fi

# 6. Telegram setup instructions
echo ""
echo "[5/5] Telegram Bot Setup"
echo "========================"
echo ""
echo "If you don't have a bot yet:"
echo ""
echo "  1. Open Telegram and search for @BotFather"
echo "  2. Send /newbot and follow the prompts"
echo "  3. Copy the bot token (looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)"
echo ""
echo "To get your chat_id:"
echo ""
echo "  1. Send any message to your new bot"
echo "  2. Open in browser: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
echo "  3. Find \"chat\":{\"id\":XXXXXXX} in the response"
echo "  4. That number is your chat_id"
echo ""
echo "Then edit: $CONFIG_FILE"
echo "  - Set \"token\" to your bot token"
echo "  - Set \"chat_id\" to your chat ID"
echo "  - Update \"projects\" paths to match your WSL project directories"
echo ""
echo "=== Setup complete ==="
echo ""
echo "To run:  ~/.claude-telegram/.venv/bin/python ~/claude-telegram/main.py"
echo "To test: ~/.claude-telegram/.venv/bin/python -c \"from bot.telegram_client import TelegramBot; from sessions.manager import SessionManager; print('imports ok')\""
echo ""
echo "Optional: Set up Claude Code hooks by merging hooks/claude_settings.json"
echo "into your ~/.claude/settings.json"
echo ""
echo "NOTE: The hooks/claude_settings.json uses the venv Python. Update the"
echo "command path there if your username differs from 'fabian'."

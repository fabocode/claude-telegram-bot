#!/usr/bin/env python3
import json
import logging
import signal
import sys
from pathlib import Path
from bot.telegram_client import TelegramBot
from sessions.manager import SessionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(Path.home() / ".claude-telegram" / "bot.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("main")


def load_config():
    config_path = Path.home() / ".claude-telegram" / "config.json"
    if not config_path.exists():
        print(f"Config not found at {config_path}")
        sys.exit(1)
    with open(config_path) as f:
        return json.load(f)


def main():
    config = load_config()
    session_manager = SessionManager(config)
    bot = TelegramBot(config, session_manager)

    def shutdown(sig, frame):
        log.info("Shutting down...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    log.info("Claude Telegram Bridge started")
    bot.run()


if __name__ == "__main__":
    main()

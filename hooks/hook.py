#!/usr/bin/env python3
import json
import os
import sys
import time
import uuid
import requests
from pathlib import Path

CONFIG_FILE = Path.home() / ".claude-telegram" / "config.json"
APPROVAL_DIR = Path.home() / ".claude-telegram" / "approvals"
APPROVAL_DIR.mkdir(parents=True, exist_ok=True)
APPROVAL_TIMEOUT = 120


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def send_telegram(config, text):
    token = config["telegram"]["token"]
    chat_id = config["telegram"]["chat_id"]
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"[hook] Telegram error: {e}", file=sys.stderr)


def get_current_project(config):
    cwd = os.getcwd()
    for p in config.get("projects", []):
        if cwd.startswith(p["path"]):
            return p["name"]
    return os.path.basename(cwd)


def request_approval(config, tool, detail, project):
    req_id = str(uuid.uuid4())
    req_file = APPROVAL_DIR / f"request_{req_id}.json"
    res_file = APPROVAL_DIR / f"response_{req_id}.json"
    with open(req_file, "w") as f:
        json.dump({"id": req_id, "tool": tool, "detail": detail, "project": project}, f)
    start = time.time()
    while time.time() - start < APPROVAL_TIMEOUT:
        if res_file.exists():
            with open(res_file) as f:
                res = json.load(f)
            req_file.unlink(missing_ok=True)
            res_file.unlink(missing_ok=True)
            return res.get("approved", False)
        time.sleep(0.5)
    req_file.unlink(missing_ok=True)
    send_telegram(config, f"⏰ *Timeout* — operación cancelada\nProyecto: `{project}` | Tool: `{tool}`")
    return False


def handle_notification(config, data, project):
    msg = data.get("message", "")
    if msg:
        send_telegram(config, f"🔔 *{project}*\n{msg}")


def handle_pre_tool(config, data, project):
    tool = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})
    needs_approval = config.get("approval_tools", ["Bash", "Write", "Edit", "MultiEdit"])
    if tool not in needs_approval:
        return
    if tool == "Bash":
        detail = tool_input.get("command", "")
    elif tool in ("Write", "Edit", "MultiEdit"):
        detail = f"Archivo: {tool_input.get('file_path','?')}"
        if "new_string" in tool_input:
            detail += f"\n\n{tool_input['new_string'][:400]}"
    else:
        detail = json.dumps(tool_input, indent=2)[:500]
    approved = request_approval(config, tool, detail, project)
    if not approved:
        print(json.dumps({"action": "block", "message": "❌ Rechazado por usuario vía Telegram"}))
        sys.exit(0)


def handle_stop(config, data, project):
    reason = data.get("stop_reason", "completed")
    send_telegram(config, f"✅ *{project}* terminó\nRazón: `{reason}`")


def main():
    hook_type = os.environ.get("CLAUDE_HOOK_TYPE", "")
    if not hook_type and len(sys.argv) > 1:
        hook_type = sys.argv[1]
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    try:
        config = load_config()
    except Exception as e:
        print(f"[hook] Config error: {e}", file=sys.stderr)
        sys.exit(1)
    project = get_current_project(config)
    handlers = {"Notification": handle_notification, "PreToolUse": handle_pre_tool, "Stop": handle_stop}
    handler = handlers.get(hook_type)
    if handler:
        handler(config, data, project)


if __name__ == "__main__":
    main()

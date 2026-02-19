import json
import logging
import threading
import time
from pathlib import Path
import requests

log = logging.getLogger("bot")
APPROVAL_DIR = Path.home() / ".claude-telegram" / "approvals"
APPROVAL_DIR.mkdir(parents=True, exist_ok=True)


class TelegramBot:
    def __init__(self, config: dict, session_manager):
        self.token = config["telegram"]["token"]
        self.chat_id = str(config["telegram"]["chat_id"])
        self.session_manager = session_manager
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.running = False
        self._streamer_threads = {}

    def _request(self, method, **kwargs):
        try:
            r = requests.post(f"{self.base_url}/{method}", json=kwargs, timeout=35)
            return r.json()
        except Exception as e:
            log.error(f"Telegram API error [{method}]: {e}")
            return {}

    def send(self, text, reply_markup=None, parse_mode="Markdown"):
        kwargs = {"chat_id": self.chat_id, "text": text[:4000], "parse_mode": parse_mode}
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        result = self._request("sendMessage", **kwargs)
        return result.get("result", {}).get("message_id", 0)

    def edit(self, message_id, text, reply_markup=None):
        kwargs = {"chat_id": self.chat_id, "message_id": message_id, "text": text[:4000], "parse_mode": "Markdown"}
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        self._request("editMessageText", **kwargs)

    def answer_callback(self, callback_id, text=""):
        self._request("answerCallbackQuery", callback_query_id=callback_id, text=text)

    def get_updates(self):
        result = self._request("getUpdates", offset=self.offset, timeout=30, allowed_updates=["message", "callback_query"])
        updates = result.get("result", [])
        if updates:
            self.offset = updates[-1]["update_id"] + 1
        return updates

    def run(self):
        self.running = True
        threading.Thread(target=self._watch_approval_requests, daemon=True).start()
        self.send("🟢 *Claude Telegram Bridge conectado*\nEscribe /help para ver comandos.")
        while self.running:
            for update in self.get_updates():
                if "message" in update:
                    self._handle_message(update["message"])
                elif "callback_query" in update:
                    self._handle_callback(update["callback_query"])

    def stop(self):
        self.running = False
        self.send("🔴 Claude Telegram Bridge desconectado.")

    def _handle_message(self, msg):
        text = msg.get("text", "").strip()
        if not text or str(msg["chat"]["id"]) != self.chat_id:
            return
        if text.startswith("/"):
            self._handle_command(text)
        else:
            self._send_prompt(text)

    def _handle_callback(self, cb):
        data = cb.get("data", "")
        msg_id = cb["message"]["message_id"]
        if data.startswith("approve:") or data.startswith("reject:"):
            action, req_id = data.split(":", 1)
            self._write_approval_response(req_id, action == "approve")
            label = "✅ Aprobado" if action == "approve" else "❌ Rechazado"
            self.edit(msg_id, f"{label} — solicitud `{req_id[:8]}`")
            self.answer_callback(cb["id"], label)
        elif data.startswith("switch:"):
            project = data.split(":", 1)[1]
            self.session_manager.set_active(project)
            self.answer_callback(cb["id"], f"Proyecto: {project}")
            self.edit(msg_id, f"✅ Proyecto activo: *{project}*")

    def _handle_command(self, text):
        parts = text.split()
        cmd = parts[0].lower()
        if cmd == "/help":
            self.send("*Comandos:*\n`/list` `/switch` `/status` `/new` `/resume` `/stop` `/output`\n\nO escribe un prompt directo.")
        elif cmd == "/list":
            projects = self.session_manager.get_projects()
            active = self.session_manager.get_active()
            lines = ["*Proyectos:*\n"]
            buttons = []
            for name, info in projects.items():
                status = "🟢" if self.session_manager.is_running(name) else "⚫"
                star = " ← activo" if name == active else ""
                lines.append(f"{status} `{name}`{star}\n   📁 `{info['path']}`")
                buttons.append([{"text": f"Activar {name}", "callback_data": f"switch:{name}"}])
            self.send("\n".join(lines), reply_markup={"inline_keyboard": buttons})
        elif cmd == "/switch":
            if len(parts) < 2:
                projects = self.session_manager.get_projects()
                buttons = [[{"text": name, "callback_data": f"switch:{name}"}] for name in projects]
                self.send("¿A cuál proyecto cambias?", reply_markup={"inline_keyboard": buttons})
            else:
                name = parts[1]
                if self.session_manager.set_active(name):
                    self.send(f"✅ Proyecto activo: *{name}*")
                else:
                    self.send(f"❌ Proyecto `{name}` no encontrado.")
        elif cmd == "/status":
            active = self.session_manager.get_active()
            if not active:
                self.send("No hay proyecto activo.")
                return
            info = self.session_manager.get_projects().get(active, {})
            running = self.session_manager.is_running(active)
            self.send(f"*Activo:* `{active}`\n*Ruta:* `{info.get('path','?')}`\n*Estado:* {'🟢 Corriendo' if running else '⚫ Sin sesión'}")
        elif cmd == "/new":
            active = self.session_manager.get_active()
            if not active:
                self.send("Usa /switch primero.")
                return
            ok = self.session_manager.new_session(active)
            self.send(f"✅ Sesión iniciada en *{active}*." if ok else "❌ Error.")
        elif cmd == "/resume":
            active = self.session_manager.get_active()
            if not active:
                self.send("Usa /switch primero.")
                return
            ok = self.session_manager.resume_session(active)
            self.send(f"✅ Sesión retomada en *{active}*." if ok else "❌ Error.")
        elif cmd == "/stop":
            active = self.session_manager.get_active()
            if active:
                self.session_manager.kill_session(active)
                self.send(f"🛑 Sesión de *{active}* terminada.")
        elif cmd == "/output":
            active = self.session_manager.get_active()
            if not active:
                self.send("No hay proyecto activo.")
                return
            output = self.session_manager.capture_output(active)
            self.send(f"📺 *{active}:*\n```\n{output[-3000:]}\n```" if output else "Sin output.")

    def _send_prompt(self, text):
        active = self.session_manager.get_active()
        if not active:
            self.send("⚠️ Usa /switch primero.")
            return
        if not self.session_manager.is_running(active):
            self.send(f"⚠️ Usa /new o /resume en *{active}*.")
            return
        self.session_manager.send_input(active, text)
        self.send(f"📤 Prompt enviado a *{active}*")
        if active not in self._streamer_threads or not self._streamer_threads[active].is_alive():
            t = threading.Thread(target=self._stream_output, args=(active,), daemon=True)
            self._streamer_threads[active] = t
            t.start()

    def _stream_output(self, project):
        last_output = ""
        last_msg_id = None
        idle_count = 0
        time.sleep(3)
        while self.running:
            output = self.session_manager.capture_output(project)
            if output and output != last_output:
                new_content = output[len(last_output):].strip()
                if new_content and len(new_content) > 10:
                    chunk = f"📺 `{project}`:\n```\n{new_content[-2000:]}\n```"
                    if last_msg_id and len(new_content) < 2000:
                        try:
                            self.edit(last_msg_id, chunk)
                        except Exception:
                            last_msg_id = self.send(chunk)
                    else:
                        last_msg_id = self.send(chunk)
                    last_output = output
                    idle_count = 0
                else:
                    idle_count += 1
            else:
                idle_count += 1
            if idle_count >= 10:
                break
            time.sleep(3)

    def _watch_approval_requests(self):
        seen = set()
        while self.running:
            for req_file in APPROVAL_DIR.glob("request_*.json"):
                if req_file.name not in seen:
                    seen.add(req_file.name)
                    try:
                        with open(req_file) as f:
                            req = json.load(f)
                        self._send_approval_request(req)
                    except Exception as e:
                        log.error(f"Error reading approval: {e}")
            time.sleep(0.5)

    def _send_approval_request(self, req):
        req_id = req["id"]
        text = (f"⚠️ *Confirmación requerida*\n\n*Proyecto:* `{req.get('project','?')}`\n"
                f"*Tool:* `{req.get('tool','?')}`\n\n```\n{req.get('detail','')[:800]}\n```")
        buttons = {"inline_keyboard": [[
            {"text": "✅ Aprobar", "callback_data": f"approve:{req_id}"},
            {"text": "❌ Rechazar", "callback_data": f"reject:{req_id}"},
        ]]}
        self.send(text, reply_markup=buttons)

    def _write_approval_response(self, req_id, approved):
        with open(APPROVAL_DIR / f"response_{req_id}.json", "w") as f:
            json.dump({"approved": approved}, f)

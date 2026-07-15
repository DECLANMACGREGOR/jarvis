"""
telegram_io.py — JARVIS's Telegram text-mode I/O channel.

This is a second front door alongside the F8 push-to-talk loop: a long-polling
Telegram bot that lets me talk to JARVIS by text from my phone.

Auth model:
- TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID live in .env (gitignored), loaded via
  config.py, exactly like the other API keys in this project.

Safety model:
- TELEGRAM_CHAT_ID is a single hardcoded allowlisted chat (mine). Every
  incoming update is checked against it immediately after parsing, before any
  other processing — updates from any other chat are silently dropped (no
  reply, no logging of their content). This is the ONLY place that check
  happens.
- send_message() has no "send to arbitrary chat" parameter — outbound
  messages always go to the same allowlisted TELEGRAM_CHAT_ID.

Step 2 scope (this file):
- This step only proves the poller, allowlist, and send path work end to end.
  Incoming text is simply echoed back. `handle_message()` below is the single
  seam a later step will replace with the real agent brain (brain.think()).
"""

import threading
import time

import requests

import config

_API_URL = "https://api.telegram.org/bot{token}/{method}"


def handle_message(text: str) -> str:
    """Handle one allowlisted incoming text message, return the reply to send.

    Step 2: just echoes. A later step swaps this out (or reassigns
    telegram_io.handle_message) to route text through the agent brain.
    """
    return f"echo: {text}"


class TelegramIO:
    def __init__(self):
        self._offset = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ── Public API ─────────────────────────────────────────────────────────────

    def send_message(self, text: str) -> None:
        try:
            requests.post(
                self._url("sendMessage"),
                json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
                timeout=10,
            )
        except requests.exceptions.RequestException as e:
            print(f"[JARVIS] Telegram send failed — {type(e).__name__}: {e}")

    # ── Internal ───────────────────────────────────────────────────────────────

    def _url(self, method: str) -> str:
        return _API_URL.format(token=config.TELEGRAM_BOT_TOKEN, method=method)

    def _run(self) -> None:
        print("[JARVIS] Telegram channel online — polling.")
        while True:
            try:
                resp = requests.get(
                    self._url("getUpdates"),
                    params={"offset": self._offset, "timeout": 30},
                    timeout=40,
                )
                resp.raise_for_status()
                updates = resp.json().get("result", [])
            except requests.exceptions.RequestException as e:
                print(f"[JARVIS] Telegram poll error — {type(e).__name__}: {e}")
                time.sleep(3)
                continue

            for update in updates:
                self._handle_update(update)
                self._offset = update["update_id"] + 1

    def _handle_update(self, update: dict) -> None:
        message = update.get("message")
        if not message or not message.get("text"):
            return  # edited messages, photos, etc. — skip gracefully

        # THE single allowlist enforcement point — before anything else happens.
        chat_id = message.get("chat", {}).get("id")
        if str(chat_id) != str(config.TELEGRAM_CHAT_ID):
            return  # not me — silently ignore, no reply, no logging of content

        text = message["text"]
        reply = handle_message(text)
        if reply:
            self.send_message(reply)


# ── Module-level singleton ─────────────────────────────────────────────────────

_telegram: TelegramIO | None = None


def start() -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[JARVIS] Telegram channel disabled (no token/chat_id in .env).")
        return
    global _telegram
    _telegram = TelegramIO()


def send_message(text: str) -> None:
    if _telegram:
        _telegram.send_message(text)

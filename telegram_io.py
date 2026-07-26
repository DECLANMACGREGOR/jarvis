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
- await_reply() (used by the permission gate for typed YES/NO confirmations)
  re-applies the same allowlist check, so a confirmation can only come from me.

Routing:
- Incoming text goes through the real agent brain (brain.think()),
  serialized with the voice loop via brain._brain_lock. `handle_message()`
  is the single seam for this — any future channel-specific behavior
  goes here.
"""

import threading
import time

import requests

import brain
import config

_API_URL = "https://api.telegram.org/bot{token}/{method}"


def handle_message(text: str) -> str:
    """Handle one allowlisted incoming text message, return the reply to send.

    Routes through brain.think() (serialized with the voice loop). Any
    exception must not escape — the poller needs a reply to send so the
    update offset can advance, and the caller here already advances the
    offset before this runs (see TelegramIO._run) so a poisoned message is
    never reprocessed even if this raised.
    """
    try:
        return brain.think(text, channel="telegram")
    except Exception as e:
        print(f"[JARVIS] Telegram handle_message failed — {type(e).__name__}: {e}")
        return "Something went wrong handling that, sir."


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
                # Advance the offset BEFORE handling: if _handle_update raises,
                # the poisoned update must never be reprocessed forever. Use max()
                # so a nested await_reply poll (during a permission confirmation)
                # that already advanced the offset past this batch is never
                # regressed — otherwise a consumed YES/NO could be re-fetched.
                self._offset = max(self._offset, update["update_id"] + 1)
                try:
                    self._handle_update(update)
                except Exception as e:
                    print(f"[JARVIS] Telegram update handling failed — {type(e).__name__}: {e}")

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

    def await_reply(self, timeout: float) -> str | None:
        """Block up to `timeout`s for the next allowlisted text message; return it.

        Used by the permission gate (_confirm_telegram) to fetch a YES/NO reply.
        It runs on THIS poller thread — the confirmation sits inside the call
        chain _run -> _handle_update -> handle_message -> brain.think -> dispatch
        -> _confirm — so the outer _run poll is suspended up the stack. We keep
        polling getUpdates here to fetch the reply; because it's the same thread
        that owns getUpdates, there is never a second concurrent long-poll.
        self._offset is shared and advanced monotonically, so neither the
        original command nor this reply is ever double-processed. Returns None on
        timeout. Non-allowlisted messages are dropped here too.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            long_poll = max(1, min(20, int(remaining)))
            try:
                resp = requests.get(
                    self._url("getUpdates"),
                    params={"offset": self._offset, "timeout": long_poll},
                    timeout=long_poll + 10,
                )
                resp.raise_for_status()
                updates = resp.json().get("result", [])
            except requests.exceptions.RequestException as e:
                print(f"[JARVIS] Telegram await_reply poll error — {type(e).__name__}: {e}")
                time.sleep(1)
                continue

            for update in updates:
                self._offset = max(self._offset, update["update_id"] + 1)
                message = update.get("message")
                if not message or not message.get("text"):
                    continue
                chat_id = message.get("chat", {}).get("id")
                if str(chat_id) != str(config.TELEGRAM_CHAT_ID):
                    continue  # allowlist enforced on replies too
                return message["text"]
        return None


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


def await_reply(timeout: float) -> str | None:
    """Wait for the next allowlisted text message (permission-gate replies)."""
    if _telegram:
        return _telegram.await_reply(timeout)
    return None

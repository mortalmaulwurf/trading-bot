"""Hilfsskript zur Fehlersuche: fragt mit dem gespeicherten TELEGRAM_BOT_TOKEN
bei Telegram ab, welche Chats dem Bot zuletzt geschrieben haben, und gibt
deren Chat-IDs aus. Braucht KEINE TELEGRAM_CHAT_ID – hilft genau dabei,
diese herauszufinden bzw. zu verifizieren.

Wichtig: Vorher dem Bot in Telegram eine aktuelle Nachricht schreiben,
sonst liefert Telegram keine (oder nur alte, ggf. abgelaufene) Updates.

Ausführung: python get_chat_id.py (vom Repo-Root aus)
"""
from __future__ import annotations

import logging
import sys

import requests

from src.config import get_telegram_credentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    token, _ = get_telegram_credentials()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN ist nicht gesetzt.")
        return 1

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        body = exc.response.text if exc.response is not None else ""
        logger.error("Abfrage fehlgeschlagen: %s | Antwort: %s", exc, body)
        return 1

    data = response.json()
    results = data.get("result", [])

    if not results:
        logger.warning(
            "Keine Updates gefunden. Hast du dem Bot GERADE EBEN eine Nachricht geschrieben? "
            "Telegram liefert nur kürzlich eingegangene, noch nicht abgeholte Nachrichten."
        )
        return 1

    seen = {}
    for update in results:
        message = update.get("message") or update.get("edited_message")
        if not message:
            continue
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        name = chat.get("first_name") or chat.get("title") or "?"
        text = message.get("text", "")
        seen[chat_id] = name
        logger.info("Chat-ID: %s | Name: %s | Nachricht: %r", chat_id, name, text)

    if not seen:
        logger.warning("Updates gefunden, aber keine Chat-Nachrichten darin (z.B. nur andere Event-Typen).")
        return 1

    logger.info("=> Trage die passende Chat-ID oben als TELEGRAM_CHAT_ID-Secret ein.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

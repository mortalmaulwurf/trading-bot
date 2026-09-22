"""Manueller Test des Telegram-Versands, unabhängig vom Scan-Ergebnis.

Nützlich zur Fehlersuche: prüft ausschließlich, ob TELEGRAM_BOT_TOKEN und
TELEGRAM_CHAT_ID korrekt sind, ohne auf einen echten Scan-Treffer zu warten.

Ausführung: python test_telegram.py (vom Repo-Root aus)
"""
from __future__ import annotations

import logging
import sys

from src.config import get_telegram_credentials
from src.notifier import send_telegram_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    token, chat_id = get_telegram_credentials()

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN ist nicht gesetzt.")
        return 1
    if not chat_id:
        logger.error("TELEGRAM_CHAT_ID ist nicht gesetzt.")
        return 1

    logger.info("Sende Testnachricht an Chat-ID %s ...", chat_id)
    ok = send_telegram_message(token, chat_id, "🔔 Testnachricht vom Trading-Bot – Verbindung funktioniert.")

    if ok:
        logger.info("Erfolgreich gesendet. Schau in Telegram nach der Nachricht.")
        return 0

    logger.error("Senden fehlgeschlagen. Details siehe Fehlermeldung oben.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

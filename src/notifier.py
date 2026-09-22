"""Telegram-Benachrichtigung bei relevanten Treffern."""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(token: str, chat_id: str, text: str) -> bool:
    url = TELEGRAM_API_URL.format(token=token)
    try:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=15,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        body = exc.response.text if exc.response is not None else ""
        logger.error("Telegram-Benachrichtigung fehlgeschlagen: %s | Antwort: %s", exc, body)
        return False


def format_hits_message(report: dict) -> str:
    lines = [f"📊 *Swing-Trading Scan* – {report['hits_count']} Treffer"]
    for h in report["hits"]:
        lines.append(
            f"\n*{h['ticker']}* ({h['confidence']})\n"
            f"Kurs {h['current_price']} {h['currency']} · {h['nearest_level_name']} @ {h['nearest_level_price']} "
            f"({h['distance_pct']:+.2f}%)\n"
            f"Bestätigungen: {h['confirmations']}/3"
        )
    lines.append("\nDetails siehe Report im Repo (reports/latest.md).")
    return "\n".join(lines)

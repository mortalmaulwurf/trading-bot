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


def format_alerts_message(report: dict, site_url: str = "") -> str:
    """Telegram text for setups that passed the confirmation and net-CRV filters."""
    lines = [f"🔔 *Setup-Alarm* – {report['alerts_count']} Setup(s)"]
    for h in report["alerts"]:
        tag = "A-Setup" if h.get("is_a_setup") else "Setup"
        extra = []
        if h.get("confluence"):
            extra.append(f"✅ Konfluenz mit {h['confluence_level_name']}")
        if h.get("weekly_trend"):
            extra.append(
                "✅ Wochentrend aufwärts" if h["weekly_trend"] == "aufwärts" else "⚠️ Wochentrend abwärts"
            )
        if h.get("upcoming_events"):
            extra.append(f"⚠️ Termin: {'; '.join(h['upcoming_events'])}")
        extra_line = f"\n{' · '.join(extra)}" if extra else ""

        p = h["position_suggestion"]
        plan = (
            f"Einstieg {p['entry_price']} · Stop {p['stop_price']} · Ziel {p['target_price']}\n"
            f"Hebel {p['leverage']}× · Einsatz {p['capital_eur']:.0f}€ · Netto-CRV {p['net_crv']}:1"
        )
        idx = p.get("index_levels")
        if idx:
            plan += f"\nIndex: Einstieg {idx['entry']} · Stop {idx['stop']} · Ziel {idx['target']}"
        lines.append(
            f"\n*{h['name']}* ({h['ticker']}) – {tag}\n"
            f"Kurs {h['current_price']} {h['currency']} · {h['nearest_level_name']} @ {h['nearest_level_price']} "
            f"({h['distance_pct']:+.2f}%)\n"
            f"Bestätigungen: {h['confirmations']}/3{extra_line}\n{plan}"
        )
    if site_url:
        lines.append(f"\n🔗 Volle Übersicht: {site_url}")
    lines.append("\nDetails siehe Report im Repo (reports/latest.md).")
    return "\n".join(lines)

"""Einstiegspunkt: lädt Konfiguration, analysiert die Watchlist und meldet Treffer.

Ausführung: python -m src.main (vom Repo-Root aus)
"""
from __future__ import annotations

import logging
import sys

from . import report as report_module
from .config import get_telegram_credentials, load_settings, load_watchlist
from .notifier import format_alerts_message, format_error_message, send_telegram_message
from .signal_engine import analyze_ticker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run() -> int:
    settings = load_settings()
    watchlist = load_watchlist()

    results = []
    errors: dict[str, str] = {}

    for entry in watchlist:
        logger.info("Analysiere %s (%s) ...", entry.name, entry.symbol)
        try:
            results.append(
                analyze_ticker(
                    entry.symbol,
                    settings.analysis,
                    settings.risk,
                    display_name=entry.name,
                    index_symbol=entry.index_symbol,
                    min_confirmations=settings.notifications.min_confirmations,
                )
            )
        except Exception as exc:
            logger.exception("Analyse für %s fehlgeschlagen", entry.symbol)
            errors[entry.symbol] = str(exc)

    report = report_module.build_report(
        results, errors, settings.analysis.proximity_threshold_pct, settings.risk
    )
    md_path, json_path = report_module.write_reports(report)
    logger.info("Report geschrieben: %s / %s", md_path, json_path)

    token, chat_id = get_telegram_credentials()
    if errors and token and chat_id:
        send_telegram_message(token, chat_id, format_error_message(errors))

    if report["alerts_count"] > 0:
        if token and chat_id:
            message = format_alerts_message(report, site_url=settings.notifications.site_url)
            if send_telegram_message(token, chat_id, message):
                logger.info("Telegram-Benachrichtigung gesendet (%d Setups)", report["alerts_count"])
        else:
            logger.warning("Setups gefunden, aber TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID nicht gesetzt")
    else:
        logger.info("Keine Setups mit ausreichenden Bestätigungen und Netto-CRV (Treffer: %d)", report["hits_count"])

    return 0


if __name__ == "__main__":
    sys.exit(run())

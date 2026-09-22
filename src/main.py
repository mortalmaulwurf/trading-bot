"""Einstiegspunkt: lädt Konfiguration, analysiert die Watchlist und meldet Treffer.

Ausführung: python -m src.main (vom Repo-Root aus)
"""
from __future__ import annotations

import logging
import sys

from . import report as report_module
from .config import get_telegram_credentials, load_settings, load_watchlist
from .data_fetcher import fetch_fx_rate_usd_to_eur
from .notifier import format_hits_message, send_telegram_message
from .signal_engine import analyze_ticker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run() -> int:
    settings = load_settings()
    tickers = load_watchlist()
    fx_rate = fetch_fx_rate_usd_to_eur()

    results = []
    errors: dict[str, str] = {}

    for ticker in tickers:
        logger.info("Analysiere %s ...", ticker)
        try:
            results.append(analyze_ticker(ticker, settings.analysis, settings.risk, fx_rate))
        except Exception as exc:
            logger.exception("Analyse für %s fehlgeschlagen", ticker)
            errors[ticker] = str(exc)

    report = report_module.build_report(results, errors, settings.analysis.proximity_threshold_pct)
    md_path, json_path = report_module.write_reports(report)
    logger.info("Report geschrieben: %s / %s", md_path, json_path)

    if report["hits_count"] > 0:
        token, chat_id = get_telegram_credentials()
        if token and chat_id:
            message = format_hits_message(report)
            if send_telegram_message(token, chat_id, message):
                logger.info("Telegram-Benachrichtigung gesendet (%d Treffer)", report["hits_count"])
        else:
            logger.warning("Treffer gefunden, aber TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID nicht gesetzt")
    else:
        logger.info("Keine Treffer in diesem Lauf")

    return 0


if __name__ == "__main__":
    sys.exit(run())

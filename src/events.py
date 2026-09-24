"""Bevorstehende Termine mit Marktrelevanz: Quartalszahlen (aus yfinance),
der US-Arbeitsmarktbericht (regelbasiert), FOMC/EZB/US-CPI (automatisch von
den offiziellen Kalenderseiten, siehe macro_calendar.py) und zusätzlich
manuell gepflegte Termine (siehe config/macro_events.yaml).

Reine Zusatzinfo zur Risikoeinschätzung (Gap-Risiko rund um Termine) –
kein Ausschlusskriterium, beeinflusst nicht, ob ein Ticker als Treffer zählt.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import yaml
import yfinance as yf

from . import macro_calendar

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def get_upcoming_earnings(ticker: str, days_ahead: int) -> Optional[date]:
    """Nächster bekannter Earnings-Termin innerhalb von days_ahead Tagen.
    Näherungswert: yfinance-Schätzungen können va. bei Nicht-US-Tickern
    ungenau oder veraltet sein, und ETFs/Futures haben keine Earnings."""
    try:
        dates_df = yf.Ticker(ticker).get_earnings_dates(limit=4)
    except Exception as exc:
        logger.warning("Earnings-Termine für %s nicht abrufbar: %s", ticker, exc)
        return None

    if dates_df is None or dates_df.empty:
        return None

    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    for ts in dates_df.index:
        d = ts.date()
        if today <= d <= horizon:
            return d
    return None


def _next_first_friday(days_ahead: int) -> Optional[date]:
    """US-Arbeitsmarktbericht (Nonfarm Payrolls): traditionell der erste
    Freitag im Monat – regelbasiert, kein Datenabruf nötig oder möglich fehleranfällig."""
    today = date.today()
    horizon = today + timedelta(days=days_ahead)

    for month_offset in (0, 1):
        year = today.year + (today.month - 1 + month_offset) // 12
        month = (today.month - 1 + month_offset) % 12 + 1
        cal = calendar.monthcalendar(year, month)
        first_friday_day = next(week[calendar.FRIDAY] for week in cal if week[calendar.FRIDAY] != 0)
        candidate = date(year, month, first_friday_day)
        if today <= candidate <= horizon:
            return candidate
    return None


def _load_macro_events() -> list[dict]:
    path = CONFIG_DIR / "macro_events.yaml"
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return raw.get("events") or []
    except FileNotFoundError:
        return []


def get_upcoming_events(ticker: str, currency: str, days_ahead: int) -> list[str]:
    """Kurze Beschreibungen bevorstehender, relevanter Termine für diesen Ticker."""
    events: list[str] = []

    earnings_date = get_upcoming_earnings(ticker, days_ahead)
    if earnings_date:
        events.append(f"Quartalszahlen am {earnings_date.isoformat()}")

    region = "US" if currency == "USD" else "EU" if currency == "EUR" else None

    if region == "US":
        nfp_date = _next_first_friday(days_ahead)
        if nfp_date:
            events.append(f"US-Arbeitsmarktbericht am {nfp_date.isoformat()}")
        for d in macro_calendar.get_fomc_dates(days_ahead):
            events.append(f"FOMC-Zinsentscheid am {d.isoformat()}")
        for d in macro_calendar.get_cpi_dates(days_ahead):
            events.append(f"US-Inflationsdaten (CPI) am {d.isoformat()}")
    elif region == "EU":
        for d in macro_calendar.get_ecb_dates(days_ahead):
            events.append(f"EZB-Ratssitzung am {d.isoformat()}")

    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    for entry in _load_macro_events():
        try:
            event_date = date.fromisoformat(str(entry["date"]))
        except (KeyError, ValueError, TypeError):
            continue
        if entry.get("region") == region and today <= event_date <= horizon:
            events.append(f"{entry.get('label', 'Makro-Termin')} am {event_date.isoformat()}")

    return events

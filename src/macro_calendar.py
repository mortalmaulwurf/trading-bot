"""Automatischer Abruf offizieller Makro-Kalender (FOMC, EZB, US-CPI).

Es gibt keine zuverlässige kostenlose strukturierte API für diese Termine,
daher werden die offiziellen Kalenderseiten direkt nach Datumsmustern
durchsucht (bewusst nur Primärquellen – Fed, EZB, BLS – keine
Drittanbieter-Aggregatoren).

Das ist fragiler als eine echte API: ändert eine Behörde ihre Seitenstruktur,
liefert die jeweilige Funktion ggf. keine Termine mehr. Das wird geloggt,
bricht den Scan aber nicht ab – Aufrufer bekommen dann einfach eine leere
Liste statt eines Fehlers. config/macro_events.yaml bleibt als manueller
Fallback/Ergänzung bestehen, falls eine Quelle mal nichts liefert.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

import requests

logger = logging.getLogger(__name__)

FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
ECB_URL = "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"
BLS_CPI_URL = "https://www.bls.gov/schedule/news_release/cpi.htm"

_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}
_MONTH_PATTERN = "|".join(_MONTHS)


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}


def _fetch(url: str) -> Optional[str]:
    try:
        response = requests.get(url, timeout=15, headers=_BROWSER_HEADERS)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        logger.warning("Makro-Kalender-Abruf fehlgeschlagen (%s): %s", url, exc)
        return None


def _dates_in_horizon(source_name: str, dates: set[date], days_ahead: int) -> list[date]:
    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    upcoming_any = sorted(d for d in dates if d >= today)
    logger.info(
        "%s: %d Termin(e) auf der Seite gefunden, nächster: %s",
        source_name, len(dates), upcoming_any[0].isoformat() if upcoming_any else "keiner",
    )
    return sorted(d for d in dates if today <= d <= horizon)


@lru_cache(maxsize=8)
def get_fomc_dates(days_ahead: int) -> tuple[date, ...]:
    """FOMC-Sitzungstermine von der offiziellen Fed-Kalenderseite.

    Die Seite gliedert sich üblicherweise in Jahres-Abschnitte ("2026 FOMC
    Meetings") mit Terminen wie "January 27-28" darunter (Jahr steht nur
    einmal in der Abschnitts-Überschrift, nicht bei jedem Termin) – daher
    zweistufig: erst Jahres-Abschnitte finden, dann Monat/Tag darin.
    """
    html = _fetch(FOMC_URL)
    if not html:
        return ()

    year_pattern = re.compile(r"(\d{4})\s+FOMC Meetings?", re.IGNORECASE)
    day_pattern = re.compile(rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}})(?:[-–]\d{{1,2}})?\b")

    year_matches = list(year_pattern.finditer(html))
    dates: set[date] = set()

    for i, year_match in enumerate(year_matches):
        year = int(year_match.group(1))
        section_start = year_match.end()
        section_end = year_matches[i + 1].start() if i + 1 < len(year_matches) else len(html)
        section_text = html[section_start:section_end]

        for month_name, day_str in day_pattern.findall(section_text):
            try:
                dates.add(date(year, _MONTHS[month_name], int(day_str)))
            except ValueError:
                continue

    return tuple(_dates_in_horizon("FOMC", dates, days_ahead))


@lru_cache(maxsize=8)
def get_ecb_dates(days_ahead: int) -> tuple[date, ...]:
    """EZB-Ratssitzungstermine (geldpolitisch) von der offiziellen EZB-Kalenderseite."""
    html = _fetch(ECB_URL)
    if not html:
        return ()

    pattern = re.compile(rf"\b(\d{{1,2}})\s+({_MONTH_PATTERN})\s+(\d{{4}})\b")
    dates: set[date] = set()
    for day_str, month_name, year_str in pattern.findall(html):
        try:
            dates.add(date(int(year_str), _MONTHS[month_name], int(day_str)))
        except ValueError:
            continue

    return tuple(_dates_in_horizon("EZB", dates, days_ahead))


@lru_cache(maxsize=8)
def get_cpi_dates(days_ahead: int) -> tuple[date, ...]:
    """US-Inflationsdaten (CPI)-Veröffentlichungstermine vom offiziellen BLS-Zeitplan."""
    html = _fetch(BLS_CPI_URL)
    if not html:
        return ()

    pattern = re.compile(rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})\b")
    dates: set[date] = set()
    for month_name, day_str, year_str in pattern.findall(html):
        try:
            dates.add(date(int(year_str), _MONTHS[month_name], int(day_str)))
        except ValueError:
            continue

    return tuple(_dates_in_horizon("BLS-CPI", dates, days_ahead))

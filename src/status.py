"""Morning status message: confirms the scan ran and summarizes the latest report.

Runs Mon-Fri around 08:00 Europe/Berlin (see .github/workflows/morning_status.yml),
so that a quiet day is visibly different from a broken bot.

Usage: python -m src.status [--force]
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .config import get_telegram_credentials, load_settings
from .notifier import send_telegram_message

logger = logging.getLogger(__name__)

REPORT_PATH = Path(__file__).resolve().parent.parent / "reports" / "latest.json"
BERLIN = ZoneInfo("Europe/Berlin")
SEND_HOUR_BERLIN = 8
# The scan runs Mon-Fri evening, so on Monday morning the newest report is the Friday one.
MAX_REPORT_AGE_HOURS = 30
MAX_REPORT_AGE_HOURS_MONDAY = 80


def should_send(now_utc: datetime, force: bool = False) -> bool:
    """The workflow fires at two UTC times to cover summer/winter time; only the one at 08:xx Berlin sends."""
    return force or now_utc.astimezone(BERLIN).hour == SEND_HOUR_BERLIN


def report_age_hours(report: dict, now_utc: datetime) -> float:
    generated = datetime.fromisoformat(report["generated_at_utc"])
    return (now_utc - generated).total_seconds() / 3600


def is_stale(age_hours: float, now_utc: datetime) -> bool:
    limit = MAX_REPORT_AGE_HOURS_MONDAY if now_utc.astimezone(BERLIN).weekday() == 0 else MAX_REPORT_AGE_HOURS
    return age_hours > limit


def _md_safe(text: str) -> str:
    """Telegram legacy Markdown breaks on stray formatting characters in free text."""
    return "".join(ch for ch in str(text) if ch not in "_*`[]")


def format_morning_message(report: dict, now_utc: datetime, site_url: str = "") -> str:
    generated_local = datetime.fromisoformat(report["generated_at_utc"]).astimezone(BERLIN)
    age = report_age_hours(report, now_utc)

    lines = [
        f"☀️ *Scan-Status* (Stand {generated_local:%d.%m. %H:%M} Uhr)",
        f"Setups: {report.get('alerts_count', 0)} · Treffer: {report['hits_count']} · "
        f"Fehler: {len(report['errors'])}",
    ]

    if is_stale(age, now_utc):
        lines.append(f"⚠️ Der letzte Scan ist {age:.0f} h alt - bitte Lauf unter GitHub Actions prüfen.")

    if report["errors"]:
        failed = ", ".join(_md_safe(t) for t in report["errors"])
        lines.append(f"⚠️ Fehler bei: {failed}")

    alerts = report.get("alerts", [])
    if alerts:
        names = ", ".join(
            f"{_md_safe(a['name'])} ({'A-Setup' if a.get('is_a_setup') else 'Setup'})" for a in alerts
        )
        lines.append(f"🔔 Setups: {names} (Details kamen als Alarm)")
    else:
        lines.append("Kein Setup, das deine Regeln erfüllt.")

    for h in report["hits"]:
        if h.get("is_actionable"):
            continue
        p = h.get("position_suggestion") or {}
        crv = f", Netto-CRV {p['net_crv']}:1" if p.get("net_crv") is not None else ""
        lines.append(f"Treffer ohne Setup: {_md_safe(h['name'])} - {h['confirmations']}/3 Bestätigungen{crv}")

    lines.append("")
    lines.append("Abstand zum nächsten Level:")
    for r in report["all_results"]:
        side = "über" if r["distance_pct"] > 0 else "unter"
        lines.append(f"• {_md_safe(r['name'])}: {abs(r['distance_pct']):.1f} % {side} {r['nearest_level_name']}")

    if site_url:
        lines.append(f"\n🔗 {site_url}")
    return "\n".join(lines)


def _load_report(path: Path = REPORT_PATH) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Report nicht lesbar (%s): %s", path, exc)
        return None


def run(force: bool = False, now_utc: Optional[datetime] = None) -> int:
    now_utc = now_utc or datetime.now(timezone.utc)
    if not should_send(now_utc, force):
        logger.info("Nicht 08 Uhr in Berlin - nichts zu senden.")
        return 0

    token, chat_id = get_telegram_credentials()
    if not (token and chat_id):
        logger.error("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID nicht gesetzt")
        return 1

    report = _load_report()
    if report is None:
        message = "⚠️ *Scan-Status*: kein lesbarer Report gefunden - bitte Lauf unter GitHub Actions prüfen."
    else:
        message = format_morning_message(report, now_utc, site_url=load_settings().notifications.site_url)

    return 0 if send_telegram_message(token, chat_id, message) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.exit(run(force="--force" in sys.argv[1:]))

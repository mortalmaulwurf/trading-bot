"""Renders the daily/weekly market analysis as an HTML email (table layout, inline CSS, no images or scripts).

Charts are built from table cells (bars, mini price history, price ladder) so every mail client shows them
without loading images. Input is a plain dict (see docs/analyse-vorlage.md); every section is optional.
"""
from __future__ import annotations

import html as html_lib
import json
import math
import sys
from datetime import date
from typing import Any, Iterable, Optional

from .formatting import de

NAVY, INK, MUTED, LINE, BG, CARD = "#0f172a", "#0f172a", "#64748b", "#e2e8f0", "#f1f5f9", "#ffffff"
TONES = {
    "good": ("#15803d", "#dcfce7"),
    "bad": ("#b91c1c", "#fee2e2"),
    "warn": ("#b45309", "#fef3c7"),
    "neutral": ("#1d4ed8", "#dbeafe"),
    "muted": ("#475569", "#e2e8f0"),
}
WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember"]
FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MAX_BARS = 20
CSS = (
    ".c{background:#fff;border:1px solid #e2e8f0;border-radius:12px}"
    ".l{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#64748b;font-weight:700;margin:0 0 8px}"
    ".p{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600;white-space:nowrap}"
    ".pg{background:#dcfce7;color:#15803d}.pb{background:#fee2e2;color:#b91c1c}.pw{background:#fef3c7;color:#b45309}"
    ".pn{background:#dbeafe;color:#1d4ed8}.pm{background:#e2e8f0;color:#475569}"
    ".t{font-size:14px;color:#0f172a;padding:8px 0;border-top:1px solid #e2e8f0}"
    ".h{font-size:11px;color:#64748b}.n{font-size:13px;line-height:20px;color:#0f172a}"
    ".k{background:#f1f5f9;border-radius:6px}.m{width:12px;height:12px;border-radius:6px}"
    ".b{border-radius:3px}.g{background:#e2e8f0;border-radius:4px}"
)


def _esc(value: Any) -> str:
    return html_lib.escape(str(value), quote=True)


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _pct(value: Any, digits: int = 2) -> str:
    number = _finite(value)
    if number is None:
        return "–"
    return f"{'+' if number >= 0 else '−'}{de(abs(number), digits)} %"


def _tone_of(pct: Any) -> str:
    number = _finite(pct)
    if number is None or number == 0:
        return "muted"
    return "good" if number > 0 else "bad"


PILL_CLASS = {"good": "pg", "bad": "pb", "warn": "pw", "neutral": "pn", "muted": "pm"}


def _pill(text: Any, tone: str = "muted") -> str:
    return f'<span class="p {PILL_CLASS.get(tone, "pm")}">{_esc(text)}</span>'


def _de_date(iso: Any) -> str:
    try:
        d = date.fromisoformat(str(iso))
    except ValueError:
        return _esc(iso)
    return f"{WEEKDAYS[d.weekday()]}, {d.day}. {MONTHS[d.month - 1]} {d.year}"


def _label(text: str) -> str:
    return f'<div class="l">{text}</div>'


def _card(inner: str, title: str = "") -> str:
    head = _label(_esc(title)) if title else ""
    return (f'<tr><td style="padding:0 16px 14px"><table width="100%" cellpadding="0" cellspacing="0" class="c">'
            f'<tr><td style="padding:16px">{head}{inner}</td></tr></table></td></tr>')


def _sparkline(closes: Iterable[Any], height: int = 46) -> str:
    values = [v for v in (_finite(c) for c in closes) if v is not None][-MAX_BARS:]
    if len(values) < 2:
        return ""
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    cells = []
    for i, v in enumerate(values):
        h = 6 + round((v - low) / span * (height - 6))
        color = "#94a3b8" if i == 0 else ("#16a34a" if v >= values[i - 1] else "#dc2626")
        cells.append(f'<td valign="bottom"><div style="height:{h}px;background:{color}"></div></td>')
    return (f'<table width="100%" height="{height}" cellpadding="0" cellspacing="1" style="table-layout:fixed">'
            f'<tr>{"".join(cells)}</tr></table>'
            f'<div class="h" style="margin-top:4px">Schlusskurse, letzte {len(values)} Handelstage '
            f'(grün: Anstieg zum Vortag, rot: Rückgang; Skala beginnt beim Tiefstwert)</div>')


def _perf_chart(items: list[dict]) -> str:
    rows = [(str(i.get("label", "")), _finite(i.get("pct"))) for i in items]
    rows = [(label, pct) for label, pct in rows if pct is not None]
    if not rows:
        return ""
    peak = max(abs(p) for _, p in rows) or 1.0
    out = []
    for label, pct in rows:
        width = max(3, round(abs(pct) / peak * 100))
        color = "#16a34a" if pct >= 0 else "#dc2626"
        align = "" if pct >= 0 else ' align="right"'
        bar = (f'<table width="{width}%" cellpadding="0" cellspacing="0"{align}><tr>'
               f'<td height="14" class="b" style="background:{color}"></td></tr></table>')
        neg = bar if pct < 0 else ""
        pos = bar if pct >= 0 else ""
        out.append(
            f'<tr><td width="30%" style="font-size:13px;padding:4px 8px 4px 0;color:{INK}">{_esc(label)}</td>'
            f'<td width="28%" style="padding:4px 0;border-right:1px solid {LINE}">{neg}</td>'
            f'<td width="28%" style="padding:4px 0">{pos}</td>'
            f'<td width="14%" align="right" style="font-size:13px;font-weight:600;padding:4px 0 4px 8px;'
            f'color:{TONES[_tone_of(pct)][0]}">{_pct(pct, 1)}</td></tr>')
    return f'<table width="100%" cellpadding="0" cellspacing="0">{"".join(out)}</table>'


def _ladder(levels: dict, close: Optional[float]) -> str:
    entries = [(name, _finite(levels.get(key))) for name, key in (("VAH", "vah"), ("POC", "poc"), ("VAL", "val"))]
    entries = [(n, p) for n, p in entries if p is not None]
    if close is not None:
        entries.append(("Schluss", close))
    if len(entries) < 2:
        return ""
    entries.sort(key=lambda e: e[1], reverse=True)
    low, high = min(p for _, p in entries), max(p for _, p in entries)
    span = (high - low) or 1.0
    rows = []
    for name, price in entries:
        pos = 6 + round((price - low) / span * 84)
        is_close = name == "Schluss"
        color = NAVY if is_close else "#2563eb"
        dist = "" if is_close or close in (None, 0) else _pct((price / close - 1) * 100, 1)
        rows.append(
            f'<tr><td width="16%" style="font-size:13px;padding:5px 0;color:{INK};font-weight:{700 if is_close else 500}">'
            f'{name}</td><td width="20%" align="right" style="font-size:13px;padding:5px 8px;color:{INK}">'
            f'{de(price, 2 if price < 1000 else 0)}</td>'
            f'<td width="14%" align="right" class="h" style="padding:5px 8px 5px 0">{dist}</td>'
            f'<td width="50%" style="padding:5px 0"><table width="100%" cellpadding="0" cellspacing="0" class="k"><tr>'
            f'<td width="{pos}%" height="12"></td><td class="m" style="background:{color}"></td><td></td>'
            f'</tr></table></td></tr>')
    note = ('<div class="h" style="margin-top:2px">Value Area: VAL bis VAH (70 % des Volumens), '
            'POC: Preis mit dem meisten Volumen. Abstand zum Schluss in Prozent.</div>')
    return f'<table width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>{note}'


def _rsi_gauge(rsi: Optional[float]) -> str:
    if rsi is None:
        return ""
    width = max(2, min(100, round(rsi)))
    tone = "neutral" if rsi < 30 else ("bad" if rsi > 70 else "muted")
    color = {"neutral": "#2563eb", "bad": "#dc2626", "muted": "#64748b"}[tone]
    zone = "überverkauft" if rsi < 30 else ("überkauft" if rsi > 70 else "neutral")
    return (f'<table width="100%" cellpadding="0" cellspacing="0"><tr><td width="60" class="h">RSI {de(rsi, 1)}</td>'
            f'<td><table width="100%" cellpadding="0" cellspacing="0" class="g"><tr>'
            f'<td width="{width}%" height="8" class="g" style="background:{color}"></td><td></td></tr></table></td>'
            f'<td width="80" align="right" class="h">{zone}</td></tr></table>')


def _trend_tone(rating: str) -> str:
    upper = rating.upper()
    if "BUY" in upper:
        return "good"
    return "bad" if "SELL" in upper else "muted"


def _header(data: dict) -> str:
    kind = "Wochenausblick" if data.get("mode") == "weekly" else "Tagesbriefing"
    return (f'<tr><td style="background:{NAVY};padding:22px 24px;border-radius:0 0 0 0">'
            f'<div style="font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#94a3b8;font-weight:700">'
            f'{kind}</div><div style="font-size:24px;line-height:30px;color:#ffffff;font-weight:700;margin-top:2px">'
            f'Marktanalyse</div><div style="font-size:14px;color:#cbd5e1;margin-top:4px">{_de_date(data.get("date", ""))}'
            f'</div></td></tr>')


def _verdict(data: dict) -> str:
    verdict = data.get("verdict")
    if not isinstance(verdict, dict):
        return ""
    color, bg = TONES.get(str(verdict.get("tone", "neutral")), TONES["neutral"])
    text = f'<div style="font-size:14px;line-height:21px;color:{INK};margin-top:6px">{_esc(verdict["text"])}</div>' \
        if verdict.get("text") else ""
    return (f'<tr><td style="padding:16px 16px 14px"><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0" border="0" style="background:{bg};border-left:5px solid {color};border-radius:8px">'
            f'<tr><td style="padding:14px 16px"><div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;'
            f'color:{color};font-weight:700">Fazit</div><div style="font-size:20px;font-weight:700;color:{color};'
            f'margin-top:2px">{_esc(verdict.get("label", ""))}</div>{text}</td></tr></table></td></tr>')


def _snapshot(instruments: list[dict]) -> str:
    rows = []
    for ins in instruments:
        close = _finite(ins.get("close"))
        price = "–" if close is None else de(close, 2 if close < 1000 else 0)
        rows.append(
            f'<tr><td class="t" style="font-weight:600">{_esc(ins.get("name", ""))}'
            f'<div class="h" style="font-weight:400">{_esc(ins.get("basis", ""))}</div></td>'
            f'<td align="right" class="t">{price}</td>'
            f'<td align="right" class="t" style="padding-left:10px">'
            f'{_pill(_pct(ins.get("day_pct")), _tone_of(ins.get("day_pct")))}</td>'
            f'<td align="right" class="t" style="padding-left:10px">'
            f'{_pill(_pct(ins.get("week_pct")), _tone_of(ins.get("week_pct")))}</td></tr>')
    head = ('<tr><td class="h">Instrument</td><td align="right" class="h">Schluss</td>'
            '<td align="right" class="h" style="padding-left:10px">Tag</td>'
            '<td align="right" class="h" style="padding-left:10px">Woche</td></tr>')
    table = f'<table width="100%" cellpadding="0" cellspacing="0">{head}{"".join(rows)}</table>'
    return _card(table, "Auf einen Blick")


def _instrument_card(ins: dict) -> str:
    close = _finite(ins.get("close"))
    pills = []
    for key, text in (("trend_day", "Tag"), ("trend_week", "Woche")):
        rating = ins.get(key)
        if rating:
            pills.append(_pill(f"{text}: {rating}", _trend_tone(str(rating))))
    if ins.get("candle"):
        pills.append(_pill(f"Kerze {ins['candle']}", "good" if str(ins["candle"]).startswith("gr") else "bad"))
    setup = str(ins.get("setup", "")).strip()
    if setup:
        pills.append(_pill(f"Setup: {setup}", "good" if setup.lower().startswith("ja") else "muted"))
    price = "" if close is None else (
        f'<span style="font-size:22px;font-weight:700;color:{INK}">{de(close, 2 if close < 1000 else 0)}</span> '
        f'{_pill(_pct(ins.get("day_pct")), _tone_of(ins.get("day_pct")))}')
    parts = [
        f'<div style="font-size:16px;font-weight:700;color:{INK}">{_esc(ins.get("name", ""))} '
        f'<span style="font-size:12px;font-weight:400;color:{MUTED}">{_esc(ins.get("basis", ""))}</span></div>',
        f'<div style="margin:6px 0 10px">{price}</div>',
        f'<div style="margin-bottom:12px">{" ".join(pills)}</div>',
    ]
    spark = _sparkline(ins.get("closes") or [])
    if spark:
        parts.append(f'<div style="margin-bottom:14px">{spark}</div>')
    ladder = _ladder(ins.get("levels") or {}, close)
    if ladder:
        parts.append(f'<div style="margin-bottom:12px">{_label("Preisleiter")}{ladder}</div>')
    rsi = _finite(ins.get("rsi"))
    adx = _finite(ins.get("adx"))
    gauge = _rsi_gauge(rsi)
    if gauge:
        adx_text = "" if adx is None else (f'<div class="h" style="margin-top:4px">ADX {de(adx, 0)}: '
                                           f'{"Trend vorhanden" if adx >= 25 else "kein klarer Trend"}</div>')
        parts.append(f'<div style="margin-bottom:8px">{gauge}{adx_text}</div>')
    if ins.get("note"):
        parts.append(f'<div class="n" style="margin-top:6px">{_esc(ins["note"])}</div>')
    return _card("".join(parts))


def _market(items: list[dict]) -> str:
    rows = []
    for m in items:
        tone = str(m.get("tone") or _tone_of(m.get("change_pct")))
        change = "" if m.get("change_pct") is None else _pill(_pct(m.get("change_pct")), _tone_of(m.get("change_pct")))
        rows.append(
            f'<tr><td class="t" style="font-weight:600">{_esc(m.get("label", ""))}</td>'
            f'<td align="right" class="t">{_esc(m.get("value", ""))}</td>'
            f'<td align="right" class="t" style="padding-left:10px">{change}</td>'
            f'<td class="t" style="padding-left:12px;font-size:12px;color:{TONES.get(tone, TONES["muted"])[0]}">'
            f'{_esc(m.get("note", ""))}</td></tr>')
    return _card(f'<table width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>', "Marktdaten")


def _events(events: list[dict]) -> str:
    out, last_day = [], None
    for ev in events:
        if ev.get("day") != last_day:
            last_day = ev.get("day")
            out.append(f'<div style="font-size:12px;font-weight:700;color:{MUTED};text-transform:uppercase;'
                       f'letter-spacing:.06em;margin:14px 0 6px">{_esc(last_day or "")}</div>')
        importance = int(_finite(ev.get("importance")) or 1)
        tone = "bad" if importance >= 3 else ("warn" if importance == 2 else "muted")
        importance_label = {3: "Hoch", 2: "Mittel"}.get(importance, "Normal")
        facts = " · ".join(f"{k} {_esc(ev[key])}" for key, k in (("forecast", "Prognose"), ("previous", "zuvor"))
                           if ev.get(key))
        lines = "".join(
            f'<div style="font-size:13px;line-height:20px;color:{INK};margin-top:4px"><b style="color:{MUTED}">{title}:</b> '
            f'{_esc(ev[key])}</div>'
            for key, title in (("why", "Warum wichtig"), ("watch", "Worauf achten"), ("reaction", "Mögliche Reaktion"))
            if ev.get(key))
        out.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid {LINE};'
            f'border-left:4px solid {TONES[tone][0]};border-radius:8px;margin-bottom:8px"><tr><td style="padding:10px 12px">'
            f'<div style="font-size:14px;font-weight:700;color:{INK}">{_esc(ev.get("time", ""))} {_esc(ev.get("title", ""))} '
            f'{_pill(importance_label, tone)}</div>'
            f'<div style="font-size:12px;color:{MUTED};margin-top:2px">{facts}</div>{lines}</td></tr></table>')
    return _card("".join(out), "Termine und Lernhilfe")


def _list_card(title: str, items: list[str], mark: str = "•") -> str:
    rows = "".join(f'<tr><td width="18" valign="top" style="font-size:14px;color:{MUTED}">{mark}</td>'
                   f'<td style="font-size:13px;line-height:20px;color:{INK};padding-bottom:6px">{_esc(i)}</td></tr>'
                   for i in items)
    return _card(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>', title)


def render_subject(data: dict) -> str:
    verdict = data.get("verdict") or {}
    first = (data.get("instruments") or [{}])[0]
    kind = "Wochenausblick" if data.get("mode") == "weekly" else "Marktanalyse"
    parts = [f"{kind} {_de_date(data.get('date', '')).split(', ', 1)[-1]}"]
    if isinstance(verdict, dict) and verdict.get("label"):
        parts.append(str(verdict["label"]))
    if first.get("name") and _finite(first.get("day_pct")) is not None:
        parts.append(f"{first['name']} {_pct(first['day_pct'], 1)}")
    return " · ".join(parts)


def render_email(data: dict) -> str:
    instruments = [i for i in data.get("instruments") or [] if isinstance(i, dict)]
    perf = data.get("perf") or [{"label": i.get("name"), "pct": i.get("week_pct")} for i in instruments]
    sections = [_header(data), _verdict(data)]
    if instruments:
        sections.append(_snapshot(instruments))
    chart = _perf_chart([p for p in perf if isinstance(p, dict)])
    if chart:
        sections.append(_card(chart, "Wochenperformance"))
    sections += [_instrument_card(i) for i in instruments]
    if data.get("market"):
        sections.append(_market([m for m in data["market"] if isinstance(m, dict)]))
    if data.get("events"):
        sections.append(_events([e for e in data["events"] if isinstance(e, dict)]))
    if data.get("alerts"):
        sections.append(_list_card("Alarme für heute", [str(a.get("text", a)) if isinstance(a, dict) else str(a) for a in data["alerts"]], "🔔"))
    if data.get("rules"):
        sections.append(_list_card("Regel-Check", [str(r) for r in data["rules"]], "✓"))
    if data.get("gaps"):
        sections.append(_list_card("Lücken und Unsicherheiten", [str(g) for g in data["gaps"]], "!"))
    footer = (f'<tr><td style="padding:6px 24px 24px;font-size:11px;line-height:17px;color:{MUTED}">Nur Anzeige und Lernhilfe, '
              f'keine Anlageberatung, es werden keine Orders platziert. Quellen: TradingView, Trading-Bot-Report. '
              f'{_esc(data.get("generated_at", ""))}</td></tr>')
    body = "".join(sections) + footer
    return (f'<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>Marktanalyse</title>'
            f'<style>{CSS}</style></head><body style="margin:0;padding:0;background:{BG};font-family:{FONT}"><table role="presentation" width="100%" '
            f'cellpadding="0" cellspacing="0" border="0" style="background:{BG}"><tr><td align="center">'
            f'<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:640px;'
            f'background:{BG}">{body}</table></td></tr></table></body></html>')


def render_text(data: dict) -> str:
    """Plain-text alternative for mail clients without HTML."""
    verdict = data.get("verdict") or {}
    lines = [f"MARKTANALYSE {_de_date(data.get('date', ''))}"]
    if isinstance(verdict, dict) and verdict.get("label"):
        lines += ["", f"Fazit: {verdict['label']}", str(verdict.get("text", ""))]
    for ins in data.get("instruments") or []:
        lines.append(f"- {ins.get('name')}: {ins.get('close')} (Tag {_pct(ins.get('day_pct'))}, Woche {_pct(ins.get('week_pct'))})")
    for ev in data.get("events") or []:
        lines.append(f"{ev.get('day', '')} {ev.get('time', '')} {ev.get('title', '')}")
    lines += ["", "Nur Anzeige und Lernhilfe, keine Anlageberatung."]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: python -m src.analysis_mail input.json output.html [output.txt]")
    with open(sys.argv[1], encoding="utf-8") as f:
        payload = json.load(f)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(render_email(payload))
    if len(sys.argv) > 3:
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            f.write(render_text(payload))
    print(render_subject(payload))

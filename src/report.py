"""Erzeugt JSON- und Markdown-Reports aus den Analyseergebnissen."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .html_report import render_html
from .signal_engine import TickerAnalysis

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SITE_DIR = Path(__file__).resolve().parent.parent / "site"


def _analysis_to_dict(a: TickerAnalysis) -> dict:
    d = {
        "ticker": a.ticker,
        "name": a.display_name,
        "current_price": round(a.current_price, 4),
        "currency": a.currency,
        "poc": round(a.profile.poc, 4),
        "val": round(a.profile.val, 4),
        "vah": round(a.profile.vah, 4),
        "nearest_level_name": a.nearest_level_name,
        "nearest_level_price": round(a.nearest_level_price, 4),
        "distance_pct": round(a.distance_pct, 2),
        "is_hit": a.is_hit,
        "rsi": round(a.rsi_value, 1) if a.rsi_value is not None else None,
        "rsi_oversold": a.rsi_oversold,
        "volume_spike": a.volume_spike,
        "intraday_momentum_up": a.intraday_momentum_up,
        "confirmations": a.confirmations,
        "confidence": a.confidence,
        "confluence": a.confluence,
        "confluence_level_name": a.confluence_level_name,
        "weekly_trend": a.weekly_trend,
        "upcoming_events": a.upcoming_events,
    }
    if a.long_profile:
        d["long_poc"] = round(a.long_profile.poc, 4)
        d["long_val"] = round(a.long_profile.val, 4)
        d["long_vah"] = round(a.long_profile.vah, 4)
    if a.position_suggestion:
        p = a.position_suggestion
        d["position_suggestion"] = {
            "entry_price": round(p.entry_price, 4),
            "stop_price": round(p.stop_price, 4),
            "stop_distance_pct": round(p.stop_distance_pct, 2),
            "shares": round(p.shares, 2),
            "position_value_eur": round(p.position_value_eur, 2),
            "margin_required_eur": round(p.margin_required_eur, 2),
        }
    return d


def build_report(results: list[TickerAnalysis], errors: dict[str, str], threshold_pct: float) -> dict:
    now = datetime.now(timezone.utc)
    hits = [r for r in results if r.is_hit]
    return {
        "generated_at_utc": now.isoformat(),
        "proximity_threshold_pct": threshold_pct,
        "tickers_analyzed": len(results),
        "hits_count": len(hits),
        "hits": [_analysis_to_dict(r) for r in sorted(hits, key=lambda r: abs(r.distance_pct))],
        "all_results": [_analysis_to_dict(r) for r in results],
        "errors": errors,
    }


def _format_markdown(report: dict) -> str:
    lines = [
        f"# Swing-Trading Scan – {report['generated_at_utc']}",
        "",
        f"Analysiert: {report['tickers_analyzed']} Ticker · Treffer: {report['hits_count']} "
        f"(Schwelle: ±{report['proximity_threshold_pct']}% um POC/VAL)",
        "",
    ]

    if report["hits"]:
        lines.append("## Treffer\n")
        for h in report["hits"]:
            lines.append(f"### {h['name']} ({h['ticker']}) – {h['confidence']}")
            lines.append(
                f"- Kurs: {h['current_price']} {h['currency']} · "
                f"Level: {h['nearest_level_name']} @ {h['nearest_level_price']} "
                f"(Abstand {h['distance_pct']:+.2f}%)"
            )
            lines.append(f"- Volumenprofil: POC {h['poc']} · VAL {h['val']} · VAH {h['vah']}")
            if "long_poc" in h:
                lines.append(
                    f"- Langfristiges Volumenprofil (Kontext): POC {h['long_poc']} · "
                    f"VAL {h['long_val']} · VAH {h['long_vah']}"
                    + (f" — ✅ Konfluenz mit {h['confluence_level_name']}" if h["confluence"] else "")
                )
            if h.get("weekly_trend"):
                trend_note = "✅ im Einklang" if h["weekly_trend"] == "aufwärts" else "⚠️ spricht dagegen"
                lines.append(f"- Wochentrend: {h['weekly_trend']} ({trend_note} mit einem Long-Einstieg)")
            if h.get("upcoming_events"):
                lines.append(f"- ⚠️ Bevorstehende Termine: {'; '.join(h['upcoming_events'])} (Gap-Risiko beachten)")
            lines.append(
                f"- Bestätigungen ({h['confirmations']}/3): "
                f"RSI {h['rsi']}{' (überverkauft)' if h['rsi_oversold'] else ''} · "
                f"Volumen-Spike {'ja' if h['volume_spike'] else 'nein'} · "
                f"Intraday-Momentum {'dreht hoch' if h['intraday_momentum_up'] else 'neutral'}"
            )
            if "position_suggestion" in h:
                p = h["position_suggestion"]
                lines.append(
                    f"- Größenvorschlag (max. 10€ Risiko, Stop {p['stop_price']} / "
                    f"{p['stop_distance_pct']:.2f}% Abstand): ~{p['shares']:.2f} Stück · "
                    f"Positionswert ~{p['position_value_eur']:.2f}€ · "
                    f"Margin bei 2er-Hebel ~{p['margin_required_eur']:.2f}€"
                )
            lines.append("")
    else:
        lines.append("_Keine Treffer in diesem Lauf._\n")

    lines.append("## Alle beobachteten Instrumente\n")
    lines.append("| Instrument | Kurs | Nächstes Level | Abstand % | RSI | Wochentrend | Treffer |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in report["all_results"]:
        lines.append(
            f"| {r['name']} ({r['ticker']}) | {r['current_price']} {r['currency']} | "
            f"{r['nearest_level_name']} @ {r['nearest_level_price']} | {r['distance_pct']:+.2f}% | "
            f"{r['rsi']} | {r.get('weekly_trend') or '–'} | {'✅' if r['is_hit'] else '–'} |"
        )

    events_by_ticker = {
        (r["name"], r["ticker"]): r["upcoming_events"] for r in report["all_results"] if r.get("upcoming_events")
    }
    if events_by_ticker:
        lines.append("\n## Bevorstehende Termine\n")
        for (name, ticker), events in events_by_ticker.items():
            lines.append(f"- **{name} ({ticker})**: {'; '.join(events)}")

    if report["errors"]:
        lines.append("\n## Fehler\n")
        for ticker, err in report["errors"].items():
            lines.append(f"- {ticker}: {err}")

    lines.append(
        "\n---\n_Nur zur Analyse-Unterstützung, keine automatisch ausgeführten Trades. "
        "Positionsgrößen sind informative Vorschläge auf Basis der hinterlegten Risiko-Parameter "
        "(config/settings.yaml) und einer vereinfachten Stop-Referenz (1% unter VAL). "
        "Termine sind Näherungswerte (Earnings via yfinance-Schätzung, Makro-Termine manuell in "
        "config/macro_events.yaml gepflegt) – bitte vor einem Einstieg selbst gegenprüfen._\n\n"
        "_**Glossar:** POC = Point of Control (Preis mit dem höchsten Handelsvolumen im Zeitraum) · "
        "VAL/VAH = Value Area Low/High (untere/obere Grenze der Kern-Handelszone, 70% des Volumens) · "
        "RSI = Relative-Stärke-Index (0–100, Werte ≤30 gelten als überverkauft)._"
    )
    return "\n".join(lines)


def write_reports(report: dict) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    json_path = REPORTS_DIR / f"{date_str}.json"
    md_path = REPORTS_DIR / f"{date_str}.md"
    latest_json = REPORTS_DIR / "latest.json"
    latest_md = REPORTS_DIR / "latest.md"

    json_text = json.dumps(report, indent=2, ensure_ascii=False)
    md_text = _format_markdown(report)

    for path in (json_path, latest_json):
        path.write_text(json_text, encoding="utf-8")
    for path in (md_path, latest_md):
        path.write_text(md_text, encoding="utf-8")

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(render_html(report), encoding="utf-8")

    return md_path, json_path

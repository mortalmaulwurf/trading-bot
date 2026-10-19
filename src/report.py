"""Erzeugt JSON- und Markdown-Reports aus den Analyseergebnissen."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typing import Optional

from .config import AnalysisSettings, RiskSettings
from .html_report import render_html
from .signal_engine import TickerAnalysis

# Version of the JSON contract consumed by dashboards. Bump on breaking changes.
REPORT_SCHEMA_VERSION = 2

# Version of reports/charts.json (candles per ticker for dashboard and HTML charts).
CHARTS_SCHEMA_VERSION = 1

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
SITE_DIR = Path(__file__).resolve().parent.parent / "site"


def _analysis_to_dict(a: TickerAnalysis) -> dict:
    d = {
        "ticker": a.ticker,
        "name": a.display_name,
        "current_price": round(a.current_price, 4),
        "currency": a.currency,
        "profile_basis": a.profile_basis,
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
        "daily_close_reversal": a.daily_close_reversal,
        "rule_checks": a.rule_checks,
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
    d["is_actionable"] = a.is_actionable
    d["is_a_setup"] = a.is_a_setup
    if a.position_suggestion:
        p = a.position_suggestion
        suggestion = {
            "entry_price": round(p.entry_price, 4),
            "stop_price": round(p.stop_price, 4),
            "target_price": round(p.target_price, 4) if p.target_price is not None else None,
            "target_name": a.target_name,
            "stop_distance_pct": round(p.stop_distance_pct, 2),
            "leverage": p.leverage,
            "max_leverage_by_buffer": p.max_leverage_by_buffer,
            "min_ko_distance_pct": round(p.min_ko_distance_pct, 2),
            "ko_level": round(p.ko_level, 4),
            "capital_eur": round(p.capital_eur, 2),
            "exposure_eur": round(p.exposure_eur, 2),
            "costs_eur": round(p.costs_eur, 2),
            "total_loss_eur": round(p.total_loss_eur, 2),
            "capped": p.capped,
            "gross_crv": round(p.gross_crv, 2) if p.gross_crv is not None else None,
            "net_crv": round(p.net_crv, 2) if p.net_crv is not None else None,
            "required_target_price": round(p.required_target_price, 4),
            "required_target_pct": round(p.required_target_pct, 2),
        }
        if a.index_ratio:
            ratio = a.index_ratio
            suggestion["index_levels"] = {
                "entry": round(p.entry_price * ratio, 2),
                "stop": round(p.stop_price * ratio, 2),
                "target": round(p.target_price * ratio, 2) if p.target_price is not None else None,
                "required_target": round(p.required_target_price * ratio, 2),
            }
        d["position_suggestion"] = suggestion
    return d


def build_report(
    results: list[TickerAnalysis],
    errors: dict[str, str],
    threshold_pct: float,
    risk_settings: RiskSettings,
    analysis_settings: Optional[AnalysisSettings] = None,
) -> dict:
    now = datetime.now(timezone.utc)
    hits = [r for r in results if r.is_hit]
    alerts = sorted(
        (r for r in results if r.is_actionable),
        key=lambda r: (not r.is_a_setup, -(r.position_suggestion.net_crv or 0)),
    )
    if errors and results:
        status = "partial"
    elif errors:
        status = "failed"
    else:
        status = "ok"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": status,
        "rule_set": {
            "min_net_crv": risk_settings.min_net_crv,
            "a_setup_net_crv": risk_settings.a_setup_net_crv,
            "max_risk_per_trade_eur": risk_settings.max_risk_per_trade_eur,
            "max_position_eur": risk_settings.max_position_eur,
            "require_daily_close_reversal": (
                analysis_settings.require_daily_close_reversal if analysis_settings else None
            ),
            "profile_anchor_date": analysis_settings.profile_anchor_date if analysis_settings else None,
        },
        "min_net_crv": risk_settings.min_net_crv,
        "a_setup_net_crv": risk_settings.a_setup_net_crv,
        "alerts_count": len(alerts),
        "alerts": [_analysis_to_dict(r) for r in alerts],
        "generated_at_utc": now.isoformat(),
        "proximity_threshold_pct": threshold_pct,
        "tickers_analyzed": len(results),
        "hits_count": len(hits),
        "hits": [_analysis_to_dict(r) for r in sorted(hits, key=lambda r: abs(r.distance_pct))],
        "all_results": [_analysis_to_dict(r) for r in results],
        "errors": errors,
    }


def format_plan_lines_md(h: dict, report: dict) -> list[str]:
    """Plan lines (entry, stop, target, leverage, costs, net CRV) for one hit."""
    p = h.get("position_suggestion")
    if not p:
        return ["- Plan: kein Plan berechenbar (Stop nicht unter dem Kurs)."]
    target = (
        f"{p['target_price']} ({p['target_name']})" if p["target_price"] is not None else "kein Level oberhalb"
    )
    lines = [
        f"- Plan (Long): Einstieg {p['entry_price']} · Stop {p['stop_price']} "
        f"({p['stop_distance_pct']:.2f}% Abstand, Level minus ATR) · Ziel {target}",
        f"- Hebel {p['leverage']}× (max. {p['max_leverage_by_buffer']}× nach KO-Puffer, KO-Abstand mind. "
        f"{p['min_ko_distance_pct']:.2f}%) · Einsatz {p['capital_eur']:.2f}€ · "
        f"Kosten {p['costs_eur']:.2f}€ · Verlust am Stop {p['total_loss_eur']:.2f}€",
    ]
    if p["net_crv"] is not None:
        if h.get("is_a_setup"):
            verdict = "✅ A-Setup"
        elif h.get("is_actionable"):
            verdict = "✅ Mindest-CRV erfüllt"
        else:
            verdict = f"❌ unter Mindest {report['min_net_crv']}:1"
        lines.append(f"- CRV brutto {p['gross_crv']}:1 · netto {p['net_crv']}:1 ({verdict})")
    else:
        lines.append("- CRV: nicht berechenbar (kein Ziel-Level oberhalb des Kurses)")
    lines.append(
        f"- Mindest-Ziel für {report['min_net_crv']}:1 netto: {p['required_target_price']} "
        f"(+{p['required_target_pct']:.2f}%)"
    )
    idx = p.get("index_levels")
    if idx:
        lines.append(
            f"- Indexwerte für Rechner/Zertifikat: Einstieg {idx['entry']} · Stop {idx['stop']} · "
            f"Ziel {idx['target']} · Mindest-Ziel {idx['required_target']}"
        )
    return lines


def _format_markdown(report: dict) -> str:
    lines = [
        f"# Swing-Trading Scan – {report['generated_at_utc']}",
        "",
        f"Analysiert: {report['tickers_analyzed']} Ticker · Treffer: {report['hits_count']} "
        f"(Schwelle: ±{report['proximity_threshold_pct']}% um POC/VAL)",
        "",
    ]

    if report["alerts"]:
        lines.append(f"## Setups (Telegram-Alarm, Netto-CRV ≥ {report['min_net_crv']}:1)\n")
        for a in report["alerts"]:
            tag = "A-Setup" if a.get("is_a_setup") else "Setup"
            lines.append(f"- **{a['name']} ({a['ticker']})** – {tag}, {a['confirmations']}/3 Bestätigungen")
        lines.append("")

    if report["hits"]:
        lines.append("## Treffer\n")
        for h in report["hits"]:
            lines.append(f"### {h['name']} ({h['ticker']}) – {h['confidence']}")
            lines.append(
                f"- Kurs: {h['current_price']} {h['currency']} · "
                f"Level: {h['nearest_level_name']} @ {h['nearest_level_price']} "
                f"(Abstand {h['distance_pct']:+.2f}%)"
            )
            basis = f" ({h['profile_basis']})" if h.get("profile_basis") else ""
            lines.append(f"- Volumenprofil{basis}: POC {h['poc']} · VAL {h['val']} · VAH {h['vah']}")
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
            checks = h.get("rule_checks") or {}
            reversal_mark = "✅" if checks.get("daily_close_reversal") else "❌"
            reversal_note = "" if checks.get("reversal_required", True) else " (nicht erforderlich)"
            crv_mark = "✅" if checks.get("net_crv_ok") else "❌"
            lines.append(
                f"- Regel-Check: Umkehr (Tagesschluss über Level) {reversal_mark}{reversal_note} · "
                f"Netto-CRV ≥ {report['min_net_crv']}:1 {crv_mark}"
            )
            lines.extend(format_plan_lines_md(h, report))
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
        "Pläne und Positionsgrößen sind informative Vorschläge auf Basis der hinterlegten Risiko-Parameter "
        "(config/settings.yaml) und einer vereinfachten Stop-Referenz (Level minus ATR). Das Ziel ist das nächste strukturelle Level oberhalb des Kurses. "
        "Termine sind Näherungswerte (Earnings via yfinance-Schätzung, Makro-Termine manuell in "
        "config/macro_events.yaml gepflegt) – bitte vor einem Einstieg selbst gegenprüfen._\n\n"
        "_**Glossar:** POC = Point of Control (Preis mit dem höchsten Handelsvolumen im Zeitraum) · "
        "VAL/VAH = Value Area Low/High (untere/obere Grenze der Kern-Handelszone, 70% des Volumens) · "
        "RSI = Relative-Stärke-Index (0–100, Werte ≤30 gelten als überverkauft)._"
    )
    return "\n".join(lines)


def build_charts(results: list[TickerAnalysis], generated_at_utc: str) -> dict:
    """Daily candles per ticker. Kept out of latest.json so the archived daily reports stay small."""
    return {
        "schema_version": CHARTS_SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc,
        "charts": {r.ticker: {"currency": r.currency, "candles": r.candles} for r in results},
    }


def write_reports(report: dict, charts: Optional[dict] = None) -> tuple[Path, Path]:
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

    if charts is not None:
        (REPORTS_DIR / "charts.json").write_text(json.dumps(charts, separators=(",", ":")), encoding="utf-8")

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(render_html(report), encoding="utf-8")

    return md_path, json_path

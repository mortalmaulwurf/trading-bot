"""Erzeugt eine einfache, eigenständige HTML-Übersichtsseite aus dem Report –
gedacht zum Hosten auf einer statischen Seite (z.B. Render Static Site),
damit die Zusammenfassung schnell im Browser/Handy aufrufbar ist.

Kein externes CSS/JS, keine Build-Schritte nötig – die Datei ist direkt
servierbar.
"""
from __future__ import annotations

import html as html_lib


def _esc(value) -> str:
    return html_lib.escape(str(value))


def _confidence_badge_class(confidence: str) -> str:
    if confidence == "stark":
        return "badge-strong"
    if confidence == "moderat":
        return "badge-moderate"
    return "badge-weak"


def _hit_card(h: dict) -> str:
    parts = [
        '<div class="card hit">',
        f'<h3>{_esc(h["name"])} <span class="ticker">({_esc(h["ticker"])})</span></h3>',
        f'<span class="badge {_confidence_badge_class(h["confidence"])}">{_esc(h["confidence"])}</span>',
        f'<p>Kurs: <strong>{_esc(h["current_price"])} {_esc(h["currency"])}</strong> · '
        f'Level: {_esc(h["nearest_level_name"])} @ {_esc(h["nearest_level_price"])} '
        f'({h["distance_pct"]:+.2f}%)</p>',
        f'<p class="muted">Volumenprofil: POC {_esc(h["poc"])} · VAL {_esc(h["val"])} · VAH {_esc(h["vah"])}</p>',
    ]

    if "long_poc" in h:
        confluence_txt = (
            f' — ✅ Konfluenz mit {_esc(h["confluence_level_name"])}' if h["confluence"] else ""
        )
        parts.append(
            f'<p class="muted">Langfristig (Kontext): POC {_esc(h["long_poc"])} · '
            f'VAL {_esc(h["long_val"])} · VAH {_esc(h["long_vah"])}{confluence_txt}</p>'
        )

    if h.get("weekly_trend"):
        icon = "✅" if h["weekly_trend"] == "aufwärts" else "⚠️"
        parts.append(f'<p>{icon} Wochentrend: {_esc(h["weekly_trend"])}</p>')

    if h.get("upcoming_events"):
        parts.append(f'<p class="warning">⚠️ Termine: {_esc("; ".join(h["upcoming_events"]))}</p>')

    parts.append(
        f'<p>Bestätigungen ({h["confirmations"]}/3): RSI {_esc(h["rsi"])}'
        f'{" (überverkauft)" if h["rsi_oversold"] else ""} · '
        f'Volumen-Spike {"ja" if h["volume_spike"] else "nein"} · '
        f'Intraday-Momentum {"dreht hoch" if h["intraday_momentum_up"] else "neutral"}</p>'
    )

    if "position_suggestion" in h:
        p = h["position_suggestion"]
        parts.append(
            f'<p class="muted">Größenvorschlag (max. 10€ Risiko, Stop {_esc(p["stop_price"])}): '
            f'~{p["shares"]:.2f} Stück · Positionswert ~{p["position_value_eur"]:.2f}€ · '
            f'Margin bei 2er-Hebel ~{p["margin_required_eur"]:.2f}€</p>'
        )

    parts.append("</div>")
    return "\n".join(parts)


def _overview_row(r: dict) -> str:
    row_class = "hit-row" if r["is_hit"] else ""
    return (
        f'<tr class="{row_class}">'
        f'<td>{_esc(r["name"])} <span class="ticker">({_esc(r["ticker"])})</span></td>'
        f'<td>{_esc(r["current_price"])} {_esc(r["currency"])}</td>'
        f'<td>{_esc(r["nearest_level_name"])} @ {_esc(r["nearest_level_price"])}</td>'
        f'<td>{r["distance_pct"]:+.2f}%</td>'
        f'<td>{_esc(r["rsi"])}</td>'
        f'<td>{_esc(r.get("weekly_trend") or "–")}</td>'
        f'<td>{"✅" if r["is_hit"] else "–"}</td>'
        "</tr>"
    )


def render_html(report: dict) -> str:
    hits_html = "\n".join(_hit_card(h) for h in report["hits"]) or '<p class="muted">Keine Treffer in diesem Lauf.</p>'
    rows_html = "\n".join(_overview_row(r) for r in report["all_results"])

    event_items = [
        f'<li><strong>{_esc(r["name"])} ({_esc(r["ticker"])})</strong>: {_esc("; ".join(r["upcoming_events"]))}</li>'
        for r in report["all_results"]
        if r.get("upcoming_events")
    ]
    events_html = (
        f'<ul>{"".join(event_items)}</ul>'
        if event_items
        else '<p class="muted">Keine bekannten Termine in den nächsten Tagen.</p>'
    )

    errors_html = ""
    if report["errors"]:
        items = "".join(f"<li>{_esc(t)}: {_esc(e)}</li>" for t, e in report["errors"].items())
        errors_html = f"<h2>Fehler</h2><ul>{items}</ul>"

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Swing-Trading Scan</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 900px; margin: 0 auto; padding: 16px 16px 40px; line-height: 1.5;
  }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #8884; padding-bottom: 4px; }}
  .summary {{ color: #666; margin-bottom: 1.5rem; }}
  .card {{ border: 1px solid #8884; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; }}
  .card h3 {{ margin: 0 0 6px 0; }}
  .ticker {{ color: #888; font-weight: normal; font-size: 0.85em; }}
  .badge {{
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 0.8rem; font-weight: 600; margin-bottom: 8px; color: white;
  }}
  .badge-strong {{ background: #1a7f37; }}
  .badge-moderate {{ background: #9a6700; }}
  .badge-weak {{ background: #6e7781; }}
  .muted {{ color: #666; font-size: 0.9rem; }}
  .warning {{ color: #9a2d00; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #8883; }}
  tr.hit-row {{ background: rgba(26, 127, 55, 0.08); }}
  footer {{ margin-top: 2rem; color: #888; font-size: 0.8rem; }}
  @media (prefers-color-scheme: dark) {{
    .badge-strong {{ background: #2ea043; }}
    tr.hit-row {{ background: rgba(46, 160, 67, 0.15); }}
  }}
</style>
</head>
<body>
  <h1>📊 Swing-Trading Scan</h1>
  <p class="summary">
    Erzeugt: {_esc(report['generated_at_utc'])} UTC · Analysiert: {report['tickers_analyzed']} Instrumente ·
    Treffer: {report['hits_count']} (Schwelle ±{report['proximity_threshold_pct']}% um POC/VAL)
  </p>

  <h2>Treffer</h2>
  {hits_html}

  <h2>Alle beobachteten Instrumente</h2>
  <table>
    <thead>
      <tr><th>Instrument</th><th>Kurs</th><th>Nächstes Level</th><th>Abstand</th><th>RSI</th><th>Wochentrend</th><th>Treffer</th></tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <h2>Bevorstehende Termine</h2>
  {events_html}

  {errors_html}

  <footer>
    Nur zur Analyse-Unterstützung, keine automatisch ausgeführten Trades. Positionsgrößen sind
    informative Vorschläge, keine Handelsempfehlung.<br>
    <strong>Glossar:</strong> POC = Point of Control (Preis mit dem höchsten Handelsvolumen) ·
    VAL/VAH = Value Area Low/High (Kern-Handelszone) ·
    RSI = Relative-Stärke-Index (0–100, ≤30 gilt als überverkauft).
  </footer>
</body>
</html>
"""

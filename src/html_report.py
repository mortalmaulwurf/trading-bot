"""Erzeugt die eigenständige HTML-Übersichtsseite aus dem Report im App-Design (Karten, Ampeln, Kerzenchart).

Gedacht zum Hosten auf einer statischen Seite (z.B. Render Static Site). Kein externes CSS/JS und keine
Build-Schritte; die einzige Skriptzeile berechnet im Browser das Alter des Reports (ohne JS fehlt nur diese Anzeige).
"""
from __future__ import annotations

import html as html_lib
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from .formatting import de, price
from .rule_lights import Light, is_paper_candidate, rule_lights
from .svg_chart import render_chart

BERLIN = ZoneInfo("Europe/Berlin")
STATUS_LABEL = {"ok": "OK", "partial": "Teilweise", "failed": "Fehlgeschlagen"}
STATUS_CLASS = {"ok": "green", "partial": "yellow", "failed": "red"}
LIGHT_SYMBOL = {"pass": "✓", "fail": "✕", "neutral": "–", "unknown": "?"}
LIGHT_TEXT = {"pass": "erfüllt", "fail": "nicht erfüllt", "neutral": "nicht ausschlaggebend", "unknown": "unbekannt"}


def _esc(value) -> str:
    return html_lib.escape(str(value))


def _light_html(light: Light) -> str:
    aria = _esc(f"{light.label}: {LIGHT_TEXT[light.state]}, {light.detail}")
    return (
        f'<li class="light light--{light.state}" aria-label="{aria}"><span class="light-dot" aria-hidden="true">'
        f'{LIGHT_SYMBOL[light.state]}</span><span class="light-label">{_esc(light.label)}</span>'
        f'<span class="light-detail">{_esc(light.detail)}</span></li>'
    )


def _chart_levels(h: dict) -> list[dict]:
    levels = [
        {"label": "VAH", "price": h["vah"], "tone": "level"},
        {"label": "POC", "price": h["poc"], "tone": "level"},
        {"label": "VAL", "price": h["val"], "tone": "level"},
    ]
    plan = h.get("position_suggestion")
    if plan:
        levels.append({"label": "Einstieg", "price": plan["entry_price"], "tone": "entry"})
        levels.append({"label": "Stop", "price": plan["stop_price"], "tone": "stop"})
        if plan.get("target_price") is not None:
            levels.append({"label": "Ziel", "price": plan["target_price"], "tone": "target"})
    return levels


def _index_levels_html(idx: Optional[dict]) -> str:
    """Index points for the knock-out certificate; the chart and plan above are in ETF prices."""
    if not idx:
        return ""
    cells = [
        ("Einstieg", idx.get("entry")),
        ("Stop", idx.get("stop")),
        ("Ziel", idx.get("target")),
        ("Mindest-Ziel", idx.get("required_target")),
    ]
    grid = "".join(f"<div><dt>{label}</dt><dd>{de(value) if value is not None else '–'}</dd></div>" for label, value in cells)
    return f'<h4 class="plan-index-title">Index (Punkte) für das Zertifikat</h4><dl class="plan-grid">{grid}</dl>'


def _plan_html(h: dict) -> str:
    p = h.get("position_suggestion")
    if not p:
        return ""
    title = "Planwerte (nur Anzeige)" if h.get("is_actionable") else "Planwerte – hypothetisch, Regeln nicht erfüllt"
    target = "–"
    if p.get("target_price") is not None:
        target = price(p["target_price"]) + (f" ({_esc(p['target_name'])})" if p.get("target_name") else "")
    crv = f"{de(p['net_crv'])}:1" if p.get("net_crv") is not None else "–"
    cur = _esc(h["currency"])
    cells = [
        ("Einstieg", f"{price(p['entry_price'])} {cur}"),
        ("Stop", f"{price(p['stop_price'])} {cur}"),
        ("Ziel", target),
        ("Hebel", f"{de(p['leverage'], 0 if float(p['leverage']).is_integer() else 1)}×"),
        ("KO-Level", f"{price(p['ko_level'])} {cur}"),
        ("Einsatz", f"{de(p['capital_eur'])} €"),
        ("Netto-CRV", crv),
        ("Max. Verlust", f"{de(p['total_loss_eur'])} €"),
    ]
    grid = "".join(f"<div><dt>{label}</dt><dd>{value}</dd></div>" for label, value in cells)
    note = '<p class="plan-note">Einsatz durch die Positionsgrenze gedeckelt.</p>' if p.get("capped") else ""
    return f'<div class="plan"><h4>{title}</h4><dl class="plan-grid">{grid}</dl>{note}{_index_levels_html(p.get("index_levels"))}</div>'


def _card(h: dict, rule_set: dict, alert_tickers: set[str], candles: Optional[list[dict]]) -> str:
    is_alert = h["ticker"] in alert_tickers
    paper = is_paper_candidate(h, rule_set)
    classes = "card" + (" card--alert" if is_alert else "") + (" card--paper" if paper else "")
    badges = ""
    if is_alert:
        badges += f'<span class="badge badge--accent">{"A-Setup" if h.get("is_a_setup") else "Setup"}</span>'
    if paper:
        badges += '<span class="badge badge--paper">Papier-Trade-Kandidat</span>'
    sign = "+" if h["distance_pct"] >= 0 else "−"
    chart = render_chart(h["name"], candles, _chart_levels(h)) if candles else ""
    lights = "".join(_light_html(light) for light in rule_lights(h, rule_set))
    events = ""
    if h.get("upcoming_events"):
        items = "".join(f"<li>{_esc(e)}</li>" for e in h["upcoming_events"])
        events = f'<div class="events"><h4>Anstehende Termine</h4><ul>{items}</ul></div>'
    return (
        f'<article class="{classes}" aria-label="{_esc(h["name"])}">'
        f'<header class="card-head"><div class="card-id"><h3>{_esc(h["name"])}</h3><span class="ticker">{_esc(h["ticker"])}</span></div>'
        f'<div class="badges">{badges}</div>'
        f'<p class="price">{price(h["current_price"])} <small>{_esc(h["currency"])}</small></p></header>'
        f'<p class="levels">POC {price(h["poc"])} · VAL {price(h["val"])} · VAH {price(h["vah"])}'
        f'<span class="basis"> ({_esc(h.get("profile_basis", ""))})</span></p>'
        f'<p class="levels">Nächstes Level: <strong>{_esc(h["nearest_level_name"])} {price(h["nearest_level_price"])}</strong>'
        f" · Abstand {sign}{de(abs(h['distance_pct']))}\u00a0%</p>"
        f'{chart}<ul class="lights" aria-label="Regel-Check">{lights}</ul>{_plan_html(h)}{events}</article>'
    )


def _rank(h: dict, alert_tickers: set[str], rule_set: dict) -> int:
    if h["ticker"] in alert_tickers:
        return 0 if h.get("is_a_setup") else 1
    if is_paper_candidate(h, rule_set):
        return 2
    return 3 if h.get("is_hit") else 4


def _stamp(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(BERLIN).strftime("%d.%m. %H:%M")


CSS = """
:root { color-scheme: light dark;
  --bg:#ecebe8; --card:#faf9f7; --sep:rgba(17,17,26,.08); --fill:rgba(17,17,26,.06); --ink:#14141a; --ink2:#5f5f68; --ink3:#9a9aa2;
  --accent:#ec5b78; --accent-tint:#f6d3d4; --green:#2f9e57; --green-tint:#dcf1e2; --red:#dc3e4c; --red-tint:#fbe1e2;
  --warn:#d9822b; --warn-tint:#fae6cf; --shadow:0 1px 2px rgba(17,17,26,.03),0 12px 32px rgba(17,17,26,.05); }
@media (prefers-color-scheme: dark) { :root {
  --bg:#0e0f13; --card:#1a1b21; --sep:rgba(255,255,255,.08); --fill:rgba(255,255,255,.07); --ink:#f3f3f5; --ink2:#a8a8b2; --ink3:#6c6c76;
  --green:#45c072; --green-tint:rgba(69,192,114,.16); --red:#ff6b72; --red-tint:rgba(255,107,114,.16);
  --warn:#f2a54a; --warn-tint:rgba(242,165,74,.18); --accent-tint:rgba(236,91,120,.22); --shadow:0 12px 32px rgba(0,0,0,.35); } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); line-height:1.45;
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue","Segoe UI",Roboto,system-ui,sans-serif; }
main { max-width:1100px; margin:0 auto; padding:20px 16px 48px; }
h1 { margin:0 0 10px; font-size:1.7rem; letter-spacing:-.02em; }
h3, h4, p, ul, dl { margin:0; } ul { padding:0; list-style:none; }
.head { display:flex; flex-direction:column; gap:8px; margin-bottom:18px; }
.head-row { display:flex; flex-wrap:wrap; align-items:center; gap:8px 12px; }
.time { color:var(--ink2); font-size:.9rem; font-variant-numeric:tabular-nums; }
.muted { color:var(--ink3); font-size:.85rem; } .warnline { color:var(--warn); font-weight:600; font-size:.85rem; }
.badge[hidden] { display:none; }
.badge { display:inline-block; font-size:.75rem; font-weight:600; padding:3px 10px; border-radius:999px; }
.badge--green { background:var(--green-tint); color:var(--green); } .badge--yellow { background:var(--warn-tint); color:var(--warn); }
.badge--red { background:var(--red-tint); color:var(--red); } .badge--accent { background:var(--accent-tint); color:var(--accent); }
.badge--paper { color:var(--warn); box-shadow:inset 0 0 0 1.5px var(--warn); }
.errors { padding:12px 14px; border-radius:14px; background:var(--red-tint); color:var(--red); font-size:.9rem; }
.errors ul { margin-top:6px; padding-left:18px; list-style:disc; }
.grid { display:grid; gap:14px; grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr)); }
.card { display:flex; flex-direction:column; gap:10px; padding:16px; border-radius:20px; background:var(--card); box-shadow:inset 0 0 0 1px var(--sep); }
.card--alert { box-shadow:inset 0 0 0 2px var(--accent), var(--shadow); }
.card--paper { box-shadow:inset 0 0 0 1.5px color-mix(in srgb,var(--warn) 55%,transparent); }
.card-head { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:4px 12px; align-items:start; }
.card-id { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 8px; min-width:0; } .card-id h3 { font-size:1.05rem; }
.ticker { color:var(--ink3); font-size:.8rem; } .badges { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:6px; }
.price { grid-column:1 / -1; font-size:1.5rem; font-weight:600; font-variant-numeric:tabular-nums; }
.price small { font-size:.8rem; font-weight:500; color:var(--ink3); }
.levels { font-size:.88rem; color:var(--ink2); font-variant-numeric:tabular-nums; } .basis { color:var(--ink3); }
.chart { display:block; width:100%; height:auto; }
.chart-candle line { stroke-width:1; } .chart-candle--up line { stroke:var(--green); } .chart-candle--up rect { fill:var(--green); }
.chart-candle--down line { stroke:var(--red); } .chart-candle--down rect { fill:var(--red); }
.chart-line { stroke:var(--ink3); stroke-width:1; stroke-dasharray:3 3; opacity:.8; }
.chart-line--entry { stroke:var(--accent); stroke-dasharray:none; } .chart-line--stop { stroke:var(--red); } .chart-line--target { stroke:var(--green); }
.chart-label { font-size:11px; fill:var(--ink2); font-variant-numeric:tabular-nums; }
.chart-label--entry { fill:var(--accent); font-weight:600; } .chart-label--stop { fill:var(--red); } .chart-label--target { fill:var(--green); }
.lights { display:flex; flex-direction:column; gap:4px; }
.light { display:grid; grid-template-columns:24px minmax(0,1fr) auto; align-items:center; gap:10px; font-size:.88rem; }
.light-dot { display:grid; place-items:center; width:24px; height:24px; border-radius:50%; font-size:.8rem; font-weight:700; background:var(--fill); color:var(--ink3); }
.light--pass .light-dot { background:var(--green-tint); color:var(--green); } .light--fail .light-dot { background:var(--red-tint); color:var(--red); }
.light--neutral .light-label, .light--unknown .light-label { color:var(--ink3); }
.light-label { min-width:0; overflow-wrap:anywhere; }
.light-detail { font-size:.8rem; color:var(--ink2); text-align:right; font-variant-numeric:tabular-nums; }
.plan, .events { padding-top:10px; border-top:1px solid var(--sep); }
.plan h4, .events h4 { margin-bottom:8px; font-size:.72rem; letter-spacing:.04em; text-transform:uppercase; color:var(--ink2); }
.plan-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 16px; }
.plan-grid dt { font-size:.75rem; color:var(--ink3); } .plan-grid dd { margin:0; font-weight:600; font-variant-numeric:tabular-nums; }
.plan-index-title { margin-top:14px; }
.plan-note { margin-top:8px; font-size:.8rem; color:var(--warn); }
.events ul { padding-left:18px; list-style:disc; font-size:.88rem; color:var(--warn); }
footer { margin-top:28px; color:var(--ink3); font-size:.8rem; }
"""

AGE_SCRIPT = """
(function () {
  var el = document.getElementById('age');
  if (!el) return;
  var generated = Date.parse(el.getAttribute('data-generated') || '');
  if (isNaN(generated)) return;
  var now = new Date();
  var hours = (now.getTime() - generated) / 36e5;
  var monday = new Intl.DateTimeFormat('en-US', { timeZone: 'Europe/Berlin', weekday: 'short' }).format(now) === 'Mon';
  var limit = monday ? 80 : 30;
  el.textContent = hours < 1 ? 'vor ' + Math.max(1, Math.round(hours * 60)) + ' Min.'
    : hours < 48 ? 'vor ' + Math.round(hours) + ' Std.'
    : 'vor ' + Math.floor(hours / 24) + ' T. ' + (Math.round(hours) - Math.floor(hours / 24) * 24) + ' Std.';
  var stale = document.getElementById('stale');
  if (stale && hours > limit) { stale.hidden = false; stale.textContent = 'Veraltet (> ' + limit + ' Std.)'; }
})();
"""


def render_html(report: dict, charts: Optional[dict] = None) -> str:
    rule_set = report.get("rule_set") or {"min_net_crv": report.get("min_net_crv", 3.0)}
    status = report.get("status", "ok")
    alert_tickers = {a["ticker"] for a in report.get("alerts", [])}
    candle_map = (charts or {}).get("charts", {})

    rows = sorted(
        report["all_results"],
        key=lambda h: (_rank(h, alert_tickers, rule_set), abs(h["distance_pct"])),
    )
    cards = "".join(
        _card(h, rule_set, alert_tickers, (candle_map.get(h["ticker"]) or {}).get("candles")) for h in rows
    ) or '<p class="muted">Der Report enthält keine Instrumente.</p>'

    rules_line = (
        f'Regelwerk: Netto-CRV ≥ {de(rule_set["min_net_crv"])}:1'
        + (f' · max. {_esc(rule_set["max_risk_per_trade_eur"])} € Risiko' if "max_risk_per_trade_eur" in rule_set else "")
        + (f' · max. {_esc(rule_set["max_position_eur"])} € Position' if "max_position_eur" in rule_set else "")
        + " · eine Position gleichzeitig · nur Anzeige, keine Orders"
    )
    multi = (
        f'<p class="warnline">{len(alert_tickers)} Setups gleichzeitig – laut Regelwerk darf nur eine Position offen sein.</p>'
        if len(alert_tickers) > 1
        else ""
    )
    errors_html = ""
    if report["errors"]:
        items = "".join(f"<li><code>{_esc(t)}</code>: {_esc(e)}</li>" for t, e in report["errors"].items())
        errors_html = f'<div class="errors" role="alert"><strong>Fehler im Bot-Lauf</strong><ul>{items}</ul></div>'

    generated = report["generated_at_utc"]
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>Swing-Trading Scan</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <section class="head" aria-label="Report-Status">
    <h1>Swing-Trading Scan</h1>
    <div class="head-row">
      <span class="badge badge--{STATUS_CLASS.get(status, "yellow")}">Status: {_esc(STATUS_LABEL.get(status, status))}</span>
      <span class="time">Stand {_esc(_stamp(generated))} Uhr · <span id="age" data-generated="{_esc(generated)}"></span></span>
      <span class="badge badge--red" id="stale" role="status" hidden></span>
    </div>
    <p class="muted">{rules_line}</p>
    <p class="muted">{report["tickers_analyzed"]} Instrumente analysiert · {report["hits_count"]} Treffer (Schwelle ±{_esc(report["proximity_threshold_pct"])} % um POC/VAL)</p>
    {multi}{errors_html}
  </section>
  <div class="grid">{cards}</div>
  <footer>
    Nur zur Analyse-Unterstützung, keine automatisch ausgeführten Trades. Positionsgrößen sind
    informative Vorschläge, keine Handelsempfehlung.<br>
    <strong>Glossar:</strong> POC = Point of Control (Preis mit dem höchsten Handelsvolumen) ·
    VAL/VAH = Value Area Low/High (Kern-Handelszone) · CRV = Chance-Risiko-Verhältnis.
  </footer>
</main>
<script>{AGE_SCRIPT}</script>
</body>
</html>
"""

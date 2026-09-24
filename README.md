# trading-bot

Automatisierte Swing-Trading-Analyse für das "Strict Coach Mode"-System:
täglicher Scan einer Watchlist auf strukturelle Unterstützungen
(Volumenprofil: POC, VAL) mit Reversal-Bestätigung, Telegram-Push bei
Treffern und ein Report zum gemeinsamen Vertiefen der Analyse.

**Wichtig:** Das Skript platziert keine Orders. Es liefert ausschließlich
Analysen, Benachrichtigungen und informative Positionsgrößen-Vorschläge zur
Diskussion.

## Wie es funktioniert

1. Für jeden Ticker der Watchlist werden Daily-Kursdaten (Standard: 6 Monate)
   und 1h-Intraday-Daten (Standard: 60 Tage, zusätzlich zu 4h resampled)
   über [yfinance](https://github.com/ranaroussi/yfinance) geladen.
2. Aus den Daily-Daten wird ein Volumenprofil berechnet: **POC** (Point of
   Control), **VAL**/**VAH** (Value Area Low/High). Da yfinance kein
   echtes Volumen-pro-Preis liefert, wird das Tagesvolumen jeder Kerze
   näherungsweise über ihre Handelsspanne verteilt – eine übliche
   Approximation ohne Tick-/Orderbuchdaten.
3. Liegt der aktuelle Kurs innerhalb der konfigurierten Schwelle
   (Standard: 1,5%) um POC oder VAL, gilt das als **Treffer**.
4. Als Bestätigung werden geprüft: RSI (überverkauft), Volumen-Spike am
   letzten Handelstag, und ein einfaches Intraday-Momentum-Signal (1h/4h).
   Je mehr Bestätigungen, desto höher die Einschätzung ("schwach" /
   "moderat" / "stark").
5. Zusätzlich wird ein **langfristiges Volumenprofil** (Standard: 12 Monate)
   berechnet. Liegt ein langfristiges POC/VAL nahe am kurzfristigen
   Treffer-Level (Standard: ±2%), gilt das als **Konfluenz** – ein
   deutlich stärkeres strukturelles Signal, da sich mehrere Zeiträume
   einig sind. Aus denselben Langzeitdaten wird außerdem ein einfacher
   **Wochentrend-Filter** abgeleitet (aktueller Wochenschluss über/unter
   dem gleitenden Durchschnitt der letzten 10 Wochen) – als Kontext, ob
   der übergeordnete Trend für oder gegen einen Long-Einstieg spricht.
6. Bei einem Treffer wird zusätzlich ein informativer
   Positionsgrößen-Vorschlag berechnet, basierend auf dem Risikorahmen aus
   `config/settings.yaml` (max. Risiko pro Trade, Hebel) und einer
   vereinfachten Stop-Referenz (1% unter VAL).
7. Für jeden Ticker wird geprüft, ob in den nächsten 7 Tagen (Standard)
   **Quartalszahlen** (via yfinance) oder ein bekannter **Makro-Termin**
   (z.B. Fed-Zinsentscheid) anstehen. Der US-Arbeitsmarktbericht wird
   automatisch erkannt (immer der erste Freitag im Monat), Fed-/EZB-Termine
   werden manuell in `config/macro_events.yaml` gepflegt (siehe unten). Das
   ist reiner Zusatzkontext zum Gap-Risiko, kein Ausschlusskriterium.
8. Ergebnisse werden als Markdown + JSON in `reports/` geschrieben
   (`reports/latest.md`, `reports/latest.json` sowie ein tagesdatiertes
   Archiv), zusätzlich als einfache HTML-Seite (`site/index.html`,
   siehe "Online-Übersicht" unten) und bei Treffern per Telegram gepusht.

## Projektstruktur

```
config/
  settings.yaml     Risiko- und Analyse-Parameter (Schwellenwerte, Indikatoren, ...)
  watchlist.yaml     Liste der beobachteten Ticker – frei erweiterbar
  macro_events.yaml   Manuell gepflegte Fed-/EZB-/Makro-Termine
src/
  config.py           Config-/Secrets-Loading
  data_fetcher.py      yfinance-Anbindung (Daily, Intraday, FX-Kurs)
  volume_profile.py    POC/VAL/VAH-Berechnung
  indicators.py        RSI, Volumen-Spike, Intraday-Momentum, Wochentrend
  events.py            Bevorstehende Quartalszahlen & Makro-Termine
  risk.py              Positionsgrößen-Vorschlag (informativ)
  signal_engine.py       Kombiniert alles zu einer Ticker-Analyse
  report.py               Markdown-/JSON-/HTML-Report-Erzeugung
  html_report.py            HTML-Übersichtsseite (für Render o.ä.)
  notifier.py                 Telegram-Versand
  main.py                       Orchestrierung / Einstiegspunkt
reports/                       Generierte Reports (werden vom Workflow committed)
site/                          Generierte HTML-Übersichtsseite (dito)
.github/workflows/
  daily_analysis.yml            GitHub-Actions-Zeitplan
```

## Watchlist & Parameter anpassen

- **Ticker hinzufügen/entfernen:** `config/watchlist.yaml` bearbeiten. Jeder
  Eintrag hat ein `symbol` (muss dem Yahoo-Finance-Symbol entsprechen, z.B.
  `RWE.DE` für RWE an der Xetra) und einen frei wählbaren `name` (Klarname,
  erscheint in Report/Telegram statt des kryptischen Symbols).
- **Schwellenwerte, Risiko, Indikator-Parameter:** `config/settings.yaml`
  bearbeiten – jede Zeile ist kommentiert. Änderungen wirken sich sofort
  beim nächsten Lauf aus, kein Code-Änderung nötig.

## Makro-Termine pflegen (Fed, EZB, ...)

Der US-Arbeitsmarktbericht wird automatisch erkannt (regelbasiert). Für
Fed-Zinsentscheide, EZB-Ratssitzungen und ähnliche Termine gibt es keine
verlässliche kostenlose Live-API – diese müssen manuell in
`config/macro_events.yaml` eingetragen werden. Die Datei ist ausführlich
kommentiert (inkl. Links zu den offiziellen Kalendern) und standardmäßig
leer, damit keine falschen/veralteten Termine vorgetäuscht werden. Am
besten alle paar Wochen kurz mit dem offiziellen Fed-/EZB-Kalender
abgleichen und anstehende Termine ergänzen.

Quartalszahlen werden automatisch über yfinance abgerufen – hier ist keine
manuelle Pflege nötig, die Schätzung kann aber va. bei Nicht-US-Tickern
ungenau sein.

## Telegram-Bot einrichten

1. In Telegram mit **@BotFather** chatten, `/newbot` senden und den Namen
   vergeben. Du bekommst einen **Bot-Token** (Format `123456:ABC-DEF...`).
2. Deine **Chat-ID** herausfinden: dem neuen Bot eine beliebige Nachricht
   schreiben, dann im Browser
   `https://api.telegram.org/bot<DEIN_TOKEN>/getUpdates` öffnen und das
   Feld `"chat":{"id":...}` ablesen. Alternativ kurz mit
   **@userinfobot** chatten.

## Automatisierung: GitHub Actions (empfohlen)

Der Workflow `.github/workflows/daily_analysis.yml` läuft automatisch
werktags um 22:00 UTC (sicher nach US-Marktschluss) und schreibt den
Report per Commit zurück ins Repo, damit du ihn direkt hier in Claude
oder auf GitHub einsehen kannst.

**Einrichtung:**

1. Im GitHub-Repo zu **Settings → Secrets and variables → Actions** gehen.
2. Zwei Repository-Secrets anlegen:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Fertig – der Workflow läuft ab dem nächsten Zeitplan-Tick automatisch.
   Manuell testen: im Tab **Actions** → "Daily Swing-Trading Scan" →
   **Run workflow**.

**Telegram isoliert testen:** Der Scan-Workflow schickt eine Nachricht nur,
wenn es Treffer gibt. Um nur die Telegram-Zugangsdaten zu prüfen (ohne auf
einen Treffer zu warten), im Tab **Actions** → "Test Telegram
Notification" → **Run workflow** ausführen. Schlägt das fehl, in den
Logs des Schritts "Send test message" nachsehen – dort steht die genaue
Fehlermeldung von Telegram (z.B. `404 Not Found` bedeutet meist: der
hinterlegte `TELEGRAM_BOT_TOKEN`-Secret ist falsch/veraltet).

**Hinweis:** GitHub deaktiviert geplante (`schedule`-)Workflows automatisch,
wenn 60 Tage lang kein Commit ins Repo ging. Der Workflow committet bei
jedem Treffer/Report selbst wieder ins Repo, was das i.d.R. verhindert –
bei längerer Pause ggf. im Tab **Actions** manuell wieder aktivieren.

## Online-Übersicht (Render Static Site)

Jeder Lauf erzeugt zusätzlich `site/index.html` – eine einfache,
eigenständige HTML-Seite mit derselben Zusammenfassung wie `reports/latest.md`
(Klarnamen, Treffer, Volumenprofil, Wochentrend, Termine), aber besser lesbar
auf dem Handy. Damit sie dauerhaft unter einer festen URL erreichbar ist
(z.B. um sie direkt in die Telegram-Nachricht zu packen):

1. Auf [render.com](https://render.com) registrieren/einloggen (kostenlose
   Stufe reicht).
2. **New** → **Static Site** → dieses GitHub-Repo verbinden
   (`mortalmaulwurf/trading-bot`).
3. Branch: `main` · Build Command: leer lassen (kein Build nötig) ·
   Publish directory: `site`.
4. Deployen – Render vergibt eine URL wie
   `https://trading-bot-xxxx.onrender.com`.
5. Diese URL in `config/settings.yaml` unter `notifications.site_url`
   eintragen und committen.

Da der Workflow nach jedem Lauf automatisch neue Inhalte ins Repo committet,
erkennt Render das (bei verbundenem GitHub-Repo) und deployt automatisch neu
– die URL bleibt dabei immer gleich. Ab dann hängt jede Telegram-Nachricht
bei Treffern den Link an.

**Hinweis:** Ohne eingetragene `site_url` funktioniert alles wie bisher,
nur ohne den Link in der Telegram-Nachricht – die HTML-Seite wird trotzdem
lokal/im Repo erzeugt.

## Alternative: Lokale Ausführung (Cronjob / Task Scheduler)

Falls du das Skript stattdessen lokal laufen lassen willst:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID eintragen
python -m src.main
```

- **Linux/Mac (Cronjob):** `crontab -e`, z.B. für 22:00 Uhr UTC werktags:
  ```
  0 22 * * 1-5 cd /pfad/zu/trading-bot && /pfad/zu/.venv/bin/python -m src.main
  ```
- **Windows (Task Scheduler):** Neue Aufgabe anlegen, Trigger täglich
  (Mo-Fr) nach US-Marktschluss, Aktion `python.exe -m src.main` mit
  Startverzeichnis = Projektordner.

## Ergebnisse ansehen

- `reports/latest.md` – kompakte, lesbare Zusammenfassung des letzten Laufs.
- `reports/latest.json` – strukturierte Daten für die Weiterverarbeitung.
- `reports/YYYY-MM-DD.md` / `.json` – Tages-Archiv.

Bei GitHub-Actions-Betrieb landen diese automatisch im Repo – einfach die
Datei in einer Claude-Session zu diesem Repo öffnen/lesen lassen, um die
Analyse gemeinsam zu vertiefen.

## Einschränkungen & Hinweise

- **yfinance** ist eine inoffizielle, aber kostenlose und zuverlässige
  Anbindung an Yahoo-Finance-Daten – ausreichend für täglichen Multi-Ticker-
  Abruf inkl. Intraday. Offizielle kostenlose Alternativen (z.B. Alpha
  Vantage, Twelve Data) haben deutlich engere Rate-Limits (teils nur 25
  Requests/Tag) und eignen sich hier schlechter.
- Das Volumenprofil ist eine **Näherung** aus OHLCV-Daten, kein echtes
  Orderbuch-/Tick-Volumenprofil.
- Intraday-Daten (`1h`) sind bei yfinance auf die letzten ~730 Tage
  begrenzt und können am Wochenende/außerhalb der Handelszeiten dünn
  ausfallen – das Skript fängt das ab und lässt die Intraday-Bestätigung
  in dem Fall einfach weg.
- Für die Positionsgrößen-Berechnung bei USD-Tickern wird der aktuelle
  EUR/USD-Kurs live abgerufen (mit Fallback-Näherungswert bei Fehlern).

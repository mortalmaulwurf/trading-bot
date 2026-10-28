# Vorlage: Wochen- und Tagesanalyse (Sonntag, täglich)

Diese Vorlage beschreibt die Analyse, die Benjamin gut fand. Sie ist **nur Anzeige und Lernhilfe**, keine
Anlageberatung, und platziert keine Orders. Sprache: Deutsch, Konfidenz bei Bedarf mit `[Sicher]`,
`[Wahrscheinlich]`, `[Vermutung]` kennzeichnen, Vorschläge als `[Empfehlung]`.

## Rhythmus
- **Sonntag (ausführlich):** alle Abschnitte unten, Ausblick auf die kommende Woche.
- **Täglich (Kurzform, vor Xetra-Öffnung):** Abschnitte 1, 2, 4 und die Termine des Tages mit Lernhilfe (Abschnitt 5);
  Trend und Stützen/Widerstände nur nennen, wenn sich etwas geändert hat.

## Regelwerk (immer gegenprüfen)
300 EUR Lernkapital, max. 10 EUR Risiko pro Trade, eine Position gleichzeitig, Netto-CRV mindestens 3:1,
Einstieg nur an Unterstützung (VAL/POC) nach bestätigter Umkehr per Tagesschluss mit grüner Kerze.
Papier-Trade-Stufe: Netto-CRV zwischen 2:1 und 3:1 (nur Journal). Volumenprofil ab Anker `profile_anchor_date`
(aktuell 2026-09-17), 30 Preisstufen, 70 % Value Area (`compute_volume_profile`).

## Datenquellen
- **TradingView-Tools** (in der Claude-Session, nicht im Bot):
  - `get-ohlcv` (1D, ab Anker): `XETR:DAX` (Index-Volumen), `XETR:EXS1` (ETF, Bot-Basis), `SP:SPX`, `AMEX:SPY`,
    `COMEX:GC1!`, `NYMEX:CL1!`.
  - `get-technicals-rating` (1D und 1W): Trend, RSI, ADX, gleitende Durchschnitte.
  - `get-symbol-data-batch` mit Spalten `close, change, Perf.W, Perf.1M, Perf.3M, Perf.YTD`: VIX (`CBOE:VIX`),
    Dollar-Index (`TVC:DXY`), US-10J (`TVC:US10Y`), Bund-10J (`TVC:DE10Y`), `FX:EURUSD`, Indizes, Gold, WTI.
  - `get-economic-calendar` (`min_importance=1`): US sowie `DE,EU`, 7 Tage voraus.
  - `get-earnings-calendar`: Big Tech (AAPL, MSFT, GOOGL, AMZN, NVDA, META) und DAX-Schwergewichte.
  - `get-news` für `XETR:DAX` und `SP:SPX` (Titel, Details oft hinter Bezahlschranke).
- **Bot-Report** `reports/latest.json`: Regel-Checks, Plan, Index-Punkte. **Achtung:** Der Report hinkt bei Aktien-ETFs
  oft einen Handelstag hinterher; den letzten Schluss deshalb aus TradingView nehmen und den Befund nennen.
- **Kassa gegen CFD:** Der CFD (z. B. Germany 40) liegt rund 170 Punkte über der Kassa (Future-Prämie, schwankt täglich).
  Level immer mit Basis angeben.

## Aufbau
1. **Empfehlung zuerst:** Einstieg ja/nein (Kandidat?) in einem Satz, mit Grund.
2. **Tabelle je Instrument** (DAX, S&P 500, Gold, WTI): Schluss, Woche (Freitag zu Freitag), Lage zu VAL/POC/VAH,
   letzte Kerze (grün/rot), Setup ja/nein.
3. **Trend:** Technicals Tag und Woche, Lage zu EMA20/50/200, RSI, ADX; Stützen und Widerstände mit Zahlen.
4. **Marktdaten:** VIX, Renditen, Dollar, Öl, Gold, mit Einordnung (steigende Angst, hohe Zinsen, Inflationsdruck).
5. **Termine mit Lernhilfe** (deutsche Zeit, Zeitumstellung beachten): Tabelle mit Zeit, Ereignis, Prognose gegen
   Vorwert, **Warum wichtig**, **Worauf achten**, **mögliche Reaktion**. Siehe Glossar unten.
6. **Was das für die Regeln heißt:** Ereignistage (keine neuen Einstiege kurz davor), Bestätigung per Tagesschluss,
   CRV-Rechnung (Stop = Level minus 1 ATR; für 3:1 muss das Ziel mindestens das Dreifache des Stopabstands entfernt sein).
7. **Alarme:** konkrete Level (Kassa und CFD), Typ (Kreuzt nach unten = Hinweis, Balkenschluss darüber = Einstiegssignal).
8. **Lücken und Unsicherheiten:** was fehlt oder unklar ist (leere `macro_events.yaml`, Bot-Daten, Basis).

## Glossar: Termine verstehen
Entscheidend ist fast nie die Zahl selbst, sondern die **Abweichung von der Erwartung** (Prognose) und von dem, was
der Markt schon eingepreist hat. Erste Reaktionen werden oft nach Minuten wieder umgedreht.

- **Zinsentscheid (Fed, EZB):** Der Leitzins bestimmt, was Geld kostet. Meist ist das Ergebnis erwartet; die Wirkung kommt
  aus dem **Ausblick** (Pressekonferenz, Wortwahl zu künftigen Zinsschritten). Höhere Zinsen belasten tendenziell Aktien
  (besonders Wachstum/Tech) und stützen den Dollar; Zinssenkungen oder ein "weicherer" Ton wirken umgekehrt.
  Achten auf: Änderung gegenüber Erwartung, Abstimmung (einstimmig?), Aussagen zu Inflation und Wachstum. Volatilität
  steigt vor und nach der Pressekonferenz.
- **Pressekonferenz:** Oft bewegender als die Entscheidung selbst; Gegenfragen können den Kurs mehrfach drehen.
- **Inflation (CPI, PCE, Core PCE):** Preisdruck. Liegt sie über der Prognose, steigen Zinserwartungen, das belastet Aktien
  und Anleihen; darunter wirkt es entlastend. **Core** (ohne Energie/Nahrung) zeigt den Grundtrend, die Notenbanken
  beachten ihn besonders. PCE ist die von der Fed bevorzugte Messgröße.
- **BIP (Wachstum):** Zeigt die Konjunktur. Ein starkes BIP stützt Gewinne, kann aber Zinssorgen nähren; ein schwaches
  BIP drückt auf Aktien, kann aber Zinssenkungshoffnung wecken. Vorab-Zahlen (Flash) werden später revidiert.
- **Arbeitsmarkt (Nonfarm Payrolls, Arbeitslosenquote):** Starke Jobs bedeuten oft höhere Zinsen für länger. Immer
  zusammen mit Löhnen lesen (Lohndruck gleich Inflationsrisiko). Erster Freitag im Monat.
- **Einkaufsmanagerindizes (ISM, PMI):** Frühindikator der Konjunktur; über 50 bedeutet Wachstum, darunter Schrumpfung.
  Wichtig sind Auftragseingang und Preiskomponente.
- **Stimmungsindizes (Ifo, GfK, ZEW):** Zeigen die Erwartung von Unternehmen/Verbrauchern; wirken auf den DAX meist
  moderat, außer bei großer Überraschung.
- **Quartalszahlen (Big Tech):** Microsoft, Alphabet, Amazon, Apple bewegen den Nasdaq und über ihn den S&P 500 und oft
  den DAX am Folgetag (Zahlen nach US-Börsenschluss). Achten auf Umsatz und Gewinn gegen Erwartung, vor allem auf den
  **Ausblick** und die Investitionen in KI.
- **Wahlen:** Erhöhen die Unsicherheit; Märkte reagieren auf Machtverhältnisse und mögliche Politikänderungen
  (Steuern, Handel, Haushalt).
- **Zeitzonen:** In der Woche nach der EU-Zeitumstellung (letzter Sonntag im Oktober) und vor der US-Umstellung
  (erster Sonntag im November) öffnet New York bereits 14:30 Uhr deutscher Zeit.

## Veröffentlichung im Dashboard (täglich)

Die geplante Claude-Sitzung schreibt zusätzlich `reports/analysis.json` in dieses Repo (Branch `main`). Das Dashboard
(Tab "Analyse") liest die Datei direkt von GitHub. Es wird nur diese eine Datei committet.

1. Daten sammeln und die Eingabe-JSON (Tabelle oben) um zwei Felder ergänzen: `"schema_version": 1` und
   `"generated_at_utc"` (ISO-Zeitstempel, UTC). `mode` ist `daily` (Montag bis Freitag) oder `weekly` (Sonntag).
2. Als `reports/analysis.json` speichern (UTF-8, eingerückt) und mit `git add reports/analysis.json` committen:
   `chore(analysis): daily analysis YYYY-MM-DD`. Danach `git push origin main`.
3. Nie andere Dateien anfassen, keine Orders, keine Geheimnisse in die Datei schreiben.
4. Das Dashboard prüft das Format zur Laufzeit. Fehlt ein Block, wird er einfach nicht angezeigt; ein falscher Typ
   (zum Beispiel Text statt Zahl bei `close`) verhindert, dass die Analyse lädt. Zahlen deshalb immer als JSON-Zahlen schreiben, nie als Text.

## E-Mail-Versand (täglich 08:00)

Die Analyse wird als HTML-Mail verschickt. Daten holt eine Claude-Sitzung (TradingView-Tools gibt es nur dort), das Layout
erzeugt `src/analysis_mail.py` deterministisch. Die Mail braucht keine Bilder: Balken, Mini-Kursverlauf und Preisleiter sind
aus Tabellenzellen gebaut und erscheinen in jedem Mail-Programm.

**Ablauf der Sitzung**
1. Daten sammeln (Abschnitt "Datenquellen") und als JSON speichern (Aufbau unten, Beispiel:
   `tests/fixtures/analysis_sample.json`).
2. `python -m src.analysis_mail eingabe.json mail.html mail.txt` erzeugt HTML und Text und gibt den Betreff aus.
3. Mit dem Gmail-Werkzeug `send_message` senden: `to` (Adresse von Benjamin), `subject` (ausgegebener Betreff),
   `htmlBody` (Inhalt von `mail.html`), `body` (Inhalt von `mail.txt`).
4. Montag bis Freitag `mode: "daily"` (Kurzform), sonntags `mode: "weekly"` (ausführlich).

**Eingabe-JSON** (jeder Block ist optional; fehlende Blöcke werden weggelassen)

| Feld | Inhalt |
|---|---|
| `date`, `mode`, `generated_at` | ISO-Datum, `daily` oder `weekly`, Fußzeilentext |
| `verdict` | `label`, `tone` (`good`, `bad`, `warn`, `neutral`), `text` |
| `instruments[]` | `name`, `basis`, `close`, `day_pct`, `week_pct` (Freitag zu Freitag), `closes[]` (letzte 20), `levels{val,poc,vah}`, `candle`, `trend_day`, `trend_week`, `rsi`, `adx`, `setup`, `note` |
| `perf[]` | optional `{label, pct}`; sonst aus `instruments` (der VIX gehört nicht hinein, er verzerrt die Skala) |
| `market[]` | `label`, `value`, `change_pct`, `note`, `tone` |
| `events[]` | `day`, `time`, `title`, `forecast`, `previous`, `importance` (1 bis 3), `why`, `watch`, `reaction` |
| `alerts[]`, `rules[]`, `gaps[]` | kurze Sätze |

**Hinweise**
- Wochenwerte immer Freitag zu Freitag rechnen. Das `Perf.W` von TradingView nutzt einen anderen Bezug und weicht ab.
- Täglich nur Termine von heute und morgen aufnehmen. Eine Mail mit vier Instrumenten und sechs Terminen hat etwa
  40 KB; Gmail kürzt ab etwa 100 KB.
- Nur Anzeige und Lernhilfe, keine Anlageberatung, keine Orders.

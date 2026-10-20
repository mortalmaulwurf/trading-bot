# Dashboard-Anbindung (Plan)

Status: **Plan, noch nicht umgesetzt.** Offen ist vor allem, welches Dashboard auf
dem NAS läuft (Dashy, Homepage, Home Assistant, Eigenbau). Der Bot liefert deshalb
einen stabilen Datenvertrag, unabhängig vom Dashboard.

## Datenvertrag: `reports/latest.json` (`schema_version: 2`)

| Feld | Bedeutung |
|---|---|
| `schema_version` | Version des Vertrags, steigt nur bei Breaking Changes |
| `status` | `ok`, `partial` (einzelne Ticker fehlgeschlagen) oder `failed` |
| `generated_at_utc` | Zeitpunkt des Laufs, für eine Aktualitäts-Anzeige im Dashboard |
| `rule_set` | Aktive Regeln (Netto-CRV, `paper_net_crv`, Risiko pro Trade, Umkehr-Pflicht, Profil-Startdatum) |
| `alerts` / `alerts_count` | Setups, die alle Regel-Checks bestehen |
| `paper_trades_count`, `all_results[].is_paper_trade` | Papier-Trades: alle Regeln erfüllt, Netto-CRV zwischen `paper_net_crv` und `min_net_crv` (nur Anzeige) |
| `all_results[]` | Je Instrument: Kurs, POC/VAL/VAH, `profile_basis`, `rule_checks`, ggf. `position_suggestion` |
| `errors` | Fehlertexte je Ticker |

`rule_checks` je Instrument: `level_hit`, `daily_close_reversal`, `daily_candle_bullish`, `reversal_required`,
`confirmations_ok`, `net_crv`, `net_crv_ok`. Damit kann das Dashboard anzeigen,
**warum** kein Alarm kam.

## Chart-Daten: `reports/charts.json` (`schema_version: 1`)

Tageskerzen der letzten 90 Handelstage je Ticker, getrennt von `latest.json`, damit die
archivierten Tagesreports klein bleiben. Wird bei jedem Lauf überschrieben, nicht archiviert.

```json
{"schema_version": 1, "generated_at_utc": "...", "charts": {"EXS1.DE": {"currency": "EUR", "candles": [{"t": "2026-10-16", "o": 1, "h": 2, "l": 0.5, "c": 1.5}]}}}
```

Level (POC/VAL/VAH) und Plan (Einstieg, Stop, Ziel) stehen in `latest.json`; das Dashboard
verbindet beide Dateien über den Ticker.

## Varianten

| | Beschreibung | Vorteil | Nachteil |
|---|---|---|---|
| A | Dashboard liest die Datei per HTTP von GitHub (Raw-URL) | Keine Änderung am NAS | Abhängig von GitHub, Repo muss öffentlich bleiben |
| B | Container auf der Synology holt per `git pull` (Cron) und liefert `GET /api/latest` (z.B. FastAPI) | Dashboard spricht nur mit dem NAS, Repo kann privat werden | Ein Container mehr |
| C | Bot läuft komplett im NAS-Container, GitHub Actions entfällt | Mehrfach täglich, Preisalarme, Intraday möglich | Secrets und Betrieb auf dem NAS, yfinance-Limits |

Empfehlung: **A als Standard.** Der Bot läuft weiter in GitHub Actions (werktags
22 Uhr UTC) und committet `reports/latest.json`. Render zeigt nur die HTML-Seite aus
`site/` an und rechnet nichts. B oder C lohnen sich erst, wenn das Repo privat werden
soll oder mehrfach täglich gescannt werden soll (Preisalarme, Intraday).

## Offene Entscheidungen

1. Welches Dashboard läuft auf dem NAS, und wie bindet es Daten ein (Widget, iFrame, eigene Seite)?
2. Wo liegt der Zustand "offene Position" (Regel: eine Position gleichzeitig)? Notion-Journal, Dashboard oder eine Datei auf dem NAS?
3. Soll das Dashboard auch die Alarm-Level je Instrument anzeigen (Wochenbriefing)?
4. Bleibt das Repo öffentlich? `config/settings.yaml` enthält Kapital und Risikoparameter, die Reports enthalten Planwerte.

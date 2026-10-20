# Morgen-Status vom NAS auslösen

GitHub startet geplante Workflows oft Stunden zu spät (beobachtet: 4 bis 8 Stunden). Der Bot sendet den
Morgen-Status aber nur, wenn es in Berlin 08:xx ist, deshalb kam keine Nachricht. Der Workflow
`morning_status.yml` hat deshalb keinen `schedule` mehr; das NAS löst ihn um 08:00 Berlin-Zeit aus.
Ein manuell gestarteter Lauf (`workflow_dispatch`) sendet immer (`--force`) und startet innerhalb von Sekunden.

## 1. GitHub-Token (nur für das NAS)

GitHub → Settings → Developer settings → Fine-grained personal access tokens → Generate new token:

- Repository access: **Only select repositories** → `mortalmaulwurf/trading-bot`
- Permissions → Repository → **Actions: Read and write** (sonst nichts)
- Ablauf: z.B. 1 Jahr (Erinnerung in den Kalender)

Den Token nirgends in Git, Logs oder Chat ablegen, nur auf dem NAS:

```bash
# per SSH auf dem NAS
mkdir -p /volume1/docker/trading-trigger
printf '%s' 'HIER_TOKEN_EINFUEGEN' > /volume1/docker/trading-trigger/github_token
chmod 600 /volume1/docker/trading-trigger/github_token
```

## 2. Skript

`/volume1/docker/trading-trigger/morning_status.sh`:

```bash
#!/bin/sh
TOKEN="$(cat /volume1/docker/trading-trigger/github_token)"
curl -sS -f -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"ref":"main"}' \
  https://api.github.com/repos/mortalmaulwurf/trading-bot/actions/workflows/morning_status.yml/dispatches
```

`chmod 700 /volume1/docker/trading-trigger/morning_status.sh`. Bei Erfolg antwortet GitHub mit HTTP 204
(keine Ausgabe); bei Fehlern bricht `-f` mit einem Fehlercode ab.

## 3. Zeitplan (Synology DSM)

Systemsteuerung → Aufgabenplaner → Erstellen → Geplante Aufgabe → Benutzerdefiniertes Skript:

- Benutzer: `root`
- Zeitplan: **Montag bis Freitag, 08:00**
- Benutzerdefiniertes Skript: `/volume1/docker/trading-trigger/morning_status.sh`
- Optional: Ausgabe-Ergebnis per E-Mail bei Fehlern senden

Der Aufgabenplaner rechnet in der NAS-Zeitzone. Steht diese auf **Europe/Berlin**
(Systemsteuerung → Regional-Optionen), kümmert sich DSM selbst um Sommer-/Winterzeit; es ist nur
eine Zeile nötig. Läuft ein eigener Linux-`crontab` in UTC, sind zwei Zeilen nötig (06:00 und 07:00 UTC),
und die Zeitprüfung im Bot sendet nur zur Stunde 08 Berlin.

## 4. Test

Aufgabe im Aufgabenplaner einmal manuell starten. Innerhalb von etwa 30 Sekunden sollte die
Telegram-Nachricht ankommen und unter GitHub → Actions ein Lauf "Morning Status" mit Event
`workflow_dispatch` erscheinen.

## Grenzen

Ist das NAS um 08:00 aus oder offline, kommt keine Nachricht und niemand merkt es. Der Status
zeigt aber weiterhin "Scan veraltet" an, sobald er wieder läuft.

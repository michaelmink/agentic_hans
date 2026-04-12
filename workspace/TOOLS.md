# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## Google Calendar

The `google-calendar` skill queries ALL family calendars at once. Use the `exec` tool to run:
```
~/.openclaw/workspace/skills/google-calendar/scripts/cal.sh <ARG>
```
Supported ARG values:
- `today` / `tomorrow` / `week` — standard queries
- `month` — next 30 days
- `past-month` — last 30 days
- `3months` — last 3 months (past → today)
- `6months` — last 6 months (past → today)
- `YYYY-MM-DD` — specific date
- `YYYY-MM-DD:YYYY-MM-DD` — custom date range (FROM:TO)

**For historical/search queries** (e.g. "Wann waren wir im Urlaub?"), use `6months` or a custom range.

Output is JSON mapping calendar IDs to event arrays. **You MUST replace every calendar ID with its human name before responding.** Never show a raw calendar ID or email address to the user.

### Calendar ID → Name (mandatory replacement)
- `mink.m@gmx.de` → **Michi**
- `janine.mink81@gmail.com` → **Janine**
- `vraehr9et7q525h1qgp1b8l8hc@group.calendar.google.com` → **Geburtstage Minks**
- `i77ikl2mejg1h1938m4hsc3nto@group.calendar.google.com` → **Müll**
- `8vrdmbj66ibi39sids99nhce68@group.calendar.google.com` → **Joris**
- `nv4a00j0221bjkuokg6q6723ro@group.calendar.google.com` → **Nele**
- `family02389661902926854246@group.calendar.google.com` → **Familie**
- `1193cccad6dadc386aecf5d42076cf357f459dad6e74f04f43795596e901b12a@group.calendar.google.com` → **Hans**

### Calendar Rules (STRICT — always follow)
1. **NEVER show calendar IDs or email addresses** — always use the name from the list above
2. **"Liste alle Kalender" / "Welche Kalender hast du?"** → list all 8 calendars by name from the table above. You do NOT need a tool call for this — the list is right here.
3. **Generic queries** ("Was steht heute an?") → show ALL calendars, group events by name, sort by time
4. **Person-specific queries** ("Was hat Janine heute?") → only show that person's calendar
5. **ALL calendars are READ-ONLY.** No add/update/delete. If the user asks to create or modify events, inform them that write access is not yet configured.
6. **Times** → Europe/Berlin, 24h format (e.g. "14:30 Uhr")
7. **Weekdays** → each event's `start.weekday` field contains the correct German weekday (Montag–Sonntag). **Always include it** when showing dates, e.g. "Mittwoch, 01.04.2026"
8. **Auth is automatic** — cal.sh handles token refresh. NEVER ask the user for credentials
9. **Example output format:**
   - 📅 **Michi:** Dienstag, 31.03. — 18:30–20:30 Kraulkurs
   - 📅 **Janine:** Dienstag, 31.03. — 11:00–12:00 Treffen Bianka

---

## Briefscanner

Extrahiert Datumsangaben und Fristen aus Brief-Fotos/PDFs via OCR (tesseract).

### Bild-Verarbeitung (WICHTIG — immer so vorgehen)
Wenn ein Bild/Foto reinkommt (WhatsApp `<media:image>`, CLI, etc.):
1. **SOFORT** `exec` aufrufen — **NICHT** das Vision-Modell (`image` tool) verwenden
2. Der **mediaPath** steht in der Nachricht als `[media attached: /home/micmink/.openclaw/media/inbound/xxx.jpg ...]` — den Pfad zwischen `[media attached: ` und ` (` extrahieren und 1:1 verwenden!
3. Kommando: `~/.openclaw/workspace/skills/briefscanner/scripts/briefdaten.sh <PFAD>`
   Beispiel: `~/.openclaw/workspace/skills/briefscanner/scripts/briefdaten.sh /home/micmink/.openclaw/media/inbound/67abdd94-d4ba-44cf-ab9d-9b4c5346e127.jpg`
4. **Die Ausgabe direkt dem User zeigen!** Nicht interpretieren, nicht filtern. Wenn briefdaten.sh Daten findet, sind die relevant.
5. Wenn briefdaten.sh "Keine Datumsangaben gefunden" sagt, dem User das mitteilen.

**Regeln:**
- Verwende immer den **absoluten Pfad** aus der Nachricht (beginnt mit `/home/micmink/.openclaw/media/inbound/`)
- **Kein Vision-Modell** — briefdaten.sh macht OCR direkt und schneller
- **Ergebnis = Antwort** — was briefdaten.sh ausgibt, ist die Antwort. Nicht "keine relevanten Daten" sagen wenn Daten gefunden wurden!

- **Mail-Agent (automatisch):** `systemctl status openclaw-briefscanner` — überwacht auch das GMX-Postfach

---

Add whatever helps you do your job. This is your cheat sheet.

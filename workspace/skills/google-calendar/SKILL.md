---
name: google-calendar
description: "Query and search family calendars. Use exec tool: ~/.openclaw/workspace/skills/google-calendar/scripts/cal.sh <timerange> [query] [calendars]. Auth is automatic."
---

# Google Calendar Skill

Use the `exec` tool to run:
```
~/.openclaw/workspace/skills/google-calendar/scripts/cal.sh <timerange> [query] [calendars]
```

## Parameters

**timerange** (required): One of:
`today`, `tomorrow`, `week`, `month`, `past-month`, `3months`, `6months`, `year`, `2years`, `next-year`, `YYYY-MM-DD`, `YYYY-MM-DD:YYYY-MM-DD`

**query** (optional): A search term. When provided, uses Groq to find semantically matching events (e.g. "Urlaub" also finds "Camping", "Hotel", etc). When omitted, returns all events in the time range.

**calendars** (optional): Comma-separated calendar names to filter. If omitted, ALL calendars are queried.
Available: `Michi`, `Janine`, `Joris`, `Nele`, `Familie`, `Hans`, `Geburtstage Minks`, `Müll`

## Examples

- `cal.sh today` — all events today, all calendars
- `cal.sh week Janine` — Janine's events this week
- `cal.sh today Michi,Janine` — Michi & Janine today
- `cal.sh year Urlaub` — search vacation events in the past year
- `cal.sh 2years Zahnarzt Janine` — search dentist appointments, 2 years, Janine only
- `cal.sh next-year Geburtstag Familie` — search birthdays next year in Familie calendar

## Rules

- **Use a search query when the user asks about a specific event type** ("Wann war der Zahnarzt?", "Wann waren wir im Urlaub?"). This avoids context overflow over large time ranges.
- **Omit the query for general listing** ("Was steht heute an?", "Was haben wir diese Woche?").
- When the user asks about a **specific person**, use the calendars parameter.
- Calendar names are **case-insensitive**.
- For event searches over unknown time ranges, default to `year`. Use `2years` only if the user explicitly asks further back.

#!/usr/bin/env bash
# Calendar query — unified list & search
# Usage: cal.sh <timerange> [query] [calendars]
#   cal.sh today                       → all events today
#   cal.sh week Janine                 → Janine's events this week
#   cal.sh year Urlaub                 → search "Urlaub" in past year (Groq)
#   cal.sh 2years Zahnarzt Janine      → search "Zahnarzt" 2 years, Janine only
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TZ_LOCAL="Europe/Berlin"

# Known calendar names (lowercase) for distinguishing query vs calendar arg
KNOWN_CALS="michi janine joris nele familie hans geburtstage\ minks müll"

# Load credentials
source ~/.openclaw/.env
export GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GOOGLE_REFRESH_TOKEN GOOGLE_CALENDAR_ID
export GOOGLE_CALENDAR_IDS GOOGLE_CALENDAR_NAMES
export GROQ_API_KEY

# Refresh access token
python3 "$SCRIPT_DIR/refresh_token.py" > /dev/null 2>&1
source ~/.config/google-calendar/secrets.env
export GOOGLE_ACCESS_TOKEN

if [ -z "${GOOGLE_CALENDAR_IDS:-}" ]; then
  export GOOGLE_CALENDAR_IDS="${GOOGLE_CALENDAR_ID}"
fi

# Parse arguments
ARG="${1:-today}"
ARG2="${2:-}"
ARG3="${3:-}"

# Determine if ARG2 is a calendar name or a search query
# Check each comma-separated part of ARG2 against known calendars
is_calendar_name() {
  local input="${1,,}"  # lowercase
  IFS=',' read -ra parts <<< "$input"
  for part in "${parts[@]}"; do
    part="$(echo "$part" | xargs)"  # trim
    local found=0
    IFS=',' read -ra names <<< "${GOOGLE_CALENDAR_NAMES,,}"
    for name in "${names[@]}"; do
      name="$(echo "$name" | xargs)"
      [[ "$part" == "$name" ]] && found=1 && break
    done
    [[ $found -eq 0 ]] && return 1
  done
  return 0
}

QUERY=""
CALENDARS=""

if [ -n "$ARG2" ]; then
  if is_calendar_name "$ARG2"; then
    # ARG2 is a calendar filter, no search query
    CALENDARS="$ARG2"
  else
    # ARG2 is a search query
    QUERY="$ARG2"
    CALENDARS="${ARG3:-}"
  fi
fi

# Determine date range and max results
MAX=20
case "$ARG" in
  today)
    FROM=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    TO="$FROM"
    ;;
  tomorrow)
    FROM=$(TZ="$TZ_LOCAL" date -d '+1 day' +%Y-%m-%d)
    TO="$FROM"
    ;;
  week)
    FROM=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    TO=$(TZ="$TZ_LOCAL" date -d '+7 days' +%Y-%m-%d)
    ;;
  month)
    FROM=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    TO=$(TZ="$TZ_LOCAL" date -d '+30 days' +%Y-%m-%d)
    MAX=100
    ;;
  past-month)
    FROM=$(TZ="$TZ_LOCAL" date -d '-30 days' +%Y-%m-%d)
    TO=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    MAX=100
    ;;
  3months)
    FROM=$(TZ="$TZ_LOCAL" date -d '-90 days' +%Y-%m-%d)
    TO=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    MAX=200
    ;;
  6months)
    FROM=$(TZ="$TZ_LOCAL" date -d '-180 days' +%Y-%m-%d)
    TO=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    MAX=200
    ;;
  year|past-year)
    FROM=$(TZ="$TZ_LOCAL" date -d '-365 days' +%Y-%m-%d)
    TO=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    MAX=500
    ;;
  next-year)
    FROM=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    TO=$(TZ="$TZ_LOCAL" date -d '+365 days' +%Y-%m-%d)
    MAX=500
    ;;
  2years)
    FROM=$(TZ="$TZ_LOCAL" date -d '-730 days' +%Y-%m-%d)
    TO=$(TZ="$TZ_LOCAL" date +%Y-%m-%d)
    MAX=500
    ;;
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])
    FROM="${ARG%%:*}"
    TO="${ARG##*:}"
    MAX=200
    ;;
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])
    FROM="$ARG"
    TO="$ARG"
    ;;
  *)
    echo "Usage: cal.sh <timerange> [query] [calendars]" >&2
    echo "Timeranges: today|tomorrow|week|month|past-month|3months|6months|year|2years|YYYY-MM-DD|YYYY-MM-DD:YYYY-MM-DD" >&2
    exit 1
    ;;
esac

# Convert local dates to UTC
UTC_FROM=$(date -u -d "TZ=\"$TZ_LOCAL\" $FROM 00:00:00" +%Y-%m-%dT%H:%M:%SZ)
UTC_TO=$(date -u -d "TZ=\"$TZ_LOCAL\" $TO 23:59:59" +%Y-%m-%dT%H:%M:%SZ)

# Build python args
PY_ARGS=(--from "$UTC_FROM" --to "$UTC_TO" --max "$MAX")
[ -n "$QUERY" ] && PY_ARGS+=(--query "$QUERY")
[ -n "$CALENDARS" ] && PY_ARGS+=(--calendars "$CALENDARS")

exec python3 "$SCRIPT_DIR/google_calendar.py" query "${PY_ARGS[@]}"

#!/usr/bin/env python3
import os, sys, json, urllib.request, urllib.parse, argparse
from datetime import datetime

BASE_URL = 'https://www.googleapis.com/calendar/v3'
GROQ_BASE_URL = 'https://api.groq.com/openai/v1'
GROQ_MODEL = 'llama-3.3-70b-versatile'

WEEKDAYS_DE = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

# Calendar ID → human name mapping from env
def get_calendar_name_map():
    ids = [c.strip() for c in os.getenv('GOOGLE_CALENDAR_IDS', '').split(',') if c.strip()]
    names = [n.strip() for n in os.getenv('GOOGLE_CALENDAR_NAMES', '').split(',') if n.strip()]
    return dict(zip(ids, names)) if len(ids) == len(names) else {}

def add_weekday(dt_str):
    try:
        if 'T' in dt_str:
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.strptime(dt_str, '%Y-%m-%d')
        return WEEKDAYS_DE[dt.weekday()]
    except (ValueError, IndexError):
        return None

def compact_event(item):
    start = item.get('start', {})
    end = item.get('end', {})
    s = start.get('dateTime') or start.get('date', '')
    e = end.get('dateTime') or end.get('date', '')
    ev = {
        'summary': item.get('summary', ''),
        'start': s,
        'end': e,
    }
    wd = add_weekday(s)
    if wd:
        ev['weekday'] = wd
    loc = item.get('location')
    if loc:
        ev['location'] = loc
    return ev

def get_access_token():
    token = os.getenv('GOOGLE_ACCESS_TOKEN')
    if not token:
        sys.stderr.write('Error: GOOGLE_ACCESS_TOKEN env var not set\n')
        sys.exit(1)
    return token

def get_calendar_ids():
    ids = os.getenv('GOOGLE_CALENDAR_IDS')
    if ids:
        return [c.strip() for c in ids.split(',') if c.strip()]
    single = os.getenv('GOOGLE_CALENDAR_ID')
    return [single] if single else []

def request(method, url, data=None):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {get_access_token()}')
    req.add_header('Accept', 'application/json')
    if data:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        sys.stderr.write(f'HTTP error {e.code}: {e.read().decode()}\n')
        sys.exit(1)

def groq_filter_summaries(query, unique_summaries):
    """Send anonymized event titles to Groq and get back matching ones.
    Only titles are sent — no dates, no calendar names, no personal data."""
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        sys.stderr.write('Error: GROQ_API_KEY env var not set\n')
        sys.exit(1)

    # Build a simple numbered list for Groq
    titles_list = '\n'.join(f'- {s}' for s in unique_summaries)
    prompt = (
        f'Search query: "{query}"\n\n'
        f'Here is a list of calendar event titles:\n{titles_list}\n\n'
        f'Return a JSON array containing the EXACT text of each title that is relevant to the search query.\n'
        f'Include titles that are directly or indirectly related. For example:\n'
        f'- "Lach Mal" is a dental practice name → relevant to "Zahnarzt"\n'
        f'- "Baden Baden" could be a trip → relevant to "Urlaub"\n'
        f'- "Campingplatz Club Farret" → relevant to "Urlaub"\n'
        f'- "Zahnreinigung" → relevant to "Zahnarzt"\n'
        f'Do NOT include titles that are clearly unrelated.\n\n'
        f'Return ONLY a JSON array of strings, copying the titles exactly as listed above. '
        f'If nothing matches, return []. No explanation, no numbering.'
    )

    body = json.dumps({
        'model': GROQ_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0,
        'max_tokens': 4096,
    }).encode()

    req = urllib.request.Request(
        f'{GROQ_BASE_URL}/chat/completions',
        data=body, method='POST'
    )
    req.add_header('Authorization', f'Bearer {api_key}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'openclaw-calendar/1.0')

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        sys.stderr.write(f'Groq API error {e.code}: {e.read().decode()}\n')
        # Fallback: simple substring match
        q = query.lower()
        return {s for s in unique_summaries if q in s.lower()}

    content = data['choices'][0]['message']['content'].strip()
    try:
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        matches = json.loads(content)
        if not isinstance(matches, list):
            raise TypeError
        # Fuzzy match returned titles against our actual titles
        # (Groq might slightly alter text, so we match case-insensitively)
        actual_lower = {s.lower(): s for s in unique_summaries}
        matched = set()
        for m in matches:
            if not isinstance(m, str):
                continue
            ml = m.strip().lower()
            # Exact match (case-insensitive)
            if ml in actual_lower:
                matched.add(actual_lower[ml])
            else:
                # Substring match: if Groq returned a close variant, find it
                for al, orig in actual_lower.items():
                    if ml in al or al in ml:
                        matched.add(orig)
        return matched
    except (json.JSONDecodeError, TypeError):
        sys.stderr.write(f'Warning: could not parse Groq response, falling back to substring\n')
        q = query.lower()
        return {s for s in unique_summaries if q in s.lower()}

def resolve_calendar_ids(calendars_arg, name_map, all_cal_ids):
    if calendars_arg:
        requested = [n.strip().lower() for n in calendars_arg.split(',')]
        reverse_map = {v.lower(): k for k, v in name_map.items()}
        cal_ids = [reverse_map[n] for n in requested if n in reverse_map]
        if not cal_ids:
            sys.stderr.write('Error: none of the requested calendars found\n')
            sys.exit(1)
        return cal_ids
    return all_cal_ids

def fetch_events(cal_ids, name_map, time_min, time_max, max_results):
    all_events = []
    for cal_id in cal_ids:
        params = {
            'maxResults': max_results,
            'singleEvents': 'true',
            'orderBy': 'startTime',
        }
        if time_min:
            params['timeMin'] = time_min
        if time_max:
            params['timeMax'] = time_max
        url = f"{BASE_URL}/calendars/{urllib.parse.quote(cal_id)}/events?{urllib.parse.urlencode(params)}"
        resp = request('GET', url)
        cal_name = name_map.get(cal_id, cal_id)
        for item in resp.get('items', []):
            ce = compact_event(item)
            summary = ce.get('summary', '').strip()
            if summary:
                all_events.append((cal_name, ce, summary))
    return all_events

def query_events(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', dest='query', help='Search term (uses Groq for semantic matching)')
    parser.add_argument('--from', dest='time_min', help='ISO start time')
    parser.add_argument('--to', dest='time_max', help='ISO end time')
    parser.add_argument('--max', dest='max_results', type=int, default=20)
    parser.add_argument('--calendars', dest='calendars', help='Comma-separated calendar names')
    parsed = parser.parse_args(args)

    name_map = get_calendar_name_map()
    cal_ids = resolve_calendar_ids(parsed.calendars, name_map, get_calendar_ids())

    # If searching, fetch more events and use higher max
    if parsed.query and parsed.max_results == 20:
        parsed.max_results = 500

    all_events = fetch_events(cal_ids, name_map, parsed.time_min, parsed.time_max, parsed.max_results)

    if not all_events:
        print(json.dumps({}))
        return

    # If query given, filter via Groq semantic matching on event titles
    if parsed.query:
        unique_summaries = list(dict.fromkeys(ev[2] for ev in all_events))
        matching_titles = groq_filter_summaries(parsed.query, unique_summaries)
        sys.stderr.write(f'Matched {len(matching_titles)} of {len(unique_summaries)} unique titles\n')
        results = {}
        for cal_name, ce, summary in all_events:
            if summary in matching_titles:
                results.setdefault(cal_name, []).append(ce)
    else:
        # No query — return all events
        results = {}
        for cal_name, ce, summary in all_events:
            results.setdefault(cal_name, []).append(ce)

    print(json.dumps(results, separators=(',', ':')))

# All calendars are READ-ONLY (calendar.readonly scope).

def add_event(args):
    sys.stderr.write('Error: All calendars are read-only. Write access is not configured.\n')
    sys.exit(1)

def update_event(args):
    sys.stderr.write('Error: All calendars are read-only. Write access is not configured.\n')
    sys.exit(1)

def delete_event(args):
    sys.stderr.write('Error: All calendars are read-only. Write access is not configured.\n')
    sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.stderr.write('Usage: google_calendar.py <query|add|update|delete> [options]\n')
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == 'query':
        query_events(args)
    elif cmd == 'add':
        add_event(args)
    elif cmd == 'update':
        update_event(args)
    elif cmd == 'delete':
        delete_event(args)
    else:
        sys.stderr.write(f'Unknown command: {cmd}\n')
        sys.exit(1)

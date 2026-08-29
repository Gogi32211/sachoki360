import csv
import io
import re
import requests
from datetime import date, datetime, timedelta

# The live master schedule ("TOURS_All Dates_2026"), not the one-off personal
# copy this used to point at — that copy stopped being updated back in June,
# so it never carried TH/TK/TM/TV (added later) and was slowly falling behind
# on every other series too.
SHEET_ID = "13FoSFZqpi4QAm2CDc1qT3uB7AKHOFEJv"
SHEET_GID = "549302577"
CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/export?format=csv&gid={SHEET_GID}"
)

# Same series set the rest of the app recognizes — this used to omit
# HM1/HM2/HT/TH/TK/TM/TV, so those tours' columns were never even seen and
# their nights stayed on the seed template's placeholder hotel.
TOUR_RE = re.compile(r'^(ZT|LN|KT|DT1|DT2|LT|HM1|HM2|HM|HT|TH|TK|TM|TV|MT|ST)-\d{4}$')

# Hotels outside GEO/ARM — skip updating daily_log for these
SKIP_HOTELS = {
    'flight', 'baku', 'baku ok', 'sheki', 'sheki ok',
    'marxal', 'wyndhem', 'wyndham', 'wyndhemgarden',
    'marriott baku', 'marriott hotel boulevard',
    'el resort', 'el resort sheki',
}

# Confirmed hotel name map (specific hotel name → canonical)
HOTEL_MAP = {
    # Tbilisi
    'pullman': 'Pullman Tbilisi',
    'pullman tbilisi': 'Pullman Tbilisi',
    'hualing': 'Hualing Tbilisi',
    'hualing tbilisi': 'Hualing Tbilisi',
    'gino': 'Gino Paradise',
    'gino - 75 usd': 'Gino Paradise',
    'pine astoria': 'Pine Astoria',
    'pine tbilisi': 'Pine Astoria',
    'pine': 'Pine Astoria',
    'redisson tbilisi': 'Radisson Blu Tbilisi',
    'radisson tbilisi': 'Radisson Blu Tbilisi',
    'radisson blu tbilisi': 'Radisson Blu Tbilisi',
    # Yerevan
    'radisson yerevan': 'Radisson Blu Yerevan',
    'radisson blu yerevan': 'Radisson Blu Yerevan',
    'aghababayan': "Aghababyan's Yerevan",
    'agababayan': "Aghababyan's Yerevan",
    'agababayans': "Aghababyan's Yerevan",
    'armenia marriott': 'Armenia Marriott Yerevan',
    # Akhaltsikhe — "akhaltsikhe inn" confirmed, "akhaltsikhe" alone is uncertain
    'akhaltsikhe inn': 'Akhaltsikhe Inn 5★',
    # Batumi
    'greenwood batumi': 'Greenwood Batumi',
    'bw batumi': 'Best Western Batumi',
    'best western batumi': 'Best Western Batumi',
    'radisson blu hotel batumi': 'Radisson Blu Batumi',
    # Mestia — "gistola" confirmed, "mestia" alone is uncertain
    'gistola': 'Gistola Resort 5★',
    'gistola resort': 'Gistola Resort 5★',
    'gistola resort mestia': 'Gistola Resort 5★',
    'lilat': 'Lilati Mestia',
    'lilati': 'Lilati Mestia',
    'lilati mestia': 'Lilati Mestia',
    # Gori — "gori inn" confirmed, "gori" alone is uncertain
    'gori inn': 'Gori Inn',
    # Gudauri — "marco polo" / "gudauri inn" confirmed, "gudauri" alone is uncertain
    'marco polo': 'Marco Polo Gudauri',
    'marco polo gudauri': 'Marco Polo Gudauri',
    'gudauri inn': 'Gudauri Inn',
    'gudauri lodge': 'Gudauri Lodge',
    # Other
    'covasar sevan': 'Covasar Sevan',
    'crown plaza borjomi': 'Crowne Plaza Borjomi',
    'crown plaa bojomi': 'Crowne Plaza Borjomi',
    'kutaisi inn': 'Kutaisi Inn',
}

# City-only names without a specific hotel → hotel not yet confirmed
UNCERTAIN_CITY = {'mestia', 'gori', 'gudauri', 'akhaltsikhe', 'yerevan'}


def _clean(name: str) -> str:
    """Strip booking-status suffixes, detect uncertainty, and normalise hotel name."""
    s = name.strip()
    # Remove trailing status markers
    for suffix in (' Rok', ' rok', ' R-no staff rooms', ' R', ' r',
                   ' ok', ' Ok', ' - revised', ' -revised',
                   ' cancelled', ' Cancelled', ' cacnelled',
                   ' - cancelled', ' - paid', ' Rok- Paid',
                   ' sent', ' paid', ' Paid'):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    # Remove parenthetical notes like " (ბუქინგიდან)"
    s = re.sub(r'\s*\(.*?\)\s*', '', s).strip()

    # Multiple hotel options separated by "/" → hotel not confirmed
    multi = '/' in s
    if multi:
        s = s.split('/')[0].strip()

    # Strip room count info: "8 twin", "3 twin", "- 1 double", etc.
    s = re.sub(r'\s*[-–]\s*\d+\s*(twin|double|single|suite|room)\b.*', '', s, flags=re.IGNORECASE).strip()
    s = re.sub(r'\s+\d+\s*(twin|double|single|suite|room)\b.*', '', s, flags=re.IGNORECASE).strip()

    if not s:
        return ''

    # Check skip list
    if s.lower() in SKIP_HOTELS or any(s.lower().startswith(k) for k in SKIP_HOTELS):
        return ''

    key = s.lower().strip()

    # Check confirmed hotel map
    if key in HOTEL_MAP:
        normalized = HOTEL_MAP[key]
        return ('? ' + normalized) if multi else normalized

    # Check uncertain city-only names
    if key in UNCERTAIN_CITY:
        return '? ' + s.title()

    # Multi-option fallback (confirmed hotel not in map)
    if multi:
        return '? ' + s.title()

    # Fall back: title-case cleaned string
    return s.title() if s else ''


def _code_date(code: str):
    """The tour code's own MMDD as a date — unambiguous, unlike the cells
    in the grid below it, and close to that block's first row regardless
    of a series' start-offset (at most a few days off)."""
    m = re.match(r'^[A-Z0-9]+-(\d{2})(\d{2})$', code)
    if not m:
        return None
    try:
        return date(2026, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def _parse_date(cell: str, expected=None):
    """Return date object or None. Handles m/d/yy, m/d/yyyy, d/m/yy, d/m/yyyy.

    A cell like "1/9" is genuinely ambiguous (Jan 9 or Sep 1?) and which one
    the sheet means depends on its locale, which isn't ours to assume. Each
    tour's rows run one calendar day after the next, though, so when a cell
    has more than one valid reading, `expected` — the previous row's date + 1,
    or (for a block's first row) the tour code's own MMDD, which is never
    ambiguous — picks whichever reading lands closest to it, instead of
    silently taking whichever format happens to match first. A genuine
    misread lands weeks or months away; the real date never does.
    """
    s = cell.strip()
    if not s:
        return None
    candidates = []
    for fmt in ('%m/%d/%y', '%m/%d/%Y', '%d/%m/%y', '%d/%m/%Y'):
        try:
            d = datetime.strptime(s, fmt).date()
        except ValueError:
            continue
        if d.year == 26:
            d = d.replace(year=2026)
        elif d.year != 2026:
            continue
        if d not in candidates:
            candidates.append(d)
    if not candidates:
        return None
    if expected is not None and len(candidates) > 1:
        return min(candidates, key=lambda d: abs((d - expected).days))
    return candidates[0]


def fetch_hotel_assignments() -> dict:
    """
    Download the Google Sheet as CSV (read-only) and return:
    {tour_code: {date_iso: hotel_name}}
    Only includes GEO/ARM hotels; skips AZ/Flight rows.
    Hotels not yet confirmed are prefixed with "? ".
    """
    try:
        resp = requests.get(CSV_URL, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[sheets_sync] Could not fetch sheet: {e}")
        return {}

    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)

    assignments: dict = {}
    active_cols: dict = {}
    expected_dates: dict = {}
    cancelled_section = False

    for row in rows:
        row_text = ' '.join(row).lower()
        if 'cancelled' in row_text and 'for cancell' in row_text:
            cancelled_section = True
        if 'done 2026' in row_text:
            cancelled_section = False

        new_cols: dict = {}
        for j, cell in enumerate(row):
            c = cell.strip()
            if TOUR_RE.match(c):
                new_cols[j] = c

        if new_cols:
            active_cols = new_cols
            expected_dates = {}
            for col, code in new_cols.items():
                anchor = _code_date(code)
                if anchor:
                    expected_dates[col] = anchor
                if code not in assignments:
                    assignments[code] = {}
            cancelled_section = False
            continue

        if not active_cols or cancelled_section:
            continue

        found_any_date = False
        for col_idx, tour_code in active_cols.items():
            if col_idx >= len(row):
                continue
            date_obj = _parse_date(row[col_idx], expected_dates.get(col_idx))
            if date_obj is None:
                continue
            found_any_date = True
            expected_dates[col_idx] = date_obj + timedelta(days=1)
            hotel_raw = row[col_idx + 1].strip() if col_idx + 1 < len(row) else ''
            hotel = _clean(hotel_raw)
            if hotel:
                assignments[tour_code][date_obj.isoformat()] = hotel

        if not found_any_date:
            non_empty = sum(1 for c in row if c.strip())
            if non_empty > 2:
                active_cols = {}

    total = sum(len(v) for v in assignments.values())
    tours_found = sum(1 for v in assignments.values() if v)
    print(f"[sheets_sync] Parsed {tours_found} tours, {total} hotel assignments from Google Sheets")
    return assignments

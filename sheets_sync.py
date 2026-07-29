import csv
import io
import re
import requests
from datetime import datetime

SHEET_ID = "1HSqlZfuatE5xb9lPP1_-A_RKXaTR0YMq"
SHEET_GID = "549302577"
CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/export?format=csv&gid={SHEET_GID}"
)

TOUR_RE = re.compile(r'^(ZT|LN|KT|DT1|DT2|LT|ST|MT|HM)-\d{4}$')

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


def _parse_date(cell: str):
    """Return date object or None. Handles m/d/yy, m/d/yyyy, d/m/yy."""
    s = cell.strip()
    if not s:
        return None
    for fmt in ('%m/%d/%y', '%m/%d/%Y', '%d/%m/%y', '%d/%m/%Y'):
        try:
            d = datetime.strptime(s, fmt).date()
            if d.year == 2026:
                return d
            if d.year == 26:
                return d.replace(year=2026)
            return None
        except ValueError:
            continue
    return None


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
            for code in new_cols.values():
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
            date_obj = _parse_date(row[col_idx])
            if date_obj is None:
                continue
            found_any_date = True
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

"""
Sync guide / hotel / restaurant phone numbers from the master schedule
workbook's "informations" tab. READ-ONLY.

Matching each phone number back to the app's own records is best-effort,
since the three lists don't share a key with what's already stored:

  - restaurants are already Georgian script, same as menu_data and
    tour_meals — near-exact, with a small alias table for known spelling
    variants between the two sheets.
  - hotels are Georgian brand names here, matched against daily_log's
    English ones by database.py's _hotel_phone_for(), which reuses the
    Georgian/English alias table _item_dates already relies on to date
    balance-sheet hotel costs — not something this module handles.
  - guides are Georgian names here, but tours.guide is transliterated to
    Latin by schedule_sync's sheet reader — matched by transliterating the
    Georgian name and comparing normalized words, so this one can
    occasionally miss on an unusual spelling.
"""
import io
import re
import requests
from openpyxl import load_workbook

from schedule_sync import SHEET_ID

INFO_TAB = "informations"
_PLACEHOLDER_NAMES = {"გიდი"}  # unnamed rows in the guide column

_GEO_LAT = {
    'ა': 'a', 'ბ': 'b', 'გ': 'g', 'დ': 'd', 'ე': 'e', 'ვ': 'v', 'ზ': 'z',
    'თ': 't', 'ი': 'i', 'კ': 'k', 'ლ': 'l', 'მ': 'm', 'ნ': 'n', 'ო': 'o',
    'პ': 'p', 'ჟ': 'zh', 'რ': 'r', 'ს': 's', 'ტ': 't', 'უ': 'u', 'ფ': 'p',
    'ქ': 'k', 'ღ': 'gh', 'ყ': 'q', 'შ': 'sh', 'ჩ': 'ch', 'ც': 'ts',
    'ძ': 'dz', 'წ': 'ts', 'ჭ': 'ch', 'ხ': 'kh', 'ჯ': 'j', 'ჰ': 'h',
}

# Known spelling variants between the "informations" tab and
# menu_data.RESTAURANT_MENUS / tour_meals.restaurant.
RESTAURANT_ALIASES = {
    'ლუზიასთან': 'ლუიზასთან',
    'კტვ პატარძეული': 'კტვ',
}

# Three one-off contacts the office typed into their own stray cells rather
# than a proper repeating column (each is just a name + the very next cell
# as its phone, sitting on its own row) — matched by prefix since neither
# their exact cell nor their full label text is stable. Shown on daily_log
# days that meet each one's own condition (see database.get_tours_on_date /
# get_guide_view): border_transport on any day with a border crossing,
# kazbegi_delika on a Kazbegi/Gudauri day, mestia_delika on a Mestia day
# (covers both the Ushguli excursion and any night at Lilati Mestia, since
# the bus can't reach either and this transport carries guests + luggage).
_EXTRA_CONTACT_PREFIXES = [
    ('სატრანსპორტო', 'border_transport'),
    ('ყაზბეგის დელიკები', 'kazbegi_delika'),
    ('მესტიის დელიკები', 'mestia_delika'),
]


def _translit(s: str) -> str:
    return ''.join(_GEO_LAT.get(ch, ch) for ch in (s or '').lower())


def _words(s: str) -> list:
    s = re.sub(r'[^a-z\s]', ' ', _translit(s))
    return [w for w in s.split() if len(w) > 2]


def _norm_phone(v) -> str:
    s = str(v or '').strip()
    if s.endswith('.0'):
        s = s[:-2]
    s = re.sub(r'[ \s\-]+', ' ', s).strip()
    return s


def fetch_contacts() -> dict:
    """Return {"guides": [{"name","phone"}], "hotels": {name: {phone,phone2}},
    "restaurants": {name: {phone,phone2}}, "extra": {key: {"name","phone"}},
    "company": [{"name","phone"}], "stay": [{"name","phone","phone2"}]}."""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
    guides, hotels, restaurants, extra, company, stay = [], {}, {}, {}, [], []
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        wb = load_workbook(io.BytesIO(resp.content), data_only=True, read_only=True)
        ws = None
        for w in wb.worksheets:
            if (w.title or '').strip().lower() == INFO_TAB:
                ws = w
                break
        if ws is None:
            print(f"[contacts_sync] no '{INFO_TAB}' tab found")
            wb.close()
            return {}

        # The three one-off contacts can be on any row/column, so scan the
        # whole tab for them before the regular min_row=3 column-position
        # loop below (which only covers the repeating guide/hotel/restaurant
        # lists starting at row 3).
        for row in ws.iter_rows(values_only=True):
            cells = list(row)
            for i, cell in enumerate(cells):
                text = str(cell or '').strip()
                if not text:
                    continue
                for prefix, key in _EXTRA_CONTACT_PREFIXES:
                    if text.startswith(prefix) and key not in extra:
                        phone = _norm_phone(cells[i + 1]) if i + 1 < len(cells) else ''
                        if phone:
                            extra[key] = {"name": text, "phone": phone}
                        break

        # GTC 360's own staff contacts sit under a literal "GTC 360" header
        # cell, and the guide/driver stay contacts under one containing
        # "დარჩენა" — found dynamically rather than by a fixed column
        # index, since the office has already inserted a whole extra
        # column group in front of the GTC block once already, which
        # would silently break a hardcoded position. The header itself
        # isn't reliably row 1 either (it's sometimes preceded by a blank
        # row), so the first several rows are scanned rather than assuming
        # a fixed row number too.
        gtc_col = None
        stay_col = None
        for header_row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
            for i, cell in enumerate(header_row):
                text = str(cell or '').strip()
                if text.upper().startswith('GTC'):
                    gtc_col = i
                elif 'დარჩენა' in text:
                    stay_col = i

        for row in ws.iter_rows(min_row=3, values_only=True):
            cells = list(row) + [None] * 20

            g_name = str(cells[1] or '').strip()
            if g_name and g_name not in _PLACEHOLDER_NAMES:
                phone = _norm_phone(cells[2])
                if phone:
                    guides.append({"name": g_name, "phone": phone})

            h_name = str(cells[4] or '').strip()
            if h_name:
                hotels[h_name] = {"phone": _norm_phone(cells[5]),
                                   "phone2": _norm_phone(cells[6])}

            r_name = str(cells[8] or '').strip()
            if r_name:
                canon = RESTAURANT_ALIASES.get(r_name, r_name)
                restaurants[canon] = {"phone": _norm_phone(cells[9]),
                                       "phone2": _norm_phone(cells[10])}

            # GTC 360's own staff contacts (tour operator / accountant /
            # emergency), shown to guides rather than tied to any one day —
            # column position found dynamically above via the "GTC 360"
            # header cell, not hardcoded.
            c_name = str(cells[gtc_col] or '').strip() if gtc_col is not None else ''
            if c_name:
                phone = _norm_phone(cells[gtc_col + 1])
                if phone:
                    company.append({"name": c_name, "phone": phone})

            # The guide/driver's own overnight-stay contact for a city
            # they can't drive out of the same day (written "hotel /
            # ქალაქი") — column position found dynamically too, same
            # reasoning as the GTC block above.
            s_name = str(cells[stay_col] or '').strip() if stay_col is not None else ''
            if s_name:
                phone = _norm_phone(cells[stay_col + 1])
                if phone:
                    stay.append({"name": s_name, "phone": phone,
                                 "phone2": _norm_phone(cells[stay_col + 2])})
        wb.close()
        print(f"[contacts_sync] guides={len(guides)} hotels={len(hotels)} "
              f"restaurants={len(restaurants)} extra={len(extra)} company={len(company)} stay={len(stay)}")
        return {"guides": guides, "hotels": hotels, "restaurants": restaurants, "extra": extra,
                "company": company, "stay": stay}
    except Exception as e:
        # Never return an all-empty-but-truthy dict here — main.py's
        # `if contacts:` check relies on a genuine failure coming back
        # falsy, so a bad fetch leaves existing contacts alone instead of
        # wiping every table out via sync_contacts().
        print(f"[contacts_sync] Could not fetch/parse informations tab: {e}")
        return {}


def _best_guide_phone(text: str, guides: list) -> str:
    """Best-effort: transliterated, normalized word sets, best overlap
    wins. Returns '' when nothing plausible matches."""
    field_words = set(_words(text))
    if not field_words:
        return ''
    best_phone, best_score = '', 0
    for g in guides:
        overlap = field_words & set(_words(g['name']))
        if len(overlap) > best_score:
            best_score, best_phone = len(overlap), g['phone']
    return best_phone


def match_guide_phone(guide_field: str, guides: list) -> str:
    """tours.guide is Latin-transliterated, the sheet's names are Georgian
    — matched by comparing transliterated, normalized word sets. A field
    naming several guides for different date ranges within the same tour
    ("11-mde Nina Peiqrishvili, 12-13 Elza") is matched segment by
    segment, so every guide's own phone shows — not just whichever one
    scores best across the whole field. Each phone is appended right
    after the name/date-range it belongs to ("11-mde Nina Peiqrishvili —
    579088982, 12-13 Elza — 579319449") rather than all names first and
    all phones bunched at the end, so it's never ambiguous which phone
    goes with which guide. This is meant as the full, ready-to-display
    line — callers show it in place of the raw guide field, not
    alongside it. Segments with no plausible match are kept, name-only.
    Returns '' only when guide_field itself is empty."""
    if not guide_field:
        return ''
    segments = [s.strip() for s in guide_field.split(',') if s.strip()]
    parts = [
        (f"{seg} — {phone}" if (phone := _best_guide_phone(seg, guides or [])) else seg)
        for seg in segments
    ]
    return ', '.join(parts)


# _translit renders ყ as 'q' (its standard scientific transliteration),
# but "ყაზბეგი" is conventionally spelled "Kazbegi" in English — the one
# city name in daily_log that doesn't just fall out of the letter-by-letter
# mapping used everywhere else here.
_CITY_TRANSLIT_FIXES = {'qazbegi': 'kazbegi'}


def match_stay_contact(city_en: str, stay_entries: list) -> dict:
    """The guide/driver's own overnight-stay contact for a daily_log day's
    city, from entries written "hotel / ქალაქი" — the city half
    transliterates to an exact match against daily_log's own English city
    name (ქუთაისი -> kutaisi, მესტია -> mestia, ...), so no separate
    alias table is needed beyond the one Kazbegi spelling mismatch above.
    Returns {"name": hotel_only, "phone": ...} — just the hotel half, since
    the city is always shown as the day's own heading already — or {} for
    a city with no such entry (Tbilisi, say — the guide/driver don't need
    one there)."""
    if not city_en or not stay_entries:
        return {}
    city_l = city_en.strip().lower()
    for entry in stay_entries:
        name = entry.get("name", "")
        city_part = name.rsplit('/', 1)[-1].strip() if '/' in name else name.strip()
        translit = _translit(city_part)
        translit = _CITY_TRANSLIT_FIXES.get(translit, translit)
        if translit == city_l:
            phone = " / ".join(p for p in (entry.get("phone", ""), entry.get("phone2", "")) if p)
            # Just the hotel half — the city is already the day's own
            # heading wherever this gets shown, so repeating it here (the
            # "/ ქალაქი" part of the sheet's own text) would be redundant.
            hotel = name.split('/', 1)[0].strip() if '/' in name else name
            return {"name": hotel, "phone": phone}
    return {}

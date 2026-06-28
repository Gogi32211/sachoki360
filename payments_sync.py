"""
Sync payment ok/paid status from Google Sheets financial files.
Reads column F to detect 'ok' markers for each vendor per tour.
READ-ONLY on the sheets.
"""
import csv
import io
import re
import requests

SHEET_IDS = {
    "KT_DT": "16NWhGGHR7mXAwRyVH_vmYSrZHx1zxrAR",
    "LN":    "1p5rgt6w_1hGpDr2W3Mug1p7rYWi7L7ZR",
    "ZT":    "1aWUi7GuMFZLuSq1dp2MgP_KV4rmwXGAE",
}

TOUR_CODE_RE = re.compile(r'\b((?:ZT|LN|KT|DT1|DT2|LT)-?\d{4})\b')

def _norm_code(code: str) -> str:
    return re.sub(r'(ZT|LN|KT|DT1|DT2|LT)(\d{4})', r'\1-\2', code)

# Meal type prefixes to strip from column B
_MEAL_PREFIXES = ('ვახშამი - ', 'ლანჩი - ', 'ვაშამი - ', 'დეგუსტაცია - ',
                  'dinner - ', 'lunch - ')

def _strip_meal_prefix(name: str) -> str:
    lower = name.lower()
    for prefix in _MEAL_PREFIXES:
        if lower.startswith(prefix.lower()):
            return name[len(prefix):].strip()
    return name

# Sheet vendor names (lowercase) → canonical vendor name used in payment_terms
_VENDOR_MAP = {
    'pullman':                  'Pullman Tbilisi',
    'pullman tbilisi':          'Pullman Tbilisi',
    'პულმანი':                  'Pullman Tbilisi',
    'radisson yerevan':         'Radisson Blu Yerevan',
    'radisson blu yerevan':     'Radisson Blu Yerevan',
    'marco polo':               'Marco Polo Gudauri',
    'marco polo gudauri':       'Marco Polo Gudauri',
    'მარკო პოლო':               'Marco Polo Gudauri',
    'გისტოლა':                  'Gistola Resort 5★',
    'მესტია გისტოლა':           'Gistola Resort 5★',
    'gistola':                  'Gistola Resort 5★',
    'gistola resort':           'Gistola Resort 5★',
    'გორი ინნ':                 'Gori Inn',
    'gori inn':                 'Gori Inn',
    'გრინვუდი':                 'Greenwood Batumi',
    'ბათუმი გრინვუდი':          'Greenwood Batumi',
    'greenwood batumi':         'Greenwood Batumi',
    'greenwood':                'Greenwood Batumi',
    'gudauri inn':              'Gudauri Inn',
    'გუდაური ინნ':              'Gudauri Inn',
    'gudauri lodge':            'Gudauri Lodge',
    'radisson batumi':          'Radisson Blu Batumi',
    'radisson blu batumi':      'Radisson Blu Batumi',
    'best western batumi':      'Best Western Batumi',
    'hualing':                  'Hualing Tbilisi',
    'hualing tbilisi':          'Hualing Tbilisi',
    'hualing preference':       'Hualing Preference 5★',
    "aghababyan's":             "Aghababyan's Yerevan",
    'aghababyan':               "Aghababyan's Yerevan",
    # Restaurants
    'დინ შენი':                 'დინ შენი',
    'din sheni':                'დინ შენი',
    'სალობიე':                  'სალობიე',
    'ზღაპარი':                  'ზღაპარი',
    'ლუშნუ ქორი':               'ლუშნუ ქორი',
    'ენგური':                   'ენგური',
    'ოქროს საწმისი':            'ოქროს საწმისი',
    'კტვ':                      'კტვ + ცეკვა / სიმღერა',
    'კტვ + ცეკვა / სიმღერა':   'კტვ + ცეკვა / სიმღერა',
    'ხარება':                   'ხარება',
    'ფასანაური':                'ფასანაური',
    'ახალი აზია (ისანი)':       'ახალი აზია (ისანი)',
    'ახალი აზია ისანი':         'ახალი აზია (ისანი)',
}

def _canonical(raw: str) -> str:
    name = _strip_meal_prefix(raw)
    return _VENDOR_MAP.get(name.lower().strip(), name.strip())


def _parse_statuses(csv_text: str) -> dict:
    """
    Parse payment ok status from a financial sheet CSV.
    Column B (index 1) = vendor/description, Column F (index 5) = ok status.
    Also checks column G (index 6) in case of shifted columns.
    Returns: {tour_code: {canonical_vendor_name: True}}
    """
    results: dict = {}
    current_tour = None

    reader = csv.reader(io.StringIO(csv_text))
    for row in reader:
        if not row:
            continue
        # Detect tour code in first 4 columns
        for cell in row[:4]:
            m = TOUR_CODE_RE.search(cell)
            if m:
                current_tour = _norm_code(m.group(1))
                results.setdefault(current_tour, {})
                break

        if not current_tour:
            continue

        vendor_raw = row[1].strip() if len(row) > 1 else ''
        if not vendor_raw:
            continue

        # Check column F (idx 5) and G (idx 6) for ok status
        status = ''
        for idx in (5, 6):
            if len(row) > idx:
                val = row[idx].strip().lower()
                if val.startswith('ok'):
                    status = val
                    break

        if status:
            canonical = _canonical(vendor_raw)
            results[current_tour][canonical] = True

    return results


def _get_gids_from_xlsx(sheet_id: str) -> dict:
    """
    Download XLSX and parse workbook.xml to get {tab_name: gid}.
    Works for 'anyone with link can view' sheets.
    The sheetId in workbook.xml == gid in the URL.
    """
    import zipfile
    import io as _io
    import xml.etree.ElementTree as ET
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    try:
        resp = requests.get(url, timeout=40)
        resp.raise_for_status()
        ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        with zipfile.ZipFile(_io.BytesIO(resp.content)) as zf:
            with zf.open('xl/workbook.xml') as f:
                root = ET.parse(f).getroot()
            result = {}
            for sheet in root.findall(f'.//{{{ns}}}sheet'):
                name = sheet.get('name', '')
                gid  = sheet.get('sheetId', '')
                if name and gid:
                    result[name] = gid
        print(f"[payments_sync] XLSX {sheet_id}: {len(result)} tabs: {list(result.keys())[:5]}")
        return result
    except Exception as e:
        print(f"[payments_sync] XLSX parse failed for {sheet_id}: {e}")
        return {}


def _fetch_sheet_statuses(sheet_id: str) -> dict:
    """Fetch ok statuses from all tabs via gids extracted from XLSX."""
    gid_map = _get_gids_from_xlsx(sheet_id)
    results: dict = {}

    if gid_map:
        for tab_name, gid in gid_map.items():
            url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
                   f"/export?format=csv&gid={gid}")
            try:
                resp = requests.get(url, timeout=20)
                if resp.status_code != 200:
                    continue
                for tc, vendors in _parse_statuses(resp.text).items():
                    results.setdefault(tc, {}).update(vendors)
            except Exception as e:
                print(f"[payments_sync] Tab '{tab_name}' gid={gid} error: {e}")
    else:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            for tc, vendors in _parse_statuses(resp.text).items():
                results.setdefault(tc, {}).update(vendors)
        except Exception as e:
            print(f"[payments_sync] Fallback tab error: {e}")

    paid_count = sum(len(v) for v in results.values())
    print(f"[payments_sync] Sheet {sheet_id}: {paid_count} ok statuses in {len(results)} tours")
    return results


def fetch_payment_statuses() -> dict:
    """
    Fetch ok/paid status for all vendors per tour from all financial sheets.
    Returns: {tour_code: {canonical_vendor_name: True}}
    """
    results: dict = {}
    for key, sheet_id in SHEET_IDS.items():
        data = _fetch_sheet_statuses(sheet_id)
        for tour_code, vendors in data.items():
            results.setdefault(tour_code, {})
            results[tour_code].update(vendors)

    paid_count = sum(len(v) for v in results.values())
    print(f"[payments_sync] Total: {paid_count} paid statuses across {len(results)} tours")
    return results

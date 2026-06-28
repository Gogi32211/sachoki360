"""
Sync the current + planned tour schedule from the master Google Sheet
"TOURS_All Dates_2026". READ-ONLY.

The sheet lists every tour as a column block. The region BEFORE the
"done 2026" marker holds ongoing + planned tours ("IN PROCESS"); after it
come completed tours, and further down the cancelled ("for cancell")
sections. We only treat the pre-"done 2026" region as the active list.

A tour code encodes its first (Baku/Almaty) date as MMDD; the app's
bus_start is that date plus a per-series offset (the Georgia / Khareba day).
"""
import io
import re
from datetime import date
import requests
from openpyxl import load_workbook

from seed_data import SERIES_START_OFFSET

SHEET_ID = "13FoSFZqpi4QAm2CDc1qT3uB7AKHOFEJv"

TOUR_CODE_RE = re.compile(r'\b((?:ZT|LN|KT|DT1|DT2|LT)-?\d{4})\b')
DONE_MARKER = "done 2026"


def _norm_code(code: str) -> str:
    return re.sub(r'(ZT|LN|KT|DT1|DT2|LT)(\d{4})', r'\1-\2', code)


def _bus_start_from_code(code: str, series: str):
    """code SERIES-MMDD → date(2026, MM, DD) + series offset → ISO bus_start."""
    m = re.search(r'-(\d{2})(\d{2})$', code)
    if not m:
        return None
    off = SERIES_START_OFFSET.get(series)
    if off is None:
        return None
    try:
        from datetime import timedelta
        d = date(2026, int(m.group(1)), int(m.group(2))) + timedelta(days=off)
        return d.isoformat()
    except ValueError:
        return None


def fetch_active_tours() -> list:
    """Return [{code, series, bus_start}] for ongoing/planned tours."""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    wb = load_workbook(io.BytesIO(resp.content), data_only=True, read_only=True)

    # Flatten all cells to text, row by row, so we can locate the marker.
    parts = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for c in row:
                if c is not None:
                    parts.append(str(c))
    wb.close()
    text = " ".join(parts)

    # Only keep the region before the "done 2026" marker.
    low = text.lower()
    idx = low.find(DONE_MARKER)
    active_text = text[:idx] if idx != -1 else text

    seen, active = set(), []
    for m in TOUR_CODE_RE.finditer(active_text):
        code = _norm_code(m.group(1))
        if code in seen:
            continue
        seen.add(code)
        series = code.split('-')[0]
        bs = _bus_start_from_code(code, series)
        if bs:
            active.append({"code": code, "series": series, "bus_start": bs})

    print(f"[schedule_sync] active tours parsed: {len(active)}")
    return active

"""
Sync estimated tour profit from the Google Sheets BALANCE files.

Each financial workbook has one tab per tour. Every tab ends with a summary
block:
    დაიხარჯა      <gel>  <usd>      (total spent)
    ტურის ღირებ.  <gel>  <usd>      (tour revenue / sale price)
    მოგება        <gel>  <usd>  <after_vat>   (profit; 3rd = profit after VAT refund)

READ-ONLY on the sheets.
"""
import io
import re
import requests
from openpyxl import load_workbook

# Same three financial workbooks used for meals/payments.
SHEET_IDS = {
    "KT_DT": "16NWhGGHR7mXAwRyVH_vmYSrZHx1zxrAR",
    "LN":    "1p5rgt6w_1hGpDr2W3Mug1p7rYWi7L7ZR",
    "ZT":    "1aWUi7GuMFZLuSq1dp2MgP_KV4rmwXGAE",
}

TOUR_CODE_RE = re.compile(r'((?:ZT|LN|KT|DT1|DT2)-?\d{4})')


def _norm_code(code: str) -> str:
    return re.sub(r'(ZT|LN|KT|DT1|DT2)(\d{4})', r'\1-\2', code)


def _num(v):
    if v is None:
        return None
    s = str(v).replace(',', '').strip()
    if s == '':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_worksheet(ws) -> tuple:
    """Return (tour_code, profit_dict) or (None, None) if no code found."""
    code = None
    m = TOUR_CODE_RE.search(ws.title or '')
    if m:
        code = _norm_code(m.group(1))

    out = {
        'spent_gel': None, 'spent_usd': None,
        'revenue_gel': None, 'revenue_usd': None,
        'profit_gel': None, 'profit_usd': None,
        'profit_after_vat': None,
    }

    for row in ws.iter_rows(values_only=True):
        cells = [str(c).strip() if c is not None else '' for c in row]
        if not code:
            for cell in cells[:4]:
                mm = TOUR_CODE_RE.search(cell)
                if mm:
                    code = _norm_code(mm.group(1))
                    break
        for i, c in enumerate(cells):
            if c not in ('დაიხარჯა', 'მოგება') and not c.startswith('ტურის ღირებ'):
                continue
            nxt = [n for n in (_num(x) for x in cells[i + 1:] if str(x).strip() != '')
                   if n is not None]
            if c == 'დაიხარჯა' and len(nxt) >= 2:
                out['spent_gel'], out['spent_usd'] = nxt[0], nxt[1]
            elif c.startswith('ტურის ღირებ') and len(nxt) >= 1:
                out['revenue_gel'] = nxt[0]
                if len(nxt) >= 2:
                    out['revenue_usd'] = nxt[1]
            elif c == 'მოგება' and len(nxt) >= 2:
                out['profit_gel'], out['profit_usd'] = nxt[0], nxt[1]
                if len(nxt) >= 3:
                    out['profit_after_vat'] = nxt[2]

    if not code:
        return None, None
    return code, out


def _fetch_workbook_profit(sheet_id: str) -> dict:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    results: dict = {}
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        wb = load_workbook(io.BytesIO(resp.content), data_only=True, read_only=True)
        for ws in wb.worksheets:
            code, data = _parse_worksheet(ws)
            if code and data and any(v is not None for v in data.values()):
                results[code] = data
        wb.close()
        print(f"[profit_sync] {sheet_id}: parsed profit for {len(results)} tours")
    except Exception as e:
        print(f"[profit_sync] Could not fetch/parse {sheet_id}: {e}")
    return results


def fetch_tour_profit() -> dict:
    """Return {tour_code: {spent/revenue/profit...}} across all balance files."""
    results: dict = {}
    for key, sheet_id in SHEET_IDS.items():
        results.update(_fetch_workbook_profit(sheet_id))
    print(f"[profit_sync] Total: profit for {len(results)} tours")
    return results

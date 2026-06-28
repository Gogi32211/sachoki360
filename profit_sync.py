"""
Sync estimated tour profit (USD) from the Google Sheets BALANCE files.

Each financial workbook has one tab per tour. Every tab ends with a summary
block. The relevant cells (all amounts in USD):

    დღგ სავარაუდო   <vat_usd>            (estimated VAT to be refunded)
    დაიხარჯა        <spent_usd>  ...
    ტურის ღირებ.    <revenue_usd> ...
    მოგება          <profit_usd>  <ignore>  <profit_after_vat>

profit_after_vat == profit_usd + vat_usd.

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

TOUR_CODE_RE = re.compile(r'((?:ZT|LN|KT|DT1|DT2|LT)-?\d{4})')
# Group size, e.g. "19+1" = 19 tourists + 1 leader.
PAX_RE = re.compile(r'(\d{1,2})\s*\+\s*(\d{1,2})')


def _extract_pax(text: str):
    m = PAX_RE.search(text or '')
    return f"{m.group(1)}+{m.group(2)}" if m else None


# Summary-block labels — not line items.
_SUMMARY_KEYS = ('დღგ სავარაუდო', 'დაიხარჯა', 'ტურის ღირებ', 'მოგება',
                 'ჩარიცხული', 'ჩასარიცხია', 'zedmeti')


def _usd_from_row(cells) -> float:
    """Best-effort USD amount for a line item.
    A GEL/USD pair shows up as adjacent numbers with ratio ~2.4–2.95;
    otherwise the amount is entered directly in USD (a lone number)."""
    nums = [n for n in (_num(c) for c in cells) if n is not None]
    for i in range(len(nums) - 1):
        a, b = nums[i], nums[i + 1]
        if b and 2.4 <= a / b <= 2.95:
            return b
    cand = [n for n in nums if n >= 5]
    return max(cand) if cand else 0.0


def _categorize(name: str):
    """Map a line-item description to a cost component (or None to skip)."""
    n = name.lower().strip()
    if not n:
        return None
    if 'აზერბაიჯ' in n:                    # Azerbaijan — excluded from stats
        return None
    if any(k in n for k in ('სომხეთი', 'yerevan', 'ერევან', 'aghababayan',
                            'აღაბაბაია', 'სევან', 'პაინ')):
        return 'armenia'
    if 'ავტობუს' in n or 'სპრინტერ' in n:
        return 'bus'
    if 'მძღოლ' in n:
        return 'driver'
    if any(k in n for k in ('ლანჩი', 'ვახშამ', 'ვაშამ', 'დეგუსტაცი')):
        return 'restaurant'
    if 'გიდი' in n or 'გიდის' in n:
        return 'guide'
    if any(k in n for k in ('ვარძი', 'სტალინ', 'უფლისციხ', 'უფლიციხ', 'საბაგირ',
                            'გემზე', 'მოზეომ', 'დელიკ', 'ბილეთ', 'მუზეუმ', 'ცაგვ')):
        return 'attraction'
    if any(k in n for k in ('ჰუალინგ', 'radisson', 'რადისონ', 'მარკო', 'გორი ინ',
                            'გრინვუდ', 'ახალციხ', 'უშბა', 'გისტოლა', 'პულმან',
                            'ლილატ', 'გუდაურ', 'best western', 'ბესთ', 'ქრაუნ',
                            'crown', 'ბორჯომ', 'ინნ')):
        return 'hotel'
    return 'other'


def _norm_code(code: str) -> str:
    return re.sub(r'(ZT|LN|KT|DT1|DT2|LT)(\d{4})', r'\1-\2', code)


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
    pax = _extract_pax(ws.title)

    out = {
        'pax': pax,               # group size, e.g. "19+1"
        'profit_usd': None,       # მოგება (1st value = USD)
        'vat_usd': None,          # დღგ სავარაუდო (USD VAT to refund)
        'profit_after_vat': None, # მოგება 3rd value = profit + vat
        'spent_usd': None,        # დაიხარჯა (1st value = USD)
        'revenue_usd': None,      # ტურის ღირებ. (1st value = USD)
        'components': {},         # {category: usd} cost breakdown (no Azerbaijan)
    }
    comp = {}
    items = []  # [{name, cat, usd}] — individual line items

    for row in ws.iter_rows(values_only=True):
        cells = [str(c).strip() if c is not None else '' for c in row]
        if not code:
            for cell in cells[:4]:
                mm = TOUR_CODE_RE.search(cell)
                if mm:
                    code = _norm_code(mm.group(1))
                    break
        if not out['pax']:
            for cell in cells[:4]:
                p = _extract_pax(cell)
                if p:
                    out['pax'] = p
                    break

        # ── Cost-component breakdown from line items ──
        name = cells[1].strip() if len(cells) > 1 else ''
        if name and not any(name.startswith(k) for k in _SUMMARY_KEYS) \
                and not TOUR_CODE_RE.search(name):
            cat = _categorize(name)
            if cat:
                usd = _usd_from_row(cells)
                if usd:
                    comp[cat] = round(comp.get(cat, 0.0) + usd, 2)
                    items.append({'name': name, 'cat': cat, 'usd': round(usd, 2)})

        for i, c in enumerate(cells):
            is_vat = c.startswith('დღგ სავარაუდო')
            is_spent = c == 'დაიხარჯა'
            is_rev = c.startswith('ტურის ღირებ')
            is_profit = c == 'მოგება'
            if not (is_vat or is_spent or is_rev or is_profit):
                continue
            nxt = [n for n in (_num(x) for x in cells[i + 1:] if str(x).strip() != '')
                   if n is not None]
            if is_vat and len(nxt) >= 1:
                out['vat_usd'] = nxt[0]
            elif is_spent and len(nxt) >= 1:
                out['spent_usd'] = nxt[0]
            elif is_rev and len(nxt) >= 1:
                out['revenue_usd'] = nxt[0]
            elif is_profit and len(nxt) >= 1:
                out['profit_usd'] = nxt[0]
                if len(nxt) >= 3:
                    out['profit_after_vat'] = nxt[2]

    if not code:
        return None, None
    out['components'] = comp
    out['items'] = items
    # Derive profit_after_vat if the sheet didn't carry it explicitly.
    if out['profit_after_vat'] is None and out['profit_usd'] is not None and out['vat_usd'] is not None:
        out['profit_after_vat'] = round(out['profit_usd'] + out['vat_usd'], 2)
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
    """Return {tour_code: {profit_usd, vat_usd, ...}} across all balance files."""
    results: dict = {}
    for key, sheet_id in SHEET_IDS.items():
        results.update(_fetch_workbook_profit(sheet_id))
    print(f"[profit_sync] Total: profit for {len(results)} tours")
    return results

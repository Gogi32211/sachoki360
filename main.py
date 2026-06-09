import os
import base64
import secrets
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
import database as db
from excel_parser import parse_all_excel
from sheets_sync import fetch_hotel_assignments
from meals_sync import fetch_all_meals
from payments_sync import fetch_payment_statuses

app = FastAPI(title="ki.360")

# ── Basic auth gate ────────────────────────────────────────────
APP_USER = os.environ.get("APP_USER", "360")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "vai2211")


@app.middleware("http")
async def basic_auth(request, call_next):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            user, _, pwd = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
            if secrets.compare_digest(user, APP_USER) and secrets.compare_digest(pwd, APP_PASSWORD):
                return await call_next(request)
        except Exception:
            pass
    return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="ki.360"'})


@app.on_event("startup")
def startup():
    db.init_db()
    db.seed_db()
    try:
        parsed = parse_all_excel()
        if parsed:
            db.seed_excel_data(parsed)
    except Exception as e:
        print(f"Excel parse warning: {e}")
    for series in ("ZT", "LN", "KT", "DT1", "DT2"):
        try:
            db.sync_series_hotels(series)
        except Exception as e:
            print(f"Hotel sync warning ({series}): {e}")
    for series in ("ZT", "LN", "KT", "DT1", "DT2"):
        try:
            db.sync_series_meals(series)
        except Exception as e:
            print(f"Meal sync warning ({series}): {e}")
    try:
        assignments = fetch_hotel_assignments()
        if assignments:
            db.update_hotels_from_sheets(assignments)
    except Exception as e:
        print(f"Sheets sync warning: {e}")
    try:
        meals_data = fetch_all_meals()
        if meals_data:
            db.sync_meals_from_financials(meals_data)
    except Exception as e:
        print(f"Meals sync warning: {e}")
    try:
        statuses = fetch_payment_statuses()
        if statuses:
            db.sync_payment_statuses(statuses)
    except Exception as e:
        print(f"Payment status sync warning: {e}")


class NoteUpdate(BaseModel):
    notes: str

class PaymentTermIn(BaseModel):
    vendor_name: str
    vendor_type: str = 'hotel'
    timing: str = 'after'
    days_offset: int = 7
    notes: str = ''
    unit_price: float = 0.0
    currency: str = 'GEL'
    series_prices: str = ''


@app.get("/", response_class=HTMLResponse)
def root():
    path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


@app.get("/api/tours")
def list_tours():
    return db.get_all_tours()


@app.get("/api/tours/{check_date}")
def tours_on_date(check_date: str):
    return db.get_tours_on_date(check_date)


@app.get("/api/tour/{code}")
def tour_detail(code: str):
    t = db.get_tour_detail(code)
    if not t:
        raise HTTPException(404, "Tour not found")
    return t


@app.get("/api/timeline")
def timeline(from_date: str = None, to_date: str = None):
    if not from_date:
        from_date = db.today_tbilisi().replace(day=1).isoformat()
    if not to_date:
        d = date.fromisoformat(from_date)
        if d.month == 12:
            to_date = date(d.year + 1, 1, 1).isoformat()
        else:
            to_date = date(d.year, d.month + 1, 1).isoformat()
    return db.get_timeline(from_date, to_date)


@app.get("/api/today")
def today_info():
    today = db.today_tbilisi()
    yesterday = (today - timedelta(days=1)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()
    return {
        "yesterday": db.get_tours_on_date(yesterday),
        "today": db.get_tours_on_date(today.isoformat()),
        "tomorrow": db.get_tours_on_date(tomorrow),
    }


@app.get("/api/border/{check_date}")
def borders(check_date: str):
    return db.get_borders_on_date(check_date)


@app.post("/api/tour/{code}/note")
def add_note(code: str, body: NoteUpdate):
    db.update_tour_notes(code, body.notes)
    return {"ok": True}


@app.post("/api/log/{log_id}/note")
def add_log_note(log_id: int, body: NoteUpdate):
    db.update_log_notes(log_id, body.notes)
    return {"ok": True}


@app.get("/api/financials")
def financials():
    return db.get_financials_all()


@app.get("/api/financials/{code}")
def financials_tour(code: str):
    all_f = db.get_financials_all()
    match = next((f for f in all_f if f['tour_code'] == code), None)
    if not match:
        raise HTTPException(404, "Not found")
    match['meals'] = db.get_meals_for_tour(code)
    return match


@app.get("/api/restaurants")
def restaurants():
    return db.get_all_restaurants()


@app.get("/api/payment-terms")
def list_payment_terms():
    return db.get_payment_terms()

@app.post("/api/payment-terms")
def save_payment_term(body: PaymentTermIn):
    db.upsert_payment_term(body.vendor_name, body.vendor_type, body.timing, body.days_offset,
                           body.notes, body.unit_price, body.currency, body.series_prices)
    return {"ok": True}

@app.delete("/api/payment-terms/{term_id}")
def remove_payment_term(term_id: int):
    db.delete_payment_term(term_id)
    return {"ok": True}

@app.get("/api/payments/schedule")
def payment_schedule(from_date: str = None, to_date: str = None):
    return db.get_payment_schedule(from_date, to_date)

@app.get("/api/payments/tour-summary")
def payment_tour_summary(from_date: str = None, to_date: str = None):
    return db.get_tour_payment_summary(from_date, to_date)

@app.get("/api/exchange-rate")
def exchange_rate():
    return {"rate": db.get_exchange_rate()}

@app.post("/api/sync-payment-status")
def sync_payment_status():
    try:
        statuses = fetch_payment_statuses()
        updated = db.sync_payment_statuses(statuses)
        return {"ok": True, "updated": updated}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/debug/payments-sync")
def debug_payments_sync():
    from payments_sync import SHEET_IDS, _parse_statuses
    import requests as _req, zipfile, io as _io
    result = {"db_statuses": db.get_payment_statuses(), "tests": {}}
    for key, sheet_id in SHEET_IDS.items():
        entry = {}
        try:
            r = _req.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv", timeout=15)
            parsed = _parse_statuses(r.text)
            entry["csv"] = {"http": r.status_code, "bytes": len(r.content),
                            "tours": {tc: list(v.keys()) for tc, v in parsed.items()}}
        except Exception as e:
            entry["csv"] = {"error": str(e)}
        try:
            r2 = _req.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx", timeout=40)
            entry["xlsx"] = {"http": r2.status_code, "bytes": len(r2.content),
                             "content_type": r2.headers.get("Content-Type","")}
            if r2.status_code == 200:
                try:
                    with zipfile.ZipFile(_io.BytesIO(r2.content)) as zf:
                        entry["xlsx"]["zip_entries"] = zf.namelist()
                except Exception as e2:
                    entry["xlsx"]["zip_error"] = str(e2)
        except Exception as e:
            entry["xlsx"] = {"error": str(e)}
        result["tests"][key] = entry
    return result

@app.get("/api/vendors")
def get_vendors():
    return db.get_all_vendors()


@app.post("/api/sync-hotels")
def sync_hotels():
    """Re-read Google Sheets and update hotel assignments. Read-only on the sheet."""
    try:
        assignments = fetch_hotel_assignments()
        updated = db.update_hotels_from_sheets(assignments)
        return {"ok": True, "tours": len(assignments), "records_updated": updated}
    except Exception as e:
        raise HTTPException(500, str(e))

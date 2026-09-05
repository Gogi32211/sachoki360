import os
import secrets
import threading
import time
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, Response, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import database as db
from excel_parser import parse_all_excel
from sheets_sync import fetch_hotel_assignments
from meals_sync import fetch_all_meals
from payments_sync import fetch_payment_statuses
from profit_sync import fetch_tour_profit
from schedule_sync import fetch_active_tours, fetch_all_tour_rooms
from cancel_sync import fetch_cancelled_tour_codes
from debts_sync import fetch_tour_debts
from archive_sync import fetch_archive, fetch_archive_tours
from contacts_sync import fetch_contacts

app = FastAPI(title="ki.360")

_static_dir = os.path.join(os.path.dirname(__file__), "frontend", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

APP_USER = os.environ.get("APP_USER", "360")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "vai2211")
# Stable token derived from the credentials so the login cookie survives
# server restarts / redeploys (otherwise users get logged out every deploy).
import hashlib
SESSION_TOKEN = hashlib.sha256(f"ki360:{APP_USER}:{APP_PASSWORD}".encode()).hexdigest()
COOKIE_MAX_AGE = 86400 * 365  # 1 year

LOGIN_HTML = """<!DOCTYPE html>
<html lang="ka">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>ki.360 — შესვლა</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%232563eb'/%3E%3Ctext x='50' y='78' font-family='Arial,Helvetica,sans-serif' font-size='82' font-weight='800' letter-spacing='-4' fill='%23ffffff' text-anchor='middle'%3Eki%3C/text%3E%3C/svg%3E"/>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Georgian:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
* { box-sizing: border-box; font-family: 'Noto Sans Georgian', sans-serif; }
body { background: #0f172a; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
.card { background: #1e293b; border-radius: 16px; padding: 40px 36px; width: 340px; box-shadow: 0 20px 60px #0005; }
h1 { color: #f1f5f9; font-size: 28px; margin: 0 0 6px; }
p { color: #94a3b8; font-size: 13px; margin: 0 0 28px; }
label { display: block; color: #cbd5e1; font-size: 12px; margin-bottom: 6px; }
input { width: 100%; padding: 10px 14px; border-radius: 8px; border: 1px solid #334155;
        background: #0f172a; color: #f1f5f9; font-size: 15px; outline: none; margin-bottom: 16px; }
input:focus { border-color: #fbbf24; }
button { width: 100%; padding: 12px; background: #fbbf24; color: #0f172a; border: none;
         border-radius: 8px; font-size: 15px; font-weight: 700; cursor: pointer; }
button:hover { background: #f59e0b; }
.err { color: #f87171; font-size: 13px; margin-bottom: 14px; text-align: center; }
</style>
</head>
<body>
<div class="card">
  <h1>ki.360</h1>
  <p>ტურ-მენეჯმენტი</p>
  {error}
  <form method="post" action="/login">
    <label>მომხმარებელი</label>
    <input type="text" name="username" autocomplete="username" autofocus/>
    <label>პაროლი</label>
    <input type="password" name="password" autocomplete="current-password"/>
    <button type="submit">შესვლა →</button>
  </form>
</div>
</body>
</html>"""


def _is_authed(request: Request) -> bool:
    return request.cookies.get("ki360_session") == SESSION_TOKEN


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    path = request.url.path
    if path in ("/login", "/logout", "/health"):
        return await call_next(request)
    if not _is_authed(request):
        return RedirectResponse("/login", status_code=302)
    return await call_next(request)


@app.get("/health")
def health():
    # Public, unauthenticated — this is what Railway's healthcheck hits.
    # Everything else redirects unauthenticated requests to /login (302),
    # which a healthcheck never follows.
    return {"ok": True}


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return LOGIN_HTML.replace("{error}", "")


@app.post("/login")
async def login_submit(username: str = Form(...), password: str = Form(...)):
    if secrets.compare_digest(username, APP_USER) and secrets.compare_digest(password, APP_PASSWORD):
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("ki360_session", SESSION_TOKEN, httponly=True, samesite="lax", max_age=COOKIE_MAX_AGE)
        return resp
    html = LOGIN_HTML.replace("{error}", '<div class="err">მომხმარებელი ან პაროლი არასწორია</div>')
    return HTMLResponse(html, status_code=401)


@app.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("ki360_session")
    return resp


@app.get("/ping")
def ping():
    return {"ok": True, "tours": len(db.get_all_tours())}


def _background_sync():
    # Remove cancelled tours FIRST so downstream syncs skip them entirely.
    try:
        cancelled = fetch_cancelled_tour_codes()
        if cancelled:
            db.remove_cancelled_tours(cancelled)
    except Exception as e:
        print(f"Cancel sync warning: {e}")
    # Reconcile schedule (add new / remove cancelled planned tours) FIRST,
    # so the rest of the syncs operate on the up-to-date tour set.
    try:
        active = fetch_active_tours()
        if active:
            db.apply_schedule_sync(active)
    except Exception as e:
        print(f"Schedule sync warning: {e}")
    try:
        all_rooms = fetch_all_tour_rooms()
        if all_rooms:
            updated = db.bulk_update_rooms(all_rooms)
            print(f"[startup] rooms updated for {updated} tours")
    except Exception as e:
        print(f"Rooms sync warning: {e}")
    for series in ("ZT", "LN", "KT", "DT1", "DT2", "LT", "TH", "TK", "TM", "TV"):
        try:
            db.sync_series_hotels(series)
        except Exception as e:
            print(f"Hotel sync warning ({series}): {e}")
    for series in ("ZT", "LN", "KT", "DT1", "DT2", "LT", "TH", "TK", "TM", "TV"):
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
    try:
        profit = fetch_tour_profit()
        if profit:
            db.sync_tour_profit(profit)
    except Exception as e:
        print(f"Profit sync warning: {e}")
    try:
        debts = fetch_tour_debts()
        if debts:
            db.sync_tour_debts(debts)
    except Exception as e:
        print(f"Debts sync warning: {e}")
    try:
        archive = fetch_archive_tours()
        if archive:
            db.sync_archive_tours(archive)
    except Exception as e:
        print(f"Archive sync warning: {e}")
    try:
        contacts = fetch_contacts()
        if contacts:
            db.sync_contacts(contacts)
    except Exception as e:
        print(f"Contacts sync warning: {e}")
    print("[startup] background sync complete")


# Google Sheets are the office's live working copy — edited throughout the
# day, not just at deploy time. A sync that only ran once at startup would
# freeze the app on whatever the sheets looked like at that moment, so it
# repeats on this interval for as long as the process runs.
SYNC_INTERVAL_SECONDS = 15 * 60


def _background_sync_loop():
    while True:
        try:
            _background_sync()
        except Exception as e:
            print(f"[sync loop] warning: {e}")
        time.sleep(SYNC_INTERVAL_SECONDS)


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
    threading.Thread(target=_background_sync_loop, daemon=True).start()


class NoteUpdate(BaseModel):
    notes: str

class SettingUpdate(BaseModel):
    value: str

class PaymentTermIn(BaseModel):
    vendor_name: str
    vendor_type: str = 'hotel'
    timing: str = 'after'
    days_offset: int = 7
    notes: str = ''
    unit_price: float = 0.0
    currency: str = 'GEL'
    series_prices: str = ''


@app.get("/api/settings/{key}")
def get_setting_api(key: str):
    return {"value": db.get_setting(key, "")}

@app.post("/api/settings/{key}")
def set_setting_api(key: str, body: SettingUpdate):
    db.set_setting(key, body.value)
    return {"ok": True}


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


@app.get("/api/menu/active-tours")
def menu_active_tours():
    return db.get_active_menu_tours()


@app.get("/api/tour/{code}/menu")
def tour_menu(code: str):
    m = db.get_tour_menu(code)
    if not m:
        raise HTTPException(404, "Tour not found")
    return m


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

@app.get("/api/tour-profit")
def tour_profit():
    return db.get_tour_profit()

@app.post("/api/sync-schedule")
def sync_schedule():
    try:
        active = fetch_active_tours()
        result = db.apply_schedule_sync(active)
        all_rooms = fetch_all_tour_rooms()
        rooms_updated = db.bulk_update_rooms(all_rooms)
        result['rooms_updated'] = rooms_updated
        return result
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/sync-profit")
def sync_profit():
    try:
        data = fetch_tour_profit()
        updated = db.sync_tour_profit(data)
        return {"ok": True, "updated": updated}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/archive-profit")
def archive_profit(year: int = 2025):
    return db.get_archive_profit(year)

@app.get("/api/archive-years")
def archive_years():
    return db.archive_years()

@app.post("/api/sync-archive")
def sync_archive():
    try:
        got = fetch_archive()
        updated = db.sync_archive_tours(got['tours'])
        # Per-workbook detail, so a file that couldn't be read is visible here
        # rather than only in the logs.
        return {"ok": True, "updated": updated, "files": got['files']}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/tour-debts")
def tour_debts():
    return db.get_tour_debts()

@app.post("/api/sync-debts")
def sync_debts():
    try:
        data = fetch_tour_debts()
        updated = db.sync_tour_debts(data)
        return {"ok": True, "updated": updated}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/sync-contacts")
def sync_contacts():
    try:
        data = fetch_contacts()
        updated = db.sync_contacts(data)
        return {"ok": True, "updated": updated}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/sync-cancelled")
def sync_cancelled():
    try:
        cancelled = fetch_cancelled_tour_codes()
        removed = db.remove_cancelled_tours(cancelled)
        return {"ok": True, "cancelled_codes": sorted(cancelled), "removed": removed}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/vendors")
def get_vendors():
    return db.get_all_vendors()


@app.post("/api/sync-hotels")
def sync_hotels():
    try:
        assignments = fetch_hotel_assignments()
        updated = db.update_hotels_from_sheets(assignments)
        return {"ok": True, "tours": len(assignments), "records_updated": updated}
    except Exception as e:
        raise HTTPException(500, str(e))

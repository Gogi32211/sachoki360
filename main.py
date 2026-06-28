import os
import secrets
import threading
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
    if path in ("/login", "/logout"):
        return await call_next(request)
    if not _is_authed(request):
        return RedirectResponse("/login", status_code=302)
    return await call_next(request)


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
    try:
        profit = fetch_tour_profit()
        if profit:
            db.sync_tour_profit(profit)
    except Exception as e:
        print(f"Profit sync warning: {e}")
    print("[startup] background sync complete")


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
    threading.Thread(target=_background_sync, daemon=True).start()


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

@app.post("/api/sync-profit")
def sync_profit():
    try:
        data = fetch_tour_profit()
        updated = db.sync_tour_profit(data)
        return {"ok": True, "updated": updated}
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

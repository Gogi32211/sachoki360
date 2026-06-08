import os
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import database as db

app = FastAPI(title="GTC360 — GOGA of TOURS")


@app.on_event("startup")
def startup():
    db.init_db()
    db.seed_db()


class NoteUpdate(BaseModel):
    notes: str


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
        from_date = date.today().replace(day=1).isoformat()
    if not to_date:
        d = date.fromisoformat(from_date)
        if d.month == 12:
            to_date = date(d.year + 1, 1, 1).isoformat()
        else:
            to_date = date(d.year, d.month + 1, 1).isoformat()
    return db.get_timeline(from_date, to_date)


@app.get("/api/today")
def today_info():
    today = date.today()
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

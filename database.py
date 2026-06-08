import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from seed_data import SERIES, TOURS_2026

DB_PATH = "gtc360.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tours (
                code TEXT PRIMARY KEY,
                series TEXT NOT NULL,
                bus_start DATE NOT NULL,
                bus_end DATE NOT NULL,
                status TEXT DEFAULT 'scheduled',
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS daily_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tour_code TEXT,
                date DATE,
                city TEXT,
                hotel TEXT,
                lunch TEXT,
                dinner TEXT,
                border_crossing TEXT,
                notes TEXT DEFAULT '',
                FOREIGN KEY (tour_code) REFERENCES tours(code)
            );
        """)

def seed_db():
    with get_db() as conn:
        existing = {r["code"] for r in conn.execute("SELECT code FROM tours").fetchall()}
        for t in TOURS_2026:
            if t["code"] in existing:
                continue
            series = t["series"]
            bus_start = date.fromisoformat(t["bus_start"])
            duration = SERIES[series]["duration"]
            bus_end = bus_start + timedelta(days=duration)
            conn.execute(
                "INSERT INTO tours (code, series, bus_start, bus_end) VALUES (?,?,?,?)",
                (t["code"], series, bus_start.isoformat(), bus_end.isoformat())
            )
            nights = SERIES[series]["nights"]
            for offset, info in nights.items():
                day_date = bus_start + timedelta(days=offset)
                conn.execute(
                    "INSERT INTO daily_log (tour_code, date, city, hotel, lunch, dinner, border_crossing) VALUES (?,?,?,?,?,?,?)",
                    (t["code"], day_date.isoformat(), info.get("city",""), info.get("hotel",""),
                     info.get("lunch",""), info.get("dinner",""), info.get("border") or "")
                )

def get_tour_status(bus_start_str: str, bus_end_str: str) -> str:
    today = date.today()
    bs = date.fromisoformat(bus_start_str)
    be = date.fromisoformat(bus_end_str)
    if today < bs:
        return "upcoming"
    elif bs <= today <= be:
        return "active"
    else:
        return "done"

def get_all_tours():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tours ORDER BY bus_start").fetchall()
        result = []
        for r in rows:
            result.append({
                "code": r["code"], "series": r["series"],
                "bus_start": r["bus_start"], "bus_end": r["bus_end"],
                "status": get_tour_status(r["bus_start"], r["bus_end"]),
                "notes": r["notes"],
                "color": SERIES[r["series"]]["color"],
                "series_name": SERIES[r["series"]]["name"],
            })
        return result

def get_tours_on_date(check_date: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT t.*, dl.city, dl.hotel, dl.lunch, dl.dinner, dl.border_crossing, dl.notes as day_notes "
            "FROM tours t JOIN daily_log dl ON t.code=dl.tour_code "
            "WHERE dl.date=? ORDER BY dl.city, t.series",
            (check_date,)
        ).fetchall()
        result = []
        for r in rows:
            bs = date.fromisoformat(r["bus_start"])
            cd = date.fromisoformat(check_date)
            day_num = (cd - bs).days + 1
            duration = SERIES[r["series"]]["duration"]
            result.append({
                "code": r["code"], "series": r["series"],
                "bus_start": r["bus_start"], "bus_end": r["bus_end"],
                "city": r["city"], "hotel": r["hotel"],
                "lunch": r["lunch"], "dinner": r["dinner"],
                "border_crossing": r["border_crossing"],
                "day_notes": r["day_notes"],
                "day_num": day_num, "total_days": duration,
                "color": SERIES[r["series"]]["color"],
            })
        return result

def get_tour_detail(code: str):
    with get_db() as conn:
        tour = conn.execute("SELECT * FROM tours WHERE code=?", (code,)).fetchone()
        if not tour:
            return None
        logs = conn.execute(
            "SELECT * FROM daily_log WHERE tour_code=? ORDER BY date", (code,)
        ).fetchall()
        days = []
        for log in logs:
            bs = date.fromisoformat(tour["bus_start"])
            ld = date.fromisoformat(log["date"])
            days.append({
                "date": log["date"],
                "day_num": (ld - bs).days + 1,
                "city": log["city"], "hotel": log["hotel"],
                "lunch": log["lunch"], "dinner": log["dinner"],
                "border_crossing": log["border_crossing"],
                "notes": log["notes"],
                "log_id": log["id"],
            })
        return {
            "code": tour["code"], "series": tour["series"],
            "bus_start": tour["bus_start"], "bus_end": tour["bus_end"],
            "status": get_tour_status(tour["bus_start"], tour["bus_end"]),
            "notes": tour["notes"],
            "color": SERIES[tour["series"]]["color"],
            "series_name": SERIES[tour["series"]]["name"],
            "days": days,
        }

def get_timeline(from_date: str, to_date: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tours WHERE bus_end >= ? AND bus_start <= ? ORDER BY series, bus_start",
            (from_date, to_date)
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "code": r["code"], "series": r["series"],
                "bus_start": r["bus_start"], "bus_end": r["bus_end"],
                "status": get_tour_status(r["bus_start"], r["bus_end"]),
                "color": SERIES[r["series"]]["color"],
                "series_name": SERIES[r["series"]]["name"],
            })
        return result

def get_borders_on_date(check_date: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT tour_code, border_crossing FROM daily_log WHERE date=? AND border_crossing != '' AND border_crossing IS NOT NULL",
            (check_date,)
        ).fetchall()
        return [{"tour_code": r["tour_code"], "border_crossing": r["border_crossing"]} for r in rows]

def update_tour_notes(code: str, notes: str):
    with get_db() as conn:
        conn.execute("UPDATE tours SET notes=? WHERE code=?", (notes, code))

def update_log_notes(log_id: int, notes: str):
    with get_db() as conn:
        conn.execute("UPDATE daily_log SET notes=? WHERE id=?", (notes, log_id))

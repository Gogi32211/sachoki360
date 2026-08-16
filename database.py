import json as _json
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta, datetime, timezone
import re as _re
from seed_data import SERIES, TOURS_2026, SERIES_START_OFFSET

DB_PATH = "gtc360.db"

# Georgia (Tbilisi) is UTC+4 year-round — no daylight saving.
TBILISI_TZ = timezone(timedelta(hours=4))

def today_tbilisi() -> date:
    """Current date in Tbilisi, regardless of the server's own timezone."""
    return datetime.now(TBILISI_TZ).date()

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
            CREATE TABLE IF NOT EXISTS tour_meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tour_code TEXT,
                date DATE,
                meal_type TEXT,
                restaurant TEXT,
                gel_amount REAL DEFAULT 0,
                usd_amount REAL DEFAULT 0,
                FOREIGN KEY (tour_code) REFERENCES tours(code)
            );
            CREATE TABLE IF NOT EXISTS payment_terms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_name TEXT UNIQUE NOT NULL,
                vendor_type TEXT DEFAULT 'hotel',
                timing TEXT DEFAULT 'after',
                days_offset INTEGER DEFAULT 7,
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS tour_financials (
                tour_code TEXT PRIMARY KEY,
                guide TEXT DEFAULT '',
                rooms TEXT DEFAULT '',
                spent_gel REAL DEFAULT 0,
                tour_price_gel REAL DEFAULT 0,
                tour_price_usd REAL DEFAULT 0,
                profit_gel REAL DEFAULT 0,
                paid_gel REAL DEFAULT 0,
                paid_cny REAL DEFAULT 0,
                due_gel REAL DEFAULT 0,
                FOREIGN KEY (tour_code) REFERENCES tours(code)
            );
            CREATE TABLE IF NOT EXISTS payment_status (
                tour_code   TEXT NOT NULL,
                vendor_name TEXT NOT NULL,
                paid        INTEGER DEFAULT 1,
                PRIMARY KEY (tour_code, vendor_name)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS tour_debts (
                tour_code     TEXT PRIMARY KEY,
                phase         INTEGER,
                invoiced_usd  REAL DEFAULT 0,
                received_usd  REAL DEFAULT 0,
                awaited_usd   REAL DEFAULT 0,
                paid_usd      REAL DEFAULT 0,
                due_usd       REAL DEFAULT 0,
                awaited_count INTEGER DEFAULT 0,
                due_count     INTEGER DEFAULT 0,
                lines         TEXT DEFAULT '[]',
                items         TEXT DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS tour_profit (
                tour_code        TEXT PRIMARY KEY,
                pax              TEXT,
                profit_usd       REAL,
                vat_usd          REAL,
                profit_after_vat REAL,
                spent_usd        REAL,
                revenue_usd      REAL,
                components       TEXT
            );
        """)
        # Migrate older tour_profit schema → add any missing columns.
        for col, defn in [
            ("pax", "TEXT"),
            ("profit_usd", "REAL"), ("vat_usd", "REAL"),
            ("profit_after_vat", "REAL"), ("spent_usd", "REAL"),
            ("revenue_usd", "REAL"), ("components", "TEXT"),
            ("components_detail", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE tour_profit ADD COLUMN {col} {defn}")
            except Exception:
                pass
        try:
            conn.execute("ALTER TABLE tour_debts ADD COLUMN items TEXT DEFAULT '[]'")
        except Exception:
            pass
        # Migrate: add rooms / guide columns to tours if missing
        for col in ("rooms", "guide"):
            try:
                conn.execute(f"ALTER TABLE tours ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass
        # Migrate: add new columns to payment_terms if missing
        for col, defn in [
            ("unit_price",    "REAL DEFAULT 0"),
            ("currency",      "TEXT DEFAULT 'GEL'"),
            ("series_prices", "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE payment_terms ADD COLUMN {col} {defn}")
            except Exception:
                pass
        # From 2026-06-24 the first-day lunch changed from ხარება to ბალკონი სიღნაღი.
        # Update any already-inserted daily_log rows for tours on/after that date.
        conn.execute("""
            UPDATE daily_log SET lunch = 'ლანჩი: ბალკონი სიღნაღი'
            WHERE lunch = 'ლანჩი: ხარება'
              AND tour_code IN (
                  SELECT code FROM tours WHERE bus_start >= '2026-06-24'
              )
        """)

# (vendor_name, vendor_type, timing, days_offset, notes, unit_price, currency, series_prices)
_DEFAULT_PAYMENT_TERMS = [
    # Hotels — twin room price × 10 rooms
    ("Pullman Tbilisi",                          "hotel",      "before", 1, "", 87.0,  "USD", ""),
    ("Radisson Blu Yerevan",                     "hotel",      "before", 1, "", 135.0, "USD", ""),
    ("Marco Polo Gudauri",                       "hotel",      "before", 1, "", 70.0,  "USD", ""),
    ("Gistola Resort 5★",                        "hotel",      "before", 1, "", 100.0, "USD", ""),
    ("Gudauri Inn",                              "hotel",      "before", 1, "", 0.0,   "USD", ""),
    ("Gudauri Lodge",                            "hotel",      "before", 1, "", 0.0,   "USD", ""),
    # Restaurants — flat price per 19+1 people
    ("დინ შენი",                                 "restaurant", "before", 1, "", 700.0, "GEL", ""),
    ("სალობიე",                                  "restaurant", "before", 1, "", 430.0, "GEL", ""),
    ("ზღაპარი",                                  "restaurant", "before", 1, "", 400.0, "GEL", ""),
    ("ლუშნუ ქორი",                               "restaurant", "before", 1, "", 580.0, "GEL", ""),
    ("ენგური",                                   "restaurant", "before", 1, "", 410.0, "GEL", ""),
    ("ოქროს საწმისი",                            "restaurant", "before", 1, "", 530.0, "GEL", ""),
    # Driver — series-specific costs (GEL)
    ("მძღოლი: კვება და სასტუმრო ტურში",         "other",      "before", 1, "", 0.0, "GEL",
     '{"ZT":125,"KT":50,"DT1":50,"DT2":50,"LN":100}'),
    # Guide — series-specific costs (GEL)
    ("გიდი: ბილეთები, კვება და სასტუმრო ტურში", "other",      "before", 1, "", 0.0, "GEL",
     '{"ZT":1314,"KT":745,"DT1":745,"DT2":745,"LN":2115}'),
]


def seed_db():
    with get_db() as conn:
        for vn, vtype, timing, days, notes, uprice, curr, sprices in _DEFAULT_PAYMENT_TERMS:
            conn.execute("""
                INSERT INTO payment_terms
                    (vendor_name, vendor_type, timing, days_offset, notes, unit_price, currency, series_prices)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(vendor_name) DO UPDATE SET
                    unit_price   = CASE WHEN payment_terms.unit_price   = 0  THEN excluded.unit_price   ELSE payment_terms.unit_price   END,
                    currency     = CASE WHEN payment_terms.unit_price   = 0  THEN excluded.currency     ELSE payment_terms.currency     END,
                    series_prices= CASE WHEN payment_terms.series_prices= '' THEN excluded.series_prices ELSE payment_terms.series_prices END
            """, (vn, vtype, timing, days, notes, uprice, curr, sprices))

        # Force-update known restaurant prices and guide series_prices
        _restaurant_prices = [
            ("დინ შენი",      700.0),
            ("სალობიე",       430.0),
            ("ზღაპარი",       400.0),
            ("ლუშნუ ქორი",    580.0),
            ("ენგური",        410.0),
            ("ოქროს საწმისი", 530.0),
        ]
        for rname, rprice in _restaurant_prices:
            conn.execute(
                "UPDATE payment_terms SET unit_price=? WHERE vendor_name=? AND vendor_type='restaurant'",
                (rprice, rname)
            )
        conn.execute(
            "UPDATE payment_terms SET series_prices=? WHERE vendor_name=?",
            ('{"ZT":1314,"KT":745,"DT1":745,"DT2":745,"LN":2115}',
             "გიდი: ბილეთები, კვება და სასტუმრო ტურში")
        )
        conn.execute(
            "UPDATE payment_terms SET series_prices=? WHERE vendor_name=?",
            ('{"ZT":125,"KT":50,"DT1":50,"DT2":50,"LN":100}',
             "მძღოლი: კვება და სასტუმრო ტურში")
        )

        existing = {r["code"] for r in conn.execute("SELECT code FROM tours").fetchall()}
        for t in TOURS_2026:
            if t["code"] in existing:
                continue
            _insert_tour(conn, t["code"], t["series"], date.fromisoformat(t["bus_start"]))


def _insert_tour(conn, code: str, series: str, bus_start: date, rooms: str = '', guide: str = ''):
    """Insert a tour + its daily_log rows from the SERIES template."""
    duration = SERIES[series]["duration"]
    # Tour ends on the Tbilisi→Urumqi flight day = last itinerary day
    bus_end = bus_start + timedelta(days=duration - 1)
    conn.execute(
        "INSERT INTO tours (code, series, bus_start, bus_end, rooms, guide) VALUES (?,?,?,?,?,?)",
        (code, series, bus_start.isoformat(), bus_end.isoformat(), rooms, guide)
    )
    for offset, info in SERIES[series]["nights"].items():
        day_date = bus_start + timedelta(days=offset)
        conn.execute(
            "INSERT INTO daily_log (tour_code, date, city, hotel, lunch, dinner, border_crossing) VALUES (?,?,?,?,?,?,?)",
            (code, day_date.isoformat(), info.get("city",""), info.get("hotel",""),
             info.get("lunch",""), info.get("dinner",""), info.get("border") or "")
        )

def sync_series_meals(series_key: str):
    """Update lunch/dinner in daily_log for all tours of a given series from SERIES definition."""
    nights = SERIES[series_key]["nights"]
    with get_db() as conn:
        tours = conn.execute(
            "SELECT code, bus_start FROM tours WHERE series=?", (series_key,)
        ).fetchall()
        updated = 0
        for t in tours:
            bs = date.fromisoformat(t["bus_start"])
            for offset, info in nights.items():
                day_date = (bs + timedelta(days=offset)).isoformat()
                cur = conn.execute(
                    "UPDATE daily_log SET lunch=?, dinner=? WHERE tour_code=? AND date=?",
                    (info.get("lunch", ""), info.get("dinner", ""), t["code"], day_date)
                )
                updated += cur.rowcount
    print(f"[sync_meals] Updated {updated} meal records for series {series_key}")
    return updated


def sync_series_hotels(series_key: str):
    """Reset hotel/city in daily_log for all tours of a series to seed_data defaults."""
    nights = SERIES[series_key]["nights"]
    with get_db() as conn:
        tours = conn.execute(
            "SELECT code, bus_start FROM tours WHERE series=?", (series_key,)
        ).fetchall()
        updated = 0
        for t in tours:
            bs = date.fromisoformat(t["bus_start"])
            for offset, info in nights.items():
                day_date = (bs + timedelta(days=offset)).isoformat()
                hotel = info.get("hotel", "")
                city = info.get("city", "")
                cur = conn.execute(
                    "UPDATE daily_log SET hotel=?, city=? WHERE tour_code=? AND date=?",
                    (hotel, city, t["code"], day_date)
                )
                updated += cur.rowcount
    print(f"[sync_hotels] Reset {updated} hotel records for series {series_key}")
    return updated


def remove_cancelled_tours(codes: set) -> int:
    """Delete all DB records for the given cancelled tour codes. Returns count removed."""
    if not codes:
        return 0
    with get_db() as conn:
        placeholders = ','.join('?' * len(codes))
        code_list = list(codes)
        existing = [r[0] for r in conn.execute(
            f"SELECT code FROM tours WHERE code IN ({placeholders})", code_list
        ).fetchall()]
        if not existing:
            return 0
        ex_ph = ','.join('?' * len(existing))
        for table, col in [
            ('daily_log',       'tour_code'),
            ('tour_meals',      'tour_code'),
            ('tour_financials', 'tour_code'),
            ('tour_profit',     'tour_code'),
            ('payment_status',  'tour_code'),
        ]:
            try:
                conn.execute(f"DELETE FROM {table} WHERE {col} IN ({ex_ph})", existing)
            except Exception:
                pass
        conn.execute(f"DELETE FROM tours WHERE code IN ({ex_ph})", existing)
        print(f"[cancel_sync] Removed {len(existing)} cancelled tours: {sorted(existing)}")
        return len(existing)


def get_tour_status(bus_start_str: str, bus_end_str: str) -> str:
    today = today_tbilisi()
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
                "rooms": r["rooms"] or "",
                "color": SERIES[r["series"]]["color"],
                "series_name": SERIES[r["series"]]["name"],
            })
        return result

def get_tours_on_date(check_date: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT t.code, t.series, t.bus_start, t.bus_end, t.notes, t.rooms, t.guide, "
            "dl.city, dl.hotel, dl.lunch, dl.dinner, dl.border_crossing, dl.notes as day_notes "
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
                "rooms": r["rooms"] or "",
                "guide": r["guide"] or "",
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
            "rooms": tour["rooms"] or "",
            "guide": tour["guide"] or "",
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

HOTEL_CITY = {
    # Tbilisi
    'Pullman Tbilisi':          'Tbilisi',
    'Hualing Tbilisi':          'Tbilisi',
    'Hualing Preference 5★':    'Tbilisi',
    'Pine Astoria':             'Tbilisi',
    'Pine Astoria Tbilisi':     'Tbilisi',
    'Radisson Blu Tbilisi':     'Tbilisi',
    'Gino Paradise':            'Tbilisi',
    # Yerevan
    'Radisson Blu Yerevan':     'Yerevan',
    "Aghababyan's Yerevan":     'Yerevan',
    'Armenia Marriott Yerevan': 'Yerevan',
    # Akhaltsikhe
    'Akhaltsikhe Inn 5★':       'Akhaltsikhe',
    'Akhaltsikhe Inn':          'Akhaltsikhe',
    # Batumi
    'Greenwood Batumi':         'Batumi',
    'Best Western Batumi':      'Batumi',
    'Radisson Blu Batumi':      'Batumi',
    # Mestia
    'Gistola Resort 5★':        'Mestia',
    'Gistola Resort Mestia':    'Mestia',
    'Lilati Mestia':            'Mestia',
    # Gori
    'Gori Inn':                 'Gori',
    # Gudauri
    'Marco Polo Gudauri':       'Gudauri',
    'Gudauri Inn':              'Gudauri',
    'Gudauri Lodge':            'Gudauri',
    # Other
    'Covasar Sevan':            'Sevan',
    'Crowne Plaza Borjomi':     'Borjomi',
    'Kutaisi Inn':              'Kutaisi',
}

_UNCERTAIN_CITY_MAP = {
    'Mestia': 'Mestia', 'Gori': 'Gori', 'Gudauri': 'Gudauri',
    'Akhaltsikhe': 'Akhaltsikhe', 'Yerevan': 'Yerevan',
}

def _city_from_hotel(hotel: str) -> str:
    """Return city name for a known hotel, or empty string. Handles '? City' uncertain markers."""
    if not hotel:
        return ''
    if hotel.startswith('? '):
        first_word = hotel[2:].split()[0] if hotel[2:].strip() else ''
        return _UNCERTAIN_CITY_MAP.get(first_word, HOTEL_CITY.get(hotel[2:].strip(), ''))
    return HOTEL_CITY.get(hotel, '')

def update_hotels_from_sheets(assignments: dict):
    """Update daily_log.hotel (and city) from Google Sheets. Read-only on sheet."""
    updated = 0
    with get_db() as conn:
        for tour_code, date_hotels in assignments.items():
            for date_iso, hotel in date_hotels.items():
                if not hotel:
                    continue
                # Don't let a generic "Hualing Tbilisi" entry override "Hualing Preference 5★"
                if hotel == 'Hualing Tbilisi':
                    row = conn.execute(
                        "SELECT hotel FROM daily_log WHERE tour_code=? AND date=?",
                        (tour_code, date_iso)
                    ).fetchone()
                    if row and row['hotel'] == 'Hualing Preference 5★':
                        continue
                city = _city_from_hotel(hotel)
                if city:
                    cur = conn.execute(
                        "UPDATE daily_log SET hotel=?, city=? WHERE tour_code=? AND date=?",
                        (hotel, city, tour_code, date_iso)
                    )
                else:
                    cur = conn.execute(
                        "UPDATE daily_log SET hotel=? WHERE tour_code=? AND date=?",
                        (hotel, tour_code, date_iso)
                    )
                updated += cur.rowcount
    print(f"[sheets_sync] Updated {updated} hotel+city records in daily_log")
    return updated

def seed_excel_data(parsed_tours: list):
    with get_db() as conn:
        for t in parsed_tours:
            code = t['tour_code']
            # upsert financials
            fin = t['financials']
            conn.execute("""
                INSERT OR REPLACE INTO tour_financials
                (tour_code, guide, rooms, spent_gel, tour_price_gel, tour_price_usd, profit_gel, paid_gel, paid_cny, due_gel)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (code, t.get('guide',''), t.get('rooms',''),
                  fin['spent_gel'], fin['tour_price_gel'], fin['tour_price_usd'],
                  fin['profit_gel'], fin['paid_gel'], fin['paid_cny'], fin['due_gel']))
            # clear and reinsert meals
            conn.execute("DELETE FROM tour_meals WHERE tour_code=?", (code,))
            for m in t['meals']:
                conn.execute("""
                    INSERT INTO tour_meals (tour_code, date, meal_type, restaurant, gel_amount, usd_amount)
                    VALUES (?,?,?,?,?,?)
                """, (code, m['date'], m['meal_type'], m['restaurant'], m['gel_amount'], m['usd_amount']))

def get_financials_all():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT tf.*, t.bus_start, t.bus_end, t.series
            FROM tour_financials tf
            JOIN tours t ON tf.tour_code = t.code
            ORDER BY t.bus_start
        """).fetchall()
        result = []
        for r in rows:
            status = get_tour_status(r['bus_start'], r['bus_end'])
            result.append({
                'tour_code': r['tour_code'],
                'series': r['series'],
                'bus_start': r['bus_start'],
                'guide': r['guide'],
                'rooms': r['rooms'],
                'spent_gel': r['spent_gel'],
                'tour_price_gel': r['tour_price_gel'],
                'tour_price_usd': r['tour_price_usd'],
                'profit_gel': r['profit_gel'],
                'paid_gel': r['paid_gel'],
                'paid_cny': r['paid_cny'],
                'due_gel': r['due_gel'],
                'status': status,
                'color': SERIES[r['series']]['color'] if r['series'] in SERIES else '#888',
            })
        return result

def get_meals_for_tour(code: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tour_meals WHERE tour_code=? ORDER BY date, meal_type",
            (code,)
        ).fetchall()
        return [dict(r) for r in rows]

def sync_meals_from_financials(meals_data: dict) -> int:
    """
    Replace tour_meals rows with data from financial sheets.
    Also updates daily_log.lunch / daily_log.dinner.
    """
    total = 0
    with get_db() as conn:
        for tour_code, meals in meals_data.items():
            if not meals:
                continue
            conn.execute("DELETE FROM tour_meals WHERE tour_code=?", (tour_code,))
            for m in meals:
                conn.execute(
                    "INSERT INTO tour_meals (tour_code, date, meal_type, restaurant, gel_amount, usd_amount) "
                    "VALUES (?,?,?,?,?,?)",
                    (tour_code, m["date"], m["meal_type"], m["restaurant"],
                     m.get("gel_amount", 0), m.get("usd_amount", 0))
                )
                total += 1
                if m["meal_type"] == "lunch":
                    conn.execute(
                        "UPDATE daily_log SET lunch=? WHERE tour_code=? AND date=?",
                        (m["restaurant"], tour_code, m["date"])
                    )
                elif m["meal_type"] == "dinner":
                    conn.execute(
                        "UPDATE daily_log SET dinner=? WHERE tour_code=? AND date=?",
                        (m["restaurant"], tour_code, m["date"])
                    )
    print(f"[sync_meals_financials] Synced {total} meal records for {len(meals_data)} tours")
    return total


def get_all_restaurants():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT restaurant, COUNT(*) as tour_count, SUM(gel_amount) as total_gel, meal_type
            FROM tour_meals
            WHERE restaurant NOT LIKE '%საკუთარი%' AND restaurant NOT LIKE '%სომხეთი%'
            GROUP BY restaurant
            ORDER BY total_gel DESC
        """).fetchall()
        return [dict(r) for r in rows]


# ── PAYMENT TERMS ──────────────────────────────────────────────────

def _extract_restaurant(meal_str: str) -> str:
    if not meal_str:
        return ''
    return meal_str.split(':', 1)[1].strip() if ':' in meal_str else meal_str.strip()

# Dinners included with the hotel — not separate restaurant payments
_HOTEL_DINNERS = {
    'სომხეთი', 'ახალციხე ინნ', 'გორი ინნ', 'გუდაური ინნ',
    'ლუიბასთან', 'ლუიზასთან', 'მარკო პოლო',
}

def _skip_vendor(name: str) -> bool:
    if not name or not name.strip() or name.strip() == '—':
        return True
    n = name.strip()
    if 'საკუთარი' in n:
        return True
    return n in _HOTEL_DINNERS

def get_payment_terms():
    with get_db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM payment_terms ORDER BY vendor_type, vendor_name"
        ).fetchall()]

def upsert_payment_term(vendor_name: str, vendor_type: str, timing: str, days_offset: int,
                        notes: str = '', unit_price: float = 0.0, currency: str = 'GEL',
                        series_prices: str = ''):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO payment_terms
                (vendor_name, vendor_type, timing, days_offset, notes, unit_price, currency, series_prices)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(vendor_name) DO UPDATE SET
                vendor_type  =excluded.vendor_type,
                timing       =excluded.timing,
                days_offset  =excluded.days_offset,
                notes        =excluded.notes,
                unit_price   =excluded.unit_price,
                currency     =excluded.currency,
                series_prices=excluded.series_prices
        """, (vendor_name.strip(), vendor_type, timing, int(days_offset),
              notes, float(unit_price), currency, series_prices))

def delete_payment_term(term_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM payment_terms WHERE id=?", (term_id,))

def get_all_vendors():
    with get_db() as conn:
        hotels = sorted({r['hotel'] for r in conn.execute(
            "SELECT DISTINCT hotel FROM daily_log WHERE hotel != '' AND hotel IS NOT NULL"
        ).fetchall()})
        meal_names = set()
        for row in conn.execute(
            "SELECT DISTINCT lunch, dinner FROM daily_log WHERE lunch != '' OR dinner != ''"
        ).fetchall():
            for field in [row['lunch'], row['dinner']]:
                n = _extract_restaurant(field)
                if n and not _skip_vendor(n):
                    meal_names.add(n)
        return {'hotels': hotels, 'restaurants': sorted(meal_names)}

_RATE_CACHE = {"rate": None, "ts": 0.0}

def _rate_from_meals(default: float = 2.68) -> float:
    """Fallback: GEL per 1 USD derived (median) from the financial meal pairs."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT gel_amount, usd_amount FROM tour_meals "
            "WHERE usd_amount > 0 AND gel_amount > 0"
        ).fetchall()
    rates = sorted(r['gel_amount'] / r['usd_amount'] for r in rows)
    if not rates:
        return default
    return round(rates[len(rates) // 2], 4)

def get_exchange_rate(default: float = 2.68) -> float:
    """Official USD→GEL rate from the National Bank of Georgia (cached ~6h)."""
    import time
    now = time.time()
    if _RATE_CACHE["rate"] and now - _RATE_CACHE["ts"] < 6 * 3600:
        return _RATE_CACHE["rate"]
    try:
        import requests
        url = "https://nbg.gov.ge/gw/api/ct/monetarypolicy/currencies/en/json/?currencies=USD"
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        resp.raise_for_status()
        cur = resp.json()[0]["currencies"][0]
        rate = round(float(cur["rate"]) / float(cur.get("quantity", 1) or 1), 4)
        if rate > 0:
            _RATE_CACHE["rate"] = rate
            _RATE_CACHE["ts"] = now
            return rate
    except Exception as e:
        print(f"[exchange_rate] NBG fetch failed: {e}")
    # Fallback to last known good, then to meal-derived rate
    return _RATE_CACHE["rate"] or _rate_from_meals(default)


def _calc_amount(term: dict, series: str = '') -> float:
    uprice = term.get('unit_price') or 0.0
    vtype  = term.get('vendor_type', 'hotel')
    sp_str = term.get('series_prices') or ''
    if vtype == 'hotel':
        return uprice * 10.0
    if vtype == 'other' and sp_str and series:
        try:
            return float(_json.loads(sp_str).get(series, uprice))
        except Exception:
            pass
    return uprice

def get_payment_schedule(from_date: str = None, to_date: str = None):
    today = today_tbilisi()
    if not from_date:
        from_date = (today - timedelta(days=14)).isoformat()
    if not to_date:
        to_date = (today + timedelta(days=120)).isoformat()

    with get_db() as conn:
        terms_rows = conn.execute("SELECT * FROM payment_terms").fetchall()
        if not terms_rows:
            return []
        terms = {r['vendor_name'].lower().strip(): dict(r) for r in terms_rows}

        logs = conn.execute("""
            SELECT dl.tour_code, dl.date, dl.hotel, dl.lunch, dl.dinner, t.series
            FROM daily_log dl JOIN tours t ON dl.tour_code=t.code
            WHERE dl.date BETWEEN ? AND ?
            ORDER BY dl.date
        """, (from_date, to_date)).fetchall()

        grouped = defaultdict(lambda: {'dates': set(), 'series': '', 'vendor_type': 'hotel', 'service_type': 'hotel'})

        def collect(tour_code, svc_date, vendor_name, svc_type, series):
            if not vendor_name or _skip_vendor(vendor_name):
                return
            vkey = vendor_name.lower().strip()
            if vkey not in terms:
                return
            vtype = terms[vkey]['vendor_type']
            # Hotels: separate payment per night; others: one grouped payment
            k = (tour_code, vendor_name.strip(), svc_date) if vtype == 'hotel' else (tour_code, vendor_name.strip())
            grouped[k]['dates'].add(svc_date)
            grouped[k]['series'] = series
            grouped[k]['vendor_type'] = vtype
            grouped[k]['service_type'] = svc_type

        for log in logs:
            collect(log['tour_code'], log['date'], log['hotel'], 'hotel', log['series'])
            collect(log['tour_code'], log['date'], _extract_restaurant(log['lunch']), 'lunch', log['series'])
            collect(log['tour_code'], log['date'], _extract_restaurant(log['dinner']), 'dinner', log['series'])

        statuses = get_payment_statuses()

        schedule = []
        for k, info in grouped.items():
            tour_code, vendor_name = k[0], k[1]
            term = terms[vendor_name.lower().strip()]
            dates_sorted = sorted(info['dates'])
            if term['timing'] == 'before':
                ref = date.fromisoformat(dates_sorted[0])
                due = ref - timedelta(days=term['days_offset'])
            else:
                ref = date.fromisoformat(dates_sorted[-1])
                due = ref + timedelta(days=term['days_offset'])
            diff = (due - today).days
            schedule.append({
                'vendor_name': vendor_name,
                'vendor_type': term['vendor_type'],
                'service_type': info['service_type'],
                'tour_code': tour_code,
                'series': info['series'],
                'first_service_date': dates_sorted[0],
                'last_service_date': dates_sorted[-1],
                'nights': len(dates_sorted),
                'due_date': due.isoformat(),
                'timing': term['timing'],
                'days_offset': term['days_offset'],
                'days_until_due': diff,
                'status': 'overdue' if diff < 0 else ('due_soon' if diff <= 3 else 'upcoming'),
                'notes': term['notes'],
                'unit_price': term.get('unit_price') or 0,
                'currency': term.get('currency') or 'GEL',
                'total_amount': _calc_amount(term, info['series']),
                'paid': statuses.get(tour_code, {}).get(vendor_name.strip(), False),
            })

        # "other" vendors (guide, driver) — one entry per tour, due before bus_start
        other_terms = [t for t in terms.values() if t['vendor_type'] == 'other']
        if other_terms:
            tour_rows = conn.execute(
                "SELECT code, series, bus_start, bus_end FROM tours "
                "WHERE bus_start <= ? AND bus_end >= ?",
                (to_date, from_date)
            ).fetchall()
            for tour in tour_rows:
                for term in other_terms:
                    ref = date.fromisoformat(tour['bus_start'])
                    if term['timing'] == 'before':
                        due = ref - timedelta(days=term['days_offset'])
                    else:
                        ref_end = date.fromisoformat(tour['bus_end'])
                        due = ref_end + timedelta(days=term['days_offset'])
                    diff = (due - today).days
                    schedule.append({
                        'vendor_name': term['vendor_name'],
                        'vendor_type': 'other',
                        'service_type': 'other',
                        'tour_code': tour['code'],
                        'series': tour['series'],
                        'first_service_date': tour['bus_start'],
                        'last_service_date': tour['bus_end'],
                        'nights': 0,
                        'due_date': due.isoformat(),
                        'timing': term['timing'],
                        'days_offset': term['days_offset'],
                        'days_until_due': diff,
                        'status': 'overdue' if diff < 0 else ('due_soon' if diff <= 3 else 'upcoming'),
                        'notes': term['notes'],
                        'unit_price': term.get('unit_price') or 0,
                        'currency': term.get('currency') or 'GEL',
                        'total_amount': _calc_amount(term, tour['series']),
                        'paid': statuses.get(tour['code'], {}).get(term['vendor_name'].strip(), False),
                    })

        schedule.sort(key=lambda x: x['due_date'])
        return schedule


def get_payment_statuses() -> dict:
    """Return {tour_code: {vendor_name: True}} for all paid entries."""
    result: dict = {}
    with get_db() as conn:
        for r in conn.execute(
            "SELECT tour_code, vendor_name FROM payment_status WHERE paid=1"
        ).fetchall():
            result.setdefault(r['tour_code'], {})[r['vendor_name']] = True
    return result


def sync_payment_statuses(statuses: dict) -> int:
    """Upsert (tour_code, vendor_name, paid=1) from {tour_code: {vendor_name: True}}."""
    count = 0
    with get_db() as conn:
        for tour_code, vendors in statuses.items():
            for vendor_name in vendors:
                conn.execute("""
                    INSERT INTO payment_status (tour_code, vendor_name, paid)
                    VALUES (?,?,1)
                    ON CONFLICT(tour_code, vendor_name) DO UPDATE SET paid=1
                """, (tour_code, vendor_name.strip()))
                count += 1
    return count


def get_tour_payment_summary(from_date: str = None, to_date: str = None):
    """Group the payment schedule by tour, with each service carrying a paid flag."""
    schedule = get_payment_schedule(from_date, to_date)
    with get_db() as conn:
        tour_rows = {r['code']: dict(r) for r in conn.execute(
            "SELECT code, series, bus_start, bus_end FROM tours"
        ).fetchall()}

    tours: dict = {}
    for item in schedule:
        tc = item['tour_code']
        if tc not in tours:
            tr = tour_rows.get(tc, {})
            tours[tc] = {
                'tour_code': tc,
                'series': item['series'],
                'bus_start': tr.get('bus_start', ''),
                'bus_end': tr.get('bus_end', ''),
                'status': get_tour_status(tr['bus_start'], tr['bus_end']) if tr else 'upcoming',
                'services': [],
                'total_usd': 0.0,
                'total_gel': 0.0,
            }
        tours[tc]['services'].append({
            'vendor_name': item['vendor_name'],
            'vendor_type': item['vendor_type'],
            'due_date': item['due_date'],
            'first_service_date': item['first_service_date'],
            'total_amount': item['total_amount'],
            'currency': item['currency'],
            'paid': item.get('paid', False),
        })
        if item['total_amount'] > 0:
            if item['currency'] == 'USD':
                tours[tc]['total_usd'] += item['total_amount']
            else:
                tours[tc]['total_gel'] += item['total_amount']

    for t in tours.values():
        t['services'].sort(key=lambda s: (s['first_service_date'] or '', s['vendor_name']))

    # Show a tour only while it still has a payment due today or later (Tbilisi time).
    # Tours whose payments are all in the past are finished and must be hidden.
    today_iso = today_tbilisi().isoformat()
    result = [
        t for t in tours.values()
        if any((s['due_date'] or '') >= today_iso for s in t['services'])
    ]
    result.sort(key=lambda t: t['bus_start'])
    return result


def sync_tour_profit(data: dict) -> int:
    """Upsert per-tour profit data from {tour_code: {profit_usd, vat_usd, ...}}.

    Also auto-inserts any tour into the `tours` table if it has balance data
    but wasn't found in the master schedule sheet (e.g. LT series).
    """
    count = 0
    with get_db() as conn:
        existing_codes = {r[0] for r in conn.execute("SELECT code FROM tours").fetchall()}
        for code, d in data.items():
            conn.execute("""
                INSERT INTO tour_profit
                    (tour_code, pax, profit_usd, vat_usd, profit_after_vat, spent_usd, revenue_usd, components, components_detail)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tour_code) DO UPDATE SET
                    pax=excluded.pax,
                    profit_usd=excluded.profit_usd, vat_usd=excluded.vat_usd,
                    profit_after_vat=excluded.profit_after_vat,
                    spent_usd=excluded.spent_usd, revenue_usd=excluded.revenue_usd,
                    components=excluded.components,
                    components_detail=excluded.components_detail
            """, (code, d.get('pax'), d.get('profit_usd'), d.get('vat_usd'),
                  d.get('profit_after_vat'), d.get('spent_usd'), d.get('revenue_usd'),
                  _json.dumps(d.get('components') or {}),
                  _json.dumps(d.get('items') or [])))
            # Rooms from the balance sheet are only a fallback — the master
            # schedule sheet is authoritative, so fill in blanks and never
            # overwrite a value it already set.
            rooms = d.get('rooms', '')
            if rooms:
                conn.execute(
                    "UPDATE tours SET rooms=? WHERE code=? AND (rooms IS NULL OR rooms='')",
                    (rooms, code)
                )
            # Auto-add to tours table if missing (e.g. not yet in the master schedule sheet)
            if code not in existing_codes:
                series = code.split('-')[0]
                off = SERIES_START_OFFSET.get(series)
                m = _re.search(r'-(\d{2})(\d{2})$', code)
                if series in SERIES and off is not None and m:
                    try:
                        bs = date(2026, int(m.group(1)), int(m.group(2))) + timedelta(days=off)
                        _insert_tour(conn, code, series, bs, rooms)
                        existing_codes.add(code)
                        print(f"[profit_sync] auto-added missing tour {code} (bus_start={bs})")
                    except Exception as e:
                        print(f"[profit_sync] could not auto-add {code}: {e}")
            count += 1
    return count


def sync_tour_debts(data: dict) -> int:
    """Upsert per-tour invoice/payment state parsed from the balance workbooks."""
    if not data:
        return 0
    count = 0
    with get_db() as conn:
        for code, d in data.items():
            conn.execute("""
                INSERT INTO tour_debts
                    (tour_code, phase, invoiced_usd, received_usd, awaited_usd,
                     paid_usd, due_usd, awaited_count, due_count, lines, items)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tour_code) DO UPDATE SET
                    phase=excluded.phase,
                    invoiced_usd=excluded.invoiced_usd,
                    received_usd=excluded.received_usd,
                    awaited_usd=excluded.awaited_usd,
                    paid_usd=excluded.paid_usd,
                    due_usd=excluded.due_usd,
                    awaited_count=excluded.awaited_count,
                    due_count=excluded.due_count,
                    lines=excluded.lines,
                    items=excluded.items
            """, (code, d.get('phase'), d.get('invoiced_usd', 0), d.get('received_usd', 0),
                  d.get('awaited_usd', 0), d.get('paid_usd', 0), d.get('due_usd', 0),
                  d.get('awaited_count', 0), d.get('due_count', 0),
                  _json.dumps(d.get('lines') or []),
                  _json.dumps(d.get('items') or [])))
            count += 1
    return count


def _debt_by_date(items: list, days: list) -> list:
    """Spread a tour's invoice lines over the dates they were incurred on.

    Same tracing the VAT split uses: a hotel belongs to the nights spent there, a
    meal to the day it was eaten, and anything that runs all tour spreads across
    it. Lets a total be taken as at a date part-way through a tour instead of
    counting the whole tour or none of it.
    """
    if not days or not items:
        return []
    buckets = {}
    for it in items:
        usd = it.get('usd') or 0
        if not usd:
            continue
        dates = _item_dates(it, days)
        if not dates:
            continue
        each = usd / len(dates)
        for d in dates:
            b = buckets.setdefault(d, {'date': d, 'invoiced': 0.0, 'awaited': 0.0,
                                       'paid': 0.0, 'due': 0.0})
            b['invoiced'] += each
            if not it.get('received'):
                b['awaited'] += each
            if it.get('paid'):
                b['paid'] += each
            elif it.get('due'):
                b['due'] += each
    out = []
    for d in sorted(buckets):
        b = buckets[d]
        out.append({k: (round(v, 2) if k != 'date' else v) for k, v in b.items()})
    return out


def get_tour_debts() -> list:
    """Per-tour invoice and payment state, newest tours last."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT d.*, t.series AS t_series, t.bus_start AS t_start,
                   t.bus_end AS t_end, t.guide AS t_guide
            FROM tour_debts d
            LEFT JOIN tours t ON t.code = d.tour_code
        """).fetchall()
        days_by_tour = defaultdict(list)
        for r in conn.execute(
            "SELECT tour_code, date, city, hotel, lunch, dinner FROM daily_log ORDER BY date"
        ).fetchall():
            days_by_tour[r['tour_code']].append(dict(r))
        result = []
        for r in rows:
            d = dict(r)
            code = r['tour_code']
            series = r['t_series'] or code.split('-')[0]
            bs, be = r['t_start'], r['t_end']
            if not (bs and be):
                bs, be = _approx_dates_from_code(code)
            d['series'] = series
            d['bus_start'], d['bus_end'] = bs, be
            d['guide'] = r['t_guide'] or ''
            for k in ('t_series', 't_start', 't_end', 't_guide'):
                d.pop(k, None)
            d['status'] = get_tour_status(bs, be) if (bs and be) else 'done'
            d['color'] = SERIES.get(series, {}).get('color', '#888')
            try:
                d['lines'] = _json.loads(d.get('lines') or '[]')
            except Exception:
                d['lines'] = []
            try:
                items = _json.loads(d.get('items') or '[]')
            except Exception:
                items = []
            d.pop('items', None)
            d['by_date'] = _debt_by_date(items, days_by_tour.get(code, []))
            result.append(d)
        result.sort(key=lambda x: (x.get('bus_start') or '', x['tour_code']))
        return result


def _approx_dates_from_code(code: str):
    """Tour codes embed MM DD (e.g. DT2-0601 → June 1). Use as a fallback
    date for balance-only tours that aren't in the schedule table."""
    import re
    m = re.search(r'-(\d{2})(\d{2})$', code)
    if not m:
        return None, None
    mm, dd = m.group(1), m.group(2)
    try:
        d = date(2026, int(mm), int(dd))
    except ValueError:
        return None, None
    return d.isoformat(), d.isoformat()


# Balance sheets name suppliers in Georgian; daily_log names hotels in English.
# Each entry pairs the words a balance row may use with the words the itinerary
# uses for the same hotel, so a cost can be traced to the nights it was incurred.
_HOTEL_ALIASES = [
    (('ჰუალინგ', 'hualing'),                 ('hualing',)),
    (('რადისონ', 'radisson'),                ('radisson',)),
    (('აღაბაბაია', 'agababaia', 'aghababayan', 'agababayan'), ('aghababyan',)),
    (('მარკო', 'marco'),                     ('marco polo',)),
    (('გორი ინ', 'gori inn'),                ('gori inn',)),
    (('გრინვუდ', 'greenwood'),               ('greenwood',)),
    (('ახალციხ', 'akhaltsikhe'),             ('akhaltsikhe',)),
    (('გისტოლა', 'gistola'),                 ('gistola',)),
    (('ლილატ', 'lilat'),                     ('lilati',)),
    (('უშბა', 'ushba'),                      ('ushba',)),
    (('პულმან', 'pullman'),                  ('pullman',)),
    (('პაინ', 'pine'),                       ('pine',)),
    (('ბორჯომ', 'borjomi'),                  ('borjomi',)),
    (('გუდაურ', 'gudauri'),                  ('gudauri',)),
    (('ყაზბეგ', 'kazbegi'),                  ('kazbegi', 'mountain house', 'melodia', 'rooms hotel')),
    (('ქუთაის', 'kutaisi'),                  ('kutaisi',)),
    (('სევან', 'sevan'),                     ('sevan',)),
]

_ARMENIA_CITIES = ('yerevan', 'sevan')
_MEAL_PREFIX_RE = _re.compile(r'^\s*(ლანჩი|ვახშამი|ვაშამი|breakfast|lunch|dinner)\s*[:：-]?\s*', _re.IGNORECASE)


def _meal_key(text: str) -> str:
    """Strip the 'ლანჩი:' style prefix and punctuation so a balance row and an
    itinerary entry for the same restaurant compare equal."""
    s = _MEAL_PREFIX_RE.sub('', (text or '').lower())
    return _re.sub(r'[^\wႠ-ჿ]+', '', s)


def _item_dates(item: dict, days: list) -> list:
    """Dates in the itinerary that a balance line item was incurred on.

    Hotels resolve to the nights spent there, meals to the day they were eaten,
    Armenia to the days spent in Armenia. Everything else — bus, guide, staff —
    runs for the whole tour. Anything that can't be placed falls back to the
    whole tour rather than being dropped, so no cost goes missing.
    """
    cat = item.get('cat')
    name = (item.get('name') or '').lower()
    all_dates = [d['date'] for d in days]

    if cat == 'hotel':
        tokens = next((en for ka, en in _HOTEL_ALIASES if any(k in name for k in ka)), None)
        if tokens:
            hit = [d['date'] for d in days
                   if any(t in (d['hotel'] or '').lower() for t in tokens)]
            if hit:
                return hit
    elif cat == 'restaurant':
        key = _meal_key(item.get('name'))
        if key:
            hit = [d['date'] for d in days
                   if key and (key in _meal_key(d['lunch']) or key in _meal_key(d['dinner']))]
            if hit:
                return hit
    elif cat == 'armenia':
        hit = [d['date'] for d in days
               if any(c in (d['city'] or '').lower() for c in _ARMENIA_CITIES)]
        if hit:
            return hit

    return all_dates


def _vat_months(items: list, days: list) -> list:
    """Split a tour's cost across the calendar months it was actually incurred in.

    Every line item is spread evenly over the dates it belongs to, and the months
    those dates fall in decide each month's share. VAT follows the same shares,
    since it is charged on the same services.
    """
    if not days:
        return []
    per_month = defaultdict(float)
    total = 0.0
    for it in items or []:
        usd = it.get('usd') or 0
        if not usd:
            continue
        dates = _item_dates(it, days)
        if not dates:
            continue
        each = usd / len(dates)
        for d in dates:
            per_month[d[:7]] += each
        total += usd
    if total <= 0:
        # No priced line items — fall back to an even spread over the tour's days.
        for d in days:
            per_month[d['date'][:7]] += 1.0
        total = float(len(days))
    return [{'month': m, 'share': per_month[m] / total} for m in sorted(per_month)]


def get_tour_profit() -> list:
    """Return per-tour profit for ALL tours that have balance data,
    whether or not they're still in the schedule table.
    Tours without balance data are considered cancelled and excluded."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.*, t.series AS t_series, t.bus_start AS t_start,
                   t.bus_end AS t_end, t.rooms AS t_rooms, d.phase AS d_phase
            FROM tour_profit p
            LEFT JOIN tours t ON t.code = p.tour_code
            LEFT JOIN tour_debts d ON d.tour_code = p.tour_code
        """).fetchall()
        # Itineraries for every tour at once — used to date each balance line item.
        days_by_tour = defaultdict(list)
        for d in conn.execute(
            "SELECT tour_code, date, city, hotel, lunch, dinner FROM daily_log ORDER BY date"
        ).fetchall():
            days_by_tour[d['tour_code']].append(dict(d))
        result = []
        for r in rows:
            d = dict(r)
            code = r['tour_code']
            series = r['t_series'] or code.split('-')[0]
            d['series'] = series
            d.pop('t_series', None)
            bs, be = r['t_start'], r['t_end']
            if not (bs and be):
                bs, be = _approx_dates_from_code(code)
            d['bus_start'], d['bus_end'] = bs, be
            d.pop('t_start', None); d.pop('t_end', None)
            d['status'] = get_tour_status(bs, be) if (bs and be) else 'done'
            d['rooms'] = r['t_rooms'] or ''
            d.pop('t_rooms', None)
            # Paperwork stage, so the profit table can show it alongside the money.
            d['phase'] = r['d_phase']
            d.pop('d_phase', None)
            d['color'] = SERIES.get(series, {}).get('color', '#888')
            # Itinerary length, so the UI can put costs on a per-day / per-night
            # footing: `days` counts every itinerary day, `nights` only the ones
            # spent in a hotel (the closing flight day has none).
            spec = SERIES.get(series)
            if spec:
                d['days'] = spec['duration']
                d['nights'] = sum(1 for n in spec['nights'].values()
                                  if (n.get('hotel') or '').strip() not in ('', '—'))
            else:
                # Balance-only tours fall back to a single approximated date, so
                # a range is only real when the end is actually past the start.
                span = ((date.fromisoformat(be) - date.fromisoformat(bs)).days
                        if (bs and be) else 0)
                d['days'] = span + 1 if span > 0 else None
                d['nights'] = span if span > 0 else None
            try:
                d['components'] = _json.loads(d.get('components') or '{}')
            except Exception:
                d['components'] = {}
            try:
                d['components_detail'] = _json.loads(d.get('components_detail') or '[]')
            except Exception:
                d['components_detail'] = []
            # Which calendar months this tour's service — and so its VAT — falls in.
            d['vat_months'] = _vat_months(d['components_detail'], days_by_tour.get(code, []))
            result.append(d)
        result.sort(key=lambda x: (x.get('bus_start') or '', x['tour_code']))
        return result


def get_setting(key: str, default: str = '') -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )


def bulk_update_rooms(meta: dict) -> int:
    """Write rooms and guide from the master schedule sheet — the authoritative
    source. `meta` is {tour_code: {"rooms": str, "guide": str}}.

    Overwrites whatever the DB holds whenever the sheet disagrees (e.g. a value
    previously filled in from a balance sheet); rows that already match are left
    alone so the return value counts real changes only. A field the sheet leaves
    blank is not written, so a gap there never erases what is already known.
    """
    if not meta:
        return 0
    updated = 0
    with get_db() as conn:
        for code, info in meta.items():
            if isinstance(info, str):          # tolerate the old rooms-only shape
                info = {"rooms": info}
            for field in ("rooms", "guide"):
                val = (info.get(field) or "").strip()
                if not val:
                    continue
                cur = conn.execute(
                    f"UPDATE tours SET {field}=? WHERE code=? AND ({field} IS NULL OR {field}<>?)",
                    (val, code, val)
                )
                updated += cur.rowcount
    return updated


def apply_schedule_sync(active: list) -> dict:
    """Reconcile the tours table with the master schedule's active list.

    `active` is [{code, series, bus_start(ISO)}] — every ongoing/planned tour
    visible in the master sheet's main tab (before the 'done 2026' marker).

    - ADD  : tours in the active list not yet in the DB.
    - REMOVE: DB tours NOT in the active list that haven't finished yet
              (bus_end >= today).  Completed tours (bus_end < today) are kept
              because they naturally fall off the master tab once done.
    """
    active_codes = {a["code"] for a in active}
    # Safety guard: never wipe tours on a bad/empty fetch.
    if len(active_codes) < 20:
        return {"ok": False, "reason": f"too few active codes ({len(active_codes)}) — skipped",
                "added": [], "removed": []}

    today = today_tbilisi()
    added, removed = [], []
    with get_db() as conn:
        existing = {r["code"]: r["bus_end"]
                    for r in conn.execute("SELECT code, bus_end FROM tours").fetchall()}

        # Additions + rooms update for existing tours
        for a in active:
            code, series = a["code"], a["series"]
            rooms = a.get("rooms", "")
            if series not in SERIES:
                continue
            if code in existing:
                # Update rooms / guide if the sheet now has info and the DB is empty
                if rooms:
                    conn.execute(
                        "UPDATE tours SET rooms=? WHERE code=? AND (rooms IS NULL OR rooms='')",
                        (rooms, code)
                    )
                if a.get("guide"):
                    conn.execute(
                        "UPDATE tours SET guide=? WHERE code=? AND (guide IS NULL OR guide='')",
                        (a["guide"], code)
                    )
                continue
            try:
                bs = date.fromisoformat(a["bus_start"])
            except Exception:
                continue
            _insert_tour(conn, code, series, bs, rooms, a.get("guide", ""))
            added.append(code)

        # Removals: not in active list AND not yet completed
        # Tours with balance data are kept even if absent from the schedule sheet.
        codes_with_profit = {r[0] for r in conn.execute("SELECT tour_code FROM tour_profit").fetchall()}
        for code, be_str in existing.items():
            if code in active_codes:
                continue
            if code in codes_with_profit:
                continue  # has balance data — not cancelled, just missing from sheet
            try:
                bus_end = date.fromisoformat(be_str)
            except Exception:
                continue
            if bus_end >= today:  # still ongoing or future → cancelled
                for tbl, col in [
                    ('daily_log',       'tour_code'),
                    ('tour_meals',      'tour_code'),
                    ('tour_financials', 'tour_code'),
                    ('tour_profit',     'tour_code'),
                    ('payment_status',  'tour_code'),
                ]:
                    try:
                        conn.execute(f"DELETE FROM {tbl} WHERE {col}=?", (code,))
                    except Exception:
                        pass
                conn.execute("DELETE FROM tours WHERE code=?", (code,))
                removed.append(code)

    print(f"[schedule_sync] added={added} removed={removed}")
    return {"ok": True, "added": added, "removed": removed}

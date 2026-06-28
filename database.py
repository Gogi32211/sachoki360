import json as _json
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, timedelta, datetime, timezone
from seed_data import SERIES, TOURS_2026

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
        # Migrate: add rooms column to tours if missing
        try:
            conn.execute("ALTER TABLE tours ADD COLUMN rooms TEXT DEFAULT ''")
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


def _insert_tour(conn, code: str, series: str, bus_start: date, rooms: str = ''):
    """Insert a tour + its daily_log rows from the SERIES template."""
    duration = SERIES[series]["duration"]
    # Tour ends on the Tbilisi→Urumqi flight day = last itinerary day
    bus_end = bus_start + timedelta(days=duration - 1)
    conn.execute(
        "INSERT INTO tours (code, series, bus_start, bus_end, rooms) VALUES (?,?,?,?,?)",
        (code, series, bus_start.isoformat(), bus_end.isoformat(), rooms)
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
            "SELECT t.code, t.series, t.bus_start, t.bus_end, t.notes, t.rooms, "
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
    """Upsert per-tour profit data from {tour_code: {profit_usd, vat_usd, ...}}."""
    count = 0
    with get_db() as conn:
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
            # Also fill rooms on the tours table if the balance sheet has it
            rooms = d.get('rooms', '')
            if rooms:
                conn.execute(
                    "UPDATE tours SET rooms=? WHERE code=? AND (rooms IS NULL OR rooms='')",
                    (rooms, code)
                )
            count += 1
    return count


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


def get_tour_profit() -> list:
    """Return per-tour profit for ALL tours that have balance data,
    whether or not they're still in the schedule table.
    Tours without balance data are considered cancelled and excluded."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT p.*, t.series AS t_series, t.bus_start AS t_start,
                   t.bus_end AS t_end, t.rooms AS t_rooms
            FROM tour_profit p
            LEFT JOIN tours t ON t.code = p.tour_code
        """).fetchall()
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
            d['color'] = SERIES.get(series, {}).get('color', '#888')
            try:
                d['components'] = _json.loads(d.get('components') or '{}')
            except Exception:
                d['components'] = {}
            try:
                d['components_detail'] = _json.loads(d.get('components_detail') or '[]')
            except Exception:
                d['components_detail'] = []
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


def bulk_update_rooms(rooms: dict) -> int:
    """Update rooms for any tour in the DB that currently has an empty rooms field."""
    if not rooms:
        return 0
    updated = 0
    with get_db() as conn:
        for code, room_str in rooms.items():
            if not room_str:
                continue
            cur = conn.execute(
                "UPDATE tours SET rooms=? WHERE code=? AND (rooms IS NULL OR rooms='')",
                (room_str, code)
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
                # Update rooms if the sheet now has info and DB is empty
                if rooms:
                    conn.execute(
                        "UPDATE tours SET rooms=? WHERE code=? AND (rooms IS NULL OR rooms='')",
                        (rooms, code)
                    )
                continue
            try:
                bs = date.fromisoformat(a["bus_start"])
            except Exception:
                continue
            _insert_tour(conn, code, series, bs, rooms)
            added.append(code)

        # Removals: not in active list AND not yet completed
        for code, be_str in existing.items():
            if code in active_codes:
                continue
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

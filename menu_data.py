"""
Restaurant dish lists, for the "მენიუ" (meals) view. No prices — just what's
served and how many portions, computed from the tour's own pax.

WHICH restaurant a tour eats at, on which day, comes from that tour's own
balance workbook tab (via tour_meals — see meals_sync.py / database.py's
get_tour_menu): every tour's finance sheet already dates each lunch/dinner
line with a restaurant name, so that's the real, per-tour source, not a
per-series guess. This module only holds WHAT each restaurant serves, keyed
by that same restaurant name, sourced from the office's per-restaurant
costing sheet (Menu_2026.xlsx) — dish names only, no prices; the quantities
there were sized for one past group and aren't reused here.

A restaurant not listed here just means its menu hasn't been typed in yet —
the tour's day still shows the restaurant name, without a dish breakdown.
"""
import math

# tourists (excluding the driver+guide table) -> portions of most dishes for
# the tourists' table. The driver+guide table is always a flat 1 portion,
# regardless of the main table's count — shown as the constant "+1".
PORTION_TABLE = [
    (6, 1), (11, 2), (16, 3), (21, 4), (25, 5),
]

# A few dishes are ordered by a straight ratio to the tourist count instead
# of the lookup table above: (restaurant, dish) -> (numerator, denominator).
# Water is the same ratio everywhere; the rest are restaurant-specific.
DISH_RATIOS = {
    (None, "წყალი"): (1.3, 2),
    ("სალობიე", "ლობიო"): (1, 2),
    ("სალობიე", "ქაბაბი"): (1, 2),
}


def portions_for(tourists):
    """Portions for the tourists' table, given the tourist headcount
    (the "19" in "19+1" — the driver and guide are never counted here,
    they eat off the same dishes at their own small table)."""
    if tourists is None:
        return None
    for cap, portions in PORTION_TABLE:
        if tourists <= cap:
            return portions
    # Beyond the given table: one more portion per 5 additional tourists,
    # continuing the same spacing.
    last_cap, last_portions = PORTION_TABLE[-1]
    return last_portions + math.ceil((tourists - last_cap) / 5)


def portion_label(tourists):
    """The "4+1" style label: main-table portions + the constant driver/guide one."""
    p = portions_for(tourists)
    return f"{p}+1" if p is not None else None


def dish_portion_label(restaurant, dish, tourists):
    """Same "N+1" label, but honouring a dish's own ratio if it has one."""
    if tourists is None:
        return None
    ratio = DISH_RATIOS.get((restaurant, dish)) or DISH_RATIOS.get((None, dish))
    if ratio:
        num, den = ratio
        return f"{math.ceil(tourists * num / den)}+1"
    return portion_label(tourists)


# Default arrival window, for the reservation text.
MEAL_TIME_WINDOW = {"lunch": "12:00 - 13:00", "dinner": "19:00 - 20:00"}
MEAL_LABEL_GEO = {"lunch": "ლანჩი", "dinner": "ვახშამი"}

# Restaurant phone numbers for the reservation text — not tracked anywhere
# yet. A restaurant with no number here just prints a blank to fill by hand.
RESTAURANT_PHONES = {}


def reservation_text(*, meal, restaurant, date_str, tour_code, tourists,
                      portion_label, guide, guide_phone=None):
    """The office's copy-paste reservation message for one meal."""
    phone = RESTAURANT_PHONES.get(restaurant)
    phone_part = phone or "___"
    guide_part = guide or "გიდი"
    if guide_phone:
        guide_part += f", {guide_phone}"
    return (
        f"{restaurant} (ტელ: {phone_part})\n"
        f"ჯავშნის გაკეთება გვინდა, {date_str}, ტურის კოდი: {tour_code} "
        f"({tourists}+3 სტუმარი) პორციების რაოდენობა {portion_label}. "
        f"{MEAL_LABEL_GEO[meal]}. ადგილზე იქნებიან დაახლოებით "
        f"{MEAL_TIME_WINDOW[meal]}-ზე. {guide_part} დაგიკავშირდებათ."
    )


# restaurant name (as it appears in the balance sheets) -> its dishes.
RESTAURANT_MENUS = {
    "ბალკონი": [
        "კიტრი-პომიდვრის სალათი", "ქამა სოკო კეცზე", "ლობიანი",
        "ოჯახური ღორის", "ხბოს ჩაშუშული", "პური", "წყალი",
    ],
    "კტვ": [
        "ხინკალი", "მწვადი ღორის", "აჯაფსანდალი კეცზე", "შოთის პური",
        "ქათმის შქმერული", "კიტრი-პომიდვრის სალათი", "ხაჭაპური", "წყალი",
    ],
    "ზღაპარი": [
        "სუფი", "კიტრი პომიდვრის სალათი", "კარტოფილი ფრი",
        "ღორის მწვადი", "ხაჭაპური იმერული", "ხბოს მწვადი კეცზე",
        "პური", "წყალი",
    ],
    # TM's own dish set at the same restaurant — the office's own sheet
    # keeps this separate from the list above.
    "ზღაპარი (ტმ მენიუ)": [
        "სუფი", "კიტრი პომიდვრის სალათი", "კარტოფილი ოჯახურად",
        "ქამა სოკო კეცზე", "შქმერული", "ხბოს მწვადი კეცზე",
        "პური", "წყალი",
    ],
    "დიარონი": [
        "ბოსტნეულის სალათი", "სოკოს სუპი", "საფირმო დიარონი",
        "ბრინჯი", "ხბოს ნეკნი აჯიკით", "პურის ასორტი", "წყალი",
    ],
    "ლუშნუ ქორი": [
        "ჭარხალი ტყემალში", "ხბოს ჩაშუშული ტომატში",
        "ტაფაზე შემწვარი კარტოფილი", "ოჯახური სოკ. და ბოსტნეულით",
        "ხაჭაპური სვანური მწვანე ფეტვით", "ღორის მწვადი ბულგარული",
        "პური", "წყალი",
    ],
    "ენგური": [
        "კიტრი პომიდორი", "კარტოფილი გლეხურად", "კუბდარი",
        "ქათმის მწვადი", "ბრინჯი ბოსტნეულით", "ხაჭაპური",
        "პური", "წყალი",
    ],
    "ლუიზასთან": [
        "მჭადი", "კიტრი პომიდვრის სალათი", "მაკარონი", "ხაშლამა",
        "ბოსტნეულის პიცა", "ლობიო აზელილი", "ჩახოხბილი",
        "პური", "წყალი",
    ],
    "სალობიე": [
        "სალათა კ/პ", "ლობიო", "ქაბაბი", "წიწაკის მჟავე",
        "შემწვარი კარტოფილი", "საწებელი", "მწვადი სუკი",
        "პური", "წყალი",
    ],
    "ვარძია შოთა": [
        "ლავაში", "სალათის ფოთლები (პომიდვრით)", "კომბოსტოს სალათი",
        "ხაჭაპური", "ფრი", "თათარბერაგი", "ქათმის მწვადი",
    ],
    "ფასანაური": [
        "ბერძნული სალათი", "ხინკალი ყველის", "ხინკალი ხორცის",
        "ქათმის მწვადი", "ოჯახური ხბოს ხორცით", "ბრინჯი ბოსტნეულით",
        "პური", "წყალი",
    ],
}


def menu_for_restaurant(raw_name):
    """The dish list for a restaurant name as it appears in a balance sheet.

    Tries an exact match first — this is how a variant like "ზღაპარი (ტმ
    მენიუ)" gets its own dishes instead of falling through to the plain
    "ზღაპარი" list. Balance sheets also tack on an extra descriptive word
    sometimes ("ბალკონი სიღნაღი", "კტვ ცეკვებით") and drop it other times
    ("ბალკონი", "კტვ") for the same restaurant, so failing that, the
    longest known name that the raw text starts with wins."""
    if raw_name in RESTAURANT_MENUS:
        return RESTAURANT_MENUS[raw_name]
    for name in sorted(RESTAURANT_MENUS, key=len, reverse=True):
        if raw_name.startswith(name):
            return RESTAURANT_MENUS[name]
    return None

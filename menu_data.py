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
# of the lookup table above: (restaurant, dish) -> (numerator, denominator) —
# portions = ceil(tourists * numerator / denominator). Sourced from the
# office's own costing sheet (Menu_2026.xlsx), which writes the ratio right
# next to the dish as "N კაცზე M" (N people : M portions) or, for khinkali,
# "კაცზე N" (1 person : N portions — a straight multiply, not a divide).
# Water and the soups/broths are the same ratio at every restaurant that
# serves them; khinkali's count is restaurant-specific since it differs
# (1 or 2 per person depending on where it's served).
DISH_RATIOS = {
    (None, "წყალი"): (1.15, 2),
    (None, "სუფი"): (1, 2),
    (None, "სოკოს სუპი"): (1, 2),
    (None, "ბოსტნეულის სუპი"): (1, 2),
    (None, "მჭადი"): (1, 2),
    ("სალობიე", "ლობიო"): (1, 2),
    ("სალობიე", "ქაბაბი"): (1, 2),
    ("კტვ", "ხინკალი"): (2, 1),
    ("ფასანაური", "ხინკალი ყველის"): (1, 1),
    ("ფასანაური", "ხინკალი ხორცის"): (1, 1),
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
    """Portions for a dish, honouring its own ratio if it has one.

    A ratio dish (water, soups, khinkali, ...) is ordered for the whole
    table at once — tourists plus the constant +3 (driver, guide, the
    extra tourist) — so it's computed over that full headcount and shown
    as one number, not split into the usual "N+1". An odd headcount
    rounds up, same as any other fractional result here.

    A dish with no ratio of its own keeps the usual "N+1" table lookup,
    where the +3 always round to a flat extra portion regardless of size.
    """
    if tourists is None:
        return None
    ratio = DISH_RATIOS.get((restaurant, dish)) or DISH_RATIOS.get((None, dish))
    if ratio:
        num, den = ratio
        total = math.ceil((tourists + 3) * num / den)
        # Soups and the kebab-style dishes are a straight halving (2 people :
        # 1 portion) — spell that out next to the number. Water's ratio
        # isn't a plain half (1.3 : 2), so it's left as just the total.
        if (num, den) == (1, 2):
            return f"{total} (გაყოფილი ორად)"
        return str(total)
    return portion_label(tourists)


# Default arrival window, for the reservation text.
MEAL_TIME_WINDOW = {"lunch": "12:00 - 13:00", "dinner": "19:00 - 20:00"}
MEAL_LABEL_GEO = {"lunch": "ლანჩი", "dinner": "ვახშამი"}

# Restaurant phone numbers for the reservation text — not tracked anywhere
# yet. A restaurant with no number here just prints a blank to fill by hand.
RESTAURANT_PHONES = {}


def reservation_text(*, meal, restaurant, date_str, tour_code, tourists,
                      portion_label, guide, guide_phone=None, phone=None,
                      dishes=None):
    """The office's copy-paste reservation message for one meal.

    Includes the dish list with each dish's own portion count, when the
    restaurant's menu is on file, so the whole reservation — not just the
    headcount — goes out in one message. A restaurant without a menu on
    file yet just gets the reservation lines, same as before.
    """
    phone = phone or RESTAURANT_PHONES.get(restaurant)
    phone_part = phone or "___"
    guide_part = guide or "გიდი"
    if guide_phone:
        guide_part += f", {guide_phone}"
    text = (
        f"{restaurant} (ტელ: {phone_part})\n"
        f"ჯავშნის გაკეთება გვინდა, {date_str}, ტურის კოდი: {tour_code} "
        f"({tourists}+3 სტუმარი) პორციების რაოდენობა {portion_label}. "
        f"{MEAL_LABEL_GEO[meal]}. ადგილზე იქნებიან დაახლოებით "
        f"{MEAL_TIME_WINDOW[meal]}-ზე. {guide_part} დაგიკავშირდებათ."
    )
    if dishes:
        menu_lines = "\n".join(f"- {d['name']}: {d['portions']}" for d in dishes)
        text += f"\n\nმენიუ:\n{menu_lines}"
    return text


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
    # დიარონი serves a different set depending on the route direction — the
    # office runs it as two separate tabs (Batumi→Mestia, Mestia→Gori) — but
    # a balance sheet just calls it "დიარონი" either way, so this is the
    # union of both.
    "დიარონი": [
        "ბოსტნეულის სალათი", "სოკოს სუპი", "საფირმო დიარონი", "ბრინჯი",
        "პურის ასორტი", "წყალი", "ბოსტნეული კორსიკულაად", "ბოსტნეულის სუპი",
        "ხბოს ოჯახური", "ხბოს მწვადი", "ქათმის მწვადი",
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
        "ხაჭაპური", "ფრი", "თათარბერაგი", "ქათმის მწვადი", "პური", "წყალი",
    ],
    "ფასანაური": [
        "ბერძნული სალათი", "ხინკალი ყველის", "ხინკალი ხორცის",
        "ქათმის მწვადი", "ოჯახური ხბოს ხორცით", "ბრინჯი ბოსტნეულით",
        "პური", "წყალი",
    ],
    "ოქროს საწმისი": [
        "კპ სალათი", "ბოსტნეული შამფურზე", "მწვადი ღორის", "იმერული",
        "მოხარშული კარტოფილი", "სოკო კეცზე", "ხბოს ჩაქაფული",
        "პური", "წყალი",
    ],
    "ცენტრალ პაბი": [
        "კიტრი პომიდვრის სალათი", "სოკოს სუპი", "მწვადი ხბოსი",
        "ქამა სოკო კეცზე", "ღორის ოჯახური კეცზე", "ლობიანი",
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

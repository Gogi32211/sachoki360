"""
Restaurant menus per series/day, for the "მენიუ" (meals) view. No prices —
just what's served and how many portions, computed from the tour's own pax.

Sourced from the office's per-restaurant costing sheet (Menu_2026.xlsx):
each dish there was portioned for a specific past group, so the quantities in
that sheet aren't reused here — only the dish names are. Portions for any
given tour are computed fresh from PORTION_TABLE, except a few dishes that
the office orders by a different ratio (see DISH_OVERRIDES below).

Breakfast is always at the hotel, so only lunch and dinner are tracked. A
night's dinner already at the hotel is marked AT_HOTEL rather than given a
restaurant — there's nothing to order. Nights with neither (own-expense
meals, or no menu on file yet) simply have no entry; the view leaves them
blank.
"""
import math

AT_HOTEL = "at_hotel"

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


# Default arrival window and restaurant phone numbers, for the reservation
# text. Phones aren't tracked anywhere yet — fill them in as the office
# supplies them; a restaurant with no number just prints a blank to fill by
# hand.
MEAL_TIME_WINDOW = {"lunch": "12:00 - 13:00", "dinner": "19:00 - 20:00"}
MEAL_LABEL_GEO = {"lunch": "ლანჩი", "dinner": "ვახშამი"}

RESTAURANT_PHONES = {
    "ბალკონი": None,
    "კტვ": None,
    "ზღაპარი": None,
    "დიარონი": None,
    "ლუშნუ ქორი": None,
    "ენგური": None,
    "ლუიზასთან": None,
    "სალობიე": None,
}


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


SERIES_MENUS = {
    "ZT": {
        0: {
            "lunch": {"restaurant": "ბალკონი", "dishes": [
                "კიტრი-პომიდვრის სალათი", "ქამა სოკო კეცზე", "ლობიანი",
                "ოჯახური ღორის", "ხბოს ჩაშუშული", "პური", "წყალი",
            ]},
            "dinner": {"restaurant": "კტვ", "dishes": [
                "ხინკალი", "მწვადი ღორის", "აჯაფსანდალი კეცზე", "შოთის პური",
                "ქათმის შქმერული", "კიტრი-პომიდვრის სალათი", "ხაჭაპური", "წყალი",
            ]},
        },
        2: {"dinner": AT_HOTEL},  # Akhaltsikhe Inn
        3: {
            "lunch": {"restaurant": "ზღაპარი", "dishes": [
                "სუფი", "კიტრი პომიდვრის სალათი", "კარტოფილი ფრი",
                "ღორის მწვადი", "ხაჭაპური იმერული", "ხბოს მწვადი კეცზე",
                "პური", "წყალი",
            ]},
        },
        4: {
            "lunch": {"restaurant": "დიარონი", "dishes": [
                "ბოსტნეულის სალათი", "სოკოს სუპი", "საფირმო დიარონი",
                "ბრინჯი", "ხბოს ნეკნი აჯიკით", "პურის ასორტი", "წყალი",
            ]},
            "dinner": {"restaurant": "ლუშნუ ქორი", "dishes": [
                "ჭარხალი ტყემალში", "ხბოს ჩაშუშული ტომატში",
                "ტაფაზე შემწვარი კარტოფილი", "ოჯახური სოკ. და ბოსტნეულით",
                "ხაჭაპური სვანური მწვანე ფეტვით", "ღორის მწვადი ბულგარული",
                "პური", "წყალი",
            ]},
        },
        5: {
            "lunch": {"restaurant": "ენგური", "dishes": [
                "კიტრი პომიდორი", "კარტოფილი გლეხურად", "კუბდარი",
                "ქათმის მწვადი", "ბრინჯი ბოსტნეულით", "ხაჭაპური",
                "პური", "წყალი",
            ]},
            "dinner": {"restaurant": "ლუიზასთან", "dishes": [
                "მჭადი", "კიტრი პომიდვრის სალათი", "მაკარონი", "ხაშლამა",
                "ბოსტნეულის პიცა", "ლობიო აზელილი", "ჩახოხბილი",
                "პური", "წყალი",
            ]},
        },
        6: {
            "lunch": {"restaurant": "დიარონი", "dishes": [
                "ბოსტნეული კორსიკულაად", "ბოსტნეულის სუპი", "ხბოს ოჯახური",
                "ბრინჯი", "ქათმის მწვადი", "პურის ასორტი", "წყალი",
            ]},
            "dinner": AT_HOTEL,  # Gori Inn
        },
        7: {
            "lunch": {"restaurant": "სალობიე", "dishes": [
                "სალათა კ/პ", "ლობიო", "ქაბაბი", "წიწაკის მჟავე",
                "შემწვარი კარტოფილი", "საწებელი", "მწვადი სუკი",
                "პური", "წყალი",
            ]},
            "dinner": AT_HOTEL,  # Gudauri Inn
        },
    },
    "TM": {
        # TM's other lunches/dinners are seeded as generic "ადგილობრივი"
        # (local) with no restaurant named, so there's nothing on file to
        # add there yet — only its Batumi lunch (day 6) matches a restaurant
        # from the costing sheet, and with its own dish list at that: the
        # sheet has a separate "ზღაპარი: TM turi" column, distinct from the
        # one the other series use at the same restaurant.
        5: {
            "lunch": {"restaurant": "ზღაპარი", "dishes": [
                "სუფი", "კიტრი პომიდვრის სალათი", "კარტოფილი ოჯახურად",
                "ქამა სოკო კეცზე", "შქმერული", "ხბოს მწვადი კეცზე",
                "პური", "წყალი",
            ]},
        },
    },
}

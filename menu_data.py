"""
Restaurant menus per series/day, for the "საკვები" (meals) view. No prices —
just what's served and how many portions, computed from the tour's own pax.

Sourced from the office's per-restaurant costing sheet (Menu_2026.xlsx):
each dish there was portioned for a specific past group, so the quantities in
that sheet aren't reused here — only the dish names are. Portions for any
given tour are computed fresh from PORTION_TABLE.

Breakfast is always at the hotel, so only lunch and dinner are tracked.
Nights with no restaurant here (own-expense meals, hotel restaurants, border
days) simply have no entry — the view leaves them blank.
"""

# tourists (excluding the driver+guide table) -> portions of each dish for
# the tourists' table. The driver+guide table is always a flat 1 portion,
# regardless of the main table's count — shown as the constant "+1".
PORTION_TABLE = [
    (6, 1), (11, 2), (16, 3), (21, 4), (25, 5),
]


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
    import math
    return last_portions + math.ceil((tourists - last_cap) / 5)


def portion_label(tourists):
    """The "4+1" style label: main-table portions + the constant driver/guide one."""
    p = portions_for(tourists)
    return f"{p}+1" if p is not None else "?+1"


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
        },
        7: {
            "lunch": {"restaurant": "სალობიე", "dishes": [
                "სალათა კ/პ", "ლობიო", "ქაბაბი", "წიწაკის მჟავე",
                "შემწვარი კარტოფილი", "საწებელი", "მწვადი სუკი",
                "პური", "წყალი",
            ]},
        },
    },
}

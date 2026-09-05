from datetime import date, timedelta

SERIES = {
    "ZT": {
        "name": "ZT — 13 დღე (მესტია ჩართულია)",
        "duration": 9,
        "color": "#42A5F5",
        "nights": {
            0: {"city": "Tbilisi", "hotel": "Hualing Tbilisi", "lunch": "ლანჩი: ბალკონი სიღნაღი", "dinner": "ვახშამი: კტვ ცეკვებით", "border": None},
            1: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: სომხეთი", "border": "GEO→ARM: სადახლო"},
            2: {"city": "Akhaltsikhe", "hotel": "Akhaltsikhe Inn 5★", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: ახალციხე ინნ", "border": "ARM→GEO: ბავრა"},
            3: {"city": "Batumi", "hotel": "Greenwood Batumi", "lunch": "ლანჩი: ზღაპარი", "dinner": "ვახშამი: საკუთარი ხარჯებით", "border": None},
            4: {"city": "Mestia", "hotel": "Gistola Resort 5★", "lunch": "ლანჩი: დიარონი", "dinner": "ვახშამი: ლუშნუ ქორი", "border": None},
            5: {"city": "Mestia", "hotel": "Gistola Resort 5★", "lunch": "ლანჩი: ენგური", "dinner": "ვახშამი: ლუიბასთან", "border": None},
            6: {"city": "Gori", "hotel": "Gori Inn", "lunch": "ლანჩი: დიარონი", "dinner": "ვახშამი: გორი ინნ", "border": None},
            7: {"city": "Gudauri", "hotel": "Marco Polo Gudauri", "lunch": "ლანჩი: სალობიე", "dinner": "ვახშამი: გუდაური ინნ", "border": None},
            8: {"city": "✈ Tbilisi→Urumqi", "hotel": "—", "lunch": "ლანჩი: დინ შენი", "dinner": "ვახშამი: ახალი აზია (ისანი)", "border": None, "notes": "CZ6040 22:50"},
        }
    },
    "LN": {
        "name": "LN — 12 დღე",
        "duration": 8,
        "color": "#66BB6A",
        "nights": {
            0: {"city": "Tbilisi", "hotel": "Hualing Tbilisi", "lunch": "ლანჩი: ბალკონი სიღნაღი", "dinner": "ვახშამი: კტვ ცეკვებით", "border": None},
            1: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: სომხეთი", "border": "GEO→ARM: სადახლო"},
            2: {"city": "Akhaltsikhe", "hotel": "Akhaltsikhe Inn 5★", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: ახალციხე ინნ", "border": "ARM→GEO: ბავრა"},
            3: {"city": "Batumi", "hotel": "Greenwood Batumi", "lunch": "ლანჩი: ზღაპარი", "dinner": "ვახშამი: საკუთარი ხარჯებით", "border": None},
            4: {"city": "Gori", "hotel": "Gori Inn", "lunch": "ლანჩი: მარტვილი", "dinner": "ვახშამი: გორი ინნ", "border": None},
            5: {"city": "Gudauri", "hotel": "Marco Polo Gudauri", "lunch": "ლანჩი: ფასანაური", "dinner": "ვახშამი: მარკო პოლო", "border": None},
            6: {"city": "Tbilisi", "hotel": "Hualing Tbilisi", "lunch": "ლანჩი: სალობიე", "dinner": "ვახშამი: დინ შენი", "border": None},
            7: {"city": "✈ Tbilisi→Urumqi", "hotel": "—", "lunch": "ლანჩი: საკუთარი ხარჯებით", "dinner": "ვახშამი: ახალი აზია (ისანი)", "border": None, "notes": "CZ6040 22:50"},
        }
    },
    "KT": {
        "name": "KT — 10 დღე",
        "duration": 6,
        "color": "#FF7043",
        "nights": {
            0: {"city": "Tbilisi", "hotel": "Hualing Tbilisi", "lunch": "ლანჩი: ბალკონი სიღნაღი", "dinner": "ვახშამი: კტვ ცეკვებით", "border": None},
            1: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: სომხეთი", "border": "GEO→ARM: სადახლო"},
            2: {"city": "Tbilisi", "hotel": "Hualing Tbilisi", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: ახალი აზია (ისანი)", "border": "ARM→GEO: სადახლო"},
            3: {"city": "Tbilisi", "hotel": "Hualing Tbilisi", "lunch": "ლანჩი: ფასანაური", "dinner": "ვახშამი: მარკო პოლო", "border": None},
            4: {"city": "Tbilisi", "hotel": "Hualing Tbilisi", "lunch": "ლანჩი: სალობიე", "dinner": "ვახშამი: დინ შენი", "border": None},
            5: {"city": "✈ Tbilisi→Urumqi", "hotel": "—", "lunch": "ლანჩი: საკუთარი ხარჯებით", "dinner": "ვახშამი: ახალი აზია (ისანი)", "border": None},
        }
    },
    "DT1": {
        "name": "DT1 — 12 დღე (ყაზახეთი + 3 ქ.)",
        "duration": 6,
        "color": "#AB47BC",
        "nights": {
            0: {"city": "Tbilisi", "hotel": "Hualing Preference 5★", "lunch": "ლანჩი: ბალკონი სიღნაღი", "dinner": "ვახშამი: კტვ + ცეკვა / სიმღერა", "border": None},
            1: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: სომხეთი", "border": "GEO→ARM: სადახლო"},
            2: {"city": "Tbilisi", "hotel": "Hualing Preference 5★", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: ახალი აზია (ისანი)", "border": "ARM→GEO: სადახლო"},
            3: {"city": "Tbilisi", "hotel": "Hualing Preference 5★", "lunch": "ლანჩი: სალობიე", "dinner": "ვახშამი: დინ შენი", "border": None},
            4: {"city": "Tbilisi", "hotel": "Hualing Preference 5★", "lunch": "ლანჩი: ფასანაური", "dinner": "ვახშამი: ოქროს საწმისი", "border": None},
            5: {"city": "✈ Tbilisi→Urumqi", "hotel": "—", "lunch": "ლანჩი: ახალი აზია (ისანი)", "dinner": "ვახშამი: საკუთარი ხარჯებით", "border": None},
        }
    },
    "DT2": {
        "name": "DT2 — 14 დღე (ყაზ.+ტაშ.+ 3 ქ.)",
        "duration": 6,
        "color": "#EC407A",
        "nights": {
            0: {"city": "Tbilisi", "hotel": "Hualing Preference 5★", "lunch": "ლანჩი: ბალკონი სიღნაღი", "dinner": "ვახშამი: კტვ + ცეკვა / სიმღერა", "border": None},
            1: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: სომხეთი", "border": "GEO→ARM: სადახლო"},
            2: {"city": "Tbilisi", "hotel": "Hualing Preference 5★", "lunch": "ლანჩი: სომხეთი", "dinner": "ვახშამი: ახალი აზია (ისანი)", "border": "ARM→GEO: სადახლო"},
            3: {"city": "Tbilisi", "hotel": "Hualing Preference 5★", "lunch": "ლანჩი: გურამიშვილის მარანი", "dinner": "ვახშამი: დინ შენი", "border": None},
            4: {"city": "Tbilisi", "hotel": "Hualing Preference 5★", "lunch": "ლანჩი: ფასანაური", "dinner": "ვახშამი: ოქროს საწმისი", "border": None},
            5: {"city": "✈ Tbilisi→Urumqi", "hotel": "—", "lunch": "ლანჩი: საკუთარი ხარჯებით", "dinner": "ვახშამი: ახალი აზია (ისანი)", "border": None},
        }
    },
}

# LT — ახალი სერია, ZT ტურის იდენტური პროგრამით (მცირე განსხვავებებით).
# განსხვავება ZT-სგან: მესტიის ორივე ღამე Lilati Mestia-ში — master განრიგის
# ფურცელში LT ჯგუფები Lilati-შია განთავსებული, არა Gistola-ში.
_LT_NIGHTS = {offset: dict(info) for offset, info in SERIES["ZT"]["nights"].items()}
_LT_NIGHTS[4]["hotel"] = "Lilati Mestia"
_LT_NIGHTS[5]["hotel"] = "Lilati Mestia"
SERIES["LT"] = {
    "name": "LT — ZT-ის მსგავსი (11 ღამე)",
    "duration": 9,
    "color": "#26A69A",
    "nights": _LT_NIGHTS,
}

# HM — 12 დღე: აზერბაიჯანი → საქართველო (მესტია/სვანეთი) → სომხეთი
# Day 1: Urumqi→Baku  Day 2: Baku→Sheki  Day 3: Sheki→Tbilisi (bus_start)
_HM_NIGHTS = {
    0: {"city": "Tbilisi",   "hotel": "Hualing / Pine / Pullman (TBD)", "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
    1: {"city": "Kazbegi",   "hotel": "Rooms Hotel Kazbegi",            "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
    2: {"city": "Kutaisi",   "hotel": "Kutaisi Inn",                    "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
    3: {"city": "Mestia",    "hotel": "Gistola Resort",                 "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
    4: {"city": "Mestia",    "hotel": "Gistola Resort",                 "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD (უშგული)", "border": None},
    5: {"city": "Batumi",    "hotel": "Greenwood Batumi",               "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
    6: {"city": "Borjomi",   "hotel": "Borjomi Likani Health & Spa",    "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
    7: {"city": "Yerevan",   "hotel": "Radisson Blu Yerevan",           "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": "GEO→ARM"},
    8: {"city": "✈ Yerevan→Urumqi", "hotel": "—",                      "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
}
SERIES["HM"] = {
    "name": "HM — 12 დღე (აზ.+საქ.+სომ.)",
    "duration": 9,
    "color": "#F59E0B",
    "nights": _HM_NIGHTS,
}
SERIES["HM1"] = {
    "name": "HM1 — 12 დღე (ჯგუფი 1)",
    "duration": 9,
    "color": "#F59E0B",
    "nights": _HM_NIGHTS,
}
SERIES["HM2"] = {
    "name": "HM2 — 12 დღე (ჯგუფი 2)",
    "duration": 9,
    "color": "#D97706",
    "nights": _HM_NIGHTS,
}
# HT — 10 დღე: აზერბაიჯანი (3 ღ.) → საქართველო → სომხეთი
# Day 1: Baku  Day 2: Baku  Day 3: Sheki  Day 4: Tbilisi (bus_start)
SERIES["HT"] = {
    "name": "HT — 10 დღე (აზ.+საქ.+სომ.)",
    "duration": 6,
    "color": "#6366F1",
    "nights": {
        0: {"city": "Tbilisi",  "hotel": "Hualing / Pine / Pullman (TBD)", "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
        1: {"city": "Tbilisi",  "hotel": "Hualing / Pine / Pullman (TBD)", "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
        2: {"city": "Gudauri",  "hotel": "Marco Polo Gudauri",             "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
        3: {"city": "Tbilisi",  "hotel": "Hualing / Pine / Pullman (TBD)", "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": None},
        4: {"city": "Yerevan",  "hotel": "Radisson Blu Yerevan",           "lunch": "ლანჩი: TBD", "dinner": "ვახშამი: TBD", "border": "GEO→ARM"},
        5: {"city": "✈ Yerevan→Urumqi", "hotel": "—",                     "lunch": "TBD",         "dinner": "TBD",           "border": None},
    },
}

# ── T* სერიები (TH / TK / TM / TV) ────────────────────────────────
# TH — 9 დღე: აზერბაიჯანი (დღე 1-3) → საქართველო (დღე 4-დან) → სომხეთი
# Day 1-3: Urumqi→Baku→Sheki   Day 4: Sheki→Tbilisi (bus_start)
# ბოლო დღე აპში = დღე 8 (ერევანი→ურუმჩი); დღე 9 ტრანზიტია, ავტობუსი არ მოძრაობს.
SERIES["TH"] = {
    "name": "TH — 9 დღე (აზ.+საქ.+სომ.)",
    "duration": 5,
    "color": "#E11D48",
    "nights": {
        0: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: მარნის დეგუსტაცია + ცეკვის შოუ",
            "border": "AZE→GEO: ლაგოდეხი"},
        1: {"city": "Gudauri", "hotel": "Marco Polo Gudauri",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი", "border": None},
        2: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: ხინკალი", "dinner": "ვახშამი: ჩინური", "border": None},
        3: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan",
            "lunch": "ლანჩი: სევანის თევზი", "dinner": "ვახშამი: სპეც. რესტორანი + დუდუკის შოუ",
            "border": "GEO→ARM: სადახლო"},
        4: {"city": "✈ Yerevan→Urumqi", "hotel": "—",
            "lunch": "ლანჩი: სომხური ლავაში + მწვადი", "dinner": "ვახშამი: საკუთარი ხარჯებით",
            "border": None, "notes": "CZ5092 23:50"},
    },
}

# TK — 14 დღე: აზერბაიჯანი (დღე 1-3) → საქართველო + სომხეთი + სვანეთი
# Day 4: Sheki→Tbilisi (bus_start)   Day 13: Tbilisi→Urumqi (CZ6040)
# დღე 14 ტრანზიტია, ავტობუსი არ მოძრაობს.
SERIES["TK"] = {
    "name": "TK — 14 დღე (აზ.+საქ.+სომ.+სვანეთი)",
    "duration": 10,
    "color": "#7C3AED",
    "nights": {
        0: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: მარნის ცეკვის შოუ",
            "border": "AZE→GEO: ლაგოდეხი"},
        1: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan",
            "lunch": "ლანჩი: სევანის თევზი", "dinner": "ვახშამი: სპეც. რესტორანი + დუდუკის შოუ",
            "border": "GEO→ARM: სადახლო"},
        2: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი", "border": None},
        3: {"city": "Borjomi", "hotel": "Borjomi Likani Health & Spa",
            "lunch": "ლანჩი: სომხური ლავაში + მწვადი", "dinner": "ვახშამი: სასტუმროს ბუფეტი",
            "border": "ARM→GEO: ბავრა"},
        4: {"city": "Mestia", "hotel": "Ushba / Lilati Mestia (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი", "border": None},
        5: {"city": "Mestia", "hotel": "Ushba / Lilati Mestia (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი (უშგული)", "border": None},
        6: {"city": "Batumi", "hotel": "Greenwood Batumi",
            "lunch": "ლანჩი: ხაჭაპური + მწვადი", "dinner": "ვახშამი: საკუთარი ხარჯებით", "border": None},
        7: {"city": "Gudauri", "hotel": "Marco Polo Gudauri",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: სასტუმროს ბუფეტი", "border": None},
        8: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი", "border": None},
        9: {"city": "✈ Tbilisi→Urumqi", "hotel": "—",
            "lunch": "ლანჩი: ჩინური", "dinner": "ვახშამი: არ შედის",
            "border": None, "notes": "CZ6040 22:50"},
    },
}

# TM — 10 დღე: იწყება ურუმჩი→ერევანის ფრენით (CZ5091), სრულდება თბილისი→ბაქოთი.
# დღე 1 = ტურის პირველი დღე → offset 0.
SERIES["TM"] = {
    "name": "TM — 11 დღე (სომხეთი + საქართველო)",
    "duration": 11,
    "color": "#0891B2",
    "nights": {
        0: {"city": "✈ Urumqi→Yerevan", "hotel": "Radisson Blu Yerevan",
            "lunch": "ლანჩი: არ შედის", "dinner": "ვახშამი: არ შედის",
            "border": None, "notes": "CZ5091 20:40–22:25"},
        1: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan",
            "lunch": "ლანჩი: სევანის თევზი", "dinner": "ვახშამი: სპეც. რესტორანი + დუდუკის შოუ",
            "border": None},
        2: {"city": "Borjomi", "hotel": "Borjomi Likani Health & Spa",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი",
            "border": "ARM→GEO: ბავრა"},
        3: {"city": "Mestia", "hotel": "Ushba / Lilati Mestia (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი", "border": None},
        4: {"city": "Mestia", "hotel": "Ushba / Lilati Mestia (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი (უშგული)", "border": None},
        5: {"city": "Batumi", "hotel": "Greenwood Batumi",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: საკუთარი ხარჯებით", "border": None},
        6: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი", "border": None},
        7: {"city": "Kazbegi", "hotel": "Mountain House / Melodia (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი", "border": None},
        8: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: არ შედის", "border": None},
        9: {"city": "Baku", "hotel": "Baku Hotel (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ჩინური",
            "border": None},
        10: {"city": "✈ Baku→Urumqi", "hotel": "—",
             "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: არ შედის",
             "border": None, "notes": "J28226 21:20 / J28234 16:40"},
    },
}

# TV — 7 დღე: იწყება ურუმჩი→ერევანის ფრენით (CZ5091), სრულდება თბილისი→ბაქოთი.
# დღე 1 = ტურის პირველი დღე → offset 0.
SERIES["TV"] = {
    "name": "TV — 8 დღე (სომხეთი + საქართველო)",
    "duration": 8,
    "color": "#65A30D",
    "nights": {
        0: {"city": "✈ Urumqi→Yerevan", "hotel": "Radisson Blu Yerevan",
            "lunch": "ლანჩი: არ შედის", "dinner": "ვახშამი: არ შედის",
            "border": None, "notes": "CZ5091 20:45–22:25"},
        1: {"city": "Yerevan", "hotel": "Radisson Blu Yerevan",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: სპეც. რესტორანი + დუდუკის შოუ",
            "border": None},
        2: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: სევანის თევზი", "dinner": "ვახშამი: ჩინური",
            "border": "ARM→GEO: სადახლო"},
        3: {"city": "Gudauri", "hotel": "Marco Polo Gudauri",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: ადგილობრივი", "border": None},
        4: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: ხინკალი", "dinner": "ვახშამი: ჩინური", "border": None},
        5: {"city": "Tbilisi", "hotel": "Hualing / Pine / Pullman (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: მარნის დეგუსტაცია + ცეკვის შოუ",
            "border": None},
        6: {"city": "Baku", "hotel": "Baku Hotel (TBD)",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: საკუთარი ხარჯებით",
            "border": None},
        7: {"city": "✈ Baku→Urumqi", "hotel": "—",
            "lunch": "ლანჩი: ადგილობრივი", "dinner": "ვახშამი: არ შედის",
            "border": None, "notes": "J28234 16:40 / J28226 21:20"},
    },
}

# Day offset from the schedule-map's first (Baku/Almaty) date to the
# app's bus_start (the Georgia / Khareba day). Used by schedule_sync.
SERIES_START_OFFSET = {
    "ZT": 3, "LN": 3, "KT": 3, "DT1": 2, "DT2": 2, "LT": 2,
    # HM: code MMDD = Baku arrival (Day 1), Georgia (Tbilisi) = Day 3 → offset +2
    "HM": 2, "HM1": 2, "HM2": 2,
    # HT: code MMDD = Baku arrival (Day 1), Georgia (Tbilisi) = Day 4 → offset +3
    "HT": 3,
    # TH/TK: code MMDD = Baku arrival (Day 1), Georgia (Tbilisi) = Day 4 → offset +3
    "TH": 3, "TK": 3,
    # TM/TV: code MMDD = Day 1 (Urumqi→Yerevan) — the tour starts there → offset 0
    "TM": 0, "TV": 0,
}

TOURS_2026 = [
    {"code": "ZT-0427", "series": "ZT", "bus_start": "2026-04-30"},
    {"code": "ZT-0504", "series": "ZT", "bus_start": "2026-05-07"},
    {"code": "ZT-0511", "series": "ZT", "bus_start": "2026-05-14"},
    {"code": "ZT-0518", "series": "ZT", "bus_start": "2026-05-21"},
    {"code": "ZT-0525", "series": "ZT", "bus_start": "2026-05-28"},
    {"code": "ZT-0601", "series": "ZT", "bus_start": "2026-06-04"},
    {"code": "ZT-0608", "series": "ZT", "bus_start": "2026-06-11"},
    {"code": "ZT-0615", "series": "ZT", "bus_start": "2026-06-18"},
    {"code": "ZT-0622", "series": "ZT", "bus_start": "2026-06-25"},
    {"code": "ZT-0629", "series": "ZT", "bus_start": "2026-07-02"},
    {"code": "ZT-0706", "series": "ZT", "bus_start": "2026-07-09"},
    {"code": "ZT-0713", "series": "ZT", "bus_start": "2026-07-16"},
    {"code": "ZT-0720", "series": "ZT", "bus_start": "2026-07-23"},
    {"code": "ZT-0727", "series": "ZT", "bus_start": "2026-07-30"},
    {"code": "ZT-0803", "series": "ZT", "bus_start": "2026-08-06"},
    {"code": "ZT-0810", "series": "ZT", "bus_start": "2026-08-13"},
    {"code": "ZT-0817", "series": "ZT", "bus_start": "2026-08-20"},
    {"code": "ZT-0824", "series": "ZT", "bus_start": "2026-08-27"},
    {"code": "ZT-0831", "series": "ZT", "bus_start": "2026-09-03"},
    {"code": "ZT-0907", "series": "ZT", "bus_start": "2026-09-10"},
    {"code": "ZT-0914", "series": "ZT", "bus_start": "2026-09-17"},
    {"code": "ZT-0921", "series": "ZT", "bus_start": "2026-09-24"},
    {"code": "ZT-0928", "series": "ZT", "bus_start": "2026-10-01"},
    {"code": "ZT-1005", "series": "ZT", "bus_start": "2026-10-08"},
    {"code": "ZT-1012", "series": "ZT", "bus_start": "2026-10-15"},
    {"code": "LN-0501", "series": "LN", "bus_start": "2026-05-04"},
    {"code": "LN-0508", "series": "LN", "bus_start": "2026-05-11"},
    {"code": "LN-0518", "series": "LN", "bus_start": "2026-05-21"},
    {"code": "LN-0525", "series": "LN", "bus_start": "2026-05-28"},
    {"code": "LN-0527", "series": "LN", "bus_start": "2026-05-30"},
    {"code": "LN-0601", "series": "LN", "bus_start": "2026-06-04"},
    {"code": "LN-0603", "series": "LN", "bus_start": "2026-06-06"},
    {"code": "LN-0608", "series": "LN", "bus_start": "2026-06-11"},
    {"code": "LN-0615", "series": "LN", "bus_start": "2026-06-18"},
    {"code": "LN-0617", "series": "LN", "bus_start": "2026-06-20"},
    {"code": "LN-0619", "series": "LN", "bus_start": "2026-06-22"},
    {"code": "LN-0622", "series": "LN", "bus_start": "2026-06-25"},
    {"code": "LN-0629", "series": "LN", "bus_start": "2026-07-02"},
    {"code": "LN-0701", "series": "LN", "bus_start": "2026-07-04"},
    {"code": "LN-0703", "series": "LN", "bus_start": "2026-07-06"},
    {"code": "LN-0715", "series": "LN", "bus_start": "2026-07-18"},
    {"code": "LN-0722", "series": "LN", "bus_start": "2026-07-25"},
    {"code": "LN-0802", "series": "LN", "bus_start": "2026-08-05"},
    {"code": "LN-0804", "series": "LN", "bus_start": "2026-08-07"},
    {"code": "LN-0809", "series": "LN", "bus_start": "2026-08-12"},
    {"code": "LN-0811", "series": "LN", "bus_start": "2026-08-14"},
    {"code": "LN-0816", "series": "LN", "bus_start": "2026-08-19"},
    {"code": "LN-0818", "series": "LN", "bus_start": "2026-08-21"},
    {"code": "LN-0823", "series": "LN", "bus_start": "2026-08-26"},
    {"code": "LN-0825", "series": "LN", "bus_start": "2026-08-28"},
    {"code": "LN-0830", "series": "LN", "bus_start": "2026-09-02"},
    {"code": "LN-0901", "series": "LN", "bus_start": "2026-09-04"},
    {"code": "LN-0906", "series": "LN", "bus_start": "2026-09-09"},
    {"code": "LN-0908", "series": "LN", "bus_start": "2026-09-11"},
    {"code": "LN-0913", "series": "LN", "bus_start": "2026-09-16"},
    {"code": "LN-0915", "series": "LN", "bus_start": "2026-09-18"},
    {"code": "LN-0920", "series": "LN", "bus_start": "2026-09-23"},
    {"code": "LN-0921", "series": "LN", "bus_start": "2026-09-24"},
    {"code": "LN-1019", "series": "LN", "bus_start": "2026-10-22"},
    {"code": "KT-0428", "series": "KT", "bus_start": "2026-05-01"},
    {"code": "KT-0505", "series": "KT", "bus_start": "2026-05-08"},
    {"code": "KT-0602", "series": "KT", "bus_start": "2026-06-05"},
    {"code": "KT-0609", "series": "KT", "bus_start": "2026-06-12"},
    {"code": "KT-0616", "series": "KT", "bus_start": "2026-06-19"},
    {"code": "KT-0623", "series": "KT", "bus_start": "2026-06-26"},
    {"code": "KT-0630", "series": "KT", "bus_start": "2026-07-03"},
    {"code": "KT-0707", "series": "KT", "bus_start": "2026-07-10"},
    {"code": "KT-0714", "series": "KT", "bus_start": "2026-07-17"},
    {"code": "KT-0721", "series": "KT", "bus_start": "2026-07-24"},
    {"code": "KT-0728", "series": "KT", "bus_start": "2026-07-31"},
    {"code": "KT-0804", "series": "KT", "bus_start": "2026-08-07"},
    {"code": "KT-0811", "series": "KT", "bus_start": "2026-08-14"},
    {"code": "KT-0818", "series": "KT", "bus_start": "2026-08-21"},
    {"code": "KT-0825", "series": "KT", "bus_start": "2026-08-28"},
    {"code": "KT-0901", "series": "KT", "bus_start": "2026-09-04"},
    {"code": "KT-0908", "series": "KT", "bus_start": "2026-09-11"},
    {"code": "KT-0915", "series": "KT", "bus_start": "2026-09-18"},
    {"code": "KT-0922", "series": "KT", "bus_start": "2026-09-25"},
    {"code": "KT-1006", "series": "KT", "bus_start": "2026-10-09"},
    {"code": "KT-1013", "series": "KT", "bus_start": "2026-10-16"},
    {"code": "DT1-0524", "series": "DT1", "bus_start": "2026-05-26"},
    {"code": "DT1-0531", "series": "DT1", "bus_start": "2026-06-02"},
    {"code": "DT1-0614", "series": "DT1", "bus_start": "2026-06-16"},
    {"code": "DT1-0628", "series": "DT1", "bus_start": "2026-06-30"},
    {"code": "DT1-0712", "series": "DT1", "bus_start": "2026-07-14"},
    {"code": "DT1-0719", "series": "DT1", "bus_start": "2026-07-21"},
    {"code": "DT1-0726", "series": "DT1", "bus_start": "2026-07-28"},
    {"code": "DT1-0802", "series": "DT1", "bus_start": "2026-08-04"},
    {"code": "DT1-0809", "series": "DT1", "bus_start": "2026-08-11"},
    {"code": "DT1-0816", "series": "DT1", "bus_start": "2026-08-18"},
    {"code": "DT1-0823", "series": "DT1", "bus_start": "2026-08-25"},
    {"code": "DT1-0830", "series": "DT1", "bus_start": "2026-09-01"},
    {"code": "DT1-0906", "series": "DT1", "bus_start": "2026-09-08"},
    {"code": "DT1-0913", "series": "DT1", "bus_start": "2026-09-15"},
    {"code": "DT1-0920", "series": "DT1", "bus_start": "2026-09-22"},
    {"code": "DT1-0927", "series": "DT1", "bus_start": "2026-09-29"},
    {"code": "DT1-1004", "series": "DT1", "bus_start": "2026-10-06"},
    {"code": "DT1-1011", "series": "DT1", "bus_start": "2026-10-13"},
    {"code": "DT2-0511", "series": "DT2", "bus_start": "2026-05-13"},
    {"code": "DT2-0524", "series": "DT2", "bus_start": "2026-05-26"},
    {"code": "DT2-0531", "series": "DT2", "bus_start": "2026-06-02"},
    {"code": "DT2-0614", "series": "DT2", "bus_start": "2026-06-16"},
    {"code": "DT2-0621", "series": "DT2", "bus_start": "2026-06-23"},
    {"code": "DT2-0628", "series": "DT2", "bus_start": "2026-06-30"},
    {"code": "DT2-0705", "series": "DT2", "bus_start": "2026-07-07"},
    {"code": "DT2-0712", "series": "DT2", "bus_start": "2026-07-14"},
    {"code": "DT2-0719", "series": "DT2", "bus_start": "2026-07-21"},
    {"code": "DT2-0726", "series": "DT2", "bus_start": "2026-07-28"},
    {"code": "DT2-0802", "series": "DT2", "bus_start": "2026-08-04"},
    {"code": "DT2-0809", "series": "DT2", "bus_start": "2026-08-11"},
    {"code": "DT2-0816", "series": "DT2", "bus_start": "2026-08-18"},
    {"code": "DT2-0823", "series": "DT2", "bus_start": "2026-08-25"},
    {"code": "DT2-0830", "series": "DT2", "bus_start": "2026-09-01"},
    {"code": "DT2-0906", "series": "DT2", "bus_start": "2026-09-08"},
    {"code": "DT2-0913", "series": "DT2", "bus_start": "2026-09-15"},
    {"code": "DT2-0920", "series": "DT2", "bus_start": "2026-09-22"},
    {"code": "DT2-0927", "series": "DT2", "bus_start": "2026-09-29"},
    {"code": "DT2-1004", "series": "DT2", "bus_start": "2026-10-06"},
    {"code": "DT2-1011", "series": "DT2", "bus_start": "2026-10-13"},
    # LT series — new (ZT-like)
    {"code": "LT-0624", "series": "LT", "bus_start": "2026-06-26"},
    {"code": "LT-0626", "series": "LT", "bus_start": "2026-06-28"},
    {"code": "LT-0706", "series": "LT", "bus_start": "2026-07-08"},
    {"code": "LT-0708", "series": "LT", "bus_start": "2026-07-10"},
    {"code": "LT-0713", "series": "LT", "bus_start": "2026-07-15"},
]

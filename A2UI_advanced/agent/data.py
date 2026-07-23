"""Invented restaurant dataset for the A2UI_advanced Concierge use case.

All fictional. `avg_price` is per-person in USD (used by the budget slider filter);
`rating` is out of 5; `dietary` lists tags matched against the user's selections.
`reviews` are {id, text} chunks surfaced via the References modal (the tool-return
pattern). No images (GE cannot render them — see repo resolution.md).
"""

CUISINES = [
    {"label": "Italian", "value": "italian"},
    {"label": "Japanese", "value": "japanese"},
    {"label": "Mexican", "value": "mexican"},
    {"label": "Indian", "value": "indian"},
]

DIETARY = [
    {"label": "Vegetarian", "value": "vegetarian"},
    {"label": "Vegan", "value": "vegan"},
    {"label": "Gluten-free", "value": "gluten_free"},
]

RESTAURANTS = [
    {
        "id": "bella-italia",
        "name": "Bella Italia",
        "cuisine": "italian",
        "avg_price": 38,
        "rating": 4.6,
        "seats": 6,
        "address": "12 Old Market Lane, Downtown",
        "hours": "Mon–Sun · 12:00–23:00",
        "description": "Rustic trattoria known for handmade pasta and wood-fired pizza.",
        "dietary": ["vegetarian"],
        "menu": [
            {"name": "Margherita Pizza", "price": 14.0},
            {"name": "Tagliatelle al Ragù", "price": 18.5},
            {"name": "Tiramisù", "price": 8.0},
        ],
        "reviews": [
            {"id": "REV-BI-01", "text": "\"Best carbonara in the city.\" — Foodie Weekly, 2026"},
            {"id": "REV-BI-02", "text": "4.6/5 across 1,240 diner reviews on TableRate."},
        ],
    },
    {
        "id": "sakura-house",
        "name": "Sakura House",
        "cuisine": "japanese",
        "avg_price": 55,
        "rating": 4.8,
        "seats": 4,
        "address": "5 Riverside Walk, Harbour District",
        "hours": "Tue–Sun · 17:30–22:30",
        "description": "Intimate omakase counter with daily-flown fish and seasonal small plates.",
        "dietary": ["vegetarian", "gluten_free"],
        "menu": [
            {"name": "Chef's Omakase (12 course)", "price": 85.0},
            {"name": "Salmon Nigiri (pair)", "price": 9.0},
            {"name": "Matcha Cheesecake", "price": 10.0},
        ],
        "reviews": [
            {"id": "REV-SH-01", "text": "Awarded 'Best New Sushi 2026' by City Eats Guide."},
            {"id": "REV-SH-02", "text": "\"The uni was sublime.\" — verified TableRate diner, 5/5"},
        ],
    },
    {
        "id": "el-fuego",
        "name": "El Fuego",
        "cuisine": "mexican",
        "avg_price": 28,
        "rating": 4.3,
        "seats": 10,
        "address": "88 Sunset Boulevard, Midtown",
        "hours": "Mon–Sun · 11:00–00:00",
        "description": "Lively cantina serving street tacos, mezcal flights, and tableside guac.",
        "dietary": ["vegetarian", "vegan", "gluten_free"],
        "menu": [
            {"name": "Al Pastor Tacos (3)", "price": 12.0},
            {"name": "Vegan Jackfruit Burrito", "price": 13.5},
            {"name": "Churros con Chocolate", "price": 7.0},
        ],
        "reviews": [
            {"id": "REV-EF-01", "text": "\"Guac made at your table — worth it.\" — Weekend Bites"},
            {"id": "REV-EF-02", "text": "4.3/5 across 2,010 reviews; praised for vegan options."},
        ],
    },
    {
        "id": "spice-route",
        "name": "Spice Route",
        "cuisine": "indian",
        "avg_price": 32,
        "rating": 4.7,
        "seats": 8,
        "address": "23 Garden Crescent, Old Town",
        "hours": "Wed–Mon · 12:00–22:00",
        "description": "Regional Indian tasting menus with a strong vegetarian and vegan range.",
        "dietary": ["vegetarian", "vegan"],
        "menu": [
            {"name": "Paneer Tikka", "price": 11.0},
            {"name": "Lamb Rogan Josh", "price": 17.0},
            {"name": "Gulab Jamun", "price": 6.5},
        ],
        "reviews": [
            {"id": "REV-SR-01", "text": "\"The thali is a tour of the subcontinent.\" — Global Table"},
            {"id": "REV-SR-02", "text": "4.7/5 across 980 reviews; top-rated for vegans."},
        ],
    },
    {
        "id": "trattoria-verde",
        "name": "Trattoria Verde",
        "cuisine": "italian",
        "avg_price": 24,
        "rating": 4.1,
        "seats": 12,
        "address": "40 Vine Street, Uptown",
        "hours": "Mon–Sat · 11:30–22:00",
        "description": "Casual, budget-friendly Italian with a big vegetarian and gluten-free menu.",
        "dietary": ["vegetarian", "gluten_free"],
        "menu": [
            {"name": "Gluten-free Penne Arrabbiata", "price": 13.0},
            {"name": "Caprese Salad", "price": 10.0},
            {"name": "Panna Cotta", "price": 6.0},
        ],
        "reviews": [
            {"id": "REV-TV-01", "text": "\"Great value, generous portions.\" — Budget Eats Blog"},
            {"id": "REV-TV-02", "text": "4.1/5 across 1,530 reviews; solid gluten-free choices."},
        ],
    },
]

_BY_ID = {r["id"]: r for r in RESTAURANTS}


def get(restaurant_id: str) -> dict | None:
    return _BY_ID.get(restaurant_id)


def search(cuisines: list[str], dietary: list[str], max_budget: float) -> list[dict]:
    """Filter restaurants by cuisine(s), dietary needs, and per-person budget.

    Empty cuisine/dietary lists mean "no filter". Results sort by rating desc.
    """
    out = []
    for r in RESTAURANTS:
        if cuisines and r["cuisine"] not in cuisines:
            continue
        if dietary and not all(tag in r["dietary"] for tag in dietary):
            continue
        if max_budget and r["avg_price"] > max_budget:
            continue
        out.append(r)
    return sorted(out, key=lambda r: r["rating"], reverse=True)

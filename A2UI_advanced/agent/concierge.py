"""A2UI v0.8 step builders for the Restaurant Concierge flow.

Each function returns the three-message sequence (surfaceUpdate / dataModelUpdate
/ beginRendering) for one step, and takes the current `booking` dict so it can
prefill inputs and render selections. Input components bind to FLAT top-level
data-model keys (GE writes edits back only to single-segment paths).
"""
import uuid

from . import data


def _surface(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _text(comp_id: str, text: str, usage_hint: str | None = None) -> dict:
    props: dict = {"text": {"literalString": text}}
    if usage_hint:
        props["usageHint"] = usage_hint
    return {"id": comp_id, "component": {"Text": props}}


def _button(comp_id: str, label: str, action: str, context: list[dict]) -> list[dict]:
    """A primary Button + its Text label. `context` is a list of {key, value}."""
    return [
        {
            "id": comp_id,
            "component": {
                "Button": {
                    "child": f"{comp_id}_lbl",
                    "primary": True,
                    "action": {"name": action, "context": context},
                }
            },
        },
        _text(f"{comp_id}_lbl", label),
    ]


def _card(children: list[str]) -> list[dict]:
    """Standard root Card > Column wrapper; caller supplies child ids."""
    return [
        {"id": "root", "component": {"Card": {"child": "col"}}},
        {
            "id": "col",
            "component": {
                "Column": {
                    "alignment": "stretch",
                    "children": {"explicitList": children},
                }
            },
        },
    ]


def _messages(surface_id: str, components: list[dict], data_model: dict) -> list[dict]:
    return [
        {"surfaceUpdate": {"surfaceId": surface_id, "components": components}},
        {"dataModelUpdate": {"surfaceId": surface_id, "contents": data_model}},
        {"beginRendering": {"surfaceId": surface_id, "root": "root"}},
    ]


def _choice(comp_id: str, path: str, options: list[dict], max_sel: int) -> dict:
    return {
        "id": comp_id,
        "component": {
            "MultipleChoice": {
                "selections": {"path": path},
                "maxAllowedSelections": max_sel,
                "options": [
                    {"label": {"literalString": o["label"]}, "value": o["value"]}
                    for o in options
                ],
            }
        },
    }


# ── Step 1: Preferences ──────────────────────────────────────────────────────

def preferences_step(booking: dict) -> list[dict]:
    sid = _surface("prefs")
    children = [
        "title", "cuisine_lbl", "cuisine", "dietary_lbl", "dietary",
        "budget_lbl", "budget", "when_lbl", "when", "find",
    ]
    components = _card(children) + [
        _text("title", "Find a table", usage_hint="h3"),
        _text("cuisine_lbl", "Cuisine", usage_hint="caption"),
        _choice("cuisine", "/cuisine", data.CUISINES, 4),
        _text("dietary_lbl", "Dietary needs", usage_hint="caption"),
        _choice("dietary", "/dietary", data.DIETARY, 3),
        _text("budget_lbl", "Max budget per person ($)", usage_hint="caption"),
        {
            "id": "budget",
            "component": {"Slider": {"value": {"path": "/budget"}, "minValue": 20, "maxValue": 100}},
        },
        _text("when_lbl", "Date & time", usage_hint="caption"),
        {
            "id": "when",
            "component": {
                "DateTimeInput": {"value": {"path": "/when"}, "enableDate": True, "enableTime": True}
            },
        },
    ]
    components += _button(
        "find", "Find tables", "find_tables",
        [
            {"key": "cuisine", "value": {"path": "/cuisine"}},
            {"key": "dietary", "value": {"path": "/dietary"}},
            {"key": "budget", "value": {"path": "/budget"}},
            {"key": "when", "value": {"path": "/when"}},
        ],
    )
    data_model = {
        "cuisine": booking.get("cuisine", []),
        "dietary": booking.get("dietary", []),
        "budget": booking.get("budget", 50),
        "when": booking.get("when", ""),
    }
    return _messages(sid, components, data_model)


# ── Step 2: Results ──────────────────────────────────────────────────────────

def results_step(booking: dict) -> list[dict]:
    sid = _surface("results")
    matches = data.search(
        booking.get("cuisine", []), booking.get("dietary", []), booking.get("budget", 100)
    )

    children = ["title"]
    components = [_text("title", "Available tables", usage_hint="h3")]

    if not matches:
        children += ["empty", "edit"]
        components.append(
            _text("empty", "No restaurants match those filters. Try widening your search.")
        )
        components += _button("edit", "Adjust search", "edit_preferences", [])
        return _messages(sid, _card(children) + components, {})

    children.append("summary")
    components.append(_text("summary", f"{len(matches)} match your search — pick one to see details."))

    for i, r in enumerate(matches):
        row, info, meta, pick = f"row_{i}", f"info_{i}", f"meta_{i}", f"pick_{i}"
        children.append(row)
        components += [
            {
                "id": row,
                "component": {
                    "Row": {
                        "alignment": "center",
                        "distribution": "spaceBetween",
                        "children": {"explicitList": [info, pick]},
                    }
                },
            },
            {
                "id": info,
                "component": {"Column": {"alignment": "start", "children": {"explicitList": [f"name_{i}", meta]}}},
            },
            _text(f"name_{i}", f"**{r['name']}**"),
            _text(
                meta,
                f"{r['cuisine'].title()} · ${r['avg_price']}/person · ★{r['rating']} · {r['seats']} seats",
                usage_hint="caption",
            ),
        ]
        components += _button(
            pick, "Select", "select_restaurant",
            [{"key": "restaurant_id", "value": {"literalString": r["id"]}}],
        )

    children.append("edit")
    components += _button("edit", "← Adjust search", "edit_preferences", [])
    return _messages(sid, _card(children) + components, {})


# ── Step 3: Restaurant detail (Tabs) ─────────────────────────────────────────

def detail_step(booking: dict) -> list[dict]:
    sid = _surface("detail")
    r = data.get(booking.get("restaurant_id") or "")
    if not r:
        components = _card(["oops", "back"]) + [_text("oops", "That restaurant is no longer available.")]
        components += _button("back", "← Back to results", "back_to_results", [])
        return _messages(sid, components, {})

    children = ["title", "tabs", "actions"]
    components = _card(children) + [
        _text("title", r["name"], usage_hint="h3"),
        {
            "id": "tabs",
            "component": {
                "Tabs": {
                    "tabItems": [
                        {"title": {"literalString": "Overview"}, "child": "t_overview"},
                        {"title": {"literalString": "Menu"}, "child": "t_menu"},
                        {"title": {"literalString": "Reviews"}, "child": "t_reviews"},
                        {"title": {"literalString": "Location"}, "child": "t_location"},
                    ]
                }
            },
        },
    ]

    # Overview tab
    components += [
        {"id": "t_overview", "component": {"Column": {"alignment": "start", "children": {"explicitList": ["ov_desc", "ov_meta"]}}}},
        _text("ov_desc", r["description"]),
        _text("ov_meta", f"★ {r['rating']} · ~${r['avg_price']}/person · {r['seats']} seats free", usage_hint="caption"),
    ]

    # Menu tab — one line per dish
    menu_ids = [f"dish_{i}" for i in range(len(r["menu"]))]
    components.append(
        {"id": "t_menu", "component": {"Column": {"alignment": "start", "children": {"explicitList": menu_ids}}}}
    )
    for i, dish in enumerate(r["menu"]):
        components.append(_text(f"dish_{i}", f"**{dish['name']}** — ${dish['price']:.2f}"))

    # Reviews tab — text lines + a References modal listing the review sources
    review_ids = [f"rev_{i}" for i in range(len(r["reviews"]))]
    components.append(
        {"id": "t_reviews", "component": {"Column": {"alignment": "start", "children": {"explicitList": review_ids + ["rev_modal"]}}}}
    )
    for i, rev in enumerate(r["reviews"]):
        components.append(_text(f"rev_{i}", f"“{rev['text']}”", usage_hint="caption"))
    # Modal: full review sources by id
    components += [
        {"id": "rev_modal", "component": {"Modal": {"entryPointChild": "rev_entry", "contentChild": "rev_card"}}},
        _text("rev_entry", "📄 View review sources"),
        {"id": "rev_card", "component": {"Card": {"child": "rev_content"}}},
        {"id": "rev_content", "component": {"Column": {"alignment": "stretch", "children": {"explicitList": ["rev_hdr"] + [f"revsrc_{i}" for i in range(len(r["reviews"]))]}}}},
        _text("rev_hdr", "Review sources", usage_hint="h4"),
    ]
    for i, rev in enumerate(r["reviews"]):
        components.append(_text(f"revsrc_{i}", f"**{rev['id']}**\n\n{rev['text']}"))

    # Location tab
    components += [
        {"id": "t_location", "component": {"Column": {"alignment": "start", "children": {"explicitList": ["loc_addr", "loc_hours"]}}}},
        _text("loc_addr", f"📍 {r['address']}"),
        _text("loc_hours", r["hours"], usage_hint="caption"),
    ]

    # Action buttons row: Reserve + Back
    components.append(
        {"id": "actions", "component": {"Row": {"alignment": "center", "distribution": "spaceBetween", "children": {"explicitList": ["reserve", "back"]}}}}
    )
    components += _button("reserve", "Reserve a table", "start_reservation", [])
    components += _button("back", "← Back to results", "back_to_results", [])
    return _messages(sid, components, {})


# ── Step 4: Reservation form ─────────────────────────────────────────────────

def reservation_step(booking: dict) -> list[dict]:
    sid = _surface("reserve")
    r = data.get(booking.get("restaurant_id") or "")
    name = r["name"] if r else "your table"
    children = [
        "title", "name_lbl", "res_name", "contact_lbl", "res_contact",
        "party_lbl", "party_size", "req_lbl", "requests", "when_lbl", "res_when", "confirm",
    ]
    components = _card(children) + [
        _text("title", f"Reserve at {name}", usage_hint="h3"),
        _text("name_lbl", "Your name", usage_hint="caption"),
        {"id": "res_name", "component": {"TextField": {"label": {"literalString": "Full name"}, "text": {"path": "/res_name"}}}},
        _text("contact_lbl", "Email or phone", usage_hint="caption"),
        {"id": "res_contact", "component": {"TextField": {"label": {"literalString": "Contact"}, "text": {"path": "/res_contact"}}}},
        _text("party_lbl", "Party size", usage_hint="caption"),
        {"id": "party_size", "component": {"Slider": {"value": {"path": "/party_size"}, "minValue": 1, "maxValue": 12}}},
        _text("req_lbl", "Special requests (optional)", usage_hint="caption"),
        {"id": "requests", "component": {"TextField": {"label": {"literalString": "Requests"}, "text": {"path": "/requests"}}}},
        _text("when_lbl", "Date & time", usage_hint="caption"),
        {"id": "res_when", "component": {"DateTimeInput": {"value": {"path": "/res_when"}, "enableDate": True, "enableTime": True}}},
    ]
    components += _button(
        "confirm", "Confirm reservation", "confirm_reservation",
        [
            {"key": "name", "value": {"path": "/res_name"}},
            {"key": "contact", "value": {"path": "/res_contact"}},
            {"key": "party_size", "value": {"path": "/party_size"}},
            {"key": "requests", "value": {"path": "/requests"}},
            {"key": "when", "value": {"path": "/res_when"}},
        ],
    )
    data_model = {
        "res_name": booking.get("res_name", ""),
        "res_contact": booking.get("res_contact", ""),
        "party_size": booking.get("party_size", 2),
        "requests": booking.get("requests", ""),
        "res_when": booking.get("when", ""),
    }
    return _messages(sid, components, data_model)


# ── Step 5: Confirmation ─────────────────────────────────────────────────────

def confirmation_step(booking: dict) -> list[dict]:
    sid = _surface("confirm")
    children = ["title", "summary", "new"]
    components = _card(children) + [
        _text("title", "Reservation confirmed ✅", usage_hint="h3"),
        _text("summary", confirmation_summary(booking)),
    ]
    components += _button("new", "Start a new search", "new_search", [])
    return _messages(sid, components, {})


def confirmation_summary(booking: dict) -> str:
    r = data.get(booking.get("restaurant_id") or "")
    lines = []
    if r:
        lines.append(f"**{r['name']}** — {r['cuisine'].title()}")
        lines.append(f"📍 {r['address']}")
    if booking.get("res_when") or booking.get("when"):
        lines.append(f"🗓️ {booking.get('res_when') or booking.get('when')}")
    lines.append(f"👥 Party of {booking.get('party_size', 2)}")
    if booking.get("res_name"):
        lines.append(f"👤 {booking['res_name']}")
    if booking.get("res_contact"):
        lines.append(f"✉️ {booking['res_contact']}")
    if booking.get("requests"):
        lines.append(f"📝 {booking['requests']}")
    return "\n\n".join(lines)

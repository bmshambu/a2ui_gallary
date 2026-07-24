"""A2UI v0.8 step builders for the Restaurant Concierge flow.

Each function returns the three-message sequence (surfaceUpdate / dataModelUpdate
/ beginRendering) for one step, and takes the current `booking` dict so it can
prefill inputs and render selections. Input components bind to FLAT top-level
data-model keys (GE writes edits back only to single-segment paths).

Enhancements over the basic flow:
  - progress indicator (● ○) atop every step
  - Icon components on step titles / labels  [EXPERIMENT — unverified in GE]
  - CheckBox filters + a min-rating Slider on Preferences
  - secondary (primary:false) buttons for Back / Adjust / New search
  - Dividers for structure; receipt-style Confirmation
  - Menu rendered via a data-bound List template  [EXPERIMENT — unverified in GE]
"""
import uuid

from . import data

# ── flow steps (for the progress indicator) ──────────────────────────────────
STEPS = ["preferences", "results", "detail", "reservation", "confirmation"]
STEP_NAMES = {
    "preferences": "Preferences", "results": "Results", "detail": "Details",
    "reservation": "Reservation", "confirmation": "Confirmed",
}


def _surface(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _text(comp_id: str, text: str, usage_hint: str | None = None) -> dict:
    props: dict = {"text": {"literalString": text}}
    if usage_hint:
        props["usageHint"] = usage_hint
    return {"id": comp_id, "component": {"Text": props}}


def _icon(comp_id: str, name: str) -> dict:
    # EXPERIMENT: GE Icon component. If icon names aren't in GE's set it simply
    # renders nothing (the adjacent title Text still shows) — degrades gracefully.
    return {"id": comp_id, "component": {"Icon": {"name": {"literalString": name}}}}


def _divider(comp_id: str) -> dict:
    return {"id": comp_id, "component": {"Divider": {"axis": "horizontal"}}}


def _checkbox(comp_id: str, label: str, path: str) -> dict:
    return {
        "id": comp_id,
        "component": {"CheckBox": {"label": {"literalString": label}, "value": {"path": path}}},
    }


def _button(comp_id: str, label: str, action: str, context: list[dict], primary: bool = True) -> list[dict]:
    return [
        {
            "id": comp_id,
            "component": {
                "Button": {
                    "child": f"{comp_id}_lbl",
                    "primary": primary,
                    "action": {"name": action, "context": context},
                }
            },
        },
        _text(f"{comp_id}_lbl", label),
    ]


def _choice(comp_id: str, path: str, options: list[dict], max_sel: int) -> dict:
    return {
        "id": comp_id,
        "component": {
            "MultipleChoice": {
                "selections": {"path": path},
                "maxAllowedSelections": max_sel,
                "options": [
                    {"label": {"literalString": o["label"]}, "value": o["value"]} for o in options
                ],
            }
        },
    }


def _header(step: str, icon_name: str, title: str) -> list[dict]:
    """Progress indicator + an icon+title bar. Adds ids: progress, titlebar,
    title_icon, title. Callers put ['progress', 'titlebar', ...] first."""
    i = STEPS.index(step)
    dots = " ".join("●" if j <= i else "○" for j in range(len(STEPS)))
    return [
        _text("progress", f"{dots}   Step {i + 1} of {len(STEPS)} · {STEP_NAMES[step]}", usage_hint="caption"),
        {
            "id": "titlebar",
            "component": {"Row": {"alignment": "center", "distribution": "start", "children": {"explicitList": ["title_icon", "title"]}}},
        },
        _icon("title_icon", icon_name),
        _text("title", title, usage_hint="h3"),
    ]


def _messages(surface_id: str, components: list[dict], data_model: dict) -> list[dict]:
    return [
        {"surfaceUpdate": {"surfaceId": surface_id, "components": components}},
        {"dataModelUpdate": {"surfaceId": surface_id, "contents": data_model}},
        {"beginRendering": {"surfaceId": surface_id, "root": "root"}},
    ]


def _root(children: list[str]) -> list[dict]:
    return [
        {"id": "root", "component": {"Card": {"child": "col"}}},
        {"id": "col", "component": {"Column": {"alignment": "stretch", "children": {"explicitList": children}}}},
    ]


# ── Step 1: Preferences ──────────────────────────────────────────────────────

def preferences_step(booking: dict) -> list[dict]:
    sid = _surface("prefs")
    children = [
        "progress", "titlebar",
        "cuisine_lbl", "cuisine", "dietary_lbl", "dietary",
        "budget_lbl", "budget", "rating_lbl", "min_rating",
        "feat_lbl", "f_outdoor", "f_open", "f_large",
        "when_lbl", "when", "div", "find",
    ]
    components = _root(children) + _header("preferences", "restaurant", "Find a table") + [
        _text("cuisine_lbl", "Cuisine", usage_hint="caption"),
        _choice("cuisine", "/cuisine", data.CUISINES, 4),
        _text("dietary_lbl", "Dietary needs", usage_hint="caption"),
        _choice("dietary", "/dietary", data.DIETARY, 3),
        _text("budget_lbl", "Max budget per person ($)", usage_hint="caption"),
        {"id": "budget", "component": {"Slider": {"value": {"path": "/budget"}, "minValue": 20, "maxValue": 100}}},
        _text("rating_lbl", "Minimum rating (★)", usage_hint="caption"),
        {"id": "min_rating", "component": {"Slider": {"value": {"path": "/min_rating"}, "minValue": 0, "maxValue": 5}}},
        _text("feat_lbl", "Must have", usage_hint="caption"),
        _checkbox("f_outdoor", "Outdoor seating", "/f_outdoor"),
        _checkbox("f_open", "Open now", "/f_open"),
        _checkbox("f_large", "Seats a large group", "/f_large"),
        _text("when_lbl", "Date & time", usage_hint="caption"),
        {"id": "when", "component": {"DateTimeInput": {"value": {"path": "/when"}, "enableDate": True, "enableTime": True}}},
        _divider("div"),
    ]
    components += _button(
        "find", "Find tables", "find_tables",
        [
            {"key": "cuisine", "value": {"path": "/cuisine"}},
            {"key": "dietary", "value": {"path": "/dietary"}},
            {"key": "budget", "value": {"path": "/budget"}},
            {"key": "min_rating", "value": {"path": "/min_rating"}},
            {"key": "outdoor", "value": {"path": "/f_outdoor"}},
            {"key": "open_now", "value": {"path": "/f_open"}},
            {"key": "large", "value": {"path": "/f_large"}},
            {"key": "when", "value": {"path": "/when"}},
        ],
    )
    data_model = {
        "cuisine": booking.get("cuisine", []),
        "dietary": booking.get("dietary", []),
        "budget": booking.get("budget", 50),
        "min_rating": booking.get("min_rating", 0),
        "f_outdoor": booking.get("outdoor", False),
        "f_open": booking.get("open_now", False),
        "f_large": booking.get("large", False),
        "when": booking.get("when", ""),
    }
    return _messages(sid, components, data_model)


# ── Step 2: Results ──────────────────────────────────────────────────────────

def results_step(booking: dict) -> list[dict]:
    sid = _surface("results")
    matches = data.search(
        booking.get("cuisine", []), booking.get("dietary", []), booking.get("budget", 100),
        booking.get("min_rating", 0), booking.get("outdoor", False),
        booking.get("open_now", False), booking.get("large", False),
    )

    children = ["progress", "titlebar"]
    components = _root(children) + _header("results", "search", "Available tables")

    if not matches:
        children += ["empty", "edit"]
        components.append(_text("empty", "No restaurants match those filters. Try widening your search."))
        components += _button("edit", "Adjust search", "edit_preferences", [], primary=False)
        return _messages(sid, components, {})

    children.append("summary")
    components.append(_text("summary", f"{len(matches)} match your search — pick one to see details."))

    for i, r in enumerate(matches):
        card, row, info, meta, pick = f"card_{i}", f"row_{i}", f"info_{i}", f"meta_{i}", f"pick_{i}"
        children.append(card)
        components += [
            {"id": card, "component": {"Card": {"child": row}}},
            {"id": row, "component": {"Row": {"alignment": "center", "distribution": "spaceBetween", "children": {"explicitList": [info, pick]}}}},
            {"id": info, "component": {"Column": {"alignment": "start", "children": {"explicitList": [f"name_{i}", meta]}}}},
            _text(f"name_{i}", f"**{r['name']}**", usage_hint="h4"),
            _text(meta, f"{r['cuisine'].title()} · ${r['avg_price']}/person · ★{r['rating']} · {r['seats']} seats", usage_hint="caption"),
        ]
        components += _button(pick, "Select", "select_restaurant",
                              [{"key": "restaurant_id", "value": {"literalString": r["id"]}}])

    children.append("edit")
    components += _button("edit", "← Adjust search", "edit_preferences", [], primary=False)
    return _messages(sid, components, {})


# ── Step 3: Restaurant detail (Tabs) ─────────────────────────────────────────

def detail_step(booking: dict) -> list[dict]:
    sid = _surface("detail")
    r = data.get(booking.get("restaurant_id") or "")
    if not r:
        components = _root(["oops", "back"]) + [_text("oops", "That restaurant is no longer available.")]
        components += _button("back", "← Back to results", "back_to_results", [], primary=False)
        return _messages(sid, components, {})

    children = ["progress", "titlebar", "tabs", "actions"]
    components = _root(children) + _header("detail", "restaurant_menu", r["name"]) + [
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

    # Each tab: a header (h4) + Divider + content — same structure as the
    # confirmation receipt, so the tabs read cleanly instead of a bare block.

    # Overview tab
    components += [
        {"id": "t_overview", "component": {"Column": {"alignment": "stretch", "children": {"explicitList": ["ov_head", "ov_div", "ov_desc", "ov_stats"]}}}},
        _text("ov_head", "About", usage_hint="h4"),
        _divider("ov_div"),
        _text("ov_desc", r["description"]),
        _text("ov_stats", f"**★ {r['rating']}**  ·  ~${r['avg_price']} / person  ·  {r['seats']} seats free", usage_hint="caption"),
    ]

    # Menu tab — header + divider + data-bound List template (EXPERIMENT)
    components += [
        {"id": "t_menu", "component": {"Column": {"alignment": "stretch", "children": {"explicitList": ["menu_head", "menu_div", "menu_list"]}}}},
        _text("menu_head", "Menu", usage_hint="h4"),
        _divider("menu_div"),
        {"id": "menu_list", "component": {"List": {"children": {"template": {"dataBinding": "/menu", "componentId": "menu_item"}}}}},
        {"id": "menu_item", "component": {"Text": {"text": {"path": "line"}}}},
    ]

    # Reviews tab — header + divider + quotes + References modal
    reviews_md = "\n\n".join(f"> {rev['text']}" for rev in r["reviews"])
    components += [
        {"id": "t_reviews", "component": {"Column": {"alignment": "stretch", "children": {"explicitList": ["rev_head", "rev_div", "rev_quotes", "rev_modal"]}}}},
        _text("rev_head", "What diners say", usage_hint="h4"),
        _divider("rev_div"),
        _text("rev_quotes", reviews_md),
        {"id": "rev_modal", "component": {"Modal": {"entryPointChild": "rev_entry", "contentChild": "rev_card"}}},
        _text("rev_entry", "📄 **View review sources**"),
        {"id": "rev_card", "component": {"Card": {"child": "rev_content"}}},
        {"id": "rev_content", "component": {"Column": {"alignment": "stretch", "children": {"explicitList": ["rev_hdr", "rev_srcs"]}}}},
        _text("rev_hdr", "Review sources", usage_hint="h4"),
        _text("rev_srcs", "\n\n".join(f"**{rev['id']}**  \n{rev['text']}" for rev in r["reviews"])),
    ]

    # Location tab — header + divider + icon/address + hours
    components += [
        {"id": "t_location", "component": {"Column": {"alignment": "stretch", "children": {"explicitList": ["loc_head", "loc_div", "loc_row", "loc_hours"]}}}},
        _text("loc_head", "Find us", usage_hint="h4"),
        _divider("loc_div"),
        {"id": "loc_row", "component": {"Row": {"alignment": "center", "distribution": "start", "children": {"explicitList": ["loc_icon", "loc_addr"]}}}},
        _icon("loc_icon", "place"),
        _text("loc_addr", f"**{r['address']}**"),
        _text("loc_hours", f"🕐 {r['hours']}", usage_hint="caption"),
    ]

    # Action row: primary Reserve + secondary Back
    components.append(
        {"id": "actions", "component": {"Row": {"alignment": "center", "distribution": "spaceBetween", "children": {"explicitList": ["reserve", "back"]}}}}
    )
    components += _button("reserve", "Reserve a table", "start_reservation", [])
    components += _button("back", "← Back to results", "back_to_results", [], primary=False)

    data_model = {"menu": [{"line": f"**{d['name']}** — ${d['price']:.2f}"} for d in r["menu"]]}
    return _messages(sid, components, data_model)


# ── Step 4: Reservation form ─────────────────────────────────────────────────

def reservation_step(booking: dict) -> list[dict]:
    sid = _surface("reserve")
    r = data.get(booking.get("restaurant_id") or "")
    name = r["name"] if r else "your table"
    children = [
        "progress", "titlebar",
        "name_lbl", "res_name", "contact_lbl", "res_contact",
        "party_lbl", "party_size", "req_lbl", "requests", "when_lbl", "res_when", "div", "confirm",
    ]
    components = _root(children) + _header("reservation", "event", f"Reserve at {name}") + [
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
        _divider("div"),
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


# ── Step 5: Confirmation (receipt style) ─────────────────────────────────────

def confirmation_step(booking: dict) -> list[dict]:
    sid = _surface("confirm")
    children = ["progress", "titlebar", "div1", "summary", "div2", "new"]
    components = _root(children) + _header("confirmation", "check_circle", "Reservation confirmed") + [
        _divider("div1"),
        _text("summary", confirmation_summary(booking)),
        _divider("div2"),
    ]
    components += _button("new", "Start a new search", "new_search", [], primary=False)
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
        lines.append(f"📞 {booking['res_contact']}")
    if booking.get("requests"):
        lines.append(f"📝 {booking['requests']}")
    return "\n\n".join(lines)


# ── Click echo ───────────────────────────────────────────────────────────────

_ACTION_LABELS = {
    "start_reservation": "Reserve a table",
    "back_to_results": "Back to results",
    "edit_preferences": "Adjust search",
    "confirm_reservation": "Confirm reservation",
    "new_search": "Start a new search",
}


def action_echo(action: dict, booking: dict) -> str | None:
    """Readable label of what the user just clicked — GE's 'User action
    triggered.' bubble can't be changed, so the reply opens with this quote."""
    name = action.get("name")
    if name == "select_restaurant":
        r = data.get(booking.get("restaurant_id") or "")
        return f"Selected {r['name']}" if r else "Selected a restaurant"
    if name == "find_tables":
        cu = booking.get("cuisine") or []
        cuisines = ", ".join(c.title() for c in cu) if cu else "Any cuisine"
        return f"Find tables · {cuisines} · ≤ ${booking.get('budget', 50)}/person"
    return _ACTION_LABELS.get(name)

"""A2UI v0.9 (basic catalog) step builders for the Restaurant Concierge.

v0.9 vs the v0.8 build (see ../guidelines.md):
  - messages: createSurface + updateComponents + updateDataModel (NOT surfaceUpdate/…),
    every message carries "version": "v0.9".
  - flat discriminator components: {"id":"x","component":"Column","children":[...]}.
  - data binding: {"path": "/key"} (JSON Pointer); data model seeded via
    updateDataModel {path:"/", value:{…}}.
  - Button: `child` (a Text id) + `variant` (default/primary/borderless) + action.event.
  - ChoicePicker: options[{label,value}] + value binding + variant
    (multipleSelection/mutuallyExclusive) + displayStyle (checkbox/chips) + filterable.
  - Slider: value + min + max.  CheckBox: value.  DateTimeInput: value+enableDate+enableTime.
"""
import uuid
from urllib.parse import quote

from . import data

CATALOG_BASIC = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


# ── message + component helpers ──────────────────────────────────────────────

def _surface(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _mix_white(hex_color: str, amount: float) -> str:
    """Lighten a #RRGGBB hex toward white by `amount` (0=unchanged, 1=white)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _msgs(surface_id: str, components: list[dict], data_model: dict | None,
          theme: str | None = None) -> list[dict]:
    create = {"surfaceId": surface_id, "catalogId": CATALOG_BASIC, "sendDataModel": False}
    if theme:  # a hex like "#e8590c" — brands primary buttons / active borders
        create["theme"] = {
            "primaryColor": theme,
            # PROBE: undocumented theme keys. The catalog's theme schema is
            # additionalProperties:true, so these won't be rejected. Testing whether GE
            # honors a page/card background (basic Card has no per-component bg). If GE
            # ignores them there's no harm; if it paints, that's a new styling lever.
            "backgroundColor": _mix_white(theme, 0.90),  # soft page tint
            "surfaceColor": _mix_white(theme, 0.96),     # near-white card ground
            "secondaryColor": theme,
        }
    msgs = [
        {"version": "v0.9", "createSurface": create},
        {"version": "v0.9", "updateComponents": {"surfaceId": surface_id, "components": components}},
    ]
    if data_model is not None:
        msgs.append({"version": "v0.9", "updateDataModel": {
            "surfaceId": surface_id, "path": "/", "value": data_model}})
    return msgs


def _text(comp_id: str, text: str, variant: str | None = None) -> dict:
    d = {"id": comp_id, "component": "Text", "text": text}
    if variant:
        d["variant"] = variant
    return d


def _card(comp_id: str, child: str) -> dict:
    return {"id": comp_id, "component": "Card", "child": child}


def _col(comp_id: str, children: list[str], align: str = "stretch", justify: str | None = None) -> dict:
    d = {"id": comp_id, "component": "Column", "children": children, "align": align}
    if justify:
        d["justify"] = justify
    return d


def _row(comp_id: str, children: list[str], align: str = "center", justify: str = "start") -> dict:
    return {"id": comp_id, "component": "Row", "children": children, "align": align, "justify": justify}


def _button(comp_id: str, label: str, action: str, context: dict | None = None,
            variant: str = "primary") -> list[dict]:
    event: dict = {"name": action}
    if context:
        event["context"] = context
    return [
        {"id": comp_id, "component": "Button", "child": f"{comp_id}_l",
         "variant": variant, "action": {"event": event}},
        _text(f"{comp_id}_l", label),
    ]


def _choice(comp_id: str, path: str, options: list[dict], *, label: str,
            variant: str = "multipleSelection", display: str = "chips",
            filterable: bool = False) -> dict:
    d = {
        "id": comp_id, "component": "ChoicePicker", "label": label,
        "variant": variant, "displayStyle": display,
        "value": {"path": path},
        "options": [{"label": o["label"], "value": o["value"]} for o in options],
    }
    if filterable:
        d["filterable"] = True
    return d


def _slider(comp_id: str, path: str, mn: float, mx: float, *, label: str) -> dict:
    return {"id": comp_id, "component": "Slider", "label": label,
            "value": {"path": path}, "min": mn, "max": mx}


def _checkbox(comp_id: str, path: str, label: str) -> dict:
    return {"id": comp_id, "component": "CheckBox", "label": label, "value": {"path": path}}


def _datetime(comp_id: str, path: str, *, label: str) -> dict:
    return {"id": comp_id, "component": "DateTimeInput", "label": label,
            "value": {"path": path}, "enableDate": True, "enableTime": True}


def _textfield(comp_id: str, path: str, *, label: str, variant: str = "shortText") -> dict:
    return {"id": comp_id, "component": "TextField", "label": label,
            "variant": variant, "value": {"path": path}}


def _image(comp_id: str, url: str, *, variant: str = "mediumFeature", fit: str = "cover") -> dict:
    return {"id": comp_id, "component": "Image", "url": url, "fit": fit, "variant": variant}


def _tabs(comp_id: str, tabs: list[tuple[str, str]]) -> dict:
    return {"id": comp_id, "component": "Tabs",
            "tabs": [{"title": t, "child": c} for t, c in tabs]}


def _modal(comp_id: str, trigger: str, content: str) -> dict:
    return {"id": comp_id, "component": "Modal", "trigger": trigger, "content": content}


def _divider(comp_id: str, axis: str = "horizontal") -> dict:
    return {"id": comp_id, "component": "Divider", "axis": axis}


# ── Step 0: Theme — the first interaction; gates the rest of the flow ─────────

def theme_step(booking: dict) -> list[dict]:
    """First screen for any question: pick a colour theme, then Apply → Preferences.

    Kept separate from Preferences so theme selection is the mandatory first step
    (confirmed in GE: theme.primaryColor repaints buttons/borders/sliders).
    """
    sid = _surface("theme")
    children = ["title", "sub", "theme", "apply"]
    components = [
        _card("root", "col"),
        _col("col", children),
        _text("title", "Choose your theme", variant="h4"),
        _text("sub", "Pick a colour to personalise your concierge — then we'll find you a table.",
              variant="body"),
        _choice("theme", "/theme_sel", data.THEMES, label="Colour theme",
                variant="mutuallyExclusive", display="chips"),
    ]
    components += _button("apply", "Apply theme", "set_theme",
                          {"theme": {"path": "/theme_sel"}}, variant="primary")
    data_model = {"theme_sel": booking.get("theme_sel", [])}
    return _msgs(sid, components, data_model, theme=booking.get("theme"))


# ── Step 1: Preferences ──────────────────────────────────────────────────────

def preferences_step(booking: dict) -> list[dict]:
    sid = _surface("prefs")
    children = [
        "title", "cuisine", "dietary", "budget", "rating",
        "f_outdoor", "f_open", "when", "find",
    ]
    components = [
        _card("root", "col"),
        _col("col", children),
        _text("title", "Find a table", variant="h4"),
        _choice("cuisine", "/cuisine", data.CUISINES, label="Cuisine", filterable=True),
        _choice("dietary", "/dietary", data.DIETARY, label="Dietary needs", filterable=True),
        _slider("budget", "/budget", 20, 100, label="Max budget per person ($)"),
        _slider("rating", "/min_rating", 0, 5, label="Minimum rating (★)"),
        _checkbox("f_outdoor", "/outdoor", "Outdoor seating"),
        _checkbox("f_open", "/open_now", "Open now"),
        _datetime("when", "/when", label="Date & time"),
    ]
    components += _button("find", "Find tables", "find_tables", {
        "cuisine": {"path": "/cuisine"},
        "dietary": {"path": "/dietary"},
        "budget": {"path": "/budget"},
        "min_rating": {"path": "/min_rating"},
        "outdoor": {"path": "/outdoor"},
        "open_now": {"path": "/open_now"},
        "when": {"path": "/when"},
    })
    data_model = {
        "cuisine": booking.get("cuisine", []),
        "dietary": booking.get("dietary", []),
        "budget": booking.get("budget", 50),
        "min_rating": booking.get("min_rating", 0),
        "outdoor": booking.get("outdoor", False),
        "open_now": booking.get("open_now", False),
        "when": booking.get("when", ""),
    }
    return _msgs(sid, components, data_model, theme=booking.get("theme"))


# ── Step 2: Results — a photo card per match with a Select button ────────────

def results_step(booking: dict) -> list[dict]:
    sid = _surface("results")
    matches = data.search(
        booking.get("cuisine", []), booking.get("dietary", []), booking.get("budget", 100),
        booking.get("min_rating", 0), booking.get("outdoor", False), booking.get("open_now", False),
    )

    children = ["title"]
    components = [_text("title", "Available tables", variant="h4")]

    if not matches:
        children += ["empty", "back"]
        components.append(_text("empty", "No restaurants match those filters — widen your search.", variant="body"))
        components += _button("back", "Adjust search", "edit_preferences", variant="borderless")
        return _msgs(sid, [_card("root", "col"), _col("col", children)] + components, None, theme=booking.get("theme"))

    children.append("summary")
    components.append(_text("summary", f"{len(matches)} match — pick one to see details.", variant="body"))

    for i, r in enumerate(matches):
        card, inner, img, name, meta, pick = (
            f"card_{i}", f"inner_{i}", f"img_{i}", f"name_{i}", f"meta_{i}", f"pick_{i}")
        children.append(card)
        components += [
            _card(card, inner),
            _col(inner, [img, name, meta, pick]),
            _image(img, r["image"], variant="smallFeature"),
            _text(name, r["name"], variant="h5"),
            _text(meta, f"{r['cuisine'].title()} · ${r['avg_price']}/person · ★{r['rating']} · {r['seats']} seats",
                  variant="caption"),
        ]
        components += _button(pick, "Select", "select_restaurant",
                              {"restaurant_id": r["id"]}, variant="primary")

    children.append("back")
    components += _button("back", "← Adjust search", "edit_preferences", variant="borderless")
    return _msgs(sid, [_card("root", "col"), _col("col", children)] + components, None, theme=booking.get("theme"))


# ── Step 3: Detail — Tabs (Overview w/ photo · Menu · Reviews+modal · Location) ─

def detail_step(booking: dict) -> list[dict]:
    sid = _surface("detail")
    r = data.get(booking.get("restaurant_id") or "")
    if not r:
        comps = [_card("root", "col"), _col("col", ["oops", "back"]),
                 _text("oops", "That restaurant is no longer available.", variant="body")]
        comps += _button("back", "← Back to results", "back_to_results", variant="borderless")
        return _msgs(sid, comps, None, theme=booking.get("theme"))

    components = [
        _card("root", "col"),
        _col("col", ["title", "tabs", "actions"]),
        _text("title", r["name"], variant="h4"),
        _tabs("tabs", [("Overview", "t_ov"), ("Menu", "t_menu"),
                       ("Reviews", "t_rev"), ("Location", "t_loc")]),
    ]

    # Overview tab — photo + description + stats  (body variant = bigger tab text)
    components += [
        _col("t_ov", ["ov_img", "ov_desc", "ov_stats"]),
        _image("ov_img", r["image"], variant="mediumFeature"),
        _text("ov_desc", r["description"], variant="body"),
        _text("ov_stats", f"★ {r['rating']} · ~${r['avg_price']}/person · {r['seats']} seats free", variant="body"),
    ]

    # Menu tab — one line per dish
    menu_ids = [f"dish_{i}" for i in range(len(r["menu"]))]
    components.append(_col("t_menu", menu_ids))
    for i, dish in enumerate(r["menu"]):
        components.append(_text(f"dish_{i}", f"**{dish['name']}** — ${dish['price']:.2f}", variant="body"))

    # Reviews tab — quotes + a Modal listing the review sources
    rev_ids = [f"rev_{i}" for i in range(len(r["reviews"]))]
    components.append(_col("t_rev", rev_ids + ["rev_modal"]))
    for i, rev in enumerate(r["reviews"]):
        components.append(_text(f"rev_{i}", f"“{rev['text']}”", variant="body"))
    components += [
        _modal("rev_modal", "rev_entry", "rev_card"),
        _text("rev_entry", "📄 View review sources", variant="body"),
        _card("rev_card", "rev_content"),
        _col("rev_content", ["rev_hdr"] + [f"revsrc_{i}" for i in range(len(r["reviews"]))]),
        _text("rev_hdr", "Review sources", variant="h5"),
    ]
    for i, rev in enumerate(r["reviews"]):
        # variant "body" (not caption): markdown bold only renders in body Text in GE v0.9.
        components.append(_text(f"revsrc_{i}", f"**{rev['id']}** — {rev['text']}", variant="body"))

    # Location tab — address + a Google Maps link (Text markdown link) + hours
    maps_url = "https://www.google.com/maps/search/?api=1&query=" + quote(r["address"])
    components += [
        _col("t_loc", ["loc_addr", "loc_map", "loc_hours"]),
        _text("loc_addr", f"📍 {r['address']}", variant="body"),
        _text("loc_map", f"[🗺️ Open in Google Maps]({maps_url})", variant="body"),
        _text("loc_hours", f"🕐 {r['hours']}", variant="body"),
    ]

    # Actions — Reserve (primary) + Back (borderless)
    components.append(_row("actions", ["reserve", "back"], justify="spaceBetween"))
    components += _button("reserve", "Reserve a table", "start_reservation", variant="primary")
    components += _button("back", "← Back to results", "back_to_results", variant="borderless")
    return _msgs(sid, components, None, theme=booking.get("theme"))


# ── Step 4: Reservation — form (server-validated in the callback) ────────────

def reservation_step(booking: dict) -> list[dict]:
    sid = _surface("reserve")
    error = booking.get("_error")
    r = data.get(booking.get("restaurant_id") or "")
    name = r["name"] if r else "your table"

    children = ["title"]
    components = [_text("title", f"Reserve at {name}", variant="h4")]
    if error:
        children.append("error")
        components.append(_text("error", f"⚠️ {error}", variant="body"))
    children += ["res_name", "res_contact", "party", "res_when", "confirm"]
    components += [
        _textfield("res_name", "/res_name", label="Your name"),
        _textfield("res_contact", "/res_contact", label="Email or phone"),
        _slider("party", "/party_size", 1, 12, label="Party size"),
        _datetime("res_when", "/res_when", label="Date & time"),
    ]
    components += _button("confirm", "Confirm reservation", "confirm_reservation", {
        "name": {"path": "/res_name"},
        "contact": {"path": "/res_contact"},
        "party_size": {"path": "/party_size"},
        "when": {"path": "/res_when"},
    }, variant="primary")

    data_model = {
        "res_name": booking.get("res_name", ""),
        "res_contact": booking.get("res_contact", ""),
        "party_size": booking.get("party_size", 2),
        "res_when": booking.get("res_when") or booking.get("when", ""),
    }
    return _msgs(sid, [_card("root", "col"), _col("col", children)] + components, data_model, theme=booking.get("theme"))


# ── Step 5: Confirmation ─────────────────────────────────────────────────────

def confirmation_step(booking: dict) -> list[dict]:
    sid = _surface("confirm")
    components = [
        _card("root", "col"),
        _col("col", ["title", "div", "summary", "new"]),
        _text("title", "Reservation confirmed ✅", variant="h4"),
        _divider("div"),
        _text("summary", confirmation_summary(booking), variant="body"),
    ]
    components += _button("new", "Start a new search", "new_search", variant="borderless")
    return _msgs(sid, components, None, theme=booking.get("theme"))


def confirmation_summary(booking: dict) -> str:
    r = data.get(booking.get("restaurant_id") or "")
    lines = []
    if r:
        lines.append(f"**{r['name']}** — {r['cuisine'].title()}")
        lines.append(f"📍 {r['address']}")
    when = booking.get("res_when") or booking.get("when")
    if when:
        lines.append(f"🗓️ {when}")
    lines.append(f"👥 Party of {booking.get('party_size', 2)}")
    if booking.get("res_name"):
        lines.append(f"👤 {booking['res_name']}")
    if booking.get("res_contact"):
        lines.append(f"📞 {booking['res_contact']}")
    return "\n\n".join(lines)


# ── click echo (what the user tapped) ────────────────────────────────────────

_ACTION_LABELS = {
    "start_reservation": "Reserve a table",
    "back_to_results": "Back to results",
    "edit_preferences": "Adjust search",
    "confirm_reservation": "Confirm reservation",
    "new_search": "Start a new search",
    "back_to_gallery": "All components",
    "exit_gallery": "Back to booking",
}


def action_echo(action: dict, booking: dict) -> str | None:
    name = action.get("name")
    if name == "select_restaurant":
        rid = (action.get("context") or {}).get("restaurant_id")
        r = data.get(rid or "")
        return f"Selected {r['name']}" if r else "Selected a restaurant"
    if name == "find_tables":
        cu = booking.get("cuisine") or []
        return f"Find tables · {', '.join(c.title() for c in cu) if cu else 'Any cuisine'}"
    if name == "show_component":
        comp = booking.get("demo_component") or ""
        return f"Component · {comp}" if comp else "Component"
    if name == "set_theme":
        sel = booking.get("theme_sel") or []
        return f"Theme · {sel[0].title()}" if sel else None
    return _ACTION_LABELS.get(name)

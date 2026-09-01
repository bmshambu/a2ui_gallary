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

from . import data

CATALOG_BASIC = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


# ── message + component helpers ──────────────────────────────────────────────

def _surface(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _msgs(surface_id: str, components: list[dict], data_model: dict | None) -> list[dict]:
    msgs = [
        {"version": "v0.9", "createSurface": {
            "surfaceId": surface_id, "catalogId": CATALOG_BASIC, "sendDataModel": False}},
        {"version": "v0.9", "updateComponents": {
            "surfaceId": surface_id, "components": components}},
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
            variant: str = "multipleSelection", display: str = "chips") -> dict:
    return {
        "id": comp_id, "component": "ChoicePicker", "label": label,
        "variant": variant, "displayStyle": display,
        "value": {"path": path},
        "options": [{"label": o["label"], "value": o["value"]} for o in options],
    }


def _slider(comp_id: str, path: str, mn: float, mx: float, *, label: str) -> dict:
    return {"id": comp_id, "component": "Slider", "label": label,
            "value": {"path": path}, "min": mn, "max": mx}


def _checkbox(comp_id: str, path: str, label: str) -> dict:
    return {"id": comp_id, "component": "CheckBox", "label": label, "value": {"path": path}}


def _datetime(comp_id: str, path: str, *, label: str) -> dict:
    return {"id": comp_id, "component": "DateTimeInput", "label": label,
            "value": {"path": path}, "enableDate": True, "enableTime": True}


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
        _choice("cuisine", "/cuisine", data.CUISINES, label="Cuisine"),
        _choice("dietary", "/dietary", data.DIETARY, label="Dietary needs"),
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
    return _msgs(sid, components, data_model)


# ── Step 2: Results (placeholder — full UI is the next port step) ────────────

def results_step(booking: dict) -> list[dict]:
    sid = _surface("results")
    matches = data.search(
        booking.get("cuisine", []), booking.get("dietary", []), booking.get("budget", 100),
        booking.get("min_rating", 0), booking.get("outdoor", False), booking.get("open_now", False),
    )
    names = ", ".join(r["name"] for r in matches) or "no restaurants"
    components = [
        _card("root", "col"),
        _col("col", ["title", "summary", "back"]),
        _text("title", "Results", variant="h4"),
        _text("summary",
              f"Your search matched **{len(matches)}**: {names}. "
              "(The full results UI — cards, photos, select buttons — is the next port step.)",
              variant="body"),
    ]
    components += _button("back", "← Adjust search", "edit_preferences", variant="borderless")
    return _msgs(sid, components, None)

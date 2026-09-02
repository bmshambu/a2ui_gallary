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


def _apply_density(components: list[dict], gap: int) -> list[dict]:
    """Inject `gap` blank spacer lines between the root Column's children (id 'col').
    Basic catalog has no line-height/gap, so density = spacer count between rows."""
    spacers: list[dict] = []
    out: list[dict] = []
    n = 0
    for c in components:
        if c.get("id") == "col" and c.get("component") == "Column":
            densed: list[str] = []
            for i, kid in enumerate(c.get("children", [])):
                if i:
                    for _ in range(gap):
                        n += 1
                        sid = f"dsp_{n}"
                        spacers.append(_spacer(sid))
                        densed.append(sid)
                densed.append(kid)
            c = {**c, "children": densed}
        out.append(c)
    return out + spacers


def _msgs(surface_id: str, components: list[dict], data_model: dict | None,
          theme: str | None = None, density_gap: int = 0) -> list[dict]:
    if density_gap:
        components = _apply_density(components, density_gap)
    create = {"surfaceId": surface_id, "catalogId": CATALOG_BASIC, "sendDataModel": False}
    if theme:  # a hex like "#e8590c" — brands primary buttons / active borders / slider tracks.
        # Only primaryColor is honored on the basic catalog. Undocumented theme keys
        # (backgroundColor/surfaceColor/secondaryColor) were probed and GE ignored them
        # (2026-09-01) — card/page background stays white; that needs the Material catalog.
        create["theme"] = {"primaryColor": theme}
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


def _spacer(comp_id: str) -> dict:
    """A blank line used to fake vertical padding/gap.

    Basic-catalog components have no `padding`/`gap` property, so the only way to
    loosen tight layouts is (a) `justify: spaceBetween/Around/Evenly` on Row/Column,
    or (b) inject empty Text lines between children. This is (b) — a body Text holding
    a non-breaking space so the renderer gives it a full line's height.
    """
    return _text(comp_id, " ", variant="body")


def _align(booking: dict) -> str:
    """The user's chosen layout alignment (Design preference), applied to every step's
    root Column cross-axis. Falls back to 'stretch' (justified/full-width)."""
    a = (booking or {}).get("align")
    return a if a in data.ALIGN_VALUES else "stretch"


def _density(booking: dict) -> int:
    """The user's chosen text density → number of spacer lines between rows (0 default)."""
    return data.DENSITY_GAP.get((booking or {}).get("density"), 0)


def _spaced(children: list[str], comps_out: list[dict], prefix: str) -> list[str]:
    """Interleave a `_spacer` between each id in `children` (loosens vertical rhythm)."""
    out: list[str] = []
    for i, cid in enumerate(children):
        if i:
            sp = f"{prefix}_sp{i}"
            comps_out.append(_spacer(sp))
            out.append(sp)
        out.append(cid)
    return out


# ── Step 0: Theme — the first interaction; gates the rest of the flow ─────────

def theme_step(booking: dict) -> list[dict]:
    """First screen for any question: pick a colour theme, then Apply → Preferences.

    Kept separate from Preferences so theme selection is the mandatory first step
    (confirmed in GE: theme.primaryColor repaints buttons/borders/sliders).
    """
    sid = _surface("theme")
    children = ["title", "sub", "theme", "align", "density", "apply"]
    components = [
        _card("root", "col"),
        _col("col", children, align=_align(booking)),
        _text("title", "Design preference", variant="h4"),
        _text("sub", "Pick a colour, a layout, and a text density — they'll apply across the whole concierge.",
              variant="body"),
        _choice("theme", "/theme_sel", data.THEMES, label="Colour theme",
                variant="mutuallyExclusive", display="chips"),
        _choice("align", "/align_sel", data.ALIGNMENTS, label="Layout alignment",
                variant="mutuallyExclusive", display="chips"),
        _choice("density", "/density_sel", data.DENSITIES, label="Text density",
                variant="mutuallyExclusive", display="chips"),
    ]
    components += _button("apply", "Apply", "set_theme",
                          {"theme": {"path": "/theme_sel"}, "align": {"path": "/align_sel"},
                           "density": {"path": "/density_sel"}},
                          variant="primary")
    data_model = {"theme_sel": booking.get("theme_sel", []), "align_sel": booking.get("align_sel", []),
                  "density_sel": booking.get("density_sel", [])}
    return _msgs(sid, components, data_model, theme=booking.get("theme"), density_gap=_density(booking))


# ── Step 1: Preferences ──────────────────────────────────────────────────────

def preferences_step(booking: dict) -> list[dict]:
    sid = _surface("prefs")
    children = [
        "title", "cuisine", "dietary", "budget", "rating",
        "f_outdoor", "f_open", "when", "find",
    ]
    components = [
        _card("root", "col"),
        _col("col", children, align=_align(booking)),  # Design-preference alignment
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
    return _msgs(sid, components, data_model, theme=booking.get("theme"), density_gap=_density(booking))


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
        return _msgs(sid, [_card("root", "col"), _col("col", children, align=_align(booking))] + components, None, theme=booking.get("theme"), density_gap=_density(booking))

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
    return _msgs(sid, [_card("root", "col"), _col("col", children, align=_align(booking))] + components, None, theme=booking.get("theme"), density_gap=_density(booking))


# ── Step 3: Detail — Tabs (Overview w/ photo · Menu · Reviews+modal · Location) ─

def detail_step(booking: dict) -> list[dict]:
    sid = _surface("detail")
    r = data.get(booking.get("restaurant_id") or "")
    if not r:
        comps = [_card("root", "col"), _col("col", ["oops", "back"], align=_align(booking)),
                 _text("oops", "That restaurant is no longer available.", variant="body")]
        comps += _button("back", "← Back to results", "back_to_results", variant="borderless")
        return _msgs(sid, comps, None, theme=booking.get("theme"), density_gap=_density(booking))

    components = [
        _card("root", "col"),
        _col("col", ["title", "tabs", "actions"], align=_align(booking)),
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

    # Menu tab — a 2-column table (Dish | Price). Basic catalog has no Table, so each
    # row is a Row with justify:spaceBetween (name left, price right — confirmed to align).
    menu_children = ["menu_hdr", "menu_hdiv"]
    components += [
        _row("menu_hdr", ["menu_hd", "menu_hp"], justify="spaceBetween"),
        _text("menu_hd", "Dish", variant="caption"),
        _text("menu_hp", "Price", variant="caption"),
        _divider("menu_hdiv"),
    ]
    for i, dish in enumerate(r["menu"]):
        rid, nid, pid = f"mrow_{i}", f"mname_{i}", f"mprice_{i}"
        menu_children.append(rid)
        components += [
            _row(rid, [nid, pid], justify="spaceBetween"),
            _text(nid, dish["name"], variant="body"),
            _text(pid, f"${dish['price']:.2f}", variant="body"),
        ]
    components.append(_col("t_menu", menu_children))

    # Reviews tab — quotes + a Modal listing the review sources
    rev_ids = [f"rev_{i}" for i in range(len(r["reviews"]))]
    components.append(_col("t_rev", rev_ids + ["rev_modal"]))
    for i, rev in enumerate(r["reviews"]):
        components.append(_text(f"rev_{i}", f"“{rev['text']}”", variant="body"))
    # Modal content: header + review sources, spacers between each (basic catalog has
    # no padding/gap — spacer Texts are the only way to loosen the "very tight" spacing).
    src_ids = [f"revsrc_{i}" for i in range(len(r["reviews"]))]
    modal_comps: list[dict] = []
    modal_children = _spaced(["rev_hdr"] + src_ids, modal_comps, "revm")
    components += [
        _modal("rev_modal", "rev_entry", "rev_card"),
        _text("rev_entry", "📄 View review sources", variant="body"),
        _card("rev_card", "rev_content"),
        _col("rev_content", modal_children),
        _text("rev_hdr", "Review sources", variant="h5"),
    ]
    for i, rev in enumerate(r["reviews"]):
        # variant "body" (not caption): markdown bold only renders in body Text in GE v0.9.
        components.append(_text(f"revsrc_{i}", f"**{rev['id']}** — {rev['text']}", variant="body"))
    components += modal_comps

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
    return _msgs(sid, components, None, theme=booking.get("theme"), density_gap=_density(booking))


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
    return _msgs(sid, [_card("root", "col"), _col("col", children, align=_align(booking))] + components, data_model, theme=booking.get("theme"), density_gap=_density(booking))


# ── Step 5: Confirmation ─────────────────────────────────────────────────────

def confirmation_step(booking: dict) -> list[dict]:
    sid = _surface("confirm")
    # Render each receipt line as its own Text with spacers between — separate
    # components get real vertical rhythm, unlike one \n\n-joined Text (looks cramped).
    lines = _confirmation_lines(booking)
    line_ids = [f"cl_{i}" for i in range(len(lines))]
    line_comps = [_text(f"cl_{i}", ln, variant="body") for i, ln in enumerate(lines)]
    spaced = _spaced(line_ids, line_comps, "cl")
    components = [
        _card("root", "col"),
        _col("col", ["title", "div"] + spaced + ["new"], align=_align(booking)),
        _text("title", "Reservation confirmed ✅", variant="h4"),
        _divider("div"),
    ] + line_comps
    components += _button("new", "Start a new search", "new_search", variant="borderless")
    return _msgs(sid, components, None, theme=booking.get("theme"), density_gap=_density(booking))


def _confirmation_lines(booking: dict) -> list[str]:
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
    return lines


def confirmation_summary(booking: dict) -> str:
    return "\n\n".join(_confirmation_lines(booking))


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
        parts = []
        tsel = booking.get("theme_sel") or []
        if tsel:
            parts.append(tsel[0].title())
        asel = booking.get("align_sel") or []
        if asel:
            labels = {a["value"]: a["label"] for a in data.ALIGNMENTS}
            parts.append(labels.get(asel[0], asel[0]))
        dsel = booking.get("density_sel") or []
        if dsel:
            parts.append(dsel[0].title())
        return "Design · " + " · ".join(parts) if parts else None
    return _ACTION_LABELS.get(name)

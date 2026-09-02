"""Component-reference branch of the v0.9 concierge.

Triggered by "show me the components used" (typed) — lists every v0.9 component the
flow uses; tapping one shows it in isolation. Same idea as the v0.8 A2UI_advanced
gallery, ported to v0.9. Reuses the concierge's v0.9 builder helpers.
"""
from . import data
from .concierge import (
    _align, _button, _card, _checkbox, _choice, _col, _datetime, _density, _divider,
    _image, _modal, _msgs, _row, _slider, _surface, _tabs, _text, _textfield,
)

# (key, label) — components the concierge flow actually uses.
COMPONENTS = [
    ("slider", "Slider"),
    ("dropdown", "ChoicePicker (chips)"),
    ("checkbox", "Checkboxes"),
    ("datetime", "Date & time picker"),
    ("textfield", "Text field"),
    ("table", "Table / rows"),
    ("tabs", "Tabs"),
    ("modal", "Modal"),
    ("image", "Image"),
    ("buttons", "Buttons & divider"),
]
_LABELS = {k: l for k, l in COMPONENTS}


def gallery_menu_step(booking: dict) -> list[dict]:
    sid = _surface("gallery")
    btn_ids = [f"c_{k}" for k, _ in COMPONENTS]
    children = ["title", "sub"] + btn_ids + ["div", "exit"]
    comps = [
        _card("root", "col"),
        _col("col", children, align=_align(booking)),
        _text("title", "Components in this concierge", variant="h4"),
        _text("sub", "Every A2UI v0.9 component the flow uses — tap one to see it on its own.", variant="body"),
    ]
    for k, label in COMPONENTS:
        comps += _button(f"c_{k}", label, "show_component", {"component": k}, variant="borderless")
    comps.append(_divider("div"))
    comps += _button("exit", "← Back to booking", "exit_gallery", variant="primary")
    return _msgs(sid, comps, None, theme=booking.get("theme"), density_gap=_density(booking))


def component_demo_step(key: str, booking: dict) -> list[dict]:
    sid = _surface("comp")
    body_children, body, data_model = _DEMOS.get(key, _demo_unknown)()
    children = ["title", "div"] + body_children + ["nav"]
    comps = [
        _card("root", "col"),
        _col("col", children, align=_align(booking)),
        _text("title", _LABELS.get(key, key), variant="h4"),
        _divider("div"),
    ] + body
    comps.append(_row("nav", ["back", "exit"], justify="spaceBetween"))
    comps += _button("back", "← All components", "back_to_gallery", variant="borderless")
    comps += _button("exit", "Back to booking", "exit_gallery", variant="borderless")
    return _msgs(sid, comps, data_model, theme=booking.get("theme"), density_gap=_density(booking))


# ── isolated demos: (children_ids, components, data_model) ────────────────────

def _demo_slider():
    return (["cap", "s"], [
        _text("cap", "Drag to choose a value (0–10):", variant="body"),
        _slider("s", "/v", 0, 10, label="Value")], {"v": 5})


def _demo_dropdown():
    return (["cap", "d"], [
        _text("cap", "Select one or more (filterable chips):", variant="body"),
        _choice("d", "/sel", data.CUISINES, label="Options", filterable=True)], {"sel": []})


def _demo_checkbox():
    return (["c1", "c2", "c3"], [
        _checkbox("c1", "/c1", "Outdoor seating"),
        _checkbox("c2", "/c2", "Open now"),
        _checkbox("c3", "/c3", "Large groups")], {"c1": False, "c2": True, "c3": False})


def _demo_datetime():
    return (["cap", "dt"], [
        _text("cap", "Pick a date and time:", variant="body"),
        _datetime("dt", "/dt", label="When")], {"dt": ""})


def _demo_textfield():
    return (["cap", "tf"], [
        _text("cap", "Type into the field:", variant="body"),
        _textfield("tf", "/tf", label="Your name")], {"tf": ""})


def _demo_table():
    ids, comps = [], []
    for i, r in enumerate(data.RESTAURANTS[:3]):
        rid = f"tr_{i}"
        ids.append(rid)
        comps += [
            _row(rid, [f"tn_{i}", f"tp_{i}"], justify="spaceBetween"),
            _text(f"tn_{i}", f"**{r['name']}**", variant="body"),
            _text(f"tp_{i}", f"${r['avg_price']} · ★{r['rating']}", variant="body")]
    return (ids, comps, None)


def _demo_tabs():
    return (["tb"], [
        _tabs("tb", [("First", "tab1"), ("Second", "tab2")]),
        _text("tab1", "Content of the first tab.", variant="body"),
        _text("tab2", "Content of the second tab.", variant="body")], None)


def _demo_modal():
    return (["cap", "m"], [
        _text("cap", "Tap to open an overlay:", variant="body"),
        _modal("m", "m_entry", "m_card"),
        _text("m_entry", "📄 Open modal", variant="body"),
        _card("m_card", "m_body"),
        _text("m_body", "This is modal content — like the review sources in the flow.", variant="body")], None)


def _demo_image():
    return (["cap", "img"], [
        _text("cap", "An external image (v0.9 renders these):", variant="body"),
        _image("img", data.RESTAURANTS[0]["image"], variant="mediumFeature")], None)


def _demo_buttons():
    ids = ["cap", "brow", "bd", "bdt"]
    comps = [
        _text("cap", "Primary vs borderless, then a divider:", variant="body"),
        _row("brow", ["bp", "bs"], justify="spaceBetween")]
    comps += _button("bp", "Primary", "noop", variant="primary")
    comps += _button("bs", "Borderless", "noop", variant="borderless")
    comps += [_divider("bd"), _text("bdt", "↑ that line is a Divider.", variant="body")]
    return (ids, comps, None)


def _demo_unknown():
    return (["u"], [_text("u", "Unknown component.", variant="body")], None)


_DEMOS = {
    "slider": _demo_slider, "dropdown": _demo_dropdown, "checkbox": _demo_checkbox,
    "datetime": _demo_datetime, "textfield": _demo_textfield, "table": _demo_table,
    "tabs": _demo_tabs, "modal": _demo_modal, "image": _demo_image, "buttons": _demo_buttons,
}

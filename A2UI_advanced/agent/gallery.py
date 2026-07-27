"""Component-reference branch of the Concierge.

A gallery view (triggered by the "show me the components used" starter prompt)
that lists every A2UI component the booking flow uses; tapping one shows it on
its own. Lets clients see both the use case AND the individual components.

Reuses the concierge's builder helpers so the isolated demos match the flow.
"""
from . import data
from .concierge import (
    _button,
    _checkbox,
    _choice,
    _divider,
    _icon,
    _messages,
    _root,
    _surface,
    _text,
)

# (key, label, icon) — the components the concierge flow actually uses.
COMPONENTS = [
    ("slider", "Slider", "tune"),
    ("dropdown", "Dropdown (MultipleChoice)", "checklist"),
    ("checkbox", "Checkboxes", "check_box"),
    ("datetime", "Date & time picker", "event"),
    ("textfield", "Text field", "edit"),
    ("table", "Table / list", "table_rows"),
    ("tabs", "Tabs", "tab"),
    ("modal", "Modal", "open_in_new"),
    ("icons", "Icons", "star"),
    ("buttons", "Buttons & divider", "smart_button"),
]
_LABELS = {k: label for k, label, _ in COMPONENTS}


def gallery_menu_step() -> list[dict]:
    """The gallery menu — one button per component + an exit back to booking."""
    sid = _surface("gallery")
    btn_ids = [f"c_{k}" for k, _, _ in COMPONENTS]
    children = ["title", "sub"] + btn_ids + ["div", "exit"]
    comps = _root(children) + [
        _text("title", "Components in this concierge", usage_hint="h3"),
        _text("sub", "Every A2UI component the booking flow uses — tap one to see it on its own.", usage_hint="caption"),
    ]
    for k, label, _icon_name in COMPONENTS:
        comps += _button(
            f"c_{k}", label, "show_component",
            [{"key": "component", "value": {"literalString": k}}], primary=False,
        )
    comps.append(_divider("div"))
    comps += _button("exit", "← Back to booking", "exit_gallery", [], primary=True)
    return _messages(sid, comps, {})


def component_demo_step(key: str) -> list[dict]:
    """Render one component in isolation, with back/exit navigation."""
    sid = _surface("comp")
    body_children, body_comps, data_model = _DEMOS.get(key, _demo_unknown)()
    children = ["title", "div"] + body_children + ["nav"]
    comps = _root(children) + [
        _text("title", _LABELS.get(key, key), usage_hint="h3"),
        _divider("div"),
    ] + body_comps
    comps.append(
        {"id": "nav", "component": {"Row": {"alignment": "center", "distribution": "spaceBetween", "children": {"explicitList": ["back", "exit"]}}}}
    )
    comps += _button("back", "← All components", "back_to_gallery", [], primary=False)
    comps += _button("exit", "Back to booking", "exit_gallery", [], primary=False)
    return _messages(sid, comps, data_model)


# ── isolated component demos: each returns (children_ids, components, data_model)

def _demo_slider():
    return (["cap", "s"], [
        _text("cap", "Drag to choose a value (0–10):", usage_hint="caption"),
        {"id": "s", "component": {"Slider": {"value": {"path": "/v"}, "minValue": 0, "maxValue": 10}}},
    ], {"v": 5})


def _demo_dropdown():
    return (["cap", "d"], [
        _text("cap", "Select one or more options:", usage_hint="caption"),
        _choice("d", "/sel", data.CUISINES, 4),
    ], {"sel": []})


def _demo_checkbox():
    return (["c1", "c2", "c3"], [
        _checkbox("c1", "Outdoor seating", "/c1"),
        _checkbox("c2", "Open now", "/c2"),
        _checkbox("c3", "Seats a large group", "/c3"),
    ], {"c1": False, "c2": True, "c3": False})


def _demo_datetime():
    return (["cap", "dt"], [
        _text("cap", "Pick a date and time:", usage_hint="caption"),
        {"id": "dt", "component": {"DateTimeInput": {"value": {"path": "/dt"}, "enableDate": True, "enableTime": True}}},
    ], {"dt": ""})


def _demo_textfield():
    return (["cap", "tf"], [
        _text("cap", "Type into the field:", usage_hint="caption"),
        {"id": "tf", "component": {"TextField": {"label": {"literalString": "Your name"}, "text": {"path": "/tf"}}}},
    ], {"tf": ""})


def _demo_table():
    ids, comps = [], []
    for i, r in enumerate(data.RESTAURANTS[:3]):
        rid = f"tr_{i}"
        ids.append(rid)
        comps += [
            {"id": rid, "component": {"Row": {"alignment": "center", "distribution": "spaceBetween", "children": {"explicitList": [f"tn_{i}", f"tp_{i}"]}}}},
            _text(f"tn_{i}", f"**{r['name']}**"),
            _text(f"tp_{i}", f"${r['avg_price']} · ★{r['rating']}", usage_hint="caption"),
        ]
    return (ids, comps, {})


def _demo_tabs():
    return (["tb"], [
        {"id": "tb", "component": {"Tabs": {"tabItems": [
            {"title": {"literalString": "First"}, "child": "tab1"},
            {"title": {"literalString": "Second"}, "child": "tab2"},
        ]}}},
        _text("tab1", "Content of the first tab."),
        _text("tab2", "Content of the second tab."),
    ], {})


def _demo_modal():
    return (["cap", "m"], [
        _text("cap", "Tap to open an overlay:", usage_hint="caption"),
        {"id": "m", "component": {"Modal": {"entryPointChild": "m_entry", "contentChild": "m_card"}}},
        _text("m_entry", "📄 **Open modal**"),
        {"id": "m_card", "component": {"Card": {"child": "m_body"}}},
        _text("m_body", "This is modal content — used for the review sources in the flow."),
    ], {})


def _demo_icons():
    ids, comps = [], []
    for i, name in enumerate(["restaurant", "restaurant_menu", "star", "place", "event", "check_circle", "search"]):
        rid = f"ir_{i}"
        ids.append(rid)
        comps += [
            {"id": rid, "component": {"Row": {"alignment": "center", "distribution": "start", "children": {"explicitList": [f"ic_{i}", f"il_{i}"]}}}},
            _icon(f"ic_{i}", name),
            _text(f"il_{i}", name, usage_hint="caption"),
        ]
    return (ids, comps, {})


def _demo_buttons():
    ids = ["cap", "brow", "bd", "bd_txt"]
    comps = [
        _text("cap", "Primary vs secondary buttons, then a divider:", usage_hint="caption"),
        {"id": "brow", "component": {"Row": {"alignment": "center", "distribution": "spaceBetween", "children": {"explicitList": ["bp", "bs"]}}}},
    ]
    comps += _button("bp", "Primary", "noop", [], primary=True)
    comps += _button("bs", "Secondary", "noop", [], primary=False)
    comps += [_divider("bd"), _text("bd_txt", "↑ that line is a Divider.", usage_hint="caption")]
    return (ids, comps, {})


def _demo_unknown():
    return (["u"], [_text("u", "Unknown component.")], {})


_DEMOS = {
    "slider": _demo_slider,
    "dropdown": _demo_dropdown,
    "checkbox": _demo_checkbox,
    "datetime": _demo_datetime,
    "textfield": _demo_textfield,
    "table": _demo_table,
    "tabs": _demo_tabs,
    "modal": _demo_modal,
    "icons": _demo_icons,
    "buttons": _demo_buttons,
}

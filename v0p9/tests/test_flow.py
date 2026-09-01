"""Offline tests for the v0.9 concierge — no LLM/network/GCP.

Confirms the v0.9 payload shapes, the state machine, v0.9 event parsing, and the
callback dispatch. Whether GE renders it is answered by deploying.

Run from v0p9/:  ..\.venv\Scripts\python -m pytest tests/ -v
"""
import json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.a2a.converters.part_converter import convert_genai_part_to_a2a_part
from google.genai import types as genai_types

from agent import concierge, data, gallery
from agent.a2ui import to_genai_part
from agent.agent import DEFAULT_BOOKING, _append_step, _extract_action, advance


def _roundtrip_ok(msgs):
    return len(msgs) >= 2 and all(convert_genai_part_to_a2a_part(to_genai_part(m)) for m in msgs)


def _components(msgs):
    return msgs[1]["updateComponents"]["components"]


# ── v0.9 payload shape ────────────────────────────────────────────────────────

class TestV09Shape:
    def test_preferences_is_v09_messages(self):
        msgs = concierge.preferences_step(DEFAULT_BOOKING)
        assert all(m.get("version") == "v0.9" for m in msgs)
        assert "createSurface" in msgs[0] and "updateComponents" in msgs[1] and "updateDataModel" in msgs[2]
        assert msgs[0]["createSurface"]["catalogId"].startswith("https://")
        assert _roundtrip_ok(msgs)

    def test_flat_discriminator(self):
        for c in _components(concierge.preferences_step(DEFAULT_BOOKING)):
            assert isinstance(c["component"], str)  # v0.9 flat, not nested wrapper

    def test_input_components_present(self):
        kinds = {c["component"] for c in _components(concierge.preferences_step(DEFAULT_BOOKING))}
        assert {"ChoicePicker", "Slider", "CheckBox", "DateTimeInput", "Button", "Card", "Column", "Text"} <= kinds

    def test_choicepicker_chips_and_binding(self):
        comps = {c["id"]: c for c in _components(concierge.preferences_step(DEFAULT_BOOKING))}
        cp = comps["cuisine"]
        assert cp["displayStyle"] == "chips"
        assert cp["value"] == {"path": "/cuisine"}
        assert cp["options"][0]["label"] and cp["options"][0]["value"]

    def test_button_variant_and_event(self):
        comps = {c["id"]: c for c in _components(concierge.preferences_step(DEFAULT_BOOKING))}
        find = comps["find"]
        assert find["variant"] == "primary"
        assert find["action"]["event"]["name"] == "find_tables"
        # context carries bindings that GE resolves at click time
        assert find["action"]["event"]["context"]["cuisine"] == {"path": "/cuisine"}
        assert comps[find["child"]]["component"] == "Text"  # label is a Text

    def test_datamodel_seeded_flat(self):
        dm = concierge.preferences_step(DEFAULT_BOOKING)[2]["updateDataModel"]["value"]
        assert "cuisine" in dm and "budget" in dm
        assert all("/" not in k for k in dm)  # flat single-segment keys


# ── state machine ────────────────────────────────────────────────────────────

class TestAdvance:
    def test_find_tables_to_results(self):
        act = {"name": "find_tables", "context": {
            "cuisine": ["italian"], "dietary": [], "budget": 40, "min_rating": 4,
            "outdoor": True, "open_now": False, "when": "2026-08-01 19:00"}}
        step, b = advance({"step": "preferences"}, act)
        assert step == "results"
        assert b["cuisine"] == ["italian"] and b["budget"] == 40 and b["outdoor"] is True

    def test_edit_preferences_back(self):
        step, _ = advance({"step": "results"}, {"name": "edit_preferences", "context": {}})
        assert step == "preferences"

    def test_default_step(self):
        assert advance({}, None)[0] == "theme"

    def test_set_theme_advances_to_preferences(self):
        step, _ = advance({"step": "theme", "booking": dict(DEFAULT_BOOKING)},
                          {"name": "set_theme", "context": {"theme": ["forest"]}})
        assert step == "preferences"


# ── v0.9 incoming event parsing ───────────────────────────────────────────────

class TestExtractAction:
    def test_parses_v09_action(self):
        content = genai_types.Content(
            parts=[genai_types.Part(text=json.dumps({"action": {"name": "find_tables", "context": {"budget": 50}}}))],
            role="user")
        a = _extract_action(content)
        assert a and a["name"] == "find_tables" and a["context"]["budget"] == 50

    def test_none_on_plain_text(self):
        content = genai_types.Content(parts=[genai_types.Part(text="hello")], role="user")
        assert _extract_action(content) is None


# ── callback dispatch ─────────────────────────────────────────────────────────

def _ctx(state, action):
    ctx = MagicMock()
    ctx.state = state
    if action is not None:
        ctx.user_content = genai_types.Content(
            parts=[genai_types.Part(text=json.dumps({"action": action}))], role="user")
    else:
        ctx.user_content = None
    return ctx


def _resp():
    r = MagicMock()
    r.partial = False
    r.content = genai_types.Content(parts=[genai_types.Part(text="hi")], role="model")
    return r


def _a2ui(resp):
    out = []
    for p in resp.content.parts:
        if not p.inline_data:
            continue
        a = convert_genai_part_to_a2a_part(p)
        if a and "application/json+a2ui" in str(a.root.metadata.values()):
            out.append(a.root.data)
    return out


class TestCallback:
    def test_first_turn_renders_theme(self):
        state = {}
        resp = _resp()
        _append_step(_ctx(state, None), resp)
        assert state["step"] == "theme"
        assert any("createSurface" in m for m in _a2ui(resp))
        assert "design" in resp.content.parts[0].text.lower()

    def test_apply_theme_advances_to_preferences(self):
        state = {"step": "theme", "booking": dict(DEFAULT_BOOKING)}
        resp = _resp()
        _append_step(_ctx(state, {"name": "set_theme", "context": {"theme": ["forest"]}}), resp)
        assert state["step"] == "preferences"
        assert state["booking"]["theme"] == "#2f9e44"
        # preferences surface is themed
        create = next(m["createSurface"] for m in _a2ui(resp) if "createSurface" in m)
        assert create["theme"]["primaryColor"] == "#2f9e44"

    def test_find_tables_advances_to_results(self):
        state = {"step": "preferences", "booking": dict(DEFAULT_BOOKING)}
        resp = _resp()
        _append_step(_ctx(state, {"name": "find_tables", "context": {
            "cuisine": ["italian"], "dietary": [], "budget": 100, "min_rating": 0,
            "outdoor": False, "open_now": False, "when": ""}}), resp)
        assert state["step"] == "results"
        assert state["booking"]["cuisine"] == ["italian"]
        # results now shows photo cards + Select buttons
        ids = [c["id"] for m in _a2ui(resp) if "updateComponents" in m
               for c in m["updateComponents"]["components"]]
        assert any(i.startswith("pick_") for i in ids)


BOOKED = {**DEFAULT_BOOKING, "cuisine": ["italian"], "restaurant_id": "bella-italia",
          "res_name": "Sam", "res_contact": "sam@x.com", "res_when": "2026-08-01 19:00", "party_size": 4}


class TestFullSteps:
    def _comps(self, msgs):
        return msgs[1]["updateComponents"]["components"]

    def test_results_has_photo_cards_and_select(self):
        msgs = concierge.results_step({**DEFAULT_BOOKING, "budget": 100})
        assert _roundtrip_ok(msgs)
        kinds = {c["component"] for c in self._comps(msgs)}
        assert "Image" in kinds
        assert any(c["id"].startswith("pick_") for c in self._comps(msgs))

    def test_detail_has_tabs_image_modal(self):
        msgs = concierge.detail_step(BOOKED)
        assert _roundtrip_ok(msgs)
        kinds = {c["component"] for c in self._comps(msgs)}
        assert {"Tabs", "Image", "Modal"} <= kinds
        tabs = next(c for c in self._comps(msgs) if c["component"] == "Tabs")
        assert [t["title"] for t in tabs["tabs"]] == ["Overview", "Menu", "Reviews", "Location"]

    def test_reservation_form_flat_datamodel(self):
        msgs = concierge.reservation_step(BOOKED)
        assert _roundtrip_ok(msgs)
        kinds = {c["component"] for c in self._comps(msgs)}
        assert {"TextField", "Slider", "DateTimeInput"} <= kinds
        dm = msgs[2]["updateDataModel"]["value"]
        assert all("/" not in k for k in dm)

    def test_confirmation_summary(self):
        s = concierge.confirmation_summary(BOOKED)
        assert "Bella Italia" in s and "Party of 4" in s


class TestFullAdvance:
    def test_select_to_detail(self):
        step, b = advance({"step": "results"}, {"name": "select_restaurant",
                          "context": {"restaurant_id": "sakura-house"}})
        assert step == "detail" and b["restaurant_id"] == "sakura-house"

    def test_confirm_valid_to_confirmation(self):
        act = {"name": "confirm_reservation", "context": {
            "name": "Sam", "contact": "sam@x.com", "party_size": 3, "when": "2026-08-02 20:00"}}
        step, b = advance({"step": "reservation", "booking": dict(BOOKED)}, act)
        assert step == "confirmation" and b["res_name"] == "Sam" and b["_error"] is None

    def test_confirm_invalid_returns_error(self):
        act = {"name": "confirm_reservation", "context": {
            "name": "", "contact": "", "party_size": 2, "when": ""}}
        step, b = advance({"step": "reservation", "booking": dict(DEFAULT_BOOKING)}, act)
        assert step == "reservation" and b["_error"]

    def test_new_search_resets(self):
        step, b = advance({"step": "confirmation", "booking": dict(BOOKED)},
                          {"name": "new_search", "context": {}})
        assert step == "preferences" and b["restaurant_id"] is None


class TestThemeAndExtras:
    def _comps(self, msgs):
        return msgs[1]["updateComponents"]["components"]

    def test_theme_step_has_picker_and_apply(self):
        comps = {c["id"]: c for c in self._comps(concierge.theme_step(DEFAULT_BOOKING))}
        assert comps["theme"]["component"] == "ChoicePicker"
        assert comps["theme"]["variant"] == "mutuallyExclusive"
        assert comps["apply"]["action"]["event"]["name"] == "set_theme"

    def test_design_step_has_alignment_picker(self):
        comps = {c["id"]: c for c in self._comps(concierge.theme_step(DEFAULT_BOOKING))}
        assert comps["align"]["component"] == "ChoicePicker"
        ev = comps["apply"]["action"]["event"]["context"]
        assert ev["theme"] == {"path": "/theme_sel"} and ev["align"] == {"path": "/align_sel"}

    def test_set_theme_stores_alignment(self):
        step, b = advance({"step": "theme", "booking": dict(DEFAULT_BOOKING)},
                          {"name": "set_theme", "context": {"theme": ["ocean"], "align": ["center"]}})
        assert step == "preferences" and b["align"] == "center"

    def test_alignment_applied_to_every_step_root_col(self):
        b = {**DEFAULT_BOOKING, "align": "center", "restaurant_id": "bella-italia"}
        for msgs in (concierge.preferences_step(b), concierge.results_step({**b, "budget": 100}),
                     concierge.detail_step(b), concierge.reservation_step(b),
                     concierge.confirmation_step(b)):
            col = next(c for c in self._comps(msgs) if c["id"] == "col")
            assert col["align"] == "center"

    def test_preferences_has_no_theme_picker(self):
        comps = {c["id"]: c for c in self._comps(concierge.preferences_step(DEFAULT_BOOKING))}
        assert "theme" not in comps  # theme moved to its own first step
        assert comps["cuisine"].get("filterable") is True

    def test_theme_applied_to_createSurface(self):
        msgs = concierge.preferences_step({**DEFAULT_BOOKING, "theme": "#e8590c"})
        assert msgs[0]["createSurface"]["theme"]["primaryColor"] == "#e8590c"

    def test_no_theme_key_when_unset(self):
        msgs = concierge.preferences_step(DEFAULT_BOOKING)
        assert "theme" not in msgs[0]["createSurface"]

    def test_set_theme_maps_name_to_color(self):
        step, b = advance({"step": "preferences", "booking": dict(DEFAULT_BOOKING)},
                          {"name": "set_theme", "context": {"theme": ["sunset"]}})
        assert step == "preferences" and b["theme"] == "#e8590c"

    def test_detail_location_has_map_link(self):
        msgs = concierge.detail_step({**DEFAULT_BOOKING, "restaurant_id": "bella-italia"})
        assert "google.com/maps" in str(self._comps(msgs))


class TestGalleryBranch:
    def test_typed_message_opens_gallery(self):
        state = {"step": "preferences", "booking": dict(DEFAULT_BOOKING)}
        resp = _resp()
        ctx = MagicMock()
        ctx.state = state
        ctx.user_content = genai_types.Content(
            parts=[genai_types.Part(text="show me all the components used")], role="user")
        _append_step(ctx, resp)
        assert state["step"] == "gallery"

    def test_show_component_renders_slider(self):
        state = {"step": "gallery", "booking": dict(DEFAULT_BOOKING)}
        resp = _resp()
        _append_step(_ctx(state, {"name": "show_component", "context": {"component": "slider"}}), resp)
        assert state["step"] == "component" and state["booking"]["demo_component"] == "slider"
        kinds = {c["component"] for m in _a2ui(resp) if "updateComponents" in m
                 for c in m["updateComponents"]["components"]}
        assert "Slider" in kinds

    def test_menu_lists_all_components(self):
        msgs = gallery.gallery_menu_step(DEFAULT_BOOKING)
        ids = [c["id"] for c in msgs[1]["updateComponents"]["components"]]
        for k, _ in gallery.COMPONENTS:
            assert f"c_{k}" in ids

    @pytest.mark.parametrize("key,expected", [
        ("slider", "Slider"), ("dropdown", "ChoicePicker"), ("checkbox", "CheckBox"),
        ("datetime", "DateTimeInput"), ("textfield", "TextField"), ("tabs", "Tabs"),
        ("modal", "Modal"), ("image", "Image")])
    def test_each_demo_has_its_component(self, key, expected):
        msgs = gallery.component_demo_step(key, DEFAULT_BOOKING)
        kinds = {c["component"] for c in msgs[1]["updateComponents"]["components"]}
        assert expected in kinds

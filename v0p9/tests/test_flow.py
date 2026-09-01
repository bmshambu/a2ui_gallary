"""Offline tests for the v0.9 concierge — no LLM/network/GCP.

Confirms the v0.9 payload shapes, the state machine, v0.9 event parsing, and the
callback dispatch. Whether GE renders it is answered by deploying.

Run from v0p9/:  ..\.venv\Scripts\python -m pytest tests/ -v
"""
import json
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.a2a.converters.part_converter import convert_genai_part_to_a2a_part
from google.genai import types as genai_types

from agent import concierge, data
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
        assert advance({}, None)[0] == "preferences"


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
    def test_first_turn_renders_preferences(self):
        state = {}
        resp = _resp()
        _append_step(_ctx(state, None), resp)
        assert state["step"] == "preferences"
        assert any("createSurface" in m for m in _a2ui(resp))
        assert "Concierge" in resp.content.parts[0].text

    def test_find_tables_advances_to_results(self):
        state = {"step": "preferences", "booking": dict(DEFAULT_BOOKING)}
        resp = _resp()
        _append_step(_ctx(state, {"name": "find_tables", "context": {
            "cuisine": ["italian"], "dietary": [], "budget": 100, "min_rating": 0,
            "outdoor": False, "open_now": False, "when": ""}}), resp)
        assert state["step"] == "results"
        assert state["booking"]["cuisine"] == ["italian"]
        assert "matched" in str(_a2ui(resp))

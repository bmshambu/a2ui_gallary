"""Offline tests for the Restaurant Concierge flow — no LLM, no network, no GCP.

Covers the pure state machine (advance), the data filter, each step's A2UI payload
round-tripping through ADK's converter, and the full after_model_callback dispatch.

Run from A2UI_advanced/:  ..\.venv\Scripts\python -m pytest tests/ -v
"""
import json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.a2a.converters.part_converter import convert_genai_part_to_a2a_part
from google.genai import types as genai_types

from agent import concierge, data
from agent.a2ui import to_genai_part
from agent.agent import DEFAULT_BOOKING, STEP_BUILDERS, _append_step, advance


# ── helpers ──────────────────────────────────────────────────────────────────

def _roundtrip_ok(messages) -> bool:
    if len(messages) != 3:
        return False
    for m in messages:
        a2a = convert_genai_part_to_a2a_part(to_genai_part(m))
        if not (a2a and a2a.root.metadata.get("mimeType") == "application/json+a2ui"):
            return False
    return True


def _ids(messages) -> list[str]:
    return [c["id"] for c in messages[0]["surfaceUpdate"]["components"]]


def _types(messages) -> list[str]:
    return [list(c["component"].keys())[0] for c in messages[0]["surfaceUpdate"]["components"]]


BOOKED = {
    **DEFAULT_BOOKING,
    "cuisine": ["italian"], "budget": 50, "when": "2026-08-01 19:30",
    "restaurant_id": "bella-italia", "res_name": "Alex", "party_size": 4,
}


# ── data filter ──────────────────────────────────────────────────────────────

class TestSearch:
    def test_no_filters_returns_all_sorted_by_rating(self):
        res = data.search([], [], 100)
        assert len(res) == len(data.RESTAURANTS)
        ratings = [r["rating"] for r in res]
        assert ratings == sorted(ratings, reverse=True)

    def test_cuisine_filter(self):
        res = data.search(["italian"], [], 100)
        assert res and all(r["cuisine"] == "italian" for r in res)

    def test_budget_filter(self):
        res = data.search([], [], 30)
        assert all(r["avg_price"] <= 30 for r in res)

    def test_dietary_filter_requires_all_tags(self):
        res = data.search([], ["vegan"], 100)
        assert all("vegan" in r["dietary"] for r in res)

    def test_impossible_combo_empty(self):
        assert data.search(["japanese"], ["vegan"], 100) == []


# ── state machine ────────────────────────────────────────────────────────────

class TestAdvance:
    def _action(self, name, context):
        return {"name": name, "context": context}

    def test_default_is_preferences(self):
        step, _ = advance({}, None)
        assert step == "preferences"

    def test_find_tables_to_results(self):
        act = self._action("find_tables", {
            "cuisine": ["italian"], "dietary": [], "budget": 40, "when": "2026-08-01 19:00",
        })
        step, booking = advance({"step": "preferences"}, act)
        assert step == "results"
        assert booking["cuisine"] == ["italian"] and booking["budget"] == 40

    def test_select_restaurant_to_detail(self):
        act = self._action("select_restaurant", {"restaurant_id": "sakura-house"})
        step, booking = advance({"step": "results"}, act)
        assert step == "detail" and booking["restaurant_id"] == "sakura-house"

    def test_start_reservation_and_confirm(self):
        step, _ = advance({"step": "detail"}, self._action("start_reservation", {}))
        assert step == "reservation"
        act = self._action("confirm_reservation", {
            "name": "Sam", "contact": "sam@x.com", "party_size": 3, "requests": "window",
            "when": "2026-08-02 20:00",
        })
        step, booking = advance({"step": "reservation", "booking": BOOKED}, act)
        assert step == "confirmation"
        assert booking["res_name"] == "Sam" and booking["party_size"] == 3

    def test_new_search_resets(self):
        step, booking = advance({"step": "confirmation", "booking": BOOKED},
                                self._action("new_search", {}))
        assert step == "preferences" and booking == DEFAULT_BOOKING

    def test_context_as_list_normalized(self):
        act = self._action("select_restaurant",
                           [{"key": "restaurant_id", "value": "el-fuego"}])
        step, booking = advance({}, act)
        assert booking["restaurant_id"] == "el-fuego"


# ── step payloads ────────────────────────────────────────────────────────────

class TestStepPayloads:
    def test_preferences_combines_inputs(self):
        msgs = concierge.preferences_step(DEFAULT_BOOKING)
        assert _roundtrip_ok(msgs)
        types = _types(msgs)
        assert {"MultipleChoice", "Slider", "DateTimeInput", "Button"} <= set(types)
        # two dropdowns (cuisine + dietary)
        assert types.count("MultipleChoice") == 2

    def test_preferences_flat_datamodel(self):
        dm = concierge.preferences_step(DEFAULT_BOOKING)[1]["dataModelUpdate"]["contents"]
        assert set(dm) == {"cuisine", "dietary", "budget", "when"}  # all single-segment

    def test_results_lists_matches_with_select_buttons(self):
        booking = {**DEFAULT_BOOKING, "cuisine": ["italian"], "budget": 100}
        msgs = concierge.results_step(booking)
        assert _roundtrip_ok(msgs)
        assert any(i.startswith("pick_") for i in _ids(msgs))

    def test_results_empty_shows_adjust(self):
        booking = {**DEFAULT_BOOKING, "cuisine": ["japanese"], "dietary": ["vegan"]}
        msgs = concierge.results_step(booking)
        assert _roundtrip_ok(msgs)
        assert "empty" in _ids(msgs)

    def test_detail_has_tabs_and_actions(self):
        msgs = concierge.detail_step(BOOKED)
        assert _roundtrip_ok(msgs)
        assert "Tabs" in _types(msgs)
        assert "reserve" in _ids(msgs) and "back" in _ids(msgs)

    def test_reservation_form_and_flat_datamodel(self):
        msgs = concierge.reservation_step(BOOKED)
        assert _roundtrip_ok(msgs)
        assert {"TextField", "Slider", "DateTimeInput"} <= set(_types(msgs))
        dm = msgs[1]["dataModelUpdate"]["contents"]
        assert all("/" not in k for k in dm)  # flat keys only

    def test_confirmation_summary(self):
        msgs = concierge.confirmation_step(BOOKED)
        assert _roundtrip_ok(msgs)
        summary = concierge.confirmation_summary(BOOKED)
        assert "Bella Italia" in summary and "Party of 4" in summary


# ── full callback dispatch ───────────────────────────────────────────────────

def _make_resp(text: str) -> MagicMock:
    part = genai_types.Part(text=text)
    resp = MagicMock()
    resp.partial = False
    resp.content = genai_types.Content(parts=[part], role="model")
    return resp


def _make_ctx(state: dict, action: dict | None) -> MagicMock:
    ctx = MagicMock()
    ctx.state = state
    if action is None:
        ctx.user_content = None
    else:
        ua = json.dumps({"userAction": action})
        ctx.user_content = genai_types.Content(
            parts=[genai_types.Part(text=ua)], role="user"
        )
    return ctx


def _a2ui_parts(resp) -> list[dict]:
    out = []
    for p in resp.content.parts:
        if not p.inline_data:
            continue
        a2a = convert_genai_part_to_a2a_part(p)
        if a2a and "application/json+a2ui" in str(a2a.root.metadata.values()):
            out.append(a2a.root.data)
    return out


class TestCallback:
    def test_first_turn_renders_preferences(self):
        state = {}
        resp = _make_resp("hi")
        _append_step(_make_ctx(state, None), resp)
        assert state["step"] == "preferences"
        assert any("surfaceUpdate" in m for m in _a2ui_parts(resp))
        # text replaced with step copy
        assert "Concierge" in resp.content.parts[0].text

    def test_find_tables_advances_and_renders_results(self):
        state = {"step": "preferences", "booking": dict(DEFAULT_BOOKING)}
        action = {"name": "find_tables", "context": {
            "cuisine": ["italian"], "dietary": [], "budget": 100, "when": "2026-08-01 19:00",
        }}
        resp = _make_resp("ok")
        _append_step(_make_ctx(state, action), resp)
        assert state["step"] == "results"
        assert state["booking"]["cuisine"] == ["italian"]
        ids = [c["id"] for m in _a2ui_parts(resp) if "surfaceUpdate" in m
               for c in m["surfaceUpdate"]["components"]]
        assert any(i.startswith("pick_") for i in ids)

    def test_one_surface_per_turn(self):
        state = {"step": "detail", "booking": BOOKED}
        resp = _make_resp("ok")
        _append_step(_make_ctx(state, {"name": "start_reservation", "context": {}}), resp)
        surface_updates = [m for m in _a2ui_parts(resp) if "surfaceUpdate" in m]
        assert len(surface_updates) == 1  # exactly one step surface

    def test_click_is_echoed_as_quote(self):
        state = {"step": "results", "booking": dict(DEFAULT_BOOKING)}
        action = {"name": "select_restaurant", "context": {"restaurant_id": "sakura-house"}}
        resp = _make_resp("ok")
        _append_step(_make_ctx(state, action), resp)
        text = resp.content.parts[0].text
        assert text.startswith("> Selected Sakura House")

    def test_first_turn_has_no_echo(self):
        state = {}
        resp = _make_resp("hi")
        _append_step(_make_ctx(state, None), resp)
        assert not resp.content.parts[0].text.startswith(">")

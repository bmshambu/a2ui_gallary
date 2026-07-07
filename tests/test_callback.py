"""Unit tests for the gallery agent callback — no LLM, no GCP, no network.

Tests the full pipeline that runs on every model response:
  LLM text with [[COMPONENT:...]] marker
    → marker stripped from output text
    → correct gallery component DataParts appended
    → nav button card always appended
    → surfaceIds are fresh per call
    → form submit userAction triggers server-side validation

Run: .venv\\Scripts\\python -m pytest tests/ -v
"""
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, ".")

from google.adk.a2a.converters.part_converter import convert_genai_part_to_a2a_part
from google.genai import types as genai_types

from agent.a2ui import A2UI_MIME_TYPE, to_genai_part
from agent.agent import (
    _MARKER_RE,
    _append_gallery_parts,
    _is_a2ui_component_part,
    _strip_a2ui_from_history,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_response(text: str) -> MagicMock:
    """Fake final LlmResponse with a single text part."""
    part = genai_types.Part(text=text)
    content = genai_types.Content(parts=[part], role="model")
    resp = MagicMock()
    resp.partial = False
    resp.content = content
    return resp


def _make_ctx() -> MagicMock:
    """Fake CallbackContext with no user action (non-button turns)."""
    ctx = MagicMock()
    ctx.user_content = None            # not set by a plugin
    ctx.session.events = []            # empty history → no userAction
    return ctx


def _a2ui_parts(resp: MagicMock) -> list[dict]:
    """Extract parsed A2UI messages from response DataParts."""
    parts = []
    for p in resp.content.parts:
        if not p.inline_data:
            continue
        a2a_part = convert_genai_part_to_a2a_part(p)
        if a2a_part and "application/json+a2ui" in str(a2a_part.root.metadata.values()):
            parts.append(a2a_part.root.data)
    return parts


def _surface_ids(a2ui_parts: list[dict]) -> list[str]:
    return [
        next(iter(m.values()))["surfaceId"]
        for m in a2ui_parts
        if next(iter(m)) in ("surfaceUpdate", "dataModelUpdate", "beginRendering")
    ]


# ── marker stripping ──────────────────────────────────────────────────────────

class TestMarkerStripping:
    def test_marker_removed_from_text(self):
        resp = _make_response("Here is the form.\n[[COMPONENT:form]]")
        _append_gallery_parts(_make_ctx(), resp)
        assert "[[COMPONENT:" not in resp.content.parts[0].text

    def test_clean_text_preserved(self):
        resp = _make_response("Here is the form.\n[[COMPONENT:form]]")
        _append_gallery_parts(_make_ctx(), resp)
        assert "Here is the form." in resp.content.parts[0].text

    def test_no_marker_still_emits_nav(self):
        resp = _make_response("Hello! [[COMPONENT:followups]]")
        _append_gallery_parts(_make_ctx(), resp)
        a2ui = _a2ui_parts(resp)
        assert any("surfaceUpdate" in m for m in a2ui), "nav card missing"

    @pytest.mark.parametrize("marker", ["form", "table", "references", "followups"])
    def test_all_valid_markers_parsed(self, marker):
        m = _MARKER_RE.search(f"Text\n[[COMPONENT:{marker}]]")
        assert m is not None and m.group(1) == marker

    def test_echoed_tagged_json_scrubbed(self):
        resp = _make_response(
            'Here you go.\n<a2a_datapart_json>{"kind":"data",'
            '"data":{"surfaceUpdate":{}}}</a2a_datapart_json>\n[[COMPONENT:followups]]'
        )
        _append_gallery_parts(_make_ctx(), resp)
        assert "a2a_datapart_json" not in resp.content.parts[0].text
        assert "surfaceUpdate" not in resp.content.parts[0].text
        assert "Here you go." in resp.content.parts[0].text

    def test_echoed_raw_surfaceupdate_scrubbed(self):
        resp = _make_response(
            'Sure.\n{"surfaceUpdate": {"surfaceId": "x", "components": []}}'
            "\n[[COMPONENT:followups]]"
        )
        _append_gallery_parts(_make_ctx(), resp)
        assert "surfaceUpdate" not in resp.content.parts[0].text
        assert "Sure." in resp.content.parts[0].text


# ── history scrubbing (before_model_callback) ──────────────────────────────────

class TestHistoryScrub:
    def _content_with(self, *parts) -> genai_types.Content:
        return genai_types.Content(parts=list(parts), role="model")

    def test_component_blob_detected(self):
        part = to_genai_part({"surfaceUpdate": {"surfaceId": "s", "components": []}})
        assert _is_a2ui_component_part(part) is True

    def test_useraction_blob_kept(self):
        import json as _json
        ua = {"userAction": {"name": "x", "context": {"q": "hi"}}}
        part = genai_types.Part(text=_json.dumps(ua))
        # userAction text has no component keys → not stripped
        assert _is_a2ui_component_part(part) is False

    def test_plain_text_kept(self):
        part = genai_types.Part(text="Just a normal sentence.")
        assert _is_a2ui_component_part(part) is False

    def test_strip_removes_component_parts_from_history(self):
        text_part = genai_types.Part(text="Show me the form")
        comp_part = to_genai_part(
            {"surfaceUpdate": {"surfaceId": "s", "components": []}}
        )
        llm_request = MagicMock()
        llm_request.contents = [self._content_with(text_part, comp_part)]
        _strip_a2ui_from_history(_make_ctx(), llm_request)
        remaining = llm_request.contents[0].parts
        assert text_part in remaining
        assert comp_part not in remaining


# ── component routing ─────────────────────────────────────────────────────────

class TestComponentRouting:
    def _run(self, marker: str) -> list[dict]:
        resp = _make_response(f"Intro.\n[[COMPONENT:{marker}]]")
        _append_gallery_parts(_make_ctx(), resp)
        return _a2ui_parts(resp)

    def test_form_marker_emits_form(self):
        parts = self._run("form")
        surface_updates = [p for p in parts if "surfaceUpdate" in p]
        assert len(surface_updates) == 1
        all_ids = [c["id"] for c in surface_updates[0]["surfaceUpdate"]["components"]]
        assert "terms_checkbox" in all_ids

    def test_table_marker_emits_table(self):
        parts = self._run("table")
        surface_updates = [p for p in parts if "surfaceUpdate" in p]
        all_ids = [
            c["id"]
            for su in surface_updates
            for c in su["surfaceUpdate"]["components"]
        ]
        assert "header_row" in all_ids
        assert "header_divider" in all_ids

    def test_references_marker_emits_modal(self):
        parts = self._run("references")
        surface_updates = [p for p in parts if "surfaceUpdate" in p]
        comps = [c for su in surface_updates for c in su["surfaceUpdate"]["components"]]
        types = [list(c["component"].keys())[0] for c in comps]
        # one separate modal per reference (3 demo refs), not one combined
        assert types.count("Modal") == 3
        blob = str(comps)
        assert "Reference Information" in blob
        assert "FLIGHT-OP-01" in blob  # ref id
        assert "Austrian Airlines" in blob  # the text chunk
        # each modal's entry point is its own chip
        modal_entries = [
            c["component"]["Modal"]["entryPointChild"]
            for c in comps if "Modal" in c["component"]
        ]
        assert modal_entries == ["chip_0", "chip_1", "chip_2"]

    def test_references_attaches_grounding_metadata(self):
        resp = _make_response("Intro.\n[[COMPONENT:references]]")
        _append_gallery_parts(_make_ctx(), resp)
        md = resp.grounding_metadata
        assert md is not None and md.grounding_chunks
        # one retrieved_context chunk per curated reference: uri + title + text
        assert len(md.grounding_chunks) == 10
        first = md.grounding_chunks[0].retrieved_context
        assert first.uri and first.title
        assert first.text, "source snippet text missing"

    def test_references_grounding_has_supports(self):
        resp = _make_response("Here are the docs.\n[[COMPONENT:references]]")
        _append_gallery_parts(_make_ctx(), resp)
        md = resp.grounding_metadata
        assert md.grounding_supports, "supports missing — GE needs them to cite"
        sup = md.grounding_supports[0]
        assert sup.grounding_chunk_indices == list(range(10))
        # byte offsets must lie within the reply text
        reply = resp.content.parts[0].text
        assert 0 <= sup.segment.start_index < sup.segment.end_index
        assert sup.segment.end_index == len(reply.rstrip().encode("utf-8"))

    def test_non_references_has_no_grounding_metadata(self):
        resp = _make_response("Here's the form.\n[[COMPONENT:form]]")
        resp.grounding_metadata = None  # baseline
        _append_gallery_parts(_make_ctx(), resp)
        assert resp.grounding_metadata is None

    def test_followups_marker_emits_only_nav(self):
        # followups has no COMPONENT_BUILDERS entry — only the nav card
        parts = self._run("followups")
        surface_updates = [p for p in parts if "surfaceUpdate" in p]
        # Should be exactly 1 surfaceUpdate (just the nav card)
        assert len(surface_updates) == 1

    def test_three_message_sequence_per_component(self):
        # Option B: component only, no nav card appended — exactly 3 DataParts
        parts = self._run("form")
        assert len(parts) == 3

    def test_nav_card_on_followups_only(self):
        # Nav card appears only for [[COMPONENT:followups]], not for other components
        followup_parts = self._run("followups")
        btn_ids = [
            c["id"]
            for su in followup_parts if "surfaceUpdate" in su
            for c in su["surfaceUpdate"]["components"]
            if "btn_" in c["id"] and "_label" not in c["id"]
        ]
        assert len(btn_ids) >= 4, "nav buttons missing for [[COMPONENT:followups]]"

        for marker in ["form", "table", "references"]:
            parts = self._run(marker)
            assert len(parts) == 3, f"[[COMPONENT:{marker}]] should emit exactly 3 DataParts"


# ── surfaceId freshness ───────────────────────────────────────────────────────

class TestSurfaceIdFreshness:
    def test_different_calls_get_different_surface_ids(self):
        def run():
            resp = _make_response("X\n[[COMPONENT:form]]")
            _append_gallery_parts(_make_ctx(), resp)
            return _a2ui_parts(resp)

        ids_a = set(_surface_ids(run()))
        ids_b = set(_surface_ids(run()))
        assert ids_a.isdisjoint(ids_b), "surfaceIds reused across calls"

    def test_all_three_messages_share_same_surface_id(self):
        resp = _make_response("X\n[[COMPONENT:form]]")
        _append_gallery_parts(_make_ctx(), resp)
        parts = _a2ui_parts(resp)
        # Group by sequence of 3
        for i in range(0, len(parts), 3):
            trio = parts[i:i+3]
            if len(trio) < 3:
                break
            ids_in_trio = {next(iter(m.values()))["surfaceId"] for m in trio}
            assert len(ids_in_trio) == 1, f"surfaceId inconsistent in trio {i//3}"




# ── DataPart mimeType ─────────────────────────────────────────────────────────

class TestDataPartMimeType:
    def test_all_parts_have_a2ui_mimetype(self):
        resp = _make_response("Test.\n[[COMPONENT:table]]")
        _append_gallery_parts(_make_ctx(), resp)
        a2ui = _a2ui_parts(resp)
        assert len(a2ui) == 3  # table only (Option B: no nav card with components)

    def test_text_part_not_converted_to_datapart(self):
        resp = _make_response("Hello.\n[[COMPONENT:followups]]")
        _append_gallery_parts(_make_ctx(), resp)
        text_parts = [p for p in resp.content.parts if p.text]
        assert len(text_parts) == 1
        assert "Hello." in text_parts[0].text


# ── form submit validation ────────────────────────────────────────────────────

import json


def _make_submit_ctx(ctx_data: dict) -> MagicMock:
    """Fake CallbackContext carrying a register_submitted userAction."""
    ua_json = json.dumps({"userAction": {
        "name": "register_submitted",
        "context": ctx_data,
    }})
    part = genai_types.Part(text=ua_json)
    content = genai_types.Content(parts=[part], role="user")
    ctx = MagicMock()
    ctx.user_content = content
    return ctx


class TestFormSubmitValidation:
    """Python-side validation replaces the LLM text on register_submitted."""

    def _submit(self, ctx_data: dict):
        resp = _make_response("Thank you for registering!\n[[COMPONENT:followups]]")
        ctx = _make_submit_ctx(ctx_data)
        _append_gallery_parts(ctx, resp)
        return resp

    def test_valid_submit_text_shows_confirmation(self):
        resp = self._submit({"email": "a@b.com", "phone": "", "zip": "12345", "agree": True})
        text = resp.content.parts[0].text
        assert "Registration received" in text
        assert "a@b.com" in text

    def test_valid_submit_emits_nav_only(self):
        resp = self._submit({"email": "a@b.com", "phone": "", "zip": "12345", "agree": True})
        parts = _a2ui_parts(resp)
        surface_updates = [p for p in parts if "surfaceUpdate" in p]
        assert len(surface_updates) == 1  # only nav card

    def test_missing_agree_reports_error(self):
        resp = self._submit({"email": "a@b.com", "phone": "", "zip": "12345", "agree": False})
        text = resp.content.parts[0].text
        assert "terms" in text.lower()

    def test_missing_contact_and_zip_reports_errors(self):
        resp = self._submit({"email": "", "phone": "", "zip": "", "agree": True})
        text = resp.content.parts[0].text
        assert "email" in text.lower() or "phone" in text.lower()
        assert "zip" in text.lower()

    def test_agree_as_string_true_accepted(self):
        # GE may send boolean context values as strings
        resp = self._submit({"email": "x@y.com", "phone": "", "zip": "99999", "agree": "true"})
        text = resp.content.parts[0].text
        assert "Registration received" in text

    def test_invalid_submit_no_form_re_emitted(self):
        resp = self._submit({"email": "", "phone": "", "zip": "", "agree": False})
        all_ids = [
            c["id"]
            for su in _a2ui_parts(resp) if "surfaceUpdate" in su
            for c in su["surfaceUpdate"]["components"]
        ]
        assert "email_field" not in all_ids


# ── question echo (follow-up click readability) ────────────────────────────────

def _make_click_ctx(question: str) -> MagicMock:
    """Fake CallbackContext carrying a followup_question userAction."""
    ua_json = json.dumps({"userAction": {
        "name": "followup_question",
        "context": {"question": question},
    }})
    part = genai_types.Part(text=ua_json)
    content = genai_types.Content(parts=[part], role="user")
    ctx = MagicMock()
    ctx.user_content = content
    return ctx


class TestQuestionEcho:
    def test_question_prepended_as_quote(self):
        resp = _make_response("Here's the form.\n[[COMPONENT:form]]")
        _append_gallery_parts(
            _make_click_ctx("Show me the registration form component"), resp
        )
        text = resp.content.parts[0].text
        assert text.startswith("> Show me the registration form component")
        assert "Here's the form." in text

    def test_no_echo_without_question(self):
        resp = _make_response("Hello!\n[[COMPONENT:followups]]")
        _append_gallery_parts(_make_ctx(), resp)
        assert not resp.content.parts[0].text.startswith(">")

    def test_click_routes_by_button_map_not_llm_marker(self):
        # LLM emits the WRONG marker (followups), but the click question is the
        # table button → the table must render, not the nav card.
        resp = _make_response("Here's the data.\n[[COMPONENT:followups]]")
        _append_gallery_parts(
            _make_click_ctx("Show me the financial data table component"), resp
        )
        all_ids = [
            c["id"]
            for su in _a2ui_parts(resp) if "surfaceUpdate" in su
            for c in su["surfaceUpdate"]["components"]
        ]
        assert "header_row" in all_ids  # table rendered
        # nav buttons should NOT be present
        assert not any(i.startswith("btn_") for i in all_ids)

    def test_form_submit_not_quoted(self):
        # register_submitted goes through validation, not the quote path
        ua_json = json.dumps({"userAction": {
            "name": "register_submitted",
            "context": {"email": "a@b.com", "phone": "", "zip": "12345", "agree": True},
        }})
        part = genai_types.Part(text=ua_json)
        ctx = MagicMock()
        ctx.user_content = genai_types.Content(parts=[part], role="user")
        resp = _make_response("ack\n[[COMPONENT:followups]]")
        _append_gallery_parts(ctx, resp)
        assert resp.content.parts[0].text.startswith("**Registration received")

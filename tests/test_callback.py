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
import json
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")

from google.adk.a2a.converters.part_converter import convert_genai_part_to_a2a_part
from google.genai import types as genai_types

from agent.a2ui import A2UI_MIME_TYPE, _TAG_END, _TAG_START
from agent.agent import _MARKER_RE, _append_gallery_parts


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_response(text: str) -> MagicMock:
    """Fake final LlmResponse with a single text part."""
    part = genai_types.Part(text=text)
    content = genai_types.Content(parts=[part], role="model")
    resp = MagicMock()
    resp.partial = False
    resp.content = content
    return resp


def _make_ctx(user_action: dict | None = None) -> MagicMock:
    """Fake CallbackContext, optionally carrying a userAction blob."""
    ctx = MagicMock()
    if user_action is None:
        ctx.user_content = None
    else:
        blob = json.dumps({"data": {"userAction": user_action}})
        part = genai_types.Part(
            inline_data=genai_types.Blob(
                mime_type="text/plain",
                data=_TAG_START + blob.encode() + _TAG_END,
            )
        )
        content = genai_types.Content(parts=[part], role="user")
        ctx.user_content = content
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


# ── component routing ─────────────────────────────────────────────────────────

class TestComponentRouting:
    def _run(self, marker: str) -> list[dict]:
        resp = _make_response(f"Intro.\n[[COMPONENT:{marker}]]")
        _append_gallery_parts(_make_ctx(), resp)
        return _a2ui_parts(resp)

    def test_form_marker_emits_form(self):
        parts = self._run("form")
        # form surfaceUpdate + nav surfaceUpdate = 2 surfaceUpdates minimum
        surface_updates = [p for p in parts if "surfaceUpdate" in p]
        assert len(surface_updates) >= 2
        # form has a CheckBox (terms) — find it
        all_ids = [
            c["id"]
            for su in surface_updates
            for c in su["surfaceUpdate"]["components"]
        ]
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
        all_component_types = [
            list(c["component"].keys())[0]
            for su in surface_updates
            for c in su["surfaceUpdate"]["components"]
        ]
        assert "Modal" in all_component_types

    def test_followups_marker_emits_only_nav(self):
        # followups has no COMPONENT_BUILDERS entry — only the nav card
        parts = self._run("followups")
        surface_updates = [p for p in parts if "surfaceUpdate" in p]
        # Should be exactly 1 surfaceUpdate (just the nav card)
        assert len(surface_updates) == 1

    def test_three_message_sequence_per_component(self):
        # form (3) + nav (3) = 6 DataParts total
        parts = self._run("form")
        assert len(parts) == 6

    def test_nav_card_always_appended(self):
        for marker in ["form", "table", "references", "followups"]:
            parts = self._run(marker)
            btn_ids = [
                c["id"]
                for su in parts if "surfaceUpdate" in su
                for c in su["surfaceUpdate"]["components"]
                if "btn_" in c["id"] and "_label" not in c["id"]
            ]
            assert len(btn_ids) >= 4, f"nav buttons missing for [[COMPONENT:{marker}]]"


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


# ── click handling ────────────────────────────────────────────────────────────

class TestButtonClickHandling:
    def test_followup_click_without_component_rewrites_card(self):
        # Click on a followup button that routes to [[COMPONENT:followups]] (no
        # builder) — card rewrite IS emitted because total stays ≤ 6 DataParts.
        surface_id = f"followup-buttons-{uuid.uuid4().hex[:12]}"
        ua = {
            "name": "followup_question",
            "surfaceId": surface_id,
            "sourceComponentId": "btn_0",
            "timestamp": "2026-06-17T10:00:00Z",
            "context": {"question": "Show me the follow-up buttons component"},
        }
        resp = _make_response("> Show me the follow-up buttons component\nHere it is.\n[[COMPONENT:followups]]")
        _append_gallery_parts(_make_ctx(user_action=ua), resp)
        parts = _a2ui_parts(resp)

        rewrite = next(
            (p for p in parts if "surfaceUpdate" in p
             and p["surfaceUpdate"]["surfaceId"] == surface_id),
            None,
        )
        assert rewrite is not None, "clicked card not rewritten for followup-only click"
        comps = rewrite["surfaceUpdate"]["components"]
        assert len(comps) == 1
        assert "Text" in comps[0]["component"]

    def test_followup_click_with_component_skips_rewrite(self):
        # Click on a button that shows a component (table) — card rewrite is
        # SKIPPED to keep DataPart count at 6 (component 3 + nav 3), avoiding
        # the GE raw-JSON bleed caused by 7 DataParts in one response.
        surface_id = f"followup-buttons-{uuid.uuid4().hex[:12]}"
        ua = {
            "name": "followup_question",
            "surfaceId": surface_id,
            "sourceComponentId": "btn_1",
            "timestamp": "2026-06-17T10:00:00Z",
            "context": {"question": "Show me the financial data table component"},
        }
        resp = _make_response("> Show me the financial data table component\nHere it is.\n[[COMPONENT:table]]")
        _append_gallery_parts(_make_ctx(user_action=ua), resp)
        parts = _a2ui_parts(resp)

        # No rewrite DataPart targeting the old surfaceId
        rewrite = next(
            (p for p in parts if "surfaceUpdate" in p
             and p["surfaceUpdate"]["surfaceId"] == surface_id),
            None,
        )
        assert rewrite is None, "card rewrite must not fire when component follows (would exceed 6 DataParts)"
        # Still exactly 6 DataParts: table (3) + nav (3)
        assert len(parts) == 6

    def test_no_click_no_rewrite(self):
        resp = _make_response("Intro.\n[[COMPONENT:form]]")
        _append_gallery_parts(_make_ctx(user_action=None), resp)
        parts = _a2ui_parts(resp)
        all_ids = {next(iter(p.values()))["surfaceId"] for p in parts}
        assert all("reg-form" in sid or "followup-buttons" in sid for sid in all_ids)


# ── DataPart mimeType ─────────────────────────────────────────────────────────

class TestDataPartMimeType:
    def test_all_parts_have_a2ui_mimetype(self):
        resp = _make_response("Test.\n[[COMPONENT:table]]")
        _append_gallery_parts(_make_ctx(), resp)
        a2ui = _a2ui_parts(resp)
        assert len(a2ui) == 6  # table (3) + nav (3)

    def test_text_part_not_converted_to_datapart(self):
        resp = _make_response("Hello.\n[[COMPONENT:followups]]")
        _append_gallery_parts(_make_ctx(), resp)
        text_parts = [p for p in resp.content.parts if p.text]
        assert len(text_parts) == 1
        assert "Hello." in text_parts[0].text


# ── form submit validation ────────────────────────────────────────────────────

class TestFormSubmitValidation:
    """The agent validates register_submitted userAction server-side.
    These tests verify the callback routes correctly (uses followups marker)
    and does NOT emit a form component on submit.
    """

    def _submit(self, ctx_data: dict) -> list[dict]:
        ua = {"name": "register_submitted", "surfaceId": "reg-form-abc", "context": ctx_data}
        # Simulate the LLM output for a valid/invalid submit (no component marker
        # for submit — it uses [[COMPONENT:followups]])
        resp = _make_response("Thank you for registering!\n[[COMPONENT:followups]]")
        _append_gallery_parts(_make_ctx(user_action=ua), resp)
        return _a2ui_parts(resp)

    def test_valid_submit_emits_nav_only(self):
        parts = self._submit({"email": "a@b.com", "phone": "", "zip": "12345", "agree": True})
        surface_updates = [p for p in parts if "surfaceUpdate" in p]
        # Only nav card (no form re-emitted)
        assert len(surface_updates) == 1

    def test_invalid_submit_no_form_re_emitted(self):
        # Even on invalid submit, the agent replies with text + nav — no form component
        parts = self._submit({"email": "", "phone": "", "zip": "", "agree": False})
        all_ids = [
            c["id"]
            for su in parts if "surfaceUpdate" in su
            for c in su["surfaceUpdate"]["components"]
        ]
        assert "email_field" not in all_ids

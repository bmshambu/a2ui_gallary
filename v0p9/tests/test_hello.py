"""Offline checks for the v0.9 'Hello Material' probe — no LLM/network/GCP.

These only confirm the payload shape and that it survives the ADK A2A converter
(same transport as v0.8). Whether GE actually RENDERS v0.9 Material is answered by
deploying, not here.

Run from v0p9/:  ..\.venv\Scripts\python -m pytest tests/ -v
"""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.a2a.converters.part_converter import convert_genai_part_to_a2a_part
from google.genai import types as genai_types

from agent.a2ui import to_genai_part
from agent.agent import _append_surface, _is_a2ui_part, _strip_history
from agent.hello import CATALOG_MATERIAL, hello_material_messages


def test_message_sequence_is_v09_shape():
    msgs = hello_material_messages()
    # every message carries the v0.9 version marker (GE needs it to pick the renderer)
    assert all(m.get("version") == "v0.9" for m in msgs)
    assert "createSurface" in msgs[0]
    assert "updateComponents" in msgs[1]
    # v0.9 has no beginRendering
    assert not any("beginRendering" in m for m in msgs)
    cs = msgs[0]["createSurface"]
    assert cs["catalogId"] == CATALOG_MATERIAL
    assert cs["surfaceId"] == msgs[1]["updateComponents"]["surfaceId"]


def test_uses_material_components_and_styling():
    comps = hello_material_messages()[1]["updateComponents"]["components"]
    kinds = {c["component"] for c in comps}
    assert {"MaterialColumn", "MaterialCard", "MaterialText", "MaterialButton"} <= kinds
    buttons = [c for c in comps if c["component"] == "MaterialButton"]
    assert len(buttons) == 3
    # each button carries the styling that v0.8 could not: appearance + color
    for b in buttons:
        assert "label" in b and "appearance" in b and "color" in b
        assert b["action"]["event"]["name"] == "hello_clicked"
    assert {b["color"] for b in buttons} == {"primary", "accent", "warn"}


def test_flat_discriminator_shape():
    # v0.9 = flat {"id","component":"X",...}, NOT nested {"component":{"X":{}}}
    comps = hello_material_messages()[1]["updateComponents"]["components"]
    for c in comps:
        assert isinstance(c["component"], str)  # discriminator string, not a dict


def test_roundtrips_through_a2a_converter():
    # same transport as v0.8: each message wraps into an A2A DataPart w/ the a2ui mime
    for m in hello_material_messages():
        a2a = convert_genai_part_to_a2a_part(to_genai_part(m))
        assert a2a is not None
        assert a2a.root.metadata.get("mimeType") == "application/json+a2ui"


def test_callback_appends_surface_and_sets_text():
    part = genai_types.Part(text="hi")
    resp = MagicMock()
    resp.partial = False
    resp.content = genai_types.Content(parts=[part], role="model")
    _append_surface(MagicMock(), resp)
    # text replaced + two DataParts appended (createSurface + updateComponents)
    assert "Material" in resp.content.parts[0].text
    data_parts = [p for p in resp.content.parts if p.inline_data]
    assert len(data_parts) == 2


def test_history_scrub_removes_v09_blobs():
    good = genai_types.Part(text="show me the card")
    blob = to_genai_part({"createSurface": {"surfaceId": "s", "catalogId": "material"}})
    req = MagicMock()
    req.contents = [genai_types.Content(parts=[good, blob], role="model")]
    _strip_history(MagicMock(), req)
    assert good in req.contents[0].parts
    assert blob not in req.contents[0].parts
    assert _is_a2ui_part(blob) is True

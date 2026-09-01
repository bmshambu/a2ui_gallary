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
from agent.hello import CATALOG_BASIC, hello_v09_messages


def test_message_sequence_is_v09_shape():
    msgs = hello_v09_messages()
    # every message carries the v0.9 version marker (GE needs it to pick the renderer)
    assert all(m.get("version") == "v0.9" for m in msgs)
    assert "createSurface" in msgs[0]
    assert "updateComponents" in msgs[1]
    # v0.9 has no beginRendering
    assert not any("beginRendering" in m for m in msgs)
    cs = msgs[0]["createSurface"]
    assert cs["catalogId"] == CATALOG_BASIC and cs["catalogId"].startswith("https://")
    assert cs["surfaceId"] == msgs[1]["updateComponents"]["surfaceId"]


def test_basic_component_shapes():
    comps = hello_v09_messages()[1]["updateComponents"]["components"]
    by_id = {c["id"]: c for c in comps}
    # Card uses `child` (single); Column/Row use `children` (array)
    assert isinstance(by_id["card"]["child"], str)
    assert isinstance(by_id["root"]["children"], list)
    # Button uses `child` (a Text id — the label) + variant, NOT text/label
    buttons = [c for c in comps if c["component"] == "Button"]
    assert len(buttons) == 3
    for b in buttons:
        assert "child" in b and "text" not in b and "label" not in b
        assert b["variant"] in {"default", "primary", "borderless"}
        assert b["action"]["event"]["name"] == "hello_clicked"
        assert by_id[b["child"]]["component"] == "Text"  # label resolves to a Text


def test_flat_discriminator_shape():
    # v0.9 = flat {"id","component":"X",...}, NOT nested {"component":{"X":{}}}
    comps = hello_v09_messages()[1]["updateComponents"]["components"]
    for c in comps:
        assert isinstance(c["component"], str)


def test_includes_image_render_test():
    comps = hello_v09_messages()[1]["updateComponents"]["components"]
    imgs = [c for c in comps if c["component"] == "Image"]
    assert len(imgs) == 1
    img = imgs[0]
    assert img["url"].startswith("https://")
    assert img["fit"] == "cover" and img["variant"] == "largeFeature"


def test_roundtrips_through_a2a_converter():
    # same transport as v0.8: each message wraps into an A2A DataPart w/ the a2ui mime
    for m in hello_v09_messages():
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
    assert "v0.9" in resp.content.parts[0].text
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

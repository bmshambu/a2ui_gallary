"""Verify every gallery A2UI payload renders-worthy without any server.

Round-trips each builder's messages through ADK's part converter and checks
they come out as A2A DataParts with the a2ui mimeType, that component id
references all resolve, and that the v0.8 three-message sequence is intact.

Run: .venv\\Scripts\\python verify_payloads.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")  # emoji in payloads vs cp1252

from google.adk.a2a.converters.part_converter import convert_genai_part_to_a2a_part

from agent.a2ui import references_modal, to_genai_part
from agent.agent import GALLERY_REFERENCES, gallery_nav_messages
from agent.gallery import data_table_messages, registration_form_messages

SEQUENCE_KEYS = ["surfaceUpdate", "dataModelUpdate", "beginRendering"]


def check_ids_resolve(surface_update: dict) -> None:
    components = surface_update["components"]
    defined = {c["id"] for c in components}
    referenced = set()
    for c in components:
        (props,) = c["component"].values()
        for key in ("child", "entryPointChild", "contentChild"):
            if key in props:
                referenced.add(props[key])
        children = props.get("children", {})
        if isinstance(children, dict) and "explicitList" in children:
            referenced.update(children["explicitList"])
        button = c["component"].get("Button")
        if button:
            referenced.add(button["child"])
    missing = referenced - defined
    assert not missing, f"referenced but never defined: {missing}"
    assert "root" in defined, "no root component"


def check_builder(name: str, messages: list[dict]) -> None:
    assert [next(iter(m)) for m in messages] == SEQUENCE_KEYS, (
        f"{name}: wrong message sequence"
    )
    surface_ids = {next(iter(m.values()))["surfaceId"] for m in messages}
    assert len(surface_ids) == 1, f"{name}: inconsistent surfaceId"

    check_ids_resolve(messages[0]["surfaceUpdate"])

    for message in messages:
        part = convert_genai_part_to_a2a_part(to_genai_part(message))
        assert part is not None, f"{name}: converter returned None"
        metadata = part.root.metadata or {}
        mime = metadata.get("mimeType") or metadata.get(
            "adk_type"
        )  # key name varies by adk version; assert on the value below
        assert "application/json+a2ui" in str(metadata.values()), (
            f"{name}: missing a2ui mimeType, metadata={metadata}"
        )
        assert part.root.data == message, f"{name}: data mangled in round-trip"

    print(f"  ✅ {name}: {len(messages[0]['surfaceUpdate']['components'])} components, "
          f"surfaceId={surface_ids.pop()}")


def main() -> None:
    print("Round-tripping gallery payloads through ADK's A2A part converter:")
    check_builder("form", registration_form_messages())
    check_builder("table", data_table_messages())
    check_builder("references", references_modal(GALLERY_REFERENCES))
    check_builder("followup-nav", gallery_nav_messages())

    # Fresh surfaceId per call (GE keys cards by surfaceId)
    a = registration_form_messages()[0]["surfaceUpdate"]["surfaceId"]
    b = registration_form_messages()[0]["surfaceUpdate"]["surfaceId"]
    assert a != b, "surfaceId reused across calls"
    print("  ✅ fresh surfaceId per builder call")
    print("\nAll gallery payloads verified.")


if __name__ == "__main__":
    main()

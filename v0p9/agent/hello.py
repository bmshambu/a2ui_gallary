"""'Hello, Material' — the smallest A2UI v0.9 probe for Gemini Enterprise.

Goal of this probe (deploy it and look at GE chat):
  1. Does GE accept our v0.9 message format over the SAME A2A transport we used for
     v0.8 (the <a2a_datapart_json> wrapper, mimeType application/json+a2ui)?
  2. Does GE render the v0.9 **Material** catalog?
  3. Does Material styling actually show — button color/appearance and card elevation
     (the thing v0.8 could NOT do)?

If the three colored/elevated buttons render → all three are answered YES and we can
port the concierge. If nothing renders or it errors, the assumptions below are what to
adjust (each is annotated).

v0.9 format facts confirmed from the a2ui spec + GE docs:
  - Messages: createSurface → updateComponents (NO beginRendering in v0.9).
  - Flat discriminator: {"id": "x", "component": "MaterialButton", ...props}.
  - MaterialButton uses `label` (not `text`/`child`), plus `appearance` + `color`.
  - MaterialCard / MaterialColumn / MaterialRow use `children` (array of ids).
  - GE selects the catalog with catalogId "material" (per GE docs example).
"""
import uuid

# ASSUMPTION #1 (verify): GE takes the short id "material" for the Material catalog.
# If GE wants a full URL instead, this is the first thing to change.
CATALOG_MATERIAL = "material"


def hello_material_messages() -> list[dict]:
    surface_id = f"hello-{uuid.uuid4().hex[:12]}"
    return [
        # createSurface — declare the surface + which catalog to render with.
        # NOTE the "version": "v0.9" marker: GE's A2UI renderer defaults to v0.8
        # semantics (it looks for surfaceUpdate/beginRendering). Without this
        # marker GE doesn't recognize createSurface and renders NOTHING (attempt #1
        # showed text but no card). This sibling field routes it to the v0.9 renderer.
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": surface_id,
                "catalogId": CATALOG_MATERIAL,
                "sendDataModel": False,
            }
        },
        # updateComponents — the component tree (root is the component with id "root").
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": surface_id,
                "components": [
                    {"id": "root", "component": "MaterialColumn",
                     "children": ["card"], "align": "stretch"},

                    {"id": "card", "component": "MaterialCard",
                     "appearance": "raised", "children": ["inner"]},

                    {"id": "inner", "component": "MaterialColumn",
                     "children": ["title", "subtitle", "btnrow"], "align": "stretch"},

                    {"id": "title", "component": "MaterialText",
                     "text": "Hello, Material 👋", "variant": "h4"},
                    {"id": "subtitle", "component": "MaterialText",
                     "text": "If these buttons are colored and this card is elevated, "
                             "A2UI v0.9 Material renders in GE — styling that v0.8 could not do.",
                     "variant": "body"},

                    {"id": "btnrow", "component": "MaterialRow",
                     "children": ["b_filled", "b_tonal", "b_outlined"], "justify": "start"},

                    # three appearance × color combos — the actual styling test
                    {"id": "b_filled", "component": "MaterialButton",
                     "label": "Filled · primary", "appearance": "filled", "color": "primary",
                     "action": {"event": {"name": "hello_clicked", "context": {"which": "filled"}}}},
                    {"id": "b_tonal", "component": "MaterialButton",
                     "label": "Tonal · accent", "appearance": "tonal", "color": "accent",
                     "action": {"event": {"name": "hello_clicked", "context": {"which": "tonal"}}}},
                    {"id": "b_outlined", "component": "MaterialButton",
                     "label": "Outlined · warn", "appearance": "outlined", "color": "warn",
                     "action": {"event": {"name": "hello_clicked", "context": {"which": "outlined"}}}},
                ],
            }
        },
    ]

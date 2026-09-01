"""'Hello, v0.9' — the smallest A2UI v0.9 surface for GE, on the BASIC catalog.

Journey so far (full log in ../guidelines.md §7):
  - ✅ Transport: the v0.8 <a2a_datapart_json> wrapper (mimeType application/json+a2ui)
    carries v0.9 messages fine — DataParts show in the Agent Engine Playground.
  - ✅ Version marker: adding "version": "v0.9" made GE recognize v0.9 and try to render
    (before it, GE defaulted to v0.8, ignored createSurface, and showed only text).
  - ❌ catalogId "material" → GE error "Catalog not found: material". The Material catalog
    is GE-proprietary; its catalogId URL is not public. So this probe uses the PUBLIC
    **basic** catalog, whose catalogId GE accepts. Basic gives Button `variant`
    (default/primary/borderless) — real v0.9 rendering; full colour/elevation still needs
    the (unknown) Material catalogId.

Exact basic v0.9 component shapes (from the google/A2UI basic catalog schema):
  Column / Row : children[] + justify + align
  Card         : child (a SINGLE component id)
  Text         : text + variant (h1..h5 / caption / body)
  Button       : child (a Text id — the label!) + variant (default/primary/borderless) + action
"""
import uuid

# Confirmed catalogId GE accepts (equals the catalog's $id). VERIFY it renders.
CATALOG_BASIC = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"


def hello_v09_messages() -> list[dict]:
    sid = f"hello-{uuid.uuid4().hex[:12]}"
    return [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": sid,
                "catalogId": CATALOG_BASIC,
                "sendDataModel": False,
            },
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": sid,
                "components": [
                    {"id": "root", "component": "Column", "children": ["card"], "align": "stretch"},
                    {"id": "card", "component": "Card", "child": "inner"},
                    {"id": "inner", "component": "Column",
                     "children": ["title", "subtitle", "img", "img_note", "btnrow"], "align": "stretch"},

                    {"id": "title", "component": "Text",
                     "text": "Hello, A2UI v0.9 👋", "variant": "h4"},
                    {"id": "subtitle", "component": "Text",
                     "text": "If you can see this card and the three buttons below, "
                             "A2UI v0.9 renders natively in Gemini Enterprise.",
                     "variant": "body"},

                    # IMAGE TEST: v0.9 basic-catalog Image with an external (Google-hosted)
                    # URL. In v0.8, external images hard-500'd in GE. If this renders, v0.9
                    # lifted the block; if the card errors/blanks, images are still blocked.
                    {"id": "img", "component": "Image",
                     "url": "https://www.gstatic.com/webp/gallery/1.jpg",
                     "fit": "cover", "variant": "largeFeature",
                     "description": "v0.9 image render test"},
                    {"id": "img_note", "component": "Text",
                     "text": "↑ image test — visible = v0.9 renders images; missing/error = still blocked (like v0.8).",
                     "variant": "caption"},

                    {"id": "btnrow", "component": "Row",
                     "children": ["b1", "b2", "b3"], "justify": "start"},

                    # Button `child` points at a Text (the label). variant is the styling.
                    {"id": "b1", "component": "Button", "child": "b1l", "variant": "primary",
                     "action": {"event": {"name": "hello_clicked", "context": {"which": "primary"}}}},
                    {"id": "b1l", "component": "Text", "text": "Primary"},

                    {"id": "b2", "component": "Button", "child": "b2l", "variant": "borderless",
                     "action": {"event": {"name": "hello_clicked", "context": {"which": "borderless"}}}},
                    {"id": "b2l", "component": "Text", "text": "Borderless"},

                    {"id": "b3", "component": "Button", "child": "b3l", "variant": "default",
                     "action": {"event": {"name": "hello_clicked", "context": {"which": "default"}}}},
                    {"id": "b3l", "component": "Text", "text": "Default"},
                ],
            },
        },
    ]

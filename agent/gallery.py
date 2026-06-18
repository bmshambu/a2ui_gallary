"""A2UI v0.8 gallery components for Gemini Enterprise.

GE-renderable conversions of the A2UI Composer prototypes in the repo root
(a2ui-form.json, a2ui-table.json). The Composer format is NOT what GE
renders — GE needs the v0.8 wire format (components as {"TypeName": {...}}
objects, children as {"explicitList": [...]}, values as literalString/path).

Composer features with no v0.8/GE equivalent, and how each is handled here:
  - formatString/formatDate/formatCurrency function calls
        -> values are computed/formatted in Python and sent as literalString
           (or pre-formatted strings in the data model)
  - per-field `checks` with custom error messages
        -> TextField.validationRegexp carries the same regex; the custom
           message and the cross-field submit-enable rule move to the agent,
           which validates the userAction payload server-side
  - `weight` (proportional column widths)
        -> absent from the published v0.8 schema, but GE's component gallery
           reference documents it as a common property (flex-grow-like, in
           Row/Column). Set at the envelope level (sibling of "id"), same
           level as "id" per the GE docs' common-properties table. Rows keep
           distribution="spaceBetween" as a fallback in case the renderer
           ignores it.
  - `variant` -> `usageHint`
"""
import uuid
from datetime import datetime


def _surface(prefix: str) -> str:
    # Fresh surfaceId per call — GE keys cards by surfaceId, reuse would
    # silently update the first card instead of rendering a new one.
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _text(
    comp_id: str,
    text: str,
    usage_hint: str | None = None,
    weight: float | None = None,
) -> dict:
    props: dict = {"text": {"literalString": text}}
    if usage_hint:
        props["usageHint"] = usage_hint
    comp: dict = {"id": comp_id, "component": {"Text": props}}
    if weight is not None:
        comp["weight"] = weight
    return comp


# ── Registration form (from a2ui-form.json) ─────────────────────────────────

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_REGEX = r"^\+?[0-9]{10,15}$"
ZIP_REGEX = r"^[0-9]{5}$"

FORM_ACTION_NAME = "register_submitted"


def _text_field(comp_id: str, label: str, path: str, regex: str) -> dict:
    return {
        "id": comp_id,
        "component": {
            "TextField": {
                "label": {"literalString": label},
                "text": {"path": path},
                "validationRegexp": regex,
            }
        },
    }


def registration_form_messages() -> list[dict]:
    """Card > Column > [greeting, email, phone, zip, terms checkbox, submit].

    The submit button reports all field values via action.context paths; GE
    resolves them from the surface's data model at click time. The Composer
    prototype's conditional submit rule (agree AND (email OR phone) AND zip)
    is enforced by the agent on the resulting userAction, since v0.8 has no
    conditional component enablement.
    """
    surface_id = _surface("reg-form")
    greeting = datetime.now().strftime("Hello! Today is %A, %B %d.")

    components = [
        {"id": "root", "component": {"Card": {"child": "main_column"}}},
        {
            "id": "main_column",
            "component": {
                "Column": {
                    "alignment": "stretch",
                    "children": {
                        "explicitList": [
                            "welcome_text",
                            "email_field",
                            "phone_field",
                            "zip_field",
                            "terms_checkbox",
                            "submit_btn",
                        ]
                    },
                }
            },
        },
        _text("welcome_text", greeting, usage_hint="h3"),
        _text_field("email_field", "Email Address", "/formData/email", EMAIL_REGEX),
        _text_field("phone_field", "Phone Number", "/formData/phone", PHONE_REGEX),
        _text_field("zip_field", "Zip Code", "/formData/zip", ZIP_REGEX),
        {
            "id": "terms_checkbox",
            "component": {
                "CheckBox": {
                    "label": {
                        "literalString": "I agree to the terms and conditions"
                    },
                    "value": {"path": "/formData/agree"},
                }
            },
        },
        {
            "id": "submit_btn",
            "component": {
                "Button": {
                    "child": "submit_btn_label",
                    "primary": True,
                    "action": {
                        "name": FORM_ACTION_NAME,
                        "context": [
                            {"key": "email", "value": {"path": "/formData/email"}},
                            {"key": "phone", "value": {"path": "/formData/phone"}},
                            {"key": "zip", "value": {"path": "/formData/zip"}},
                            {"key": "agree", "value": {"path": "/formData/agree"}},
                        ],
                    },
                }
            },
        },
        _text("submit_btn_label", "Submit Registration"),
    ]

    return [
        {"surfaceUpdate": {"surfaceId": surface_id, "components": components}},
        {
            "dataModelUpdate": {
                "surfaceId": surface_id,
                "contents": {
                    "formData": {
                        "email": "",
                        "phone": "",
                        "zip": "",
                        "agree": False,
                    }
                },
            }
        },
        {"beginRendering": {"surfaceId": surface_id, "root": "root"}},
    ]


# ── Financial data grid (from a2ui-table.json) ──────────────────────────────

DEMO_ASSETS = [
    {"name": "Bitcoin", "symbol": "BTC", "price": 43500.25, "change": 1.2, "marketCap": 850_000_000_000},
    {"name": "Ethereum", "symbol": "ETH", "price": 2250.50, "change": -0.5, "marketCap": 270_000_000_000},
    {"name": "Solana", "symbol": "SOL", "price": 95.80, "change": 5.4, "marketCap": 40_000_000_000},
]


def _compact_usd(value: float) -> str:
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= threshold:
            return f"${value / threshold:,.1f}{suffix}"
    return f"${value:,.2f}"


def data_table_messages(assets: list[dict] | None = None) -> list[dict]:
    """Header row + one Row per asset, all expanded server-side.

    The Composer prototype bound a List to /assets with a row template;
    expanding rows explicitly avoids template data binding entirely and
    lets Python do the currency/percent formatting that v0.8's missing
    formatCurrency/formatString calls used to do.
    """
    assets = assets if assets is not None else DEMO_ASSETS
    surface_id = _surface("data-grid")

    # NOTE: `weight` is intentionally omitted. It is documented in GE's
    # component-gallery reference but NOT verified to render in GE chat; when
    # present on this (large) surface GE rejected the payload and bled raw
    # JSON into the conversation. Column widths rely on distribution instead.
    row_ids = [f"asset_row_{i}" for i in range(len(assets))]
    components = [
        {"id": "root", "component": {"Card": {"child": "main_column"}}},
        {
            "id": "main_column",
            "component": {
                "Column": {
                    "alignment": "stretch",
                    "children": {
                        "explicitList": ["header_row", "header_divider"] + row_ids
                    },
                }
            },
        },
        {
            "id": "header_row",
            "component": {
                "Row": {
                    "alignment": "center",
                    "distribution": "spaceBetween",
                    "children": {
                        "explicitList": [
                            "col_asset",
                            "col_price",
                            "col_change",
                            "col_market_cap",
                        ]
                    },
                }
            },
        },
        _text("col_asset", "Asset", usage_hint="caption"),
        _text("col_price", "Price", usage_hint="caption"),
        _text("col_change", "24h Change", usage_hint="caption"),
        _text("col_market_cap", "Market Cap", usage_hint="caption"),
        {"id": "header_divider", "component": {"Divider": {"axis": "horizontal"}}},
    ]

    for i, asset in enumerate(assets):
        change = asset["change"]
        # Arrows stand in for the green/red coloring the Composer preview had
        # (no color control in GE). Name + symbol merged into one markdown
        # Text to keep the payload small (large table surfaces bleed raw JSON).
        change_text = f"{'▲' if change >= 0 else '▼'} {change:+.1f}%"
        components += [
            {
                "id": f"asset_row_{i}",
                "component": {
                    "Row": {
                        "alignment": "center",
                        "distribution": "spaceBetween",
                        "children": {
                            "explicitList": [
                                f"asset_info_{i}",
                                f"asset_price_{i}",
                                f"asset_change_{i}",
                                f"asset_mcap_{i}",
                            ]
                        },
                    }
                },
            },
            _text(f"asset_info_{i}", f"**{asset['name']}** · {asset['symbol']}"),
            _text(f"asset_price_{i}", f"${asset['price']:,.2f}"),
            _text(f"asset_change_{i}", change_text),
            _text(f"asset_mcap_{i}", _compact_usd(asset["marketCap"])),
        ]

    return [
        {"surfaceUpdate": {"surfaceId": surface_id, "components": components}},
        {"dataModelUpdate": {"surfaceId": surface_id, "contents": {}}},
        {"beginRendering": {"surfaceId": surface_id, "root": "root"}},
    ]

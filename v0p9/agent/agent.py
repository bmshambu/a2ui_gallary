"""A2UI v0.9 Restaurant Concierge for Gemini Enterprise (basic catalog).

Port of the v0.8 A2UI_advanced concierge onto v0.9. Same stateful flow, but:
  - v0.9 messages (createSurface/updateComponents/updateDataModel, "version":"v0.9")
  - flat components, {"path":…} binding, ChoicePicker chips, Button variant styling
  - incoming clicks arrive as {"action": {"name", "context", …}} (v0.9), context bindings
    pre-resolved by GE — so no more raw-JSON parsing of typed values.

Step 1 (Preferences) is built; Results is a placeholder until the next port step. The
v0.8 build in ../A2UI_advanced stays as the baseline.
"""
import json
import re

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

from . import concierge
from .a2ui import to_genai_part

_TAG_START = b"<a2a_datapart_json>"
_TAG_END = b"</a2a_datapart_json>"

# A2UI message keys (v0.9 + v0.8) to strip from history so the model can't echo them.
_A2UI_KEYS = ("createSurface", "updateComponents", "updateDataModel", "deleteSurface",
              "surfaceUpdate", "dataModelUpdate", "beginRendering")
_ECHO_RE = re.compile(
    r"<a2a_datapart_json>.*?</a2a_datapart_json>"
    r'|\{\s*"(?:createSurface|updateComponents|updateDataModel)"\s*:.*',
    re.DOTALL,
)


# ── history scrub ────────────────────────────────────────────────────────────

def _is_a2ui_part(part) -> bool:
    blob = getattr(part, "inline_data", None)
    if blob and blob.data and blob.data.startswith(_TAG_START):
        try:
            d = json.loads(blob.data[len(_TAG_START):-len(_TAG_END)])
        except (ValueError, UnicodeDecodeError):
            return False
        inner = d.get("data", d)
        return isinstance(inner, dict) and any(k in inner for k in _A2UI_KEYS)
    if part.text and any(f'"{k}"' in part.text for k in _A2UI_KEYS):
        return True
    return False


def _strip_history(callback_context: CallbackContext, llm_request: LlmRequest):
    for cnt in llm_request.contents:
        if not cnt.parts:
            continue
        kept = [p for p in cnt.parts if not _is_a2ui_part(p)]
        if len(kept) != len(cnt.parts):
            cnt.parts = kept
    return None


def _current_user_content(callback_context):
    uc = getattr(callback_context, "user_content", None)
    if uc is not None:
        return uc
    try:
        for event in reversed(callback_context.session.events):
            if getattr(event, "author", None) == "user" and event.content:
                return event.content
    except Exception:
        pass
    return None


def _extract_action(content) -> dict | None:
    """Parse the v0.9 incoming click: {"action": {"name","context",…}}."""
    if not content or not getattr(content, "parts", None):
        return None
    for p in content.parts:
        data = None
        blob = getattr(p, "inline_data", None)
        if blob and blob.data and blob.data.startswith(_TAG_START):
            try:
                data = json.loads(blob.data[len(_TAG_START):-len(_TAG_END)])
            except (ValueError, UnicodeDecodeError):
                continue
        elif getattr(p, "text", None) and '"action"' in p.text:
            try:
                data = json.loads(p.text)
            except ValueError:
                continue
        if not data:
            continue
        inner = data.get("data", data)
        act = inner.get("action") if isinstance(inner, dict) else None
        if act:
            return act
    return None


# ── flow state machine ───────────────────────────────────────────────────────

DEFAULT_BOOKING = {
    "cuisine": [], "dietary": [], "budget": 50, "min_rating": 0,
    "outdoor": False, "open_now": False, "when": "", "restaurant_id": None,
}

STEP_BUILDERS = {
    "preferences": concierge.preferences_step,
    "results": concierge.results_step,
}

STEP_TEXT = {
    "preferences": "👋 Welcome to the Concierge (v0.9). Set your preferences and tap **Find tables**.",
    "results": "Here's what matched your search.",
}


def _as_list(v):
    return v if isinstance(v, list) else ([] if v in (None, "") else [v])


def _as_num(v, default):
    try:
        return v if isinstance(v, (int, float)) else float(v)
    except (TypeError, ValueError):
        return default


def _as_bool(v):
    return v is True or str(v).lower() == "true"


def advance(state, action) -> tuple[str, dict]:
    booking = dict(state.get("booking") or DEFAULT_BOOKING)
    step = state.get("step") or "preferences"
    if not action:
        return step, booking
    name = action.get("name")
    ctx = action.get("context") or {}
    if name == "find_tables":
        booking["cuisine"] = _as_list(ctx.get("cuisine"))
        booking["dietary"] = _as_list(ctx.get("dietary"))
        booking["budget"] = _as_num(ctx.get("budget"), 50)
        booking["min_rating"] = _as_num(ctx.get("min_rating"), 0)
        booking["outdoor"] = _as_bool(ctx.get("outdoor"))
        booking["open_now"] = _as_bool(ctx.get("open_now"))
        booking["when"] = str(ctx.get("when") or "")
        step = "results"
    elif name == "edit_preferences":
        step = "preferences"
    return step, booking


def _append_step(callback_context: CallbackContext, llm_response: LlmResponse):
    if llm_response.partial:
        return None
    content = llm_response.content
    if not content or not content.parts:
        return None
    has_text = any(p.text for p in content.parts if p.text)
    has_fc = any(p.function_call for p in content.parts if p.function_call)
    if not has_text or has_fc:
        return None

    for p in content.parts:
        if p.text:
            p.text = _ECHO_RE.sub("", p.text).rstrip()

    action = _extract_action(_current_user_content(callback_context))
    step, booking = advance(callback_context.state, action)
    callback_context.state["booking"] = booking
    callback_context.state["step"] = step

    for p in content.parts:
        if p.text is not None:
            p.text = STEP_TEXT.get(step, "")
            break

    for message in STEP_BUILDERS[step](booking):
        content.parts.append(to_genai_part(message))
    return llm_response


root_agent = LlmAgent(
    name="a2ui_v09_concierge_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a restaurant-booking concierge in Gemini Enterprise. An interactive "
        "card is attached to every reply automatically and your text is replaced with "
        "step copy — just write one short friendly sentence and never output JSON."
    ),
    before_model_callback=_strip_history,
    after_model_callback=_append_step,
)

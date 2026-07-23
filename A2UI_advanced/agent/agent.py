"""Restaurant Concierge — a stateful, multi-step A2UI use case for GE.

Unlike the component gallery (stateless "show me X"), this drives a 5-step flow:

    preferences → results → detail → reservation → confirmation

The step is tracked in ADK session state; each button click is a named userAction
that the after_model_callback dispatches deterministically, updates the booking in
state, and renders the next step's A2UI components. The LLM's text is replaced with
step-appropriate copy, so the flow is fully controlled (not LLM-dependent).

Reuses the gallery's hard-won lessons: flat data-model binding, history scrubbing
(so the model can't echo A2UI JSON into chat), and the <a2a_datapart_json> transport.
"""
import json
import re

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

from . import concierge
from .a2ui import extract_user_action, to_genai_part

# ── history scrub (identical approach to the gallery agent) ───────────────────
_A2UI_COMPONENT_KEYS = ("surfaceUpdate", "dataModelUpdate", "beginRendering")
_A2A_TAG_START = b"<a2a_datapart_json>"
_A2A_TAG_END = b"</a2a_datapart_json>"
_ECHO_RE = re.compile(
    r"<a2a_datapart_json>.*?</a2a_datapart_json>"
    r'|\{\s*"(?:surfaceUpdate|dataModelUpdate|beginRendering|kind)"\s*:.*',
    re.DOTALL,
)


def _is_a2ui_component_part(part) -> bool:
    blob = getattr(part, "inline_data", None)
    if blob and blob.data and blob.data.startswith(_A2A_TAG_START):
        try:
            data = json.loads(blob.data[len(_A2A_TAG_START):-len(_A2A_TAG_END)])
        except (ValueError, UnicodeDecodeError):
            return False
        inner = data.get("data", data)
        return isinstance(inner, dict) and any(k in inner for k in _A2UI_COMPONENT_KEYS)
    if part.text and (
        "<a2a_datapart_json>" in part.text
        or any(f'"{k}"' in part.text for k in _A2UI_COMPONENT_KEYS)
    ):
        return True
    return False


def _strip_a2ui_from_history(callback_context: CallbackContext, llm_request: LlmRequest):
    for cnt in llm_request.contents:
        if not cnt.parts:
            continue
        kept = [p for p in cnt.parts if not _is_a2ui_component_part(p)]
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


# ── flow state machine ───────────────────────────────────────────────────────
DEFAULT_BOOKING = {
    "cuisine": [], "dietary": [], "budget": 50, "when": "",
    "restaurant_id": None,
    "res_name": "", "res_contact": "", "party_size": 2, "requests": "",
}

STEP_BUILDERS = {
    "preferences": concierge.preferences_step,
    "results": concierge.results_step,
    "detail": concierge.detail_step,
    "reservation": concierge.reservation_step,
    "confirmation": concierge.confirmation_step,
}

STEP_TEXT = {
    "preferences": "👋 Welcome to the Concierge. Set your preferences below and tap **Find tables**.",
    "results": "Here are your matches — pick a restaurant to explore it.",
    "detail": "Explore the tabs, then reserve when you're ready.",
    "reservation": "Almost done — enter your details to book.",
    "confirmation": "🎉 You're all set — your booking is below.",
}


def _normalize_ctx(ctx):
    if isinstance(ctx, list):
        return {i["key"]: i.get("value") for i in ctx if "key" in i}
    return ctx or {}


def _as_list(v):
    if isinstance(v, list):
        return v
    return [] if v in (None, "") else [v]


def _as_int(v, default):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return default


def advance(state, action) -> tuple[str, dict]:
    """Pure transition: (current state) + (userAction) → (next step, booking).

    Does not mutate `state`; the caller persists the returned booking/step.
    """
    booking = dict(state.get("booking") or DEFAULT_BOOKING)
    step = state.get("step") or "preferences"
    if not action:
        return step, booking

    name = action.get("name")
    ctx = _normalize_ctx(action.get("context"))
    if name == "find_tables":
        booking["cuisine"] = _as_list(ctx.get("cuisine"))
        booking["dietary"] = _as_list(ctx.get("dietary"))
        booking["budget"] = _as_int(ctx.get("budget"), 50)
        booking["when"] = str(ctx.get("when") or "")
        step = "results"
    elif name == "select_restaurant":
        booking["restaurant_id"] = str(ctx.get("restaurant_id") or "")
        step = "detail"
    elif name == "start_reservation":
        step = "reservation"
    elif name == "back_to_results":
        step = "results"
    elif name == "edit_preferences":
        step = "preferences"
    elif name == "confirm_reservation":
        booking["res_name"] = str(ctx.get("name") or "")
        booking["res_contact"] = str(ctx.get("contact") or "")
        booking["party_size"] = _as_int(ctx.get("party_size"), 2)
        booking["requests"] = str(ctx.get("requests") or "")
        booking["when"] = str(ctx.get("when") or booking.get("when") or "")
        step = "confirmation"
    elif name == "new_search":
        booking = dict(DEFAULT_BOOKING)
        step = "preferences"
    return step, booking


def _set_text(content, text: str) -> None:
    for p in content.parts:
        if p.text is not None:
            p.text = text
            return


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

    action = extract_user_action(_current_user_content(callback_context))
    step, booking = advance(callback_context.state, action)
    callback_context.state["booking"] = booking
    callback_context.state["step"] = step

    text = STEP_TEXT.get(step, "")
    # Echo what the user clicked as a quote (GE's "User action triggered." bubble
    # is uneditable, so this keeps the transcript readable).
    if action:
        echo = concierge.action_echo(action, booking)
        if echo:
            text = f"> {echo}\n\n{text}"
    _set_text(content, text)

    for message in STEP_BUILDERS[step](booking):
        content.parts.append(to_genai_part(message))
    return llm_response


root_agent = LlmAgent(
    name="a2ui_concierge_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a friendly restaurant-booking concierge in Gemini Enterprise. "
        "An interactive card is attached to every reply automatically and your "
        "text is replaced with step-appropriate copy — so just produce a short, "
        "friendly sentence; never describe forms/tables/buttons or the booking "
        "steps in words, and never output JSON."
    ),
    before_model_callback=_strip_a2ui_from_history,
    after_model_callback=_append_step,
)

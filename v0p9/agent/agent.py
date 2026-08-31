"""Minimal A2UI v0.9 'Hello Material' agent for Gemini Enterprise.

Emits the v0.9 Material probe surface on every reply. Reuses the v0.8 transport
(the <a2a_datapart_json> wrapper is version-agnostic — it just carries JSON) and the
history scrub (still needed: the model must not echo A2UI JSON into chat).
"""
import json
import re

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

from .a2ui import to_genai_part
from .hello import hello_material_messages

# v0.9 message keys (+ v0.8 keys, harmless) — used to strip A2UI JSON from history
# so the model can't parrot it into the chat bubble.
_A2UI_KEYS = (
    "createSurface", "updateComponents", "updateDataModel", "deleteSurface",
    "surfaceUpdate", "dataModelUpdate", "beginRendering",
)
_TAG_START = b"<a2a_datapart_json>"
_TAG_END = b"</a2a_datapart_json>"
_ECHO_RE = re.compile(
    r"<a2a_datapart_json>.*?</a2a_datapart_json>"
    r'|\{\s*"(?:createSurface|updateComponents|updateDataModel|surfaceUpdate)"\s*:.*',
    re.DOTALL,
)


def _is_a2ui_part(part) -> bool:
    blob = getattr(part, "inline_data", None)
    if blob and blob.data and blob.data.startswith(_TAG_START):
        try:
            data = json.loads(blob.data[len(_TAG_START):-len(_TAG_END)])
        except (ValueError, UnicodeDecodeError):
            return False
        inner = data.get("data", data)
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


def _append_surface(callback_context: CallbackContext, llm_response: LlmResponse):
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
    for p in content.parts:
        if p.text is not None:
            p.text = ("Here's an A2UI **v0.9 Material** card — the buttons below should be "
                      "colored and the card elevated.")
            break

    for message in hello_material_messages():
        content.parts.append(to_genai_part(message))
    return llm_response


root_agent = LlmAgent(
    name="a2ui_v09_hello_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are a probe agent for A2UI v0.9. A Material card is attached to every "
        "reply automatically; just write one short friendly sentence and never output JSON."
    ),
    before_model_callback=_strip_history,
    after_model_callback=_append_surface,
)

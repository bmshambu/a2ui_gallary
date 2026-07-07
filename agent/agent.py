"""A2UI Component Gallery agent for Gemini Enterprise.

Shows off what A2UI can render in GE chat. The LLM routes each user question
to a gallery component by ending its reply with a marker line
([[COMPONENT:form]] etc.); the after_model_callback strips the marker and
appends the matching A2UI v0.8 DataParts. A navigation button card is added
under every response so the demo drives itself.

Adding a new gallery component:
  1. Write a builder in gallery.py returning the v0.8 message sequence
  2. Register it in COMPONENT_BUILDERS below
  3. Mention its trigger phrases + marker in the instruction
"""
import json
import re
from urllib.parse import urlparse

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types

from .a2ui import (
    extract_user_action,
    followup_messages,
    references_modal,
    to_genai_part,
)
from .gallery import data_table_messages, registration_form_messages

_MARKER_RE = re.compile(r"\[\[COMPONENT:(\w+)\]\]")

# Defensive scrub: if the model ever echoes raw A2UI payload into its text,
# strip it so it never reaches the chat bubble.
_ECHO_RE = re.compile(
    r"<a2a_datapart_json>.*?</a2a_datapart_json>"
    r'|\{\s*"(?:surfaceUpdate|dataModelUpdate|beginRendering|kind)"\s*:.*',
    re.DOTALL,
)

# A2UI component messages we emit; if the model sees these in history it tends
# to parrot the raw JSON back into its text, which then bleeds into GE chat.
_A2UI_COMPONENT_KEYS = ("surfaceUpdate", "dataModelUpdate", "beginRendering")
_A2A_TAG_START = b"<a2a_datapart_json>"
_A2A_TAG_END = b"</a2a_datapart_json>"


def _is_a2ui_component_part(part) -> bool:
    """True if this part is an A2UI component DataPart blob (not a userAction).

    Both outgoing component messages and incoming clicks use the same
    <a2a_datapart_json> wrapper; peek inside so we strip only the component
    payloads (the echo source) and keep userAction events the model needs.
    """
    blob = getattr(part, "inline_data", None)
    if blob and blob.data and blob.data.startswith(_A2A_TAG_START):
        try:
            raw = blob.data[len(_A2A_TAG_START):-len(_A2A_TAG_END)]
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return False
        inner = data.get("data", data)
        if isinstance(inner, dict) and any(k in inner for k in _A2UI_COMPONENT_KEYS):
            return True
        return False
    # A prior turn where the model already echoed raw JSON as text
    if part.text and (
        "<a2a_datapart_json>" in part.text
        or any(f'"{k}"' in part.text for k in _A2UI_COMPONENT_KEYS)
    ):
        return True
    return False


def _strip_a2ui_from_history(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> LlmResponse | None:
    """Remove A2UI component payloads from the history before the model runs.

    Prevents the model from reproducing the raw component JSON in its text as
    the conversation grows (the cause of JSON bleeding into chat after a few
    turns). userAction blobs are kept so clicks are still understood.
    """
    for cnt in llm_request.contents:
        if not cnt.parts:
            continue
        kept = [p for p in cnt.parts if not _is_a2ui_component_part(p)]
        if len(kept) != len(cnt.parts):
            cnt.parts = kept
    return None

# A2UI/ADK reading list for the references-modal demo. `snippet` is the source
# passage we surface via grounding retrieved_context.text (client asked to see the
# actual source text, not just a title) — see _references_grounding_metadata.
GALLERY_REFERENCES = [
    {"title": "A2UI Specification (v0.8)", "url": "https://github.com/google/a2ui",
     "snippet": "A2UI v0.8 defines the standard component catalog and the three-message wire format — surfaceUpdate, dataModelUpdate, and beginRendering — that Gemini Enterprise renders natively."},
    {"title": "Agent Development Kit (ADK) Docs", "url": "https://google.github.io/adk-docs/",
     "snippet": "ADK is Google's open-source framework for building, evaluating, and deploying agents, including LlmAgent, tools, callbacks, and session management."},
    {"title": "A2A Protocol", "url": "https://a2a-protocol.org/",
     "snippet": "The Agent2Agent (A2A) protocol lets agents from different platforms discover each other and exchange messages, tasks, and structured DataParts."},
    {"title": "Vertex AI Agent Engine", "url": "https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview",
     "snippet": "Agent Engine is the managed runtime that deploys, scales, and serves ADK agents, handling sessions and memory behind a stable resource name."},
    {"title": "Gemini Enterprise Overview", "url": "https://cloud.google.com/gemini-enterprise",
     "snippet": "Gemini Enterprise is Google's platform for building, governing, and running enterprise agents grounded in company data, with a chat surface that renders A2UI."},
    {"title": "ADK A2A Integration Guide", "url": "https://google.github.io/adk-docs/a2a/",
     "snippet": "Explains how ADK exposes an agent over the A2A protocol and how parts are converted to and from A2A messages on the wire."},
    {"title": "AG-UI Protocol", "url": "https://docs.ag-ui.com/",
     "snippet": "AG-UI is an open protocol for streaming agent-generated user interface events to a front end, a sibling effort to A2UI."},
    {"title": "A2UI Composer Playground", "url": "https://a2ui-composer.ag-ui.com/",
     "snippet": "An interactive playground for prototyping A2UI component layouts; note its export format differs from the GE v0.8 wire format and must be converted."},
    {"title": "Agent Engine Deployment Guide", "url": "https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/deploy",
     "snippet": "Step-by-step guide to packaging and deploying an agent to Vertex AI Agent Engine, including dependency pinning and staging buckets."},
    {"title": "CopilotKit", "url": "https://www.copilotkit.ai/",
     "snippet": "CopilotKit is an open-source framework for embedding in-app AI copilots and generative UI into web applications."},
]


def _references_grounding_metadata(reply_text: str = "") -> genai_types.GroundingMetadata:
    """Build synthetic grounding metadata from our curated reference list.

    EXPERIMENT: GE renders a native "Sources" chip + side panel from a response's
    grounding_metadata (normally produced by a real grounding tool). We attach it
    ourselves to test whether GE surfaces our hand-picked links the same way.

    First attempt sent grounding_chunks only and GE rendered nothing — real
    grounding always includes grounding_supports (segment→chunk citations), so we
    anchor one support to the reply text.

    Chunks use `retrieved_context` (which carries a `text` field = the actual
    source passage) rather than `web` (title/uri only). This is the experiment for
    the client ask "show the source text, not just a name" — if GE surfaces
    retrieved_context.text in its citation/Sources UI, users see the concrete
    passage. Falls back gracefully: title + uri still render if text is ignored.
    """
    chunks = []
    for ref in GALLERY_REFERENCES:
        chunks.append(
            genai_types.GroundingChunk(
                retrieved_context=genai_types.GroundingChunkRetrievedContext(
                    uri=ref["url"],
                    title=ref["title"],
                    text=ref.get("snippet", ""),
                )
            )
        )

    supports = None
    text = reply_text.rstrip()
    if text:
        # Anchor a single citation to the final sentence, citing every source.
        # Segment offsets are UTF-8 byte indices into the response text.
        anchor = text.rsplit(". ", 1)[-1] or text
        start = text.rfind(anchor)
        start = start if start >= 0 else 0
        supports = [
            genai_types.GroundingSupport(
                segment=genai_types.Segment(
                    start_index=len(text[:start].encode("utf-8")),
                    end_index=len(text.encode("utf-8")),
                    text=text[start:],
                ),
                grounding_chunk_indices=list(range(len(chunks))),
            )
        ]

    return genai_types.GroundingMetadata(
        grounding_chunks=chunks, grounding_supports=supports
    )


# Nav buttons: (label, question reported on click, target component marker).
# The question→component map lets us route a click deterministically instead of
# relying on the LLM to emit the right [[COMPONENT:...]] marker (it doesn't,
# reliably — that caused table/form clicks to fall through to the nav card).
_NAV_BUTTONS = [
    ("📝 Form with validation", "Show me the registration form component", "form"),
    ("📊 Data table", "Show me the financial data table component", "table"),
    ("📚 References modal", "Show me the references component", "references"),
    ("💬 Follow-up buttons", "Show me the follow-up buttons component", "followups"),
]
_QUESTION_TO_COMPONENT = {question: comp for _, question, comp in _NAV_BUTTONS}


def gallery_nav_messages() -> list[dict]:
    """The gallery's navigation card — also serves as the follow-up demo."""
    return followup_messages(
        prompt="Which A2UI component would you like to see?",
        buttons=[{"label": label, "action": q} for label, q, _ in _NAV_BUTTONS],
    )


# Marker name -> builder for the A2UI message sequence to append.
COMPONENT_BUILDERS = {
    "form": registration_form_messages,
    "table": data_table_messages,
    "references": lambda: references_modal(GALLERY_REFERENCES),
    # "followups" needs no entry: the nav card below every response IS the demo
}


def _current_user_content(callback_context):
    """Return the current turn's user Content from the callback context.

    InvocationContext.user_content is only populated when a plugin modifies the
    incoming message; in normal usage it stays None. The reliable source is the
    last 'user' event in the session history, which is always appended before
    the model is called.
    """
    # Prefer the explicit attribute (works in tests and plugin-modified flows)
    uc = getattr(callback_context, "user_content", None)
    if uc is not None:
        return uc
    # Fall back to the session events
    try:
        for event in reversed(callback_context.session.events):
            if getattr(event, "author", None) == "user" and event.content:
                return event.content
    except Exception:
        pass
    return None


def _append_gallery_parts(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    if llm_response.partial:
        return None

    content = llm_response.content
    if not content or not content.parts:
        return None

    has_text = any(p.text for p in content.parts if p.text)
    has_function_call = any(p.function_call for p in content.parts if p.function_call)
    if not has_text or has_function_call:
        return None

    # Pull the routing marker out of the model text (never show it to the user)
    component = None
    for p in content.parts:
        if p.text:
            match = _MARKER_RE.search(p.text)
            if match:
                component = match.group(1).lower()
            p.text = _MARKER_RE.sub("", p.text)
            p.text = _ECHO_RE.sub("", p.text).rstrip()

    # Button clicks: GE always shows a fixed "User action triggered." bubble and
    # gives us no way to add a user-role message. We make the transcript readable
    # by handling the click deterministically here instead of trusting the LLM.
    user_action = extract_user_action(_current_user_content(callback_context))
    if user_action:
        ctx = user_action.get("context") or {}
        if isinstance(ctx, list):
            ctx = {item["key"]: item.get("value") for item in ctx if "key" in item}
        if user_action.get("name") == "register_submitted":
            _handle_form_submit(content, ctx)
        else:
            # Echo the chosen question as a quote above the reply, so the bubble
            # reads "> Show me the … component" instead of just the component.
            # (Rewriting the clicked card in place via a surfaceUpdate to its
            # surfaceId was unreliable in GE — it only landed sometimes.)
            question = ctx.get("question")
            if question:
                _prepend_quote(content, str(question))
                # Route the click by the known button mapping, not the LLM
                # marker — the model often omits/mangles it on clicks, which
                # made component requests fall through to the nav card.
                mapped = _QUESTION_TO_COMPONENT.get(str(question))
                if mapped is not None:
                    component = mapped

    builder = COMPONENT_BUILDERS.get(component)
    if builder:
        for message in builder():
            content.parts.append(to_genai_part(message))
    else:
        # No component selected — show the nav card (followups, "menu", plain chat)
        for message in gallery_nav_messages():
            content.parts.append(to_genai_part(message))

    # EXPERIMENT: on the references demo, also attach grounding metadata so GE can
    # try to render its native "Sources" side panel from our curated links.
    if component == "references":
        reply_text = next((p.text for p in content.parts if p.text), "")
        llm_response.grounding_metadata = _references_grounding_metadata(reply_text)
    return llm_response


def _prepend_quote(content, question: str) -> None:
    """Prepend the selected question as a markdown quote to the reply text.

    Mitigates GE's uneditable "User action triggered." bubble: the agent's reply
    then opens with what the user actually picked, e.g. "> Show me the form".
    """
    for p in content.parts:
        if p.text is not None:
            body = p.text.lstrip()
            p.text = f"> {question}\n\n{body}" if body else f"> {question}"
            return


def _handle_form_submit(content, ctx) -> None:
    """Validate the register_submitted userAction and overwrite the LLM text."""
    # GE may return context as a list [{key, value}, ...] or a flat dict
    if isinstance(ctx, list):
        ctx = {item["key"]: item.get("value") for item in ctx if "key" in item}
    email = str(ctx.get("email") or "").strip()
    phone = str(ctx.get("phone") or "").strip()
    zip_code = str(ctx.get("zip") or "").strip()
    # agree may arrive as bool True/False or string "true"/"false"
    agree_raw = ctx.get("agree", False)
    agree = agree_raw is True or str(agree_raw).lower() == "true"

    errors = []
    if not agree:
        errors.append("You must agree to the terms and conditions.")
    if not email and not phone:
        errors.append("Provide at least an email address or a phone number.")
    if not zip_code:
        errors.append("Zip code is required.")

    if errors:
        result = "**Please fix the following before submitting:**\n\n" + "\n".join(
            f"- {e}" for e in errors
        )
    else:
        lines = ["**Registration received!** ✅\n"]
        if email:
            lines.append(f"- Email: `{email}`")
        if phone:
            lines.append(f"- Phone: `{phone}`")
        lines.append(f"- Zip: `{zip_code}`")
        result = "\n".join(lines)

    for p in content.parts:
        if p.text:
            p.text = result
            break


root_agent = LlmAgent(
    name="a2ui_gallery_agent",
    model="gemini-2.5-flash",
    instruction=(
        "You are the A2UI Component Gallery guide. You demonstrate the "
        "interactive UI components that A2UI can render natively in Gemini "
        "Enterprise chat. Interactive cards are attached below your text "
        "automatically — never describe buttons/forms/tables in words or "
        "promise to render them; just introduce them briefly.\n"
        "\n"
        "ROUTING — end EVERY reply with exactly one marker on its own last "
        "line (it is stripped before display; never mention it):\n"
        "  [[COMPONENT:form]] — user asks for a form, registration, sign-up, "
        "input fields, or validation demo\n"
        "  [[COMPONENT:table]] — user asks for a table, data grid, market/"
        "crypto/financial data, or tabular layout\n"
        "  [[COMPONENT:references]] — user asks for references, sources, "
        "citations, links, or documentation\n"
        "  [[COMPONENT:followups]] — anything else: greetings, questions "
        "about the gallery or A2UI, the follow-up-buttons demo itself, or "
        "when the user says 'menu', 'back', 'home', or 'navigation'\n"
        "\n"
        "When showing a component, write 1-3 sentences: what the component "
        "is and what GE capability it demonstrates (e.g. the form shows "
        "two-way data binding and regex validation; the table shows nested "
        "Row/Column layout; references show the Modal overlay).\n"
        "\n"
        "BUTTON CLICKS — if the user message contains a JSON userAction "
        "event:\n"
        "- context has 'question': treat that text as the user's message and "
        "respond to it, routing as above. Do NOT echo or quote the question "
        "yourself — the server adds it above your reply automatically.\n"
        "- name is 'register_submitted': the server validates this for you "
        "and replaces your text automatically. Just write a short neutral "
        "acknowledgement (e.g. 'Processing your registration…') and end "
        "with [[COMPONENT:followups]].\n"
        "\n"
        "If asked what you can show, summarize the four demos in one line "
        "each — the buttons below let them pick."
    ),
    before_model_callback=_strip_a2ui_from_history,
    after_model_callback=_append_gallery_parts,
)

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
import re

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse

from .a2ui import (
    extract_user_action,
    followup_messages,
    references_modal,
    to_genai_part,
)
from .gallery import data_table_messages, registration_form_messages

_MARKER_RE = re.compile(r"\[\[COMPONENT:(\w+)\]\]")

# A2UI/ADK reading list for the references-modal demo
GALLERY_REFERENCES = [
    {"title": "A2UI Specification (v0.8)", "url": "https://github.com/google/a2ui"},
    {"title": "Agent Development Kit (ADK) Docs", "url": "https://google.github.io/adk-docs/"},
    {"title": "A2A Protocol", "url": "https://a2a-protocol.org/"},
    {"title": "Vertex AI Agent Engine", "url": "https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview"},
    {"title": "Gemini Enterprise Overview", "url": "https://cloud.google.com/gemini-enterprise"},
    {"title": "ADK A2A Integration Guide", "url": "https://google.github.io/adk-docs/a2a/"},
    {"title": "AG-UI Protocol", "url": "https://docs.ag-ui.com/"},
    {"title": "A2UI Composer Playground", "url": "https://a2ui-composer.ag-ui.com/"},
    {"title": "Agent Engine Deployment Guide", "url": "https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/deploy"},
    {"title": "CopilotKit", "url": "https://www.copilotkit.ai/"},
]


def gallery_nav_messages() -> list[dict]:
    """The gallery's navigation card — also serves as the follow-up demo."""
    return followup_messages(
        prompt="Which A2UI component would you like to see?",
        buttons=[
            {"label": "📝 Form with validation", "action": "Show me the registration form component"},
            {"label": "📊 Data table", "action": "Show me the financial data table component"},
            {"label": "📚 References modal", "action": "Show me the references component"},
            {"label": "💬 Follow-up buttons", "action": "Show me the follow-up buttons component"},
        ],
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
            p.text = _MARKER_RE.sub("", p.text).rstrip()

    # Form submission: validate in Python — the LLM cannot reliably parse typed
    # values out of the raw userAction JSON it receives in context.
    user_action = extract_user_action(_current_user_content(callback_context))
    if user_action and user_action.get("name") == "register_submitted":
        _handle_form_submit(content, user_action.get("context") or {})

    builder = COMPONENT_BUILDERS.get(component)
    if builder:
        for message in builder():
            content.parts.append(to_genai_part(message))
    else:
        # No component selected — show the nav card (followups, "menu", plain chat)
        for message in gallery_nav_messages():
            content.parts.append(to_genai_part(message))
    return llm_response


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
        "- context has 'question': treat that text as the user's message. "
        "Start your reply with it as a markdown quote on its own line "
        "(e.g. '> Show me the registration form component'), then respond "
        "and route as above.\n"
        "- name is 'register_submitted': the server validates this for you "
        "and replaces your text automatically. Just write a short neutral "
        "acknowledgement (e.g. 'Processing your registration…') and end "
        "with [[COMPONENT:followups]].\n"
        "\n"
        "If asked what you can show, summarize the four demos in one line "
        "each — the buttons below let them pick."
    ),
    after_model_callback=_append_gallery_parts,
)

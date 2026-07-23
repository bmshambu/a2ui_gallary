# A2UI Gallery Agent — Resolutions & GE Gotchas

Hard-won findings from building the A2UI Component Gallery agent on **Gemini Enterprise (GE)** with **ADK + Vertex AI Agent Engine**. Each item below was reproduced in GE chat and fixed in code. Share freely — these are the non-obvious GE behaviours that aren't in the docs.

> Stack: ADK `LlmAgent` → `after_model_callback` appends A2UI v0.8 DataParts → A2A → GE renders natively. All logic lives in [`agent/agent.py`](agent/agent.py) and [`agent/gallery.py`](agent/gallery.py). 45 unit tests in [`tests/test_callback.py`](tests/test_callback.py) (no network/LLM).
>
> Gallery entries: form, table, references (id+text modal), dropdown, slider, date/time, tabs, image (text note — see §7), follow-ups.

---

## 1. Native "Sources" side panel from a curated link list ✅

**Goal:** make GE render its native **Sources** chip + right-side panel (the one clients liked) from our *own* hand-picked reference links — no grounding tool or data store.

**What works:** set `llm_response.grounding_metadata` in the `after_model_callback`. ADK forwards it over A2A automatically; GE renders the native chip, the inline citation marker, and the full Sources side panel.

**The decisive detail — `grounding_supports` is REQUIRED:**

| Attempt | Payload | GE result |
|---|---|---|
| 1st | `grounding_chunks` only (10 web sources) | **Nothing rendered** |
| 2nd | `grounding_chunks` **+ `grounding_supports`** | **Native Sources panel** ✅ |

Without a `grounding_support`, GE has no citation to anchor and shows nothing. One support is enough to activate the entire UI.

```python
from google.genai import types as genai_types
from urllib.parse import urlparse

md = genai_types.GroundingMetadata(
    grounding_chunks=[
        genai_types.GroundingChunk(web=genai_types.GroundingChunkWeb(
            uri=ref["url"], title=ref["title"],
            domain=urlparse(ref["url"]).netloc.removeprefix("www."),
        ))
        for ref in REFERENCES
    ],
    grounding_supports=[
        genai_types.GroundingSupport(
            segment=genai_types.Segment(
                start_index=<utf-8 byte offset into reply text>,
                end_index=<utf-8 byte offset>,
                text=<that slice of the reply>,
            ),
            grounding_chunk_indices=list(range(len(REFERENCES))),  # cite all
        )
    ],
)
llm_response.grounding_metadata = md
```

**Key facts:**
- Segment `start_index`/`end_index` are **UTF-8 byte offsets** into the response text, not character indices.
- An external A2A/Agent Engine agent **can** drive the native panel — it is *not* GE-internal-only. The doc wording "sources used by the Gemini models" is a red herring.
- Additive: it does not interfere with A2UI component DataParts in the same response.

---

## 2. Raw JSON bleeding into chat after 2–3 turns ✅

**Symptom:** first turn clean; by turn 2–3 raw `<a2a_datapart_json>{...}</a2a_datapart_json>` text appears in the chat bubble. Affected every component type.

**Root cause:** the callback appends A2UI component blobs to each response; they're stored in the session. ADK replays the full history to the model each turn, so the model starts **parroting that JSON into its own text output**. It was never a DataPart-count limit.

**Fix:** a `before_model_callback` (`_strip_a2ui_from_history`) removes A2UI component blobs (`surfaceUpdate`/`dataModelUpdate`/`beginRendering`, and any text already containing them) from `llm_request.contents` **before** the model runs — while keeping `userAction` blobs so clicks are still understood. Plus a defensive regex scrub in the after-callback.

**Takeaway:** any GE A2UI agent that re-emits components every turn needs history-scrubbing, or the model eventually echoes payloads into chat.

---

## 3. Form submit returned empty values even when filled ✅

**Symptom:** user fills Email/Phone/Zip and ticks the checkbox; on submit, validation reports everything empty.

**Investigation:** GE *did* resolve the button `action.context` paths (correct keys came back) but every value was empty — and **both** TextField and CheckBox failed identically, so it wasn't a property-name issue.

**Root cause:** the data-model paths were **nested** (`/formData/email`). GE writes input edits back only to **flat, single-segment top-level keys**.

**Fix:** flatten the data model and all paths.

| Before | After |
|---|---|
| data model `{"formData": {"email": "", ...}}` | `{"email": "", "phone": "", "zip": "", "agree": false}` |
| TextField `text:{path:"/formData/email"}` | `text:{path:"/email"}` |
| Button context `{path:"/formData/email"}` | `{path:"/email"}` |

**Rule:** in GE forms, always use single-segment `/key` paths — never `/parent/child`.

Validation also runs **server-side in Python** (in the callback), not via the LLM — the model can't reliably parse typed values out of the raw `userAction` JSON.

---

## 4. Button clicks rendered the wrong component (nav card instead of table) ✅

**Symptom:** clicking "Data table" showed the nav card, not the table.

**Root cause:** routing depended on the LLM emitting the exact `[[COMPONENT:table]]` marker. On button clicks the model is unreliable — it wrote the table intro but didn't emit a usable marker, so routing fell through to the nav card.

**Fix:** route button clicks **deterministically**. Each nav button's question maps directly to its component (`_QUESTION_TO_COMPONENT`); on a click the callback uses that mapping, overriding whatever marker the LLM produced. The marker remains the fallback only for free-typed messages.

---

## 5. The "User action triggered." bubble ✅ (mitigation, not removal)

**Constraint:** GE shows a fixed "User action triggered." bubble for every button click. The v0.8 `userAction` schema has **no display-text field**, so this bubble cannot be changed or removed, and we cannot inject our own user-role message bubble.

**What we do instead:** the agent's reply opens with the selected question as a markdown quote (`> Show me the … component`), prepended **deterministically in Python** (not LLM-dependent), so the transcript reads clearly.

> Note: rewriting the clicked card in place (`clicked_card_replacement`, a `surfaceUpdate` to the clicked surfaceId) was tried and is **unreliable in GE** — it only lands sometimes. We use the prepended quote instead.

---

## 6. Adding more standard-catalog components (dropdown, slider, date/time, tabs) ✅

Added from [`wadave/agent-a2ui-demo`](https://github.com/wadave/agent-a2ui-demo). **GE renders the standard v0.8 catalog only** — that repo's `GoogleMap` / `WebFrameUrl` are *custom* components (need a registered catalog GE's standard rendering lacks) and were skipped. The dropdown is GE's **`MultipleChoice`** (the repo calls it `ChoicePicker`).

Exact v0.8 payloads (verified against GE's component-gallery reference):
- `Tabs` → `{"tabItems": [{"title": {"literalString": "…"}, "child": "id"}]}`
- `MultipleChoice` → `{"options": [{"label": {"literalString": "…"}, "value": "…"}], "selections": {"path": "/x"}, "maxAllowedSelections": N}`
- `Slider` → `{"value": {"path": "/x"}, "minValue": 0, "maxValue": 10}`
- `DateTimeInput` → `{"value": {"path": "/x"}, "enableDate": true, "enableTime": true}`

**Input demos** (dropdown/slider/date-time) bind to **flat single-segment paths** (§3) and report their value via a shared `demo_submitted` action that the callback echoes server-side (`_handle_demo_submit`) — same server-side pattern as form validation.

Per-component workflow: builder in `gallery.py` → register in `COMPONENT_BUILDERS` + `_NAV_BUTTONS` + `_QUESTION_TO_COMPONENT` + routing marker in the instruction → test.

---

## 7. Images do NOT render in this GE environment ❌ (platform limitation)

Exhaustively tested — **every** avenue failed:

| Attempt | Result |
|---|---|
| `Image` + external URL (picsum) | "This content could not be displayed" (CSP block) |
| `Image` + external URL (gstatic) | **Hard 500** — "Something went wrong" (GE fetches server-side, throws) |
| `Image` + base64 data URI | Not rendered |
| Markdown `data:` image inside `Text` | **Breaks the whole surface** — nothing renders, even sibling bold text |

Network inspection (`streamAssist` response) confirmed the A2UI payload is **delivered correctly** (`application/json+a2ui`) — so this is purely **GE-side CSP/renderer**, not fixable from the payload. A large `data:` URI in markdown is actively harmful: it blanks the entire surface.

**Resolution:** the `image` gallery entry is now a **text explanation** of the limitation (no `Image` component, no `data:` URI). `encode_image.py` + `agent/demo_image.py` are kept (unused) for environments where image hosts are allowlisted.

**Rule:** don't put images (any source) or large `data:` URIs into GE payloads in this environment.

---

## 8. Starter prompts — turn-1 suggestion chips ✅

A2UI buttons only appear *after* the agent's first reply. For clickable suggestions **before** the user types, set **Starter Prompts** — these are **GE assistant configuration, not agent code**:
- GE Console → assistant config → Prompt Chips, **or**
- Discovery Engine API: `PATCH .../assistants/default_assistant?updateMask=starterPrompts` with `{"starterPrompts": [{"text": "…"}]}` (see [`set_starter_prompts.sh`](set_starter_prompts.sh)).

Unlike A2UI button clicks, **clicked starter prompts arrive as real message text** — so they route through the agent's normal typed-message markers (no "User action triggered"). Combine: starter prompts for turn 1, A2UI nav buttons every turn after.

---

## Quick reference — GE A2UI gotchas

| Area | Rule |
|---|---|
| A2UI version | GE renders **v0.8 only** (flat component list, 3-message sequence). |
| Transport | A2A DataPart via the `<a2a_datapart_json>` tag wrapper; raw inline_data → "Unsupported attachment". |
| surfaceId | Fresh UUID per response, or later cards silently update the first one. |
| Form binding | **Flat single-segment data-model paths** (`/email`), never nested. |
| Form validation | Do it **server-side in Python** in the callback, not in the LLM. |
| Click routing | Map the button's question → component **deterministically**; don't trust the LLM marker on clicks. |
| History | **Scrub A2UI blobs from history** (`before_model_callback`) or the model echoes JSON into chat. |
| Native Sources panel | `grounding_metadata` with **both** `grounding_chunks` **and** `grounding_supports` (byte-offset segments). |
| "User action triggered." | Uneditable; mitigate by prepending the chosen question as a quote. |
| `weight` property | Documented but unverified in GE chat; currently omitted (revisit later). |
| Custom components | GE renders the **standard catalog only** — `GoogleMap`/`WebFrameUrl` etc. need a registered custom catalog. |
| Input binding | Dropdown/slider/date-time bind to flat paths; echo the submitted value server-side (`demo_submitted`). |
| **Images** | **Do not render in this GE env** — external URLs error/500, `data:` URIs fail, `data:` in markdown breaks the surface. Avoid entirely. |
| Markdown in `Text` | Bold / italic / links render. Backticks render **literally**. Images do **not** render. |
| Starter prompts | GE assistant config (not agent code); clicked ones arrive as real message text. |

---

*Generated from the build session. Code references point to the `a2ui_gallary` repo.*

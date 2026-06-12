# A2UI Component Gallery Agent

An ADK agent for **Gemini Enterprise** that demonstrates what A2UI (v0.8) can
render natively in GE chat. Ask it a question, it answers and attaches the
matching interactive component — with navigation buttons under every response
so the demo drives itself.

## Gallery components

| Component | What it demonstrates | Source |
|---|---|---|
| 💬 Follow-up buttons | Clickable suggestions, `userAction` round trip, in-place card rewrite after click | skill asset `a2ui.py` |
| 📚 References modal | Top-3 links inline + full list behind a `Modal` overlay (two-column grid) | skill asset `a2ui.py` |
| 📝 Registration form | `TextField` regex validation, `CheckBox`, two-way data binding, submit button reading the data model | converted from `a2ui-form.json` |
| 📊 Data table | Nested `Row`/`Column` layout, `Divider`, text hierarchy — a table without a table component | converted from `a2ui-table.json` |

## Trigger questions

The agent routes by intent (it appends a hidden `[[COMPONENT:...]]` marker
that the callback strips and maps to a payload builder):

| You ask | It shows |
|---|---|
| "What can you show me?", "hi", any general question | answer + **follow-up buttons** (navigation card) |
| "Show me a form", "I want to register / sign up", "show input validation" | **registration form** |
| "Show me a table", "show crypto prices", "display market data" | **data table** |
| "Show me your references / sources / citations / docs" | **references modal** |
| Submitting the form | server-side validation result (agree + email-or-phone + 5-digit zip) |

Button clicks come back as `userAction` events — the agent quotes the chosen
question (GE shows a fixed "User action triggered." bubble otherwise) and
rewrites the clicked card in place.

## Do the Composer JSONs align with GE rendering?

**No — not as-is.** `a2ui-form.json` / `a2ui-table.json` are in the
**A2UI Composer** format (a2ui-composer.ag-ui.com), which differs from the
v0.8 wire format GE renders. Sending them directly renders nothing. They are
kept as design references; `agent/gallery.py` is the GE-compatible
conversion. What had to change:

| Composer feature | GE v0.8 status | Conversion |
|---|---|---|
| `"component": "Card"` + flat props | ❌ wrong encoding | `"component": {"Card": {...}}` |
| `children: ["a","b"]` | ❌ | `children: {"explicitList": [...]}` |
| `"text": "..."` / `variant` | ❌ | `{"literalString": "..."}` / `usageHint` |
| `formatDate` / `formatString` / `formatCurrency` calls | ❌ no function system | computed in Python, sent pre-formatted |
| `checks` with custom error messages | ❌ | `TextField.validationRegexp` (same regex, default message) |
| Conditional submit enablement (`and`/`or`/`required` checks on Button) | ❌ | agent validates the `userAction` payload and replies with what's missing |
| `weight` (proportional columns) | ✅ per [GE component gallery reference](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/a2ui-component-gallery-reference) (common property, flex-grow-like; absent from the published v0.8 schema) | kept, at envelope level next to `id`; `spaceBetween` retained as fallback |
| `List` + row template bound to `/assets` | ⚠️ template syntax differs | rows expanded server-side via `explicitList` (simpler + proven) |
| Colored +/- change values | ❌ no styling control in GE | ▲/▼ arrows + sign |

## Project layout

```
agent/
  __init__.py        exports root_agent
  agent.py           gallery agent: routing instruction + after_model_callback
  a2ui.py            v0.8 payload builders + DataPart wrapper (from the skill, unmodified)
  gallery.py         form + table builders (GE conversions of the Composer JSONs)
verify_payloads.py   offline check: ADK converter round-trip + id resolution
deploy_to_agent_engine.py
requirements.txt     pinned — aiplatform 1.148.1 + google-adk 1.31.1 (load-bearing)
a2ui-form.json       Composer prototype (design reference only, not GE-renderable)
a2ui-table.json      Composer prototype (design reference only, not GE-renderable)
```

## Run / verify / deploy

```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 1. Offline payload verification (no server, no GCP)
.venv\Scripts\python verify_payloads.py

# 2. Local smoke test — adk web does NOT render A2UI; check the raw event
#    JSON for <a2a_datapart_json> parts
.venv\Scripts\adk web . --port 8080 --a2a

# 3. Deploy (after: gcloud auth application-default login; copy
#    env.dev.example -> .env.dev and fill in)
.venv\Scripts\python deploy_to_agent_engine.py
```

First deploy only: register the printed `projects/.../reasoningEngines/...`
resource name in GE Admin console → Agents → Add agent → Vertex AI Agent
Engine. Updates keep the resource name, so registration survives redeploys.

Only the GE chat surface renders A2UI — `adk web`, the Agent Engine
playground, and the Cloud console test panel all show raw JSON.

## Adding a new gallery component

1. Write a builder in `agent/gallery.py` returning the v0.8 three-message
   sequence (`surfaceUpdate`, `dataModelUpdate`, `beginRendering`) with a
   **fresh surfaceId per call**
2. Register it in `COMPONENT_BUILDERS` in `agent/agent.py`
3. Add its trigger phrases + marker to the instruction, and (optionally) a
   button to `gallery_nav_messages()`
4. Add a `check_builder(...)` line to `verify_payloads.py` and run it

Candidates from the v0.8 catalog not yet in the gallery: `Tabs`,
`MultipleChoice` (dropdown), `Slider`, `DateTimeInput`, `Image`, `Video`,
`AudioPlayer`.

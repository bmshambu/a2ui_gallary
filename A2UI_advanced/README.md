# A2UI Advanced — Restaurant Concierge

A **stateful, multi-step** A2UI use case for Gemini Enterprise, in contrast to the
component gallery (which shows one component per turn). The concierge combines many
components into a single guided flow to book a restaurant table.

```
preferences ──▶ results ──▶ detail ──▶ reservation ──▶ confirmation
```

| Step | Components combined |
|---|---|
| **Preferences** | 2× MultipleChoice (cuisine, dietary) · Slider (budget) · DateTimeInput · Button |
| **Results** | filtered restaurant rows (Row/Column/Text) · a Select button per row |
| **Detail** | Tabs: Overview · Menu (dish list) · Reviews (+ References modal) · Location · Reserve/Back |
| **Reservation** | Form (TextField ×2) · Slider (party size) · DateTimeInput · Confirm |
| **Confirmation** | booking summary built from state · New-search |

## How it works
- **State** lives in the ADK session state (`booking` dict + `step`). Every button is
  a named `userAction`; `agent.advance()` is a pure transition that updates the booking
  and returns the next step. The `after_model_callback` persists it and renders that
  step's A2UI components. The LLM's text is replaced with step copy — the flow is fully
  deterministic, not LLM-dependent.
- **Reuses the gallery's lessons**: flat single-segment data-model paths, history
  scrubbing (so the model can't echo A2UI JSON into chat), and the `<a2a_datapart_json>`
  transport (`agent/a2ui.py`, copied verbatim).
- **No images** — GE cannot render them (see `../resolution.md`).

## Layout
```
A2UI_advanced/
  agent/
    a2ui.py        reused transport/helpers (verbatim from the gallery)
    data.py        invented restaurant dataset + search filter
    concierge.py   the 5 step builders
    agent.py       LlmAgent + state machine (advance) + callbacks
  tests/test_flow.py   21 offline tests (no LLM/network)
  deploy_to_agent_engine.py, requirements.txt, env.dev.example
```

## Run tests
```bash
cd A2UI_advanced
../.venv/Scripts/python -m pytest tests/ -v
```

## Deploy
1. `cp env.dev.example .env.dev` and fill in project/bucket. **Keep the distinct
   `AGENT_DISPLAY_NAME`** — deploy matches create-or-update by display name, so a shared
   name would overwrite the gallery agent.
2. `python deploy_to_agent_engine.py`
3. Register the printed resource name in the GE Admin console (first deploy only).

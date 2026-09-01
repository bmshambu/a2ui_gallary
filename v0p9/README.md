# A2UI v0.9 — `v0p9/`

The Restaurant Concierge **revamped on A2UI v0.9** (GE added v0.9 support 2026‑05‑13).
Read [`guidelines.md`](guidelines.md) — it maps v0.9's wins to our v0.8 struggles and is the
**living log of everything we confirmed in GE** (§7). The v0.8 build in `../A2UI_advanced/`
stays as the baseline.

## Status: full flow working in GE ✅

Same 5-step booking journey as v0.8, rebuilt on v0.9 with capabilities v0.8 never had:

| Step | v0.9 build |
|---|---|
| **Preferences** | `ChoicePicker` **chips** (cuisine/dietary), `Slider` ×2, `CheckBox`, `DateTimeInput`, primary button |
| **Results** | a **photo card** per match (`Image` — v0.9 renders external images!) + Select |
| **Detail** | `Tabs`: Overview (photo) · Menu · Reviews (+ `Modal`) · Location |
| **Reservation** | `TextField` ×2 · `Slider` · `DateTimeInput` · server-side validation |
| **Confirmation** | styled receipt (`Divider` + summary) |

### What v0.9 gave us over v0.8
- **Images render** (restaurant photos) — the v0.8 hard-block is gone
- **`variant` styling** (blue primary / borderless buttons), **chips** selection
- **Flat components**, `{path}` binding, **pre-resolved event context** (no raw-JSON parsing of form values)
- Cleaner messages: `createSurface` / `updateComponents` / `updateDataModel`

## How it works
- `"version": "v0.9"` on **every** message (required — without it GE falls back to v0.8 and renders nothing).
- `catalogId` is the **basic catalog URL** `https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json`.
- Clicks arrive as `{"action": {name, context}}` with **bindings pre-resolved**; the state machine
  (`agent.advance`) updates the booking in ADK session state and renders the next step.
- Transport = the version-agnostic `<a2a_datapart_json>` wrapper (`agent/a2ui.py`, reused from v0.8).

## Layout
```
v0p9/
  guidelines.md        ← v0.9 findings + build log (share this)
  agent/
    a2ui.py            transport (reused)
    data.py            restaurant dataset + photos + search
    concierge.py       the 5 step builders (v0.9 basic catalog)
    agent.py           LlmAgent + state machine + v0.9 event parsing
    hello.py           the original "hello v0.9" probe (kept for reference)
  tests/test_flow.py   21 offline tests
```

## Run tests / deploy
```bash
cd v0p9
../.venv/Scripts/python -m pytest tests/ -v
cp env.dev.example .env.dev   # fill project/bucket; distinct display name already set
python deploy_to_agent_engine.py
```

## Next (optional): Material catalog
The **basic** catalog covers the whole flow. The **Material** catalog would add richer styling —
`color` (primary/accent/warn), elevation, `MaterialTable`, `MaterialExpansionPanel` (accordion),
`MaterialChips` — but its `catalogId` is GE-proprietary and not public. Get that URL from your GE
admin/console to swap it in; not a blocker.

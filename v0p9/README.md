# A2UI v0.9 — `v0p9/`

New work on **A2UI v0.9** (GE added v0.9 support 2026‑05‑13). Read
[`guidelines.md`](guidelines.md) first — it maps v0.9's wins to our v0.8 struggles and
lists what still needs verifying. The v0.8 `../A2UI_advanced/` build stays as the baseline.

## Step 1 — the "Hello Material" probe (this)

The smallest possible v0.9 surface, built to answer three questions in one deploy:

1. Does GE accept **v0.9 messages** over the **same A2A transport** we used for v0.8?
2. Does GE render the **Material catalog**?
3. Does **Material styling** actually show (button `color`/`appearance`, card elevation) —
   the thing v0.8 could not do?

It renders one elevated `MaterialCard` with a title and **three buttons**: filled·primary,
tonal·accent, outlined·warn.

```
v0p9/agent/hello.py   → the v0.9 Material message sequence (createSurface + updateComponents)
v0p9/agent/agent.py   → LlmAgent + callbacks (transport + history scrub reused from v0.8)
v0p9/tests/test_hello.py → 6 offline checks (shape + A2A round-trip)
```

### Run tests
```bash
cd v0p9
../.venv/Scripts/python -m pytest tests/ -v
```

### Deploy
```bash
cp env.dev.example .env.dev   # fill in project/bucket; display name is already distinct
python deploy_to_agent_engine.py
```
Register the printed resource name in the GE Admin console (first deploy only), then open
the agent in GE chat and say "hi".

### How to read the result

| What you see in GE | Verdict |
|---|---|
| Elevated card + **three colored buttons** | ✅ v0.9 Material + styling work → port the concierge |
| Card + buttons render but **no color/elevation** | v0.9 renders, but styling props ignored — check `appearance`/`color` names or catalog |
| Raw JSON / "Unsupported attachment" | Transport or format rejected — check the `catalogId` and the v0.9 message shape |
| Nothing / error | Wrong `catalogId` (try a full URL) or GE needs a different handshake |

### Assumptions baked in (the things to adjust if it fails)
- `catalogId: "material"` (short id, per GE docs example) — may need a full URL.
- Transport = the v0.8 `<a2a_datapart_json>` wrapper + `mimeType application/json+a2ui`
  (version-agnostic — carries any JSON). The probe reuses it verbatim.
- Material property names: `MaterialButton.label`, `appearance`, `color`;
  `MaterialCard.children` + `appearance`; `MaterialColumn/Row.children`.

Once this renders, Step 2 is porting the Restaurant Concierge onto v0.9 Material
(see `guidelines.md` §5).

# A2UI v0.9 on Gemini Enterprise — Guidelines (read before building)

Research notes for revamping the Restaurant Concierge POC on **A2UI v0.9**. Written
before any code so the team agrees the direction. Everything here is from the v0.9 spec
+ GE docs (May 2026); items we can't confirm from docs are called out as **VERIFY**.

---

## 0. The headline

**Gemini Enterprise now renders A2UI v0.9** (announced **2026‑05‑13**), *alongside* v0.8.
This overturns the constraint the whole v0.8 build worked around ("GE supports v0.8 only").

v0.9 ships **two catalogs**:
- **Basic catalog** — the portable, framework-agnostic set (v0.8's "standard catalog", renamed).
- **Material catalog** — **Material Design 3 components with real styling** (`MaterialButton`,
  `MaterialTable`, `MaterialExpansionPanel`, `MaterialProgressBar`, `MaterialChips`, …).
  **This is the big win** — it fixes our single biggest v0.8 pain: *no styling / color control.*

> Sources: [A2UI v0.9 announcement](https://developers.googleblog.com/a2ui-v0-9-generative-ui/) ·
> [A2UI v0.9 spec](https://a2ui.org/specification/v0.9-a2ui/) ·
> [v0.8→v0.9 evolution guide](https://a2ui.org/specification/v0.9-evolution-guide/) ·
> [GE component gallery reference](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/a2ui-component-gallery-reference) ·
> [GE release notes](https://docs.cloud.google.com/gemini/enterprise/docs/release-notes)

---

## 1. Format changes (v0.8 → v0.9)

| Area | v0.8 | v0.9 |
|---|---|---|
| Component shape | nested key wrapper `{"component": {"Text": {…}}}` | **flat discriminator** `{"id":"t","component":"Text","text":"…"}` |
| Messages | `surfaceUpdate` · `dataModelUpdate` · `beginRendering` | **`createSurface`** · **`updateComponents`** · **`updateDataModel`** · `deleteSurface` |
| Version | implicit | explicit **`"version": "v0.9"`** on each message |
| Catalog | standard only | **`catalogId`** on `createSurface` (basic **or** material catalog URL) |
| Data values | typed wrappers `{"literalString":"x"}` / `{"literalNumber":5}` | **implicit typing** — just `"x"` / `5` |
| Binding | `{"path":"/a/b"}` (+ our GE flat-key quirk) | unified **`path`** (JSON Pointer) everywhere |
| Formatting | none — **we formatted everything in Python** | **`formatString`** with `${expression}` interpolation |
| Validation | our **Python** server-side checks | declarative **`checks`** (client-side function calls) |
| Styling | **`usageHint`**, no colors | **`variant`** + (material) `color`, `appearance`, `elevation`, surface **`theme`** |
| Button emphasis | `primary: true/false` | `variant: "primary" | "borderless"` (basic) / material appearance enum |
| List rendering | explicit children (our unverified template experiment) | **template + collection scopes** (relative paths per item) |

The flat discriminator + implicit typing + shorter names exist to make the JSON **easier for
the LLM to generate** and cheaper in tokens ("prompt-first" design).

---

## 2. The Material catalog — what it unlocks (GE v0.9)

Material Design 3 components GE renders in v0.9, with **actual styling knobs**:

- **Styling props (across components):** `color` = `primary` / `accent` / `warn`;
  button `appearance` = `text` / `filled` / `elevated` / `outlined` / `tonal`;
  card `appearance` = `raised` / `outlined`; a surface **`theme`**.
- **Components (Material\* prefix):** MaterialCard, MaterialColumn, MaterialRow, MaterialDialog,
  MaterialDivider, **MaterialExpansionPanel**, **MaterialGridList**, MaterialBadge, MaterialIcon,
  MaterialImage, **MaterialProgressBar**, **MaterialProgressSpinner**, **MaterialTable**, MaterialText,
  MaterialButton, MaterialIconButton, MaterialMenu, MaterialTabs, MaterialButtonToggle, MaterialCheckbox,
  **MaterialChips**, MaterialDatepicker, MaterialInput, MaterialRadioButton, MaterialSelect,
  MaterialSlideToggle, MaterialSlider, MaterialTimepicker.

Example (from GE docs):
```json
{ "id": "book", "component": "MaterialButton",
  "text": "Reserve a table",
  "appearance": "filled", "color": "primary",
  "action": { "event": { "name": "start_reservation" } } }
```

---

## 3. v0.8 struggles → v0.9 fixes  ⭐ (the reason to revamp)

| What we fought in v0.8 (see `../resolution.md`) | v0.9 fix |
|---|---|
| **No color / styling control** at all | **Material `color` / `appearance` + surface `theme`** |
| **No accordion / collapsible** — we abused `Modal` | **`MaterialExpansionPanel`** (native collapsible) |
| **Hand-built table** from Row/Column/Text | **`MaterialTable`** |
| **Scattered buttons, no grid**, `weight` unverified (see `../solution.md`) | **`MaterialGridList`** + **`MaterialChips`** for even, ordered layouts |
| **No loading state** | **`MaterialProgressBar` / `MaterialProgressSpinner`** |
| **All formatting done in Python** (currency, dates) | **`formatString` `${…}`** interpolation client-side |
| **List template unverified** | v0.9 **formalizes templates** with collection scopes |
| **Typed value wrappers** everywhere | implicit typing — less boilerplate, fewer bugs |

### v0.8 lessons that probably STILL apply in v0.9 — **carry them over**
- **History scrub** (`before_model_callback`) so the model doesn't echo A2UI JSON into chat
  — almost certainly still needed (LLM-in-the-loop). See `[[a2ui-json-bleed-cause]]`.
- **Fresh `surfaceId` per surface** (unless deliberately updating one in place).
- **"User action triggered." bubble** is GE-side and uneditable — keep the click-echo mitigation.
- **Deterministic click routing** in the callback beats trusting LLM markers.
- **Images may still not render** in GE (v0.8 was a CSP/renderer block, not a spec gap) — **VERIFY `MaterialImage`** before relying on it.

---

## 4. Open questions to VERIFY before/while building

1. **Version + catalog declaration to GE.** v0.9 sets `"version":"v0.9"` and a `createSurface.catalogId`
   (basic vs material catalog URL). Docs don't spell out the exact GE handshake — confirm the
   catalogId string for the **material** catalog and that GE selects it. **VERIFY.**
2. **Transport.** Is it still an A2A **DataPart** (our `<a2a_datapart_json>` wrapper +
   `mimeType application/json+a2ui`), or a v0.9-specific mimeType? The announcement mentions an
   **A2UI Agent SDK** (`CatalogConfig`, `A2uiSchemaManager`, `parse_response_to_parts()`) that may
   replace our manual wrapping. Check whether it's in our pinned ADK or a separate package. **VERIFY.**
3. **Data-binding write-back quirk.** In v0.8, GE only wrote input edits to **flat top-level keys**
   (`/email`, not `/formData/email`). Does v0.9 lift this? Test nested `path` on a real input. **VERIFY.**
   See `[[a2ui-ge-flat-databinding]]`.
4. **`checks` validation** — do GE-rendered inputs actually run client-side `checks`, or do we still
   validate server-side in the callback? **VERIFY** (keep the Python validator as fallback).
5. **`formatString`** — confirm `${…}` interpolation renders in GE (would remove a lot of Python).
6. **Exact Material property names** — the docs showed minor inconsistencies (`min/max` vs
   `minValue/maxValue`, `variant` vs `appearance`). Pin them against the live GE v0.9 gallery
   reference per component before coding. **VERIFY.**

---

## 5. Plan for the v0.9 restaurant revamp (`v0p9/`)

Same 5-step concierge, rebuilt on v0.9 Material to *show off* what v0.8 couldn't:

| Step | v0.8 build | v0.9 upgrade |
|---|---|---|
| Preferences | dropdowns + sliders + checkboxes | **MaterialChips** (cuisine), **MaterialSelect**, **MaterialSlider**, **MaterialDatepicker/Timepicker**; primary filled CTA |
| Results | hand-built rows | **MaterialTable** (or MaterialGridList of MaterialCards), colored rating badges via **MaterialBadge** |
| Detail | Tabs + Modal-as-accordion | **MaterialTabs** + **MaterialExpansionPanel** for menu/reviews (real accordion) |
| Reservation | TextFields + Python validation | **MaterialInput** with declarative **`checks`**; **MaterialProgressSpinner** on submit |
| Confirmation | text receipt | styled **MaterialCard** (elevation, theme color), MaterialDivider |

Approach: **start tiny** — one `createSurface` + one `MaterialButton` with `color: primary`,
deploy, confirm GE renders v0.9 Material and styling actually shows. *Only then* port the flow.
Keep the v0.8 `A2UI_advanced/` untouched as the working baseline to compare against.

### Suggested `v0p9/` layout (mirrors the v0.8 folders)
```
v0p9/
  guidelines.md          ← this file
  agent/
    a2ui.py              ← v0.9 transport helpers (build fresh — format differs from v0.8)
    ...builders, agent.py
  tests/
  README.md
```

---

## 6. TL;DR for the team

- **GE renders v0.9 now** (since 2026‑05‑13) — with a **Material Design catalog** that finally
  gives us **colors, elevation, theme, real Table, real Accordion, Grid, Chips, Progress**.
- v0.9 also makes the JSON **flatter and easier to generate** (discriminator, implicit typing,
  `formatString`, `checks`, JSON-Pointer `path`, new `createSurface/updateComponents/updateDataModel`
  messages).
- **Before porting the flow, verify the load-bearing unknowns in §4** (version/catalog declaration,
  transport/SDK, data-binding write-back). Carry over the v0.8 hardening in §3 that still applies.
- Then rebuild the concierge in `v0p9/` to showcase the components we *couldn't* do in v0.8.

---

## 7. Build log — verified in GE (append every new result here) 📓

Living record of what we actually confirmed on GE, from the `v0p9/` Hello-Material probe onward.

### Transport & deploy
- ✅ **Same transport as v0.8 works for v0.9.** The `<a2a_datapart_json>` wrapper +
  `mimeType: application/json+a2ui` carries v0.9 messages fine — DataParts are emitted and
  visible in the Agent Engine **Playground**. (`agent/a2ui.py` reused verbatim.)
- ✅ **Playground never renders A2UI** — it shows the raw base64 `inlineData`. **Only GE chat
  renders.** Don't judge rendering from the Playground (same rule as v0.8).
- ⚠️ **`agent_engines.update()` can 500 (INTERNAL / code 13)** — often transient; retry, or
  deploy under a distinct display name so it takes the *create* path. Not an A2UI issue.

### v0.9 rendering
- ❌ **Attempt #1 — no version marker → GE rendered NOTHING** (text only). GE defaults to
  **v0.8 semantics** (looks for `surfaceUpdate`/`beginRendering`), doesn't recognize `createSurface`.
- ✅ **Attempt #2 — `"version": "v0.9"` (sibling of `createSurface`/`updateComponents`) WORKS.**
  GE recognized v0.9 and tried to render — it advanced to a *specific catalog error* instead of
  silence. **This version marker is REQUIRED for v0.9.**
- ❌ **`catalogId: "material"` → GE error "Catalog not found: material".** `catalogId` must be the
  catalog's **full URL** (it equals the catalog `$id`), and GE looks it up in a registry. The GE
  docs' short `"material"` example does NOT work. **The Material catalog is GE-proprietary — its
  catalogId URL is not in any public repo** (`google/A2UI` ships only the *basic* catalog).
- ✅ **Basic catalog `catalogId` is public and GE-accepted:**
  `https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json`
- ✅ **Attempt #3 — basic catalog RENDERS in GE. v0.9 confirmed working end-to-end.** 🎉
  The card, `h4` title, `body` subtitle, and three buttons all rendered. Button **`variant` shows
  real styling**: `primary` = **blue filled**, `borderless` = text-only, `default` = outlined —
  already richer than v0.8's `primary` boolean. Card renders bordered; Column/Row layout works.
  Clicking a Button fires its `action.event` → the same GE **"User action triggered."** bubble as
  v0.8 (uneditable — our click-echo mitigation still applies) and the next turn rendered a fresh card.

**Confirmed working recipe (copy this):**
```json
{"version":"v0.9","createSurface":{"surfaceId":"s","catalogId":"https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json","sendDataModel":false}}
{"version":"v0.9","updateComponents":{"surfaceId":"s","components":[
  {"id":"root","component":"Column","children":["title","btn"],"align":"stretch"},
  {"id":"title","component":"Text","text":"Hello","variant":"h4"},
  {"id":"btn","component":"Button","child":"lbl","variant":"primary","action":{"event":{"name":"clicked"}}},
  {"id":"lbl","component":"Text","text":"Primary"}
]}}
```
Transport = the v0.8 `<a2a_datapart_json>` wrapper (`mimeType application/json+a2ui`), one message
per DataPart. `"version":"v0.9"` on every message is mandatory.

### Basic catalog v0.9 component shapes (CONFIRMED from google/A2UI schema)
| Component | Props |
|---|---|
| `Column` / `Row` | `children` (array of ids), `justify` (start/center/end/spaceBetween/…/stretch), `align` (start/center/end/stretch) |
| `Card` | **`child`** (a SINGLE id — not `children`) |
| `Text` | `text` (string), `variant` (h1–h5 / caption / body) |
| `Button` | **`child`** (a Text id = the label — NOT `text`/`label`), `variant` (default/primary/borderless), `action` |
| `Icon` | `name` |
Basic catalog components (all): AudioPlayer, Button, Card, CheckBox, ChoicePicker, Column,
DateTimeInput, Divider, Icon, Image, List, Modal, Row, Slider, Tabs, Text, TextField, Video.

### Confirmed by attempt #3
- ✅ Basic catalog renders in GE; `createSurface` + `updateComponents` are enough (no render trigger needed).
- ✅ `variant` styling works (primary=blue filled / borderless / default=outlined).
- ✅ `action.event` round-trips (click → "User action triggered" bubble → next turn).

### Images (v0.9)
- ✅ **Spec supports Image/Video/AudioPlayer** in the basic catalog. `Image`: `url`, `description`,
  `fit` (contain/cover/fill/none/scaleDown), `variant` (icon/avatar/smallFeature/mediumFeature/
  largeFeature/header) — richer than v0.8.
- 🔄 **GE render test in progress** — probe now includes an `Image` with an external Google-hosted
  URL (`gstatic`). v0.8 hard-500'd on external images; testing whether v0.9 lifts that. **Update
  with the verdict.**

### Still open
- **The Material catalog's `catalogId` URL** — only needed for the *extra* Material styling/components
  (color/accent/warn, MaterialTable, MaterialExpansionPanel, MaterialChips, elevation). It's
  GE-proprietary and not public — get it from the GE Admin console / a GE sample / GE support.
  **Not a blocker:** the basic catalog already covers the concierge (ChoicePicker, Slider,
  DateTimeInput, Tabs, Modal, List, Card, CheckBox, TextField, Button+variant) + v0.9 wins
  (flat format, `formatString`, `checks`, List templates).
- How does the click **event** arrive back to the agent in v0.9 (shape of the incoming userAction)?
  — confirm when we wire interactions in the concierge.

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
- ✅ **v0.9 RENDERS external images — the v0.8 block is LIFTED.** 🎉 An `Image` with an external
  Google-hosted URL (`https://www.gstatic.com/webp/gallery/1.jpg`, `fit: cover`,
  `variant: largeFeature`) rendered cleanly in the GE card. In v0.8 the same external image
  hard-500'd; **in v0.9 it just works.** This is a genuine capability gain — the concierge can now
  show restaurant photos. (Tested a Google-hosted host; if a specific host misbehaves, try another,
  but external images are viable in v0.9.)

### Concierge Step 1 (Preferences) — ALL CONFIRMED in GE ✅
Deployed the v0.9 concierge Preferences surface — everything rendered and worked:
- ✅ **ChoicePicker `displayStyle: chips`** — renders as selectable chips (selected = blue).
  Both cuisine and dietary. (Nicer than v0.8's dropdown / the scattered-button problem.)
- ✅ **Slider** (with value shown), **CheckBox**, **DateTimeInput** (date **and** time pickers,
  calendar/clock icons) all render natively.
- ✅ **Button `variant: primary`** = blue filled; `borderless` = text.
- ✅ **Data-binding WRITE-BACK works** — user's chip/checkbox/slider selections reached the
  data model via **flat single-segment paths** (`/cuisine`, `/outdoor`, …). (Same rule as v0.8:
  keep paths flat.)
- ✅ **`action.event.context` is pre-resolved by GE** — the `find_tables` click arrived with the
  real selected values (not raw bindings), so `advance()` filtered correctly (Italian + Outdoor
  → exactly Bella Italia + Trattoria Verde). **No more raw-JSON parsing of typed values** (v0.8 pain gone).
- ✅ **`updateDataModel` `path:"/" value:{…}`** seeds the initial model.
- ✅ **Multi-step state machine** (ADK session state) + incoming `{"action":{name,context}}` parsing works.
- ⚠️ "User action triggered." bubble still appears on click (unchanged from v0.8 — mitigation carries over).

### Concierge FULL FLOW — CONFIRMED in GE ✅ 🎉
Deployed all 5 steps; the whole booking journey works end-to-end:
- ✅ **Results**: multiple **external images render at once** (photo card per match) — v0.8 couldn't show any image.
- ✅ **Detail `Tabs`** (4 tabs, new `tabs: [{title, child}]` shape) render and switch; a **large `Image`** renders inside a tab.
- ✅ **`Modal`** (new `trigger`/`content` shape) opens on click, showing overlay content.
- ✅ **Markdown bold renders in `Text` `variant: body`** (Menu dish names bold). ⚠️ It did **NOT**
  render in a `variant: caption` Text (the modal source list showed literal `**…**`) → **use
  `variant: body` (not caption) when a Text contains markdown.** Fixed the review-sources list.
- ✅ Full state machine (find_tables → results → detail → reservation → confirmation), click echo,
  variant button styling, `updateDataModel` binding all working.

### Styling / control available in v0.9 basic catalog (researched)
**CAN control:**
- ✅ **Surface `theme`** (on `createSurface`): `primaryColor` (hex `#RRGGBB` — brands primary buttons /
  active borders), `iconUrl` (agent icon by the surface), `agentDisplayName`. The one real global
  styling lever.
- ✅ **Text `variant`**: `h1`–`h5` (heading sizes), `body`, `caption` (small). This is font sizing.
- ✅ **`weight`** (common) — proportional size within a Row/Column; layout via Row/Column `align`/`justify`.
- ✅ **Button `variant`** (default/primary/borderless), **Image `variant`** (icon/avatar/…/largeFeature).
- ✅ **`Text` renders Markdown** (bold, **links**) — but NOT HTML/images. So a **map link** =
  `[Open in Maps](https://www.google.com/maps/search/?api=1&query=<address>)` in a Text.
- ✅ **ChoicePicker**: `displayStyle` `chips` (compact) or `checkbox` (list) + `filterable: true`
  (adds a search box for long option lists).

**CANNOT control (basic catalog):**
- ❌ Per-component **padding / margin / arbitrary font-size / color** (only theme.primaryColor globally
  + component variants). Card gives padding automatically.
- ❌ A true collapsing **dropdown** for ChoicePicker (only chips/checkbox) — need `MaterialSelect`
  (Material catalog).
- ❌ Native **Map** component — not in basic catalog (use a Markdown map *link*). Material may have one.

### Enhancements — GE verdicts (deployed 2026-09-01)
- 🎨 **Theme selector** — ✅ **CONFIRMED in GE**. `createSurface.theme.primaryColor` (a hex) really
  repaints primary buttons, active chip fill, AND slider tracks — set it per surface and GE honors
  it on the **basic** catalog. This is the one working global styling lever. Persist the hex in
  state and stamp it on every surface. (Screenshot: Forest → green chip + green sliders.)
- 🗺️ **Map link** — ✅ **CONFIRMED**. A Markdown link `[label](https://…)` in a `variant:body` Text
  renders as a real clickable link in GE v0.9.
- 🔠 **Bigger tab text** — ✅ **CONFIRMED**. Tab body content reads noticeably larger with
  `variant:body` vs `caption`. Use `body` for anything you want at readable size inside Tabs.
- 🔎 **`filterable: true`** — ❌ **DOES NOT WORK** on the basic-catalog `ChoicePicker`. GE renders the
  same chip list with no search box; the flag is silently ignored. A real searchable/typeahead
  picker needs the **Material** catalog (`MaterialSelect`). Don't rely on `filterable` on basic.
- 🧩 **Components gallery** — built ("show me the components used" typed trigger → menu →
  per-component demo). Ported from the v0.8 A2UI_advanced gallery.

### Padding / corners / text spacing — schema limits + workarounds (stakeholder Qs, 2026-09-01)
Checked every basic-catalog component's full property set:
- **Padding: no property.** Card=`child` only; Column/Row=`children`+`justify`+`align`; Modal=
  `trigger`+`content`. Google's renderer sets padding automatically. **Levers we DO have** on
  Column/Row: `justify` ∈ `start·center·end·spaceBetween·spaceAround·spaceEvenly·stretch` (main
  axis) and `align` ∈ `start·center·end·stretch` (cross axis). To add gaps, use
  `spaceBetween/Around/Evenly` **or** inject spacer components (see `_spacer` / `_spaced` in
  concierge.py — a body Text holding `\xa0`, since renderers collapse a trailing regular space).
- **Modal / Card rounded corners: ❌ not possible on basic.** No `cornerRadius`/`shape`/`elevation`
  property — box shape is 100% renderer-decided. Rounded modals need Material (`MaterialDialog`/
  `MaterialCard`).
- **Font size / line-height / letter-spacing: ❌ none.** Text has only `text` + `variant`
  (h1–h5·body·caption). Can't set word/letter spacing. **Fix for "text too tight":** don't pack
  lines into one Text via `\n\n` — split each line into its **own** Text inside a Column (separate
  components get real vertical rhythm) and interleave `_spacer`s. `body` > `caption` for size.
  Applied to the reviews Modal and the Confirmation receipt.
- **Bottom line:** real padding, corner-radius, and typography controls are **Material-catalog**
  features. On basic, layout = `justify`/`align` + spacer Texts; size = `variant`.

### Design preference step (colour + layout, applied globally)
The first step is now **"Design preference"** — two `mutuallyExclusive` ChoicePickers on one surface:
- **Colour theme** → `theme.primaryColor` (confirmed to repaint buttons/chips/sliders).
- **Layout alignment** → the Column **cross-axis `align`** applied to **every step's root Column**
  (`Left→start`, `Center→center`, `Justify→stretch`). `data.ALIGNMENTS` maps label→value;
  `concierge._align(booking)` resolves it (fallback `stretch`).
The single **Apply** button fires `set_theme` carrying both `{theme, align}` (context bindings
`/theme_sel`, `/align_sel`); `advance()` stores `booking["align"]` and every builder threads it via
`_col("col", …, align=_align(booking))`. `new_search` keeps both; echo reads e.g. "Design · Ocean ·
Center". Pattern worth reusing: **one gated "preferences" surface can carry several global display
choices at once** (colour, density, alignment) — each a ChoicePicker, all applied on one Apply.
> Note: `align` is applied to each step's **root** Column only (not nested cards/tab bodies), so
> inputs inside tabs keep their normal layout. Whether `stretch` vs `start` visibly moves the
> Slider's built-in value label is renderer-dependent — pending the deploy screenshot.

### Theme-first flow (theme as the mandatory first interaction)
The user wanted theme selection to gate the whole flow — for **any** opening question, show the
theme picker first; only after **Apply theme** does it proceed to "Find a table". Implemented as a
dedicated **`theme_step`** (its own surface: title + `ChoicePicker` + "Apply theme" button):
- Default step is now **`theme`** (not `preferences`); the first no-action turn renders it.
- `set_theme` stores the hex and advances → `preferences` (the theme is the gate).
- The theme_step surface is itself themed once a colour is set, so "Apply theme" previews the colour.
- `new_search` keeps the chosen theme (no re-picking); `exit_gallery` returns to `theme` if no
  theme yet, else `preferences`.
- Keeping theme in its **own** step (vs inline in Preferences) is the clean way to make a selection
  mandatory before the rest of a form in A2UI — one surface per gated stage.

### How to change the theme colour 🎨
The colour lives in **`createSurface.theme.primaryColor`** — a hex string `"#RRGGBB"` that GE uses
for primary buttons and active borders (the `theme` object also takes `iconUrl` and
`agentDisplayName`). It is set at surface level, so it must go on **every** surface's `createSurface`.

**A. Change what colours the user can pick** (the theme selector) — edit two lists in
`v0p9/agent/data.py`:
```python
THEMES       = [{"label": "Sunset", "value": "sunset"}, …]   # picker chips (label shown, value = key)
THEME_COLORS = {"sunset": "#e8590c", …}                       # key → hex the renderer uses
```
Add/rename an entry in both (a label chip + its hex). The picker + "Apply theme" button do the rest.

**B. How it flows through the code:**
1. Preferences shows a `ChoicePicker` bound to `/theme_sel`; the **"Apply theme"** button fires
   `set_theme` with `{"theme": {"path": "/theme_sel"}}`.
2. `agent.advance()` maps the chosen name → hex via `data.THEME_COLORS` and stores it in
   `booking["theme"]` (persists across steps).
3. Every step builder passes it down: `concierge._msgs(sid, comps, dm, theme=booking.get("theme"))`,
   which adds `create["theme"] = {"primaryColor": booking["theme"]}` when set.

**C. To hard-code ONE brand colour** (no picker): drop the theme UI and just seed the booking, e.g.
`DEFAULT_BOOKING["theme"] = "#e8590c"` in `agent.py` — it then applies to every surface automatically.

> ✅ Confirmed in GE (2026-09-01): `primaryColor` repaints primary buttons, active chips, and slider
> tracks on the **basic** catalog. It's global-only — per-component colour still needs Material.

**Card / background colour — schema check (2026-09-01).** The basic-catalog **`Card`** is a *closed*
schema (`unevaluatedProperties:false`); its only props are `child`, `weight`, `id`, `accessibility`.
There is **no** per-component `backgroundColor`/`color`/`padding`/`fontSize` anywhere in basic — any
such key is rejected. Per-card/surface colour is a **Material-catalog** feature.

**🚪 Background probe — ❌ REJECTED by GE (2026-09-01).** Even though `theme` is
`additionalProperties:true` (so `backgroundColor`/`surfaceColor`/`secondaryColor` pass schema
validation), GE **ignored** them — card/page ground stayed white with a Sunset theme applied.
Verdict: on the basic catalog **only `primaryColor` is honored**; background/surface colour is a
**Material-catalog** feature. The probe keys were removed from `_msgs()` — we now send just
`primaryColor`. Don't bother re-sending background keys on basic.

### "User action triggered." bubble — NO A2UI fix (schema-confirmed 2026-09-01)
Checked the v0.9 `Action.event` schema: it's **closed** (`additionalProperties:false`), only
`name` + `context` — there is **no** `label`/`displayText`/`title` field to set the text of GE's
right-side "User action triggered." bubble, and any extra key is rejected. The bubble is GE-generated
chrome for the user's action turn (same class as the auto follow-up chips — GE app-side, not
agent-provided). The `functionCall` Action branch doesn't help either: basic-catalog client functions
are only validators/formatters (`required`, `email`, `formatCurrency`, `openUrl`, `and`/`or`/`not`) —
none advance a server step. **Mitigation (unchanged from v0.8):** own the agent's LEFT-side reply and
prepend a readable echo via `action_echo()` (e.g. "Theme · Sunset"). If the bubble is suppressible at
all, it'd be a GE **app/agent config** setting, not an A2UI payload field.

### Material catalog `catalogId` — HUNT RESULTS (2026-09-01)
Dug hard; the exact string is **not published anywhere public**:
- ❌ Not on the spec site — probed `…/catalogs/material/catalog.json`, `…/material_catalog.json`,
  `…/gemini_enterprise_composite_catalog.json`, and even the flat `…/v0_9/basic_catalog.json` a
  sample used — **all 404**. Only `…/catalogs/basic/catalog.json` exists.
- ❌ Not in open source — `google/A2UI` ships only `basic_catalog`; no material catalog files.
- ❌ GE docs ([component gallery](https://docs.cloud.google.com/gemini/enterprise/docs/a2ui-agents/a2ui-component-gallery-reference))
  list the Material components (MaterialSelect, MaterialTable, MaterialExpansionPanel, MaterialChips,
  MaterialButtonToggle, MaterialDatepicker, …) but withhold the `catalogId`.
- 🔑 **Why:** `catalogId` is a **negotiation token**, not a live URL. GE's frontend holds a registry
  of catalogs it can render; the agent stamps `createSurface.catalogId` with a string GE recognises.
  URLs are convention (globally-unique, human-inspectable) — GE does **not** fetch them. Our old
  `"material"` failed with "Catalog not found" because that literal isn't the registered id.
- GE reportedly ships a **`gemini_enterprise_composite_catalog.json`** (Material + GE components like
  `GoogleMap`/`WebFrameUrl`), but the exact id string is GE-internal.

**How to obtain it (needs GE/GCP access) — best first:**
1. **DevTools network capture (no deploy).** In GE, open an experience that renders Material (a Google
   sample agent / the component-gallery demo). F12 → Network → the streamed agent response → read the
   `catalogId` inside its `createSurface`. Also inspect the **request** GE sends the agent — it may
   advertise supported catalogs (client capabilities). Whatever GE emits is ground truth.
2. **Log it from our own agent (Cloud Logging).** Add a diagnostic callback that dumps the incoming
   A2A request + metadata to stdout; deploy; open in GE; read GCP → Logging. If GE advertises
   supported catalogs during negotiation, the material id shows there.
3. **Agent Garden / GE-provided A2UI sample** source, or **GE support / Admin console**.
- **Once found:** swap `CATALOG_BASIC` in `concierge.py` for the material id and switch component
  names (`Button`→`MaterialButton`, `ChoicePicker`→`MaterialSelect`, etc.). Unlocks real dropdown/
  filterable, per-component colour, background, MaterialTable, expansion panels.
  **Not a blocker:** the basic catalog already covers the concierge (ChoicePicker, Slider,
  DateTimeInput, Tabs, Modal, List, Card, CheckBox, TextField, Button+variant) + v0.9 wins
  (flat format, `formatString`, `checks`, List templates).
- How does the click **event** arrive back to the agent in v0.9 (shape of the incoming userAction)?
  — confirm when we wire interactions in the concierge.

# Neatly ordering A2UI section buttons in Gemini Enterprise

**Problem:** a set of "section" buttons (Summary, Current Strategic Priorities, Key
Industry Trends…, Bottom Line) renders **scattered** — uneven widths, ragged rows,
odd gaps.

**Why it happens:** in A2UI v0.8 a `Button` **sizes itself to its label text**. When
you place buttons in a `Row` (especially with `distribution: "spaceBetween"` or relying
on wrap), each button is a different width because each label is a different length, so
they never line up. A two-item last row with `spaceBetween` also pushes the two buttons
to opposite edges (the "7. …" left, "Bottom Line" right gap you see).

**Fix:** stop letting the label decide the width. Either stack the buttons full-width
in a single `Column`, or lay them in fixed rows where each cell is forced to equal width.

---

## Option A — Single-column list *(recommended: always neat, nothing unverified)*

Put every button in one `Column` with **`alignment: "stretch"`**. Stretch makes each
child fill the card's width, so all buttons become the **same width regardless of label
length** and stack in a clean, ordered list.

```json
[
  { "id": "root", "component": { "Card": { "child": "col" } } },
  { "id": "col", "component": { "Column": {
      "alignment": "stretch",
      "children": { "explicitList": ["b1","b2","b3","b4","b5","b6","b7","bottom"] }
  } } },

  { "id": "b1", "component": { "Button": { "child": "b1_l",
      "action": { "name": "open_section", "context": [
        { "key": "section", "value": { "literalString": "summary" } } ] } } } },
  { "id": "b1_l", "component": { "Text": { "text": { "literalString": "1 · Summary" } } } },

  { "id": "b2", "component": { "Button": { "child": "b2_l",
      "action": { "name": "open_section", "context": [
        { "key": "section", "value": { "literalString": "priorities" } } ] } } } },
  { "id": "b2_l", "component": { "Text": { "text": { "literalString": "2 · Current Strategic Priorities" } } } }

  /* …b3–b7 the same… */,

  { "id": "bottom", "component": { "Button": { "child": "bottom_l", "primary": true,
      "action": { "name": "open_section", "context": [
        { "key": "section", "value": { "literalString": "bottom_line" } } ] } } } },
  { "id": "bottom_l", "component": { "Text": { "text": { "literalString": "Bottom Line" } } } }
]
```

Notes:
- `alignment: "stretch"` on the Column is the whole trick — it equalizes width.
- Keep the number **inside the label** (`"1 · Summary"`) so the sequence reads top-to-bottom.
- Make `Bottom Line` `primary: true` so the final action stands out as a footer.
- Wrap the Column in a `Card` for padding/background (optional but tidier).

---

## Option B — Two-up grid *(if you specifically want a 2-column grid)*

A `Column` of `Row`s, **two buttons per Row**, each button given equal width with
**`weight: 1`** (envelope-level, sibling of `id`). `spaceBetween` then distributes them
evenly instead of by label length.

```json
[
  { "id": "root", "component": { "Card": { "child": "col" } } },
  { "id": "col", "component": { "Column": {
      "alignment": "stretch",
      "children": { "explicitList": ["r1","r2","r3","r4"] } } } },

  { "id": "r1", "component": { "Row": {
      "alignment": "stretch", "distribution": "spaceBetween",
      "children": { "explicitList": ["b1","b2"] } } } },

  { "id": "b1", "weight": 1, "component": { "Button": { "child": "b1_l",
      "action": { "name": "open_section", "context": [
        { "key": "section", "value": { "literalString": "summary" } } ] } } } },
  { "id": "b1_l", "component": { "Text": { "text": { "literalString": "1 · Summary" } } } },

  { "id": "b2", "weight": 1, "component": { "Button": { "child": "b2_l",
      "action": { "name": "open_section", "context": [
        { "key": "section", "value": { "literalString": "priorities" } } ] } } } },
  { "id": "b2_l", "component": { "Text": { "text": { "literalString": "2 · Priorities" } } } }

  /* r2 → b3,b4 · r3 → b5,b6 · r4 → b7, bottom … all Buttons carry "weight": 1 */
]
```

⚠️ **Caveat on `weight`:** it is documented in GE's component-gallery reference as a
common property, but its rendering in GE chat is **not fully verified** — some builds
appear to ignore it. If the two columns still come out uneven after adding `weight: 1`,
GE isn't honoring it in your environment → **use Option A** (which needs no `weight`).
Always `alignment: "stretch"` on the Row so the two cells are equal height too.

---

## A2UI layout cheat-sheet (what actually controls alignment)

| Property | Where | Effect |
|---|---|---|
| `alignment: "stretch"` | on `Column`/`Row` | children fill the cross-axis → **equal widths** (Column) / equal heights (Row). The single most useful fix here. |
| `distribution` | on `Row`/`Column` | spacing along the main axis: `start`, `center`, `end`, `spaceBetween`, `spaceAround`, `spaceEvenly`. Avoid `spaceBetween` for a 2-item last row — it pushes them to the edges. |
| `weight: N` | envelope level (sibling of `id`) | proportional share of space within a Row/Column (flex-grow-like). Needed for equal-width **grid** cells — but unverified in GE (see caveat). |

## Recommendation for your section menu

Use **Option A** (single-column, `alignment: "stretch"`, number-in-label, `Bottom Line`
as a primary footer button). It's the only layout that is guaranteed neat in GE today —
no dependence on `weight`, no ragged rows, and the numbered order reads naturally
top-to-bottom. Switch to Option B only if a 2-column grid is a hard requirement and you
confirm `weight` renders in your GE build.

---

## Bonus: also cleans up the follow-up questions

The same rule applies to the "Select a follow-up question" chips at the bottom — stack
them in a `Column` with `alignment: "stretch"` (each on its own full-width row) rather
than a wrapping Row, and they'll line up the same way.

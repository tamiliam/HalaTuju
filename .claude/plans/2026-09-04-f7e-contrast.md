# F7e — the contrast sprint (plan, 2026-09-04)

Closes **TD-224** (high, live in LIGHT mode today). Roadmap:
`docs/plans/2026-07-29-layer1-themes-roadmap.md` → "F7e — the contrast sprint".

---

## What the measurement actually says (re-derived today, not read off the ticket)

The roadmap framed the owner's decision as *"move `ground-400` (one edit) or move ~150 call sites
to `ground-500`"*. **Both halves of that were wrong, and the second option does not work.**

| claim in the roadmap | measured today |
|---|---|
| ~150 call sites use the muted token | **404**, across **102 files** |
| moving them to `ground-500` fixes it | it does **not** — `ground-500` on a well (`ground-100`) is **4.39** against a bar of 4.5, so the chip cluster in TD-224 stays failing |
| the choice is token *or* call sites | there is a third: **`ground-400` is named for the SMALLER role.** It is the placeholder stop (`.input` says `placeholder:text-ground-400`, and the dark block literally comments it *"placeholder text"*) and is used as muted text in ~395 places. **3 call sites** rely on the placeholder meaning. |

**The ground ramp, measured in both modes:**

| ink | light: card / page / well | dark: card / page / well |
|---|---|---|
| `ground-400` (today) | 2.54 / 2.43 / **2.31** | 5.78 / 6.99 / **4.06** |
| `ground-500` (today) | 4.83 / 4.63 / **4.39** | 9.96 / 12.04 / 7.00 |

⚠ **Dark fails too, on a well** (4.06). The ticket recorded this as a light-mode problem; the well
case is bad in both.

## Owner ruling, 2026-09-04

1. **Move the token; move placeholders out.** ~10 edits rather than ~400, and it leaves no trap.
2. **Do the tone fills in the same sprint.** They are the other half of the same defect.

---

## Deliverable

**One coherent thing: give the four TONE ramps and the muted-ink stop the treatment the BRAND
already has, and make the gate name the pairs.**

### 1. The muted-ink stop (≈11 files)
- `--ground-400` is **redefined as the muted-INK stop** and moved to a value that passes 4.5 on the
  tightest ground it ever sits on (the well), in **both** modes:
  - light `#656d7a` → card 5.22 / page 5.00 / well **4.74**
  - dark `#b4bac4` → card 7.52 / page 9.09 / well **5.28**
- **New `--ground-placeholder`** keeps today's `#9ca3af` in both modes, so placeholders look
  exactly as they do now. Three call sites move onto it (`globals.css` `.input`, `/search`,
  `CommandPalette`).
- The ~6 `disabled` uses of `text-ground-400` are read individually: WCAG 1.4.3 exempts inactive
  controls, and TD-224 deliberately did not count them. Any that should stay faint move to
  `ground-placeholder` or `-300` with the reason at the line.

### 2. The tone fills (≈35 files, ~46 call sites)
- `--positive-fill / -fill-ink`, and the same for `caution`, `critical`, `info` — the **F7a
  `--brand-fill` pattern, verbatim**, resolving to a different stop per mode.
- ~46 `bg-<tone>-[456]00 text-white` sites move onto the role. Worst today: the cockpit **Accept**
  button, **1.40** in dark and **3.30** in light.
- Tone INK as small text (`text-critical-500` etc. on white, 3.19–3.76) gets the **F7b** move —
  one stop darker — where it is text rather than a shape.

### 3. The gate (≈4 files)
- `contrast.py` gains a pair per tone fill and a pair for muted ink on each ground, **in both
  modes**. Today its seven pairs are all brand-versus-ground, so this whole class sits outside it
  while it passes correctly.
- `theme.test.ts` ordering assertions re-checked — the dark block warns *"change a stop here and
  check the ROLE, not the number"*, and this sprint changes a stop.

### Deliberately NOT in this sprint
**TD-223 (links `info` vs `brand`) is DEFERRED.** The roadmap said to fold it in because it
"touches the same call sites". Measured: **89 sites across 49 files**, and the overlap with the
tone-fill files is small — it is a different change with a different blast radius, and adding it
takes this sprint from ~48 files to ~90. It becomes **F7f**.

**Estimated files: ~48.** Over the 40 guideline, but ~46 of them are one mechanical class swap
produced by a single classified codemod; the cap is about reviewability and those review as one
change. Say so at close rather than hiding it.

---

## Lessons from `docs/lessons.md` that bind this sprint, and how each is handled

| lesson | how this sprint accounts for it |
|---|---|
| **"A gate is blind to every pair it does not name" (recorded THREE times: F7b, F7c, F7d)** | Widening `contrast.py` is a deliverable, not a follow-up. Every new role gets a named pair in both modes, and the bite-check is to move a role to a failing stop and watch the gate refuse. |
| **"When you fix one token FAMILY, ask which sibling families have the same shape"** | This sprint IS that lesson's bill: brand got `--brand-fill` (F7a) and the `-500`→`-600` text move (F7b), and the four tones — which reverse in dark identically — got neither. All four are done together, not one. |
| **"Measure the RENDERED result, not the declared one"** | Values above were computed from the actual composited pairs, not chosen by eye. At close the sweep in `docs/contrast-sweep.md` is re-run over all 25 routes in **both** modes and the before/after counts reported. |
| **"Distrust a scan that returns zero — plant a defect to prove it bites"** | The sweep's own doc requires this and F7d already got burned by a clean landing page. Two planted defects before believing any zero. |
| **"Never generate a regex; sweep for control bytes after any generated write"** + my own **"the right character from the WRONG ALPHABET"** (S-ASSIGN) | The codemod is a classified list of literal from→to pairs, not a generated pattern. Post-write scan for control bytes **and** out-of-script characters, refusing rather than warning. |
| **"Read a codemod's residue rather than counting it"** | After the sweep, grep the OLD classes and read every survivor, and grep the NEW token in comment context for stale tense. |
| **"Bite-check by injecting a fault AND VERIFYING IT LANDED"** + my own **"a bite that cannot be injected has told you nothing"** (S-ASSIGN) | Every bite prints the changed line before running the suite. Anchors are read from the bytes first — **this repo is CRLF in some files and LF in others**. |
| **"Classify a token's call sites by what they DO before choosing a role"** (F7a) | Already done, and it is what produced the third option above: 3 placeholder sites vs ~395 muted-text sites. The token was named for the smaller role. |
| **"`next build` before believing any of the other gates"** | In the gate list; it lints before it emits and the other three do not run ESLint. |
| **"A surface with no way to be looked at has NOT been reviewed"** | The sandbox covers all 25 routes including the cockpit fixture (F7c). Both modes walked. |
| **"Nothing visible changes today has to be asked of the SCREEN as well as the API"** | Inverted here and must be said plainly: **this sprint IS visible.** Every muted label in the product darkens and ~46 filled buttons change ink. That is the point, not a side effect — do not write "nothing a visitor sees changes". |

## Decisions from `docs/decisions.md` that constrain the approach

- **F7a's fill role** — `--brand-fill: var(--brand-600)`, **never a literal**, because a tenant's
  colours arrive as inline styles on `:root`. The four tone roles follow the same indirection.
- **F7a: a filled control cannot be fixed by moving it down the ramp** — `brand-400` let white text
  read and dropped the button to 2.52 against its own card. Expect the same trap on the tones:
  the fix is a role with its own ink, not a lighter fill.
- **A2's `link_on_card` pair asserts `brand`** — so TD-223 is settled design, merely unbuilt. That
  is why deferring it is safe: nothing has to be re-decided, only converted.

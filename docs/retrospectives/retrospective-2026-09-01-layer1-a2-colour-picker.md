# Retrospective — Layer 1 A2: the colour picker, and the contrast gate

**Date:** 2026-09-01
**Branch:** `feat/layer1-a2-colour-picker`
**Roadmap:** `docs/plans/2026-07-29-layer1-themes-roadmap.md`, arc A sprint 2
**Migration:** none.
**Design of record:** the working mock approved by the owner 2026-09-01 —
<https://claude.ai/code/artifact/97405467-1fd5-45e3-97be-d83c5fb8739e>

---

## What was built

An `org_admin` picks one colour, sees it immediately, and **cannot ship one nobody can read.**

| Piece | File |
|---|---|
| The gate | `apps/courses/contrast.py` (new) |
| The endpoint | `AdminOrganisationThemeView` — GET/PUT/DELETE, org-fenced, audited |
| The browser's copy | `src/lib/contrast.ts` (new) |
| The tab shell | `src/app/admin/programme/page.tsx` (rewritten) |
| The two tabs | `components/admin/ProgrammeConfigTab.tsx` (moved), `ProgrammeColoursTab.tsx` (new) |
| The product fix the maths found | 54 filled controls across 21 files |

---

## The finding that shaped the sprint

**The gate, as first written, refused the platform's own live blue.**

Every pair it checks is counted in the web app, not imagined. One of them was `text-white` on
`bg-primary-500` — small white text on the lightest usable brand stop — and for `#137fec` that
measures **3.98** against AA's 4.5. Orange failed the same single check. Eleven of sixteen realistic
brand colours passed; every unfair refusal traced to that one row.

That is not a mis-calibrated gate. It is a correctly-calibrated gate reporting something true:
**F4 had already ruled that a filled control the user ACTS on carries `bg-primary-600`, and 52 of
them had never moved.** The maths found the stragglers.

So A2 moved them. What is left on `-500` is dots, progress bars, toggles and `aria-hidden` icon
circles — **shapes, not words** — which is why the pair table has exactly one row held to WCAG's
3:1 for non-text rather than 4.5.

Measured after the move: **13 of 18** realistic brand colours pass, our own blue among them, and
every refusal is a colour a person genuinely could not read.

**`test_the_platform_colour_passes_its_own_gate` is now the calibration canary**, and its docstring
says what to ask when it fails: *which pair, and is the PRODUCT wrong there?*

---

## What went wrong

**1. The codemod was blind to a pair composed across two elements.**

*Symptom.* After the sweep, 17 `bg-primary-500` uses remained, reported as shapes. Three were not.

*Root cause.* The codemod matched within ONE class string. CSS does not work that way: the landing
page's stats band sets the background on a `<section>` and `text-white` on its child grid, and the
course card's rank badge does the same. Both are text pairs; both were missed. The count looked
right, which is what made it convincing.

*Fix.* Read all 17 survivors rather than trusting the number, and correct the two by hand. The
third — an `aria-hidden` icon inside a circle — is genuinely a shape and correctly stayed.

*System change.* Recorded as a lesson: when a codemod's unit is a class string but the property's
unit is a rendered element, the residue has to be read, not counted.

**2. tsc went 24 → 6, and jest passed 1,573 tests over a file that does not parse.**

*Symptom.* A dropping error count, which looks like an improvement.

*Root cause.* A JSX comment I added inside a `cond && (` expression — **and** containing braces, so
`#{rank}` closed the expression container early. Two faults in one line, both variants of a lesson
already written down twice. TypeScript stopped parsing `CourseCard.tsx` and therefore stopped
reporting the pre-existing errors in it.

*Why nothing else caught it.* `jest` does not type-check, and no test renders that component.

*System change.* None needed — the rule *"expect exactly 24, never fewer than before"* already
existed and is exactly what caught this. It is now three-for-three.

**3. The screen offered to save a change nobody had made.**

*Symptom.* A rendered test found Save **awake on load** for an organisation using the default.

*Root cause.* `changed` compared the draft against the STORED colour, which is `''` when there is no
row — while the draft is seeded with the platform colour, because that is what the organisation is
already showing. So the two differed on arrival.

*Why it mattered more than it looks.* Pressing it would have created a row that changes nothing
visible while quietly taking the organisation off the stylesheet — and off the "reset really
resets" guarantee that makes trying a colour safe.

*Fix.* Compare against the EFFECTIVE colour (`stored || platform`).

*System change.* This is the third sprint running where a rendered test found something no pure test
could see. The house rule holds; nothing to add.

**4. I hard-coded the platform hex three lines under my own comment saying not to.**

`theme.test.ts` failed the build. The guard did its job; the note did not. Now read from
`PLATFORM.brandColour`.

---

## What went well

- **Four bite-checks, all landing**, each injection verified before the suite ran:

  | Injection | Caught by |
  |---|---|
  | Save stops consulting the readability check | 2 rendered cases |
  | The server stops refusing an unreadable colour | 4 endpoint tests |
  | Shapes held to the text bar again (the pre-A2 mistake) | 4 tests, canary first |
  | A pair loses its label in `en.json` | the label-coverage guard |

- **The config tab moved with its eight rendered tests untouched.** That is what says a move was a
  move rather than a rewrite wearing one's clothes.
- **The browser and the server agree by construction** — same pair keys, same golden fixtures, both
  suites asserting the same 13-pass / 5-refuse spread.

---

## The tab shell was a retro-fit, exactly as written

The roadmap's open question 3 said: *"Whichever of the two is built first OWNS the tabbed shell …
Build either as a single-purpose page and the other arrives as a retro-fit."* Layer 0 Sprint 5 built
a single-purpose page. A2 paid the retro-fit — which was small, because the warning meant nobody was
surprised by it.

---

## Numbers

| Gate | Before | After |
|---|---|---|
| pytest | 5706 | **5738** |
| jest | 1548 | **1573** |
| `tsc --noEmit` | 24 | **24** (baseline, TD-221) |
| `next lint` | 0 errors | **0 errors** |
| i18n parity | 4581 × 3 | **4629 × 3** (ms/ta first drafts) |
| `next build` | clean | clean |

---

## At deploy

**No migration. api + web.** Push, confirm both builds SUCCESS.

**⚠ THIS ONE IS VISIBLE, unlike the last seven.** 54 filled controls go one shade darker in light
mode — the main button on student and admin screens alike. Not jarring, and it is the shade F4
already ruled correct, but it is the first Layer 1 deploy a person could notice. Say so rather than
repeating "nothing a visitor sees changes".

Post-check: sign in as the BrightPath `org_admin` (**elanjelian@me.com**, not the super account),
open Programme → Colours, confirm the palette draws and the six checks pass on the current colour.
**Change nothing.**

---

## Owed

- **ms/ta for the 48 new `admin.programme.*` keys are my first drafts.**
- **TD-222 — the dark gate.** In dark, `white` on `brand-600` measures 3.2 for the platform's own
  colour, because F3b swapped the shade end toward white for tinted panels without accounting for
  the same stops carrying white button text. `check_tokens` already takes the mode, so switching it
  on is an argument — after the ramp is fixed. **F7 must not ship before both.**
- **A browser pass.** The gate, the endpoint and the screen are covered by 47 tests between them,
  but nobody has clicked it. TD-182 still breaks admin Google sign-in on localhost.

---

## Next

**A3 — draft, preview, publish, revert.** Changing a colour is not a live experiment on applicants.
It relaxes A1's `OneToOne` to several rows per organisation (a constraint drop plus a status column,
both additive), mirrors the sponsor-terms shape already in the codebase, writes an `AUDIT` line per
publish, and gives one-click revert.

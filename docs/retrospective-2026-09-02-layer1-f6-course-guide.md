# Layer 1 F6 — the last unpainted surfaces

**2026-09-02. Web only. No migration.** Branch `feat/layer1-f6-remaining-surfaces`.
jest 1583 → **1595**; tsc **24** (baseline, TD-221); lint **0**; i18n **4636 × 3**; build clean.
Seven guards bite-checked, each injection verified as landed before the suite was run.

---

## What shipped

36 files, ~860 utilities. **The repaint is finished** — nothing under `src/` carries a raw Tailwind
colour, a raw hex, or an arbitrary-value colour class. The only thing between here and dark mode is
F7 itself, and its two blockers (TD-222, the cockpit fixture) are unchanged by this sprint.

The sprint's shape was three-quarters mechanical and one-quarter judgement, as every repaint has
been. The judgement is what is written down below.

---

## ▶ THE FILE TABLE HAD AGED, FOR THE FOURTH SPRINT RUNNING — and this time so had the TITLE

The roadmap said *"F6 — Public course guide. 36 files."* The count was right to the file. The
**description** was not: what was actually left was the course guide plus `components/contracts`,
`components/emails`, `components/sources`, `components/reviewers`, the interview panel and
`content/manual`. F7's whole job is to assert that every surface is converted, so a narrow reading
of F6 would have left it blocked by files nobody had scheduled.

The standing lesson says re-derive the file TABLE at sprint start. This adds a corollary that cost
nothing to check and would have cost a sprint to miss: **when a plan names a surface, re-derive the
surface too.** One grep for unconverted files answered both questions at once.

---

## ▶ THE LOAD-BEARING DECISION IS A REFUSAL TO WIDEN THE VOCABULARY

Two sets did not fit:

| set | wanted | had |
|---|---|---|
| STPM subject chips | 16 hues over 17 codes | 8 |
| institution type **+** qualification level, side by side on one card | 13 | 8 |

The obvious move was to grow `--category-*` from eight swatches to sixteen. It was refused, and the
reason is a property of the family rather than a matter of taste: the eight deliberately avoid
green, blue, amber and red so that a category chip is never mistaken for a status. Sixteen hues that
dodge those four, stay apart from **each other**, and survive the light→dark role swap do not exist.
Shipping sixteen muddy pastels would have produced exactly the indistinguishability the family was
created to prevent — F2c's own finding, re-introduced at twice the scale.

Both sets went neutral instead, and neither lost anything:

- **Subject chips** render beside their own full name — `BIO  Biology`. The hue decoded nothing.
- **Level chips** say "Diploma". `/search` has a Level dropdown. And an *unrecognised* level had
  **always** rendered grey, so grey level chips have been in the product from the start; this only
  makes the recognised ones agree with them.

**A third option was considered and killed by reading the code.** Colouring subjects by STREAM
(science vs social) looked ideal — the two sets already existed in the file. `filterSubjects` shows
one stream at a time, so every chip on screen would have been the same colour. It took one look at
the caller to find that, and the idea had already been written into a plan.

---

## ▶ THREE MORE COPIES OF THE F4 ROLE-PALETTE BUG, FOUND BY GREPPING RATHER THAN READING

The checklist item added after F2b — *grep the surface for `Record<…, colour>` lookup tables* —
earned its place three times in one sprint:

1. **institution type → colour** in `courseBadges.ts` AND `RequirementsCard.tsx`, with a **fourth**
   copy hard-coded inline in `stpm/[id]/page.tsx`.
2. **the STPM subject vocabulary** (names, streams, filter, legend) byte-identical in
   `course/[id]/page.tsx` and `pathway/stpm/page.tsx`.
3. **the matriculation tracks** byte-identical in `course/[id]/page.tsx` and
   `pathway/matric/page.tsx`.

Every pair is on two pages **a student moves between**, one click apart, while comparing the exact
thing the colour encodes. A drift would have shown the same Politeknik teal in the search grid and
orange on the course page, and the student would have blamed the data.

`RequirementsCard`'s six numbers were carried over **unchanged**, so the merge moved nothing a
person sees. That was deliberate: a de-duplication and a re-colouring in one commit is a diff
nobody can review.

---

## ▶ A CATEGORY SET THAT STOPS A THIRD OF THE WAY THROUGH IS NOT A CATEGORY SET

The institution card carried a `stateColors` map: a pastel background for six of Malaysia's sixteen
states, grey for the other ten. It survived every previous sprint because it looked like decoration.

The codemod made it undeniable — it renamed four of the six onto **tones**, so Kuala Lumpur became
`critical` and Johor `positive`. Reading that output is what surfaced the real question, which was
never "which token?" but **"what is this colour claiming?"** It was claiming a distinction it
abandoned after six members, on a fact already written on the card in words.

Removed. All cards take what ten of the sixteen already had. The general shape is worth keeping:
**when a lookup table covers only part of its domain, the colour is asserting something false about
the members it omits** — and the fallback branch tells you how big that omission is.

---

## ▶ THE FIFTH HIDING PLACE, AND THE GUARD FINALLY STOPPED BEING A LIST

`src/app/quiz/page.tsx` and `src/app/stpm/quiz/page.tsx` set their entire page ground with
`bg-[#f5f7f8]`. That is F3's discovery exactly — an arbitrary-value class, invisible to any scan
that enumerates colour NAMES. F3 wrote the guard and scoped it to `F3_FILES`, so it could never
have seen these two.

Running list, in order found: inline styles and gradients (F1); the stylesheet's own `@layer` rules
and a control with no declared background (F2a); lookup tables returning class strings (F2b);
arbitrary-value classes and raw hex in SVG props (F3); **the same arbitrary-value class in files no
list covered (F6)**.

The pattern is not that new hiding places keep appearing — it is that **a guard scoped to a file
list is blind by construction to whatever is not on the list**, which is precisely where the next
one will be. F6 could finally fix that, because it is the sprint after which no exemption is needed:
the three scans now run over `walkFiles('src')`.

**The per-surface blocks were kept, and the test says why.** Each carries its own sprint's reasoning
and fails with a message naming its surface; the tree-wide one fails with a list of every file in
the app. **Assume there is one more.**

---

## ▶ TWO GUARDS ACCUSED THEIR OWN DOCUMENTATION — the F2a lesson, twice

F2a established that a guard reading source text must strip comments, or the only way to pass it is
to stop explaining yourself. Both new failures were that lesson again:

- The raw-colour scan flagged **this sprint's note** explaining why the state tint was removed —
  which has to name `bg-gray-50` to explain it.
- The white-literal check flagged **`contrast.ts`**, whose comment states the very invariant the
  check enforces and therefore quotes both sides of it.

The scan that already stripped comments (hex) was silent. The two that did not, fired. Worth noting
that F2a fixed the guard it was looking at and not its neighbours — **a lesson applied to one call
site is a lesson half-applied**, which is the same shape as this codebase's own "wrapped the N call
sites that exist" lesson from August.

---

## ▶ A FALLING `tsc` COUNT AGAIN, AND THIS TIME IT WAS A RISING ONE

The count went 24 → **26**. That direction is the easy one: a rising count is a new error you go and
read. Both were mine, both real, and both the same cause — a `TrackId` union moved into a shared
module while a component prop was still typed `string`. Fixed in two lines.

The asymmetry named in F2a's lesson held: nothing about a rising count needs discipline, because
the errors name themselves. It is the FALL that has to be treated as suspicious on purpose.

---

## ▶ ONE FINDING RECORDED RATHER THAN FIXED

The new sandbox surface is the first screen in the product's history that renders **all eight**
category swatches at once. Measured in dark mode, the closest pair is
`Politeknik rgb(19, 78, 74)` and `Kolej Komuniti rgb(22, 78, 99)` — distinct by value, and hard to
separate by eye. `Universiti rgb(76, 29, 149)` and `PISMP rgb(112, 26, 117)` are the next closest.

It is **not F6's mapping** — those six numbers came from `RequirementsCard` unchanged, and every
prior screen rendered one badge at a time, so nothing had ever put the set beside itself. It is a
property of F2c's family, and changing `--category-*` moves every category set in the product
(institution types, fields of study, entry conditions, staff roles, exam types, request components,
billing). **That is an owner decision and it belongs to F7's review pass**, not to a repaint sprint.

The distinctness guard passes, correctly — it asserts distinct VALUES, which is what a test can
check. "Tellable apart by a person" is what the sandbox is for, and this is the sandbox doing its
job on the first day it could.

---

## ▶ THE FIXTURE READ AS A BUG BEFORE THE SURFACE DID

The first `merit_label` in the new fixture was `'Good'`, which is outside the closed set
(`High | Fair | Low`) and falls through to **"Low Chance"** with a red bar — on all eight cards. A
reviewer opening that screen sees eight alarming cards and starts debugging the thing they were
asked to look at.

Same family as F1's far-future date lesson: **a fixture that renders a legitimate-looking screen is
part of the deliverable**, because a design surface is read, not asserted. It cycles High/Fair/Low
now, which costs nothing and additionally shows the merit tones honestly.

---

## What did NOT change, deliberately

- **Link colour.** `text-info-600 hover:underline` and `text-primary-600 hover:underline` both exist
  across the product, split by which sprint converted the file. A2's contrast gate has a
  `link_on_card` pair asserting **brand**, so the design of record says brand — but making that true
  everywhere touches files from F1 through F5 and is a product-wide decision, not a leftover of this
  sprint's surface. **Raised as TD-223 for F7's review pass.**
- **`formatPhone`**, duplicated in the same two files as the subject vocabulary. It is not colour,
  and widening a repaint sprint into a general de-duplication makes the diff unreviewable. Noted.
- **The sandbox's own chrome** goes deep amber in dark. That is the `caution` ramp working as
  designed on a deliberately loud banner, on a page that never ships.

---

## For F7

**The repaint is complete and the two blockers are unchanged.**

1. **TD-222 — the dark brand ramp cannot carry white button text.** `brand-600` measures 3.22 and
   `brand-700` 2.59 for the platform's own colour. Flipping dark on today renders 106
   `bg-primary-600` buttons white-on-pale. **Fix the ramp, THEN widen A2's gate to both modes** —
   an argument to `check_tokens`, not a rewrite.
2. **The officer cockpit has never been seen in a browser.** It needs a large
   `AdminApplicationDetail` sandbox fixture, and the sandbox forbids a hand-written approximation.

**And two new ones, both small:**

3. **TD-223 — links are `info` on some surfaces and `brand` on others.** Settle it during the review
   pass; the gate already says which one is right.
4. **The eight category swatches, seen together for the first time** — see above. Open
   `/sandbox/course-guide` in both modes and decide whether the closest pairs need separating.

**There is no ceiling left to lower.** Every previous sprint handed F7 a number; this one hands it
the strong assertion instead, which is what it actually needed.

# Layer 1 F7a — the filled control becomes a role, and dark is gated

**2026-09-02. web + api. No migration.** Branch `feat/layer1-f7a-brand-fill-role`.
jest 1595 → **1597**; pytest 5757 → **5765**; tsc **24** (baseline); lint **0**; i18n **4640 × 3**;
build clean. Three guards bite-checked, each injection verified as landed first.
Reviewed in a browser in both modes.

---

## ▶ THE TICKET NAMED A SYMPTOM, AND THE FIX WAS TWO THINGS

TD-222 read: *"the dark brand ramp cannot carry white button text — `white` on `brand-600` measures
3.22, `-700` measures 2.59, for the platform's own colour."* Both numbers were right. The diagnosis
was half a diagnosis.

Measuring **18 realistic tenant colours** against **every pair the product renders**, in both
modes, found two independent faults:

| | what was wrong | how many colours it broke in dark |
|---|---|---|
| **the ramp's distances** | F3b aimed the dark shade end at white — correct — and kept LIGHT's step sizes. At 15% toward white, `brand-600` is barely lighter than the tenant's own colour, and the app spells its LINK ink `text-primary-600`, on a `#1f2937` card. | **14 of 18** failed `link_on_card` |
| **one stop, two roles** | a filled button and a link were spelled with the same stop while wanting opposite things on a dark card | all of them |

**Building only what the ticket described would have fixed the buttons and left every link in the
product unreadable, with a green suite.** The habit that caught it is cheap: before implementing a
recorded fix, re-derive the failure over a spread of realistic inputs and over every consumer of
the thing being changed — not only the one the ticket names.

---

## ▶ THE FIRST HALF COST FOUR NUMBERS AND CHANGED NO CALL SITES

`_SHADE_MIX` splits by mode: light keeps `.15 / .30 / .45 / .60`, dark becomes
`.45 / .60 / .75 / .86`. After that, **all 18 colours pass every text pair the product renders.**

Nothing about the direction was wrong and nothing about the light ramp moves. The dark set in
`globals.css` was regenerated from `brandRamp()` rather than typed, and the shared golden fixture
was re-derived **by hand on both sides** — a golden copied out of the implementation pins whatever
that implementation does, which is the one thing the fixture exists to prevent.

---

## ▶ THE SECOND HALF COULD NOT BE FIXED BY MOVING THE BUTTON, AND THAT IS NOW A TEST

The obvious next move, once white text failed on the dark fill, is to walk the button DOWN the ramp
until the contrast passes. **It does pass — `brand-400` measures 5.82.** It also drops the button to
**2.52** against its own card, under the 3.0 a non-text shape needs, and the control stops looking
like a control.

Squeezed from both ends, the escape is the one **F2c** already took for the category family: swap
the ROLE, not the value. In dark a brand button is a **pale fill with dark ink**.

```
              light                     dark
fill          brand-600                 brand-800
hover         brand-700                 brand-900
ink           white                     ground-50 (the page it punches through)
```

Measured over nine colours: ink-on-fill never below **5.82**, fill-against-card never below
**4.82**. Light is byte-identical to before.

**The near-miss is now a pair.** `filled_button_visible` sits beside `filled_button` in the gate, so
the second constraint is not something the next person has to happen to think of. That is the
transferable part: **a control has to be findable as well as readable, and both belong in the
table.**

---

## ▶ `var()` INDIRECTION IS WHY `branding-context` NEEDED NO NEW CODE

`--brand-fill: var(--brand-600)`, not `--brand-fill: 16 102 194`.

A tenant's colours arrive at runtime as INLINE styles on `:root`. An indirection resolves against
whatever that element currently carries, so a tenant's button follows their colour for free. A
literal would have painted **every tenant's primary button in HalaTuju's blue** while every other
brand surface followed theirs — and it would have read as a branding bug on one control rather than
as a CSS mistake, which is the sort of thing that survives three sprints.

---

## ▶ THE GATE RUNS IN BOTH MODES NOW, AND TWO COLOURS HONESTLY LOST

`failures_all_modes` is what the save path calls. A colour is stored once and rendered in both, so
a tenant refused only after somebody flips the switch has been let down by the gate rather than
protected by it. Every check row on the screen carries its mode, because the same pair now appears
twice with different numbers and a person reading two identical labels would assume one was a bug.

**`#010066` and `#111827` moved from PASSES to REFUSES.** Both near-black, both failing only the
dark link pairs and nothing else. That is the gate telling the truth: they were never unreadable
before *because nobody could see the surface they are unreadable on*.

Two pair names changed for accuracy: `filled_button_dark` was never about dark mode — it named the
darker sibling stop — and became `filled_button_hover` before the old name turned into an outright
lie.

---

## ▶ ONE THING DELIBERATELY NOT FIXED, WITH A NAME

`ui_shape` — dots, progress bars and focus rings at `brand-500` — is **exempt in dark**.
`brand-500` is the identity stop and is byte-identical across modes by owner ruling, so a dark
tenant colour makes a dark shape on a dark card: **10 of 18 measure under 3.0**.

The fix is a `--brand-shape` role, the same move `--brand-fill` just made, over ~50 files that are
almost entirely one repeating pattern (`focus:ring-2 focus:ring-primary-500 focus:border-primary-500`
on form inputs). **That is F7b.** Gating it today would refuse ten tenants for a defect of ours —
precisely the mistake A2's docstring warned about — so it is an exemption with a test that names it
and asserts the defect is real, not a silence.

---

## ▶ THE F4 REGEX LESSON RECURRED, THROUGH A PATH I HAD ASSUMED WAS SAFE

Three guards were updated with a `python - <<'PY'` heredoc. One of them needed a word-boundary
escape, and it arrived in the file as a literal **BACKSPACE byte (0x08)** — F4's bug, verbatim,
eleven days later.

It was caught only because that assertion **counts** occurrences and got 0. Phrased as
`not.toMatch` it would have been a dead test with a green tick, which is what happened in F4.

Two habits, and the second is the one that generalises: type regexes by hand with an editing tool;
and **sweep for control characters after any generated write**
(`grep -P '[\x00-\x08\x0b\x0c\x0e-\x1f]'`) rather than trusting that this heredoc was the safe one.

---

## ▶ A MEASUREMENT THAT NEARLY BECAME A BUG REPORT

Toggling `data-theme` and reading `getComputedStyle` in the same `page.evaluate` returned OLD values
for some elements and new ones for others — which reads exactly like half the buttons failing to
update. I was one step from writing it up.

Re-querying afterwards showed every element correct, and the `:root` variables had been right all
along. **When a measurement disagrees with the tokens you just read from `:root`, suspect the
measurement first.** Read the variable and the element in separate calls.

---

## ▶ THE MODULE'S OWN DOCSTRING WAS ARGUING FOR SOMETHING THAT NO LONGER EXISTED

`contrast.py` opened with **"LIGHT MODE ONLY, AND THAT IS DELIBERATE"** and eleven lines defending
it with real numbers. Gating dark turned that into a confident, well-written falsehood sitting above
the code contradicting it — found only because a bite-check made me read the file top to bottom.

Same shape as F2c's sandbox note advocating for a gap after the gap was closed. **Advocacy text is
documentation with a shelf life, and the sprint that removes the omission owns rewriting the case
for it.**

---

## Three files describe the fill role, and both suites pin them

`globals.css` (what the browser paints), `branding.ts` (what the picker measures as somebody types)
and `contrast.py` (what the SAVE PATH measures, and therefore what is enforced). A disagreement is
silent in both directions — approving a colour on a button nobody will see, or refusing one that
renders perfectly.

That is the F4 role-palette shape, **caught before it could bite** rather than after. The web suite
pins the CSS against `branding.ts`; the Python suite pins the CSS against `contrast.py`. Whichever
side drifts, its own suite goes red.

---

## For F7b

1. **`--brand-shape`** — light `brand-500`, dark a paler stop. ~50 files, overwhelmingly one
   repeating focus-ring pattern. Then delete `DARK_EXEMPT` and the test that names it.
2. Re-measure the 18-colour spread afterwards; `#010066` and `#111827` may or may not return.

## For F7c (the flip)

**There is still no switch a person can click.** The flag gates only the before-paint script, so
turning it on today means everyone follows their device with no way to override. The owner's ruling
(2026-09-02) is a **device-local switch, no account storage** — language, a bigger per-person
choice, is already device-local, and making theme more persistent than language would be backwards.
Mount it where `LanguageSelector` is mounted, plus the admin and sponsor shells.

And the two carried items: **TD-223** (links are `info` on some surfaces and `brand` on others; A2's
gate says brand) and the **eight category swatches seen together** on `/sandbox/course-guide`.

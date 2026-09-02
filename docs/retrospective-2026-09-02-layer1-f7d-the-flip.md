# Layer 1 F7d — the flip, and what the walk found

**2026-09-02. web only. No migration.** Branch `feat/layer1-f7d-the-flip`.
jest 1605 → **1617**; tsc **24** (baseline); lint **0**; i18n 4640 → **4646 × 3**; build clean.
**All 25 surfaces walked in both modes, measured rather than eyeballed.**

---

## What shipped

Dark mode has been complete and unreachable since F1. This sprint made it reachable.

- **`ThemeSelector`** — Light / Dark / Auto, a `<select>` matching `LanguageSelector` class for
  class, on the public header (desktop and mobile), the landing nav, the settings page, the admin
  top bar and the sponsor portal shell. Device-local, by the owner's ruling.
- **`ThemeWatcher`** — renders nothing; keeps `auto` following the device for the life of the tab.
  In the PROVIDER STACK, not in the control, so a chromeless page (document upload) is covered too.
- **The flag is gone.** `themeSwitchEnabled()` deleted; `theme-boot.js` is unconditional.
- **The sandbox dropped its own toggle** and mounts the real control.

**F1b as originally scoped — four settings surfaces, three identity models, a migration — is
SUPERSEDED, not deferred.** The owner ruled device-local on the grounds that language is a larger
per-person choice and is already device-local, so a *more* persistent theme would be backwards.

---

## ▶ THE SPRINT'S REAL FINDING: LIGHT MODE IS FIVE TIMES WORSE THAN DARK, AND LIGHT IS WHAT SHIPPED

The walk existed to check that dark was safe to switch on. Measured over 25 routes with a composited
contrast sweep (`docs/contrast-sweep.md`):

| mode | failing elements | distinct causes |
|---|---|---|
| **light — live in production since launch** | **263** | **55** |
| dark — nobody has ever seen it | 54 | 11 |

`text-ground-400`, the muted-text token, measures **2.43–2.54** on a light ground against a bar of
4.5. It is the footer copyright on every public page, 29 field labels in the officer cockpit, and
every `text-xs` hint in the product. Nobody put it there wrongly; it is Tailwind's `gray-400`, which
has always failed AA on white, and the arc never measured light because light was the mode that
already worked.

**The flip does not make the product less readable. It makes an existing problem visible.** That
inverts the deploy question this sprint was expected to raise: holding the flip would fix nothing,
because the worse mode is the one already shipped. Recorded as **TD-224** and sized as **F7e**.

---

## ▶ TWO OF THE FAULTS ARE ONES THIS ARC ALREADY FIXED — FOR THE BRAND, AND ONLY THE BRAND

- **F7a** gave the brand a `--brand-fill` role because a fill that reverses in dark cannot keep the
  ink that light chose for it.
- **F7b** moved brand TEXT off `-500` because it measured 3.98 against white.

**The four tone ramps reverse in dark exactly the same way and were given neither.** So
`bg-positive-600 text-white` — the cockpit's **Accept** button — measures **1.40** in dark and
**3.30** in light, and `text-critical-500` asterisks measure **3.76** on white.

The pattern was named twice and generalised zero times. **When a fix is written for one token
family, ask which other families have the same shape before closing the sprint** — the tones were
sitting in the same stylesheet, reversing by the same rule, the whole time.

---

## ▶ THE GATE IS BLIND TO EVERY PAIR IT DOES NOT NAME. THIRD TIME.

`contrast.py` has seven pairs and all seven are brand-versus-ground. It has no pair for a tone fill
and none for `ground-400` as ink, so the entire TD-224 class is outside what it measures — while
passing, correctly, on everything it does measure.

F7b recorded this shape ("when a token is checked at one bar, enumerate its uses and ask about the
other kind"). F7c recorded the scope version of it (a guard scoped to `fixtures/` is blind to
fixture data outside it). This is the third form: **a gate is blind to every pair it does not name,
and the pairs it names are chosen by whoever wrote it, on the day they wrote it.**

Which is the argument for the sweep: it measures what the browser actually painted, so it cannot
have a blind spot chosen in advance.

---

## ▶ THE SWEEP RETURNED ZERO ON ITS FIRST RUN, WHICH IS WHEN TO DISTRUST IT

The landing page came back clean. That is the exact shape of a scan silently matching nothing —
this project has been bitten by it three times, most recently by an F4 regex that a heredoc turned
into a literal backspace byte.

So the sweep was bite-checked before any result was believed: two defects planted, one low-contrast
label and one control whose ink equals its own background (the F7c shape), both caught, ratios 1.69
and 1.00. **The zero was real.** It is only trustworthy because it was checked.

The first draft also had a genuine bug the bite-check did not catch: it treated any background with
non-zero alpha as opaque and measured against the raw colour, inventing four failures on tinted
panels. **Compositing is not a detail — a translucent panel over a dark ground is a different colour
from the panel.**

---

## ▶ A DOCSTRING THAT OUTLIVES ITS DECISION IS A CONFIDENT FALSEHOOD. FOURTH TIME.

`theme.ts` and `theme-boot.js` both said, in as many words, that the theme's home is the ACCOUNT and
that local storage is a cache of it. That was true when F1 wrote it and false the moment the owner
ruled. It was also load-bearing: F1b was scoped around that sentence.

Both rewritten. The arc's tally on this is now four — F2c's advocacy note, F7a's `contrast.py`
docstring, F7b's again, and this. **Whichever sprint acts on a ruling owns rewriting the case that
was made against it.**

---

## ▶ THE TEST THAT ASSERTED THE OPPOSITE, AND WAS RIGHT BOTH TIMES

`theme.test.ts` carried `it('IS GATED ON THE FLAG — with the switch off, nothing paints a theme at
all')`. F7d asserts the exact inverse. Both versions were correct in their turn, and the F1 defect
that produced the first one is still worth keeping — **a flag that gates only the affordance gates
nothing** — so the lesson was moved into the new test's comment rather than deleted with the flag.

A second guard was added that the first version did not need: no file in `src` may mention
`themeSwitchEnabled` or `NEXT_PUBLIC_THEME_SWITCH`. A deleted flag surviving in one call site is
worse than no flag — the switch works, and one surface silently does not.

Two small test bugs, both mine and both the same kind: an anchor matching earlier than intended.
Slicing from `'useEffect'` caught the import line; scanning `src` for the flag caught the test file
that has to spell the flag out to search for it. **Anchor on the call, not the identifier**, and
name a self-exclusion narrowly rather than skipping a whole directory.

---

## What the review confirmed

- The switch paints instantly, survives a reload, and the stored value drives the before-paint
  script — no flash on navigation in either mode.
- Rubbish in `localStorage` falls back to `auto` rather than being painted onto `<html>`.
- Light mode is byte-identical: F7d changed no token and no colour utility.
- **The brand logo is drawn for a light ground** and its icon half-disappears in dark. Artwork, not
  a token, and tenants supply their own — recorded as **TD-225**, owner's call.

---

## For F7e

1. **TD-224** — the contrast cluster, in BOTH modes. Tone fills want the F7a treatment (a `-fill` /
   `-fill-ink` role per tone). The muted-ink stops want a ruling: move `ground-400`, which is one
   edit that changes every muted label in the product, or move ~150 call sites to `ground-500` and
   leave the token as a trap. **Owner's call.**
2. **TD-223** — links are `info` on some surfaces and `brand` on others. Same call sites; fold in.
3. **The eight `category-N` swatches** on `/sandbox/course-guide`, still unlooked-at by the owner:
   `Politeknik` and `Kolej Komuniti` are distinct by value and hard to separate by eye in dark.

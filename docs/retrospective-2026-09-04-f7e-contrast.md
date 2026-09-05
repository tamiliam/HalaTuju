# Retrospective — Layer 1 F7e, the contrast sprint

**Date:** 2026-09-04 (closed 2026-09-05). **Branch:** `feat/layer1-f7e-contrast` →
`main` at `242b60fa`. **Closes TD-224 (high, live in LIGHT mode since launch).**

**SHIPPED AND DEPLOYED.** Only the WEB trigger fired (0 Python files changed); Cloud Build
SUCCESS on `242b60f`; serving **halatuju-web-00824-v55** at 100%, api unchanged at
`halatuju-api-00975-nrj`. All eight public routes 200, no error logs since the deploy. The
served stylesheets were downloaded and read back rather than assumed.

**NO MIGRATION. NO BACKEND.** 68 files, web only.

---

## The number this sprint exists for

Measured in a browser over all 25 sandbox + public routes, in both modes, against the
effective background with alpha composited (`docs/contrast-sweep.md`):

| mode | before (F7d's walk) | after |
|---|---|---|
| **light** | **263 elements / 55 distinct** | **1 / 1** |
| dark | 54 / 11 | **1 / 1** |

The one survivor in each mode is the decorative `·` separator (`text-ground-300 mx-1.5`,
1.47 light / 3.04 dark). It carries no information and is excluded under the procedure's own
"Reading the result" rules — **stated in the doc rather than quietly dropped**, so a later
reader can disagree with the judgement rather than wonder whether it was made.

---

## What Was Built

### 1. `ground-400` became the muted-INK stop, and placeholders moved out

This is the ruling that turned ~400 edits into ~10, and it came from re-measuring rather than
reading the ticket. **`ground-400` was NAMED for the small role and USED for the big one:**
`.input` says `placeholder:text-ground-400` and the dark block literally commented it
*"placeholder text"* — yet **395 of its 404 call sites are muted body text.** Three sites
relied on the placeholder meaning.

| token | light | dark | why |
|---|---|---|---|
| `--ground-400` | `101 109 122` (`#656d7a`) | `180 186 196` (`#b4bac4`) | muted ink; **4.74** on a well in light, **5.28** in dark |
| `--ground-500` | `88 95 107` (`#585f6b`) | unchanged | stronger muted ink; 5.85 on a well |
| `--ground-placeholder` **(new)** | `156 163 175` | `156 163 175` | today's value, both modes — placeholders look exactly as they did |

**⚠ The roadmap's framing of the owner decision was wrong in both halves, and the second
option does not work.** It said *"move the token (one edit) or move ~150 call sites to
`ground-500`"*. Measured: 404 sites across 102 files, not ~150 — and **`ground-500` on a well
(`ground-100`) is 4.39 against a bar of 4.5**, so the chip cluster in TD-224 would have stayed
failing after all ~400 edits. The third option — move the token, move the *smaller* role out —
existed only because the call sites were classified before a role was chosen (F7a's lesson).

**⚠ Dark failed too.** The ticket recorded TD-224 as a light-mode problem. `ground-400` on a
well in dark measured **4.06**. Both modes moved.

### 2. The four tone ramps got the `--brand-fill` role, verbatim

`--positive-fill` / `-fill-hover` / `-fill-ink`, and the same for `caution`, `critical`,
`info` — `var()` indirections onto a stop, never a literal, so a tenant's inline `:root`
override still resolves. Light resolves to `-700`/`-600`; dark resolves all four to `-600`
with `var(--ground-50)` as ink.

**This is F7a and F7b's bill coming due.** The brand got a fill role (F7a) and had its text
moved off `-500` (F7b) because the ramp reverses in dark. **The four tone ramps reverse
identically and were given neither.** The pattern was named twice and generalised zero times.
Worst site: the cockpit's **Accept** button, `bg-positive-600 text-white` — **3.30** in light
and **1.40** in dark.

Tone INK as small text took the F7b move — one stop darker, **text only**. Measured on a card
in light: positive 2.28/3.30 → **5.02**, caution 2.15/3.19 → **5.02**, critical 3.76 → **4.83**,
info 3.68 → **5.17**. `critical-600` and `info-600` already passed and did **not** move.
`bg-`, `border-`, `ring-`, `fill-` and `stroke-` are SHAPES whose bar is 3:1 and were left
alone — moving a dot or a border would change how the product looks for no accessibility
reason.

### 3. Five new guards in `theme.test.ts`, each naming a pair

**This file passed throughout TD-224.** The distinctness test asked whether two stops share a
value; nothing asked whether a stop a person has to READ can be read.

- every ink stop (`400`–`900`) clears 4.5 **on a well**, in both modes — failure prints the
  actual ratio, not `expected false to be true`
- the ink ramp stays **monotonic**, so a later tuning cannot silently invert two stops
- **a filled control may never be spelled as a tone stop again** — `bg-<tone>-<400..800>` on
  a line with `text-white` fails, naming file and line
- every tone fill clears **both** bars in both modes: ink 4.5 on the fill, fill 3.0 on the card
- `ground-placeholder` stays a separate token, is **exempt** from the ink bar by design, and
  no file may spell `placeholder:text-ground-<anything else>`

---

## Design Decisions

Both logged in `docs/decisions.md`. Two owner rulings, taken on the record before building:

1. **Move the token; move placeholders out.** ~10 edits rather than ~400, and it leaves no trap
   for the next person.
2. **Do the tone fills in the same sprint.** They are the other half of the same defect.

And one engineering call: **TD-223 (links `info` vs `brand`) was DEFERRED to F7f**, against the
roadmap's instruction to fold it in. Measured: 89 sites across 49 files, with small overlap.
It would have taken the sprint from ~48 files to ~90.

**Why deferring it is safe:** A2's contrast gate already carries a `link_on_card` pair
asserting **brand**, so this is settled design — unfinished conversion, not an open question.

---

## What Went Well

- **Re-deriving the measurement instead of trusting the ticket** overturned the plan on its
  first page and saved roughly 390 edits. Every number in the plan was computed from the
  composited pair, not chosen by eye.
- **The browser sweep is now a proven procedure, not a one-off.** It was bite-checked before
  any zero was believed — two defects planted, both caught at exactly the predicted ratios
  (1.69 and 1.00) — as its own doc demands after F7d was burned by a clean landing page.
- **The two F2b/F5 guards that had to change were respelled, not re-decided.** Each carries a
  comment saying the CLAIM is unchanged and only the spelling moved.
- **The gate is now widened where widening it means something.** See "Design Decisions" in
  `decisions.md` for why `contrast.py` was left alone: it validates a **tenant-supplied brand
  hex**, and the tone ramps are fixed platform tokens no tenant can set.

---

## What Went Wrong

### 1. The codemod ate a hover state, and the count would not have shown it

**What happened:** rewriting `bg-critical-600` → `bg-critical-fill` also matched inside
`hover:bg-critical-600`, producing `hover:bg-critical-fill`. The hover state became the
resting state — a real visual regression, on buttons.

**Why:** a bare substring rewrite over a class list has no notion of a variant prefix, and the
change count looked exactly right. The plan already carried the lesson *"read a codemod's
residue rather than counting it"*, and reading the residue is the only thing that caught it.

**System change:** the rewrite now does **hover first**, longest-match first, and the sprint's
residue read is a required step rather than a habit. Recorded in `docs/lessons.md`.

### 2. The codemod applied itself half-way, because printing a tick killed the console

**What happened:** the script printed a line containing `✓` after each file. On the cp1252
Windows console that raised `UnicodeEncodeError` — **after nine files had already been
written**. The repo was left in a partially converted state with a traceback on screen.

**Why:** the writes and the reporting were interleaved, so a failure in the *reporting* left
the *writing* half done. The encoding is an old known hazard on this box; the interleaving is
what made it damaging rather than annoying.

**System change:** a codemod now **writes every file first, then reports to a UTF-8 file** —
never to the console mid-run. Recorded in `docs/lessons.md`.

### 3. The post-write scan failed on somebody else's deliberate content

**What happened:** the control-byte / wrong-script scan (added after S-ASSIGN's Arabic U+0658)
ran over the whole tree and flagged a pre-existing, deliberate `U+0001` cache-key separator in
`src/lib/documentHelp.ts`.

**Why:** the scan's job is *"did MY generated write emit something wrong"*, but it was pointed
at everything. A guard that reports other people's intentional code is one people learn to
ignore — which is exactly how the Arabic mark would have got through.

**System change:** the scan is **scoped to the files the codemod actually wrote**.

### 4. The sweep found what no static tool could — and it nearly was not run

**What happened:** `CourseCard`'s merit bar puts the student's score in white **on** the bar.
The fill class and the `text-white` sit **twenty lines apart**, so the codemod's pair rule —
match both on one line — could never have seen it. The number measured **1.67**.

**Why:** a line-scanning tool is structurally blind to a pair split across a file, and the
sprint's confidence came from the codemod's own report.

**System change:** `docs/contrast-sweep.md` now opens with this case in bold — *run this
before believing a repaint is finished* — and carries the before/after table so the next
reader sees the procedure has a track record.

---

## Numbers

| gate | result |
|---|---|
| jest | **1697** (1692 → 1697, +5 guards) |
| pytest | **5844** — backend untouched, 0 Python files in the diff |
| `tsc --noEmit` | **24** (TD-221 baseline, unchanged) |
| `next lint` | **0 Errors** |
| `check-i18n.js` | **4745 × 3** (unchanged — no new keys) |
| `next build` | clean |
| files touched | **68** |

**⚠ 68 files is over the 40 guideline, and it is said here rather than hidden.** ~46 of them
are one mechanical class swap produced by a single classified from→to codemod and review as
one change; the cap exists for reviewability, and this sprint stays reviewable.

**⚠ THIS SPRINT IS VISIBLE.** Every muted label in the product darkens and ~46 filled controls
change ink. That is the deliverable, not a side effect — do not write "nothing a visitor sees
changes".

---

## Owner post-check

Open the live site and look at four things, in **both** Light and Dark (the switch is in the
header):

1. **The footer on any public page** — the copyright line should read as text, not a smudge.
2. **The officer cockpit** — the 29 field labels beside each fact, and the **Accept** button
   (its ink was 1.40 in dark).
3. **A course card's merit bar** — the score number sitting on the coloured bar.
4. **Any placeholder** (the search box) — it must look **exactly as faint as before**. If a
   placeholder now reads as a filled-in value, that is the one thing this sprint could have
   got wrong.

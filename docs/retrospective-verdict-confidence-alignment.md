# Retrospective — Officer cockpit + verdict confidence-scale alignment

**Date:** 2026-06-07
**Commits:** `c748284` → `dd40865` (9 commits on `main`)
**Scope:** Officer cockpit (`admin/scholarship/[id]`) + the four-fact verification verdict engine.
No migration. Gates at close: **778 scholarship + 1037 courses/reports pytest · 274 jest · next build clean.**

A live-testing pass with the user over the officer cockpit and the verification verdict —
layout, the colour/confidence model, and per-fact alignment of the colours with reality and
with a stricter "don't pass weak evidence" policy.

## What Was Built

1. **Cockpit layout** — flipped so *About the student* sits above *Review & actions*; the
   *Documents* drawer is fixed-height + scrollable; *Pre-interview flags* moved under
   *Caveats*; *Referees* hidden behind `SHOW_REFEREES=false` (handlers kept; consent stays).
2. **Verdict = a Kent confidence scale (4 bands)** — 🟢 Certain / 🔵 Probable / 🟡 Unsure /
   🔴 Can't verify, with the estimative word on each tile + a legend. Blue/amber **swapped**
   so colour temperature tracks certainty, and **"blue needs a green"**: a `review` fact is
   blue only with ≥1 genuinely-verified value (`factTileTone(fact)` + `SOFT_EVIDENCE`).
3. **Per-fact alignment (policy: bounce weak evidence for re-upload, don't manually vet)** —
   - **Identity:** IC registered-address state is no longer a false-yellow caveat (it's a
     pre-interview flag); identity never auto-fails (the gate already blocks NRIC-mismatch /
     unreadable).
   - **Academic:** a slip-name mismatch is a hard stop (red + fails `documents_done`).
   - **Pathway:** no offer letter → red (offer already a `consent_blockers` blocker; new
     `offer_letter_missing` verdict item + re-upload ticket).
   - **Income:** no income info → red (consistency); informal / unprovable-relationship /
     salary-above-B40-line stay 🟡 (interview-assessable).
4. **TDs resolved:** TD-082, TD-087, TD-088, TD-090. New reference doc
   `docs/scholarship/verdict-confidence-bands.md`.

## What Went Well

- **Tight Q&A → decision → implement loop.** Each policy call (slip mismatch, no-offer,
  income-no-info, blue/amber) was confirmed with the user, implemented with tests, and
  shipped in a small deploy — fast feedback, no big-bang.
- **The Kent reframing unified the model.** Four ad-hoc statuses became one coherent
  confidence scale with a written reference doc — easier to reason about and extend.
- **Clean parallel-agent coexistence.** A second agent ran its own "input length-guard"
  sprint in the same working tree; explicit `git add <paths>` (never `-A`) kept the two
  workstreams' commits cleanly separated.

## What Went Wrong

1. **The colour model took three passes (Kent scale → swap blue/amber → blue-needs-green),
   each a separate deploy.**
   *Symptom:* three deploys to settle one model.
   *Root cause:* the model wasn't designed up front — it emerged from the user's questions
   ("what is blue?", "how is it different from yellow?", "blue needs a green").
   *Fix:* when a user asks *"what is X / how does X differ from Y"* about a UI semantic,
   read it as "the model isn't settled" and propose the **whole** model (a scale/table) for
   sign-off before coding — not the literal first tweak. (Doing exactly that — the Kent
   table — is what converged it.)

2. **`factTileTone` had to change signature from `(status)` to `(fact)` mid-sprint.**
   *Symptom:* a one-line rule ("blue needs a green") rippled to three call sites + the test
   helper + the test suite.
   *Root cause:* the tone helper was first written as `status → colour`, but a compound rule
   needs the `evidence` array, which the status alone doesn't carry.
   *Fix:* presentation/verdict helpers should take the **whole domain object** from the
   start; a single field rarely survives the first compound rule.

3. **A foreign i18n key briefly looked like cross-contamination in my diff.**
   *Symptom:* `grades_verified` showed as an added line in my `en.json` diff.
   *Root cause:* a diff artifact — it gained a trailing comma when my new key was appended
   after it; not the other agent's work.
   *Fix:* in a shared working tree, confirm diff ownership by **reading the hunk**, not by
   grepping for added keys — a neighbouring line can flip on punctuation alone.

## Design Decisions

See `docs/decisions.md` — "Verdict tiles as a 4-band Kent confidence scale" and "Per-fact
evidence policy: hard-stop unusable documents, keep income interview-assessable".

## Numbers

- 9 commits, FE + scholarship-backend, no migration.
- Tests: 778 scholarship (+ the slip-name gate test and renames) + 1037 courses/reports
  pytest; 274 jest (+ the factTileTone band/verified-value tests). i18n parity maintained
  (band keys + `offer_letter_missing`).
- TDs: TD-082 / TD-087 / TD-088 / TD-090 resolved.

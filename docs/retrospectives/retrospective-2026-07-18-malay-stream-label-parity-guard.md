# Retrospective — Cockpit pre-U stream in Malay + cross-runtime label parity guard (2026-07-18)

A short owner-live-review follow-up on the same day as the Academic-box work. NO migration; web +
one backend test. Commits `258bac51` (label) / `ed7d6bdf` (guard).

## What Was Built

1. **Cockpit pre-U stream/track shown in Malay only.** The chosen-programme line appended the pre-U
   track via the apply form's bilingual i18n label ("Tingkatan Enam · Social Science (Sains
   Sosial)"). The officer cockpit now shows the Malay term only ("· Sains Sosial") via a new
   `preUTrackMalay()` helper. The student apply form's bilingual labels are untouched (deliberate —
   student comprehension).

2. **One FE source for the labels.** `preUTrackMalay()` reads the Malay values from the SAME
   `ms.json` the apply form uses (`scholarship.apply.plan.stream`/`.track`), not a hardcoded map. An
   initial cut DID hardcode a `PREU_TRACK_MS` map; the owner flagged the duplication, so it was
   replaced with an `ms.json` read (already statically bundled by `lib/i18n.tsx` → zero extra weight).

3. **Cross-runtime label parity guard** (`TestTrackLabelParity`). The same code→label map lives in
   two separately-deployed runtimes (backend `card_display._TRACK_LABEL` for the sponsor card/emails;
   FE `ms.json` for the apply form/cockpit) that can't share a file at runtime. The test reads the FE
   JSON and fails the build on drift; skips in an api-only checkout. Chosen over the heavier
   unification options (see decisions.md).

## What Went Well

- The owner's "aren't they the same source / we shouldn't have more than one truth" challenge caught
  a real (self-introduced) FE duplication before it shipped, and reframed the fix from "add a third
  map" to "reuse the one that exists + guard the unavoidable cross-runtime copy."
- The whole thing is data-safe: both surfaces already read the same DB columns; only presentation
  labels were ever in question.

## What Went Wrong

- **Misdiagnosed #80's missing Institution tick as a browser cache issue.** Symptom: a tertiary
  student didn't show the new tick after deploy; I attributed it to a stale bundle and even verified
  the live JS chunk contained the code. Root cause: I'd assumed the offer's pathway was a "match"
  (mis-reading which ticks were present); it was actually a **mismatch** (a false PISMP clash — the
  offer's programme field holds the generic degree name while the student declared the Bidang), and
  the Institution tick is correctly suppressed on a pathway mismatch. Fix/lesson: when a
  conditional badge is absent, read the ACTUAL governing condition from the data (run the matcher on
  the real strings) before blaming the deploy — don't infer the condition from other badges. The
  PISMP false-clash itself is a separate, pre-existing issue handed to another agent.

- **First cut of the Malay label duplicated `ms.json`.** Root cause: reached for a quick hardcoded
  map without checking that the values already lived in the i18n messages. Fix: reuse the existing
  source; the owner's review caught it. (Captured as the parity-guard lesson.)

## Design Decisions

- **Keep two cross-runtime copies + a parity test, over unifying** (option B vs API-supplied text or
  build-time codegen) — full rationale + the security/stability/sustainability/speed rating in
  `decisions.md`.

## Numbers

- +1 backend test (parity guard) + 3 jest (`preUTrackMalay`). Full jest 589 green.
- No migration. Web-only runtime change (cockpit label); the guard is CI-only.
- Deploy = push (owner-gated, currently HELD — a push would also carry another agent's TD-161 work).

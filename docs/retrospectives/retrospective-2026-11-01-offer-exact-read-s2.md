# Retrospective — Offer letters read exactly, Sprint 2: answers and the failure map (2026-11-01)

Roadmap: `docs/plans/2026-11-01-offer-letter-exact-read-roadmap.md`. Eval tooling and gitignored answers only — no
reader change, no migration, nothing live changes. Vision: 106 page calls (~US$0.16, free tier).

## What Was Built

- 126 dev answers (the AI-read dev letters) by four parallel labellers on one written brief, then a consistency pass
  for the owner's institution / campus split — 216 letters answered.
- Free text for every letter (`capture_ocr.py --corpus`), a replay of today's free readers (`offer_replay.py`), a
  rule-based failure map (`offer_failure_map.py`), and a second owner page (`--offer-check`, 47 letters).
- An NRIC placement map (owner: the offer NRIC belongs to this arc).

**Scores:** held-out 19/90 fully exact, dev 31/126. Institution is the biggest gap (about 46 % right), then programme
(codes, PISMP wrapper), then intake (dropped "Semester"). 21 of 71 stored exact reads would fall back to Gemini on a
re-read today; only 1 of 38 known-format AI letters locks today.

## What Went Well

- One written labelling brief carrying every S1 convention: the four batches came back consistent, unlike S1.
- The owner's checks turned guesses into rules: what `not_offer_letter` vs `suspect` means, IPTS offers, public
  confirmation letters, IKBN / IKM — S6 now has proven wrong calls instead of suspicions.
- The matcher's session agreed the institution / campus shape before any reader code exists, and the S4 push now
  waits on its matcher change — no surprise breakage of multi-campus pins.
- The NRIC map showed 30 of 33 live blanks are correct: the "gap" was mostly letters that print no NRIC.

## What Went Wrong

1. **The owner's two checks mixed a document label with a bursary decision.** Why: the S2 page asked "what is this
   document?" and "what did the system decide?" without saying the system's status is an acceptance decision, so
   12 real private-college offers looked like contradictions. Prevention: the status meaning is now written down
   (decisions.md); a future check page says "accept / fail / not sure" for the system line.
2. **A builder's Vision run used gcloud ADC because the repo `.env` had no Vision key.** Why: the brief named a key
   that is not set locally. Cost was nil (free tier), but a paid call billed to an unconfirmed project is a risk.
   Prevention: S3's brief names the billing project and checks it before any paid call.
3. **The S1 convention "the institution line" was not precise enough** for letters printing the university and the
   campus on separate lines; it needed an owner ruling and a 128-file relabel. Prevention: ask the owner on the first
   ambiguous case, not after a full batch.

## Numbers

- Scholarship tests at the last builder run: 9,562 passed / 3 skipped. No web change.
- Owner time: two checks (32 + 47 letters). Cost: ~US$0.16 of Vision (free tier).

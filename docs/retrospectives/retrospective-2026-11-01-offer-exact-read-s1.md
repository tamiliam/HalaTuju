# Retrospective — Offer letters read exactly, Sprint 1: the baseline (2026-11-01)

Roadmap: `docs/plans/2026-11-01-offer-letter-exact-read-roadmap.md` (approved 2026-11-01, D1–D6 option a).
Eval tooling only — no reader change, no migration, nothing live changes.

## What Was Built

- `eval/offer_read_check.py` — the scorer: per core field (name, NRIC, institution, programme, intake, reporting
  date) exact / blank_correct / missing / wrong / extra, after tidying only (no fuzzy matching); reports by family,
  input kind, capture, programme, split and answer kind; prints keys, field names and counts, never a value.
- `eval/offer_split.py` + `offer_split.json` — a held-out set of 90 letters, drawn only from unseen letters the
  AI reader read (owner steer: the fixed-format formats are already exact).
- `eval/offer_review_page.py` — a local, gitignored review page for the owner (every line pre-ticked Right at the
  owner's request), and `--apply` that counts the saved results.
- `fetch_corpus.py` — pages every PostgREST read (profiles were silently cut at 1,000).
- 90 agent-written correct answers (three parallel labellers, shared conventions), spot-checked by the owner (32).

**Baseline (stored reads, held-out 90): 21 of 90 fully exact (23.3 %).** Institution 51 % (the reader takes the
reporting venue or hall instead of the institution), programme 73 %, intake 81 %, name 94 %, reporting date 97 %,
NRIC 99 %. 45 known-format letters (STPM / matriculation / polytechnic) were read by the AI reader, 21 of them
photos — the cheap wins for S5.

## What Went Well

- The owner's steer early in the sprint (known formats are already exact) cut the labelling to the letters that
  matter and produced the 45 known-format-AI count, now the first item of S5.
- Writing the answer from the letter BEFORE opening the stored read kept the labellers from copying its mistakes.
- The owner's spot-check found 1 core-field labelling error in 32 letters; it also surfaced a real production fault:
  the stored genuineness check calls private-college (IPTS) offer letters "not an offer letter".

## What Went Wrong

1. **The three labellers started with different conventions** (campus-code prefixes, programme codes, intake labels).
   Why: the answer format said "as printed" without the edge cases. Fix: the lead sent shared conventions mid-run and
   one labeller re-applied them. Prevention: S2's labelling brief carries the full convention list (now in the eval
   README), including the owner's rulings (intake label kept; PISMP programme = the degree title).
2. **One convention the lead chose (strip the intake label) was overturned by the owner.** Why: the lead decided a
   formatting question that was the owner's taste, without asking. It cost nothing in score (the scorer strips the
   label), but 14 owner "wrong" ticks were spent on it. Prevention: show the conventions on the review page next time,
   so the owner judges content, not format.
3. **The draft roadmap missed the owner's known-format point.** Why: the planner sized labelling across all 287 letters
   without asking which families are already trusted. Prevention: the S2 scope now labels only AI-read letters.

## Design Decisions

Owner rulings 2026-11-01 (recorded in the roadmap): intake kept as printed with its label; PISMP programme = the degree
title (specialisation scored, not core); a postgraduate offer is an offer (eligibility is a separate matter). Lead:
a trailing bracketed acronym on the institution is optional; "Tahun" before a year is part of the intake label.

## Numbers

- pytest (scholarship) 9,499 passed / 3 skipped at the last builder run; no web change.
- Cost: nil (no Gemini or Vision call). Owner time: one spot-check of 32 letters.

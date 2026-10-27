# Retrospective — STPM exact read (S1–S4), 2026-10-27 → 2026-10-28

Roadmap: `docs/plans/2026-10-27-stpm-exact-read-roadmap.md`. Live: S1+S2 21ac26b5 · S3 ea10a4c9 · S4 live
re-read (job execution release-decisions-twfkb). MODEL_VERSION 1.10.0 → 1.11.0; VERDICT 2026-10-27.4.

## Outcome
24 of the live STPM documents now read Exact (was 2) and 27 are scored genuine; the two checker pages are
caught (1A). Every exact value matched the earlier AI read. Total paid cost: a few US cents.

## What went well
- A real corpus first (S1): the owner sorted the documents, we split them by page, captured OCR once and
  wrote expected answers. Every later decision was measured against it (0 wrong reads throughout).
- Owner rulings landed fast and were recorded in the roadmap as they came (layout is reader-only, exam year
  from the title, grade letter + point on the fixed scale, student's entry as an anchor only on PNGK rows,
  portal printouts are slips).
- Three adversarial reviews each found a real issue before release (name over-capture; a 5th subject not
  guarded by the PNGK check; the browser-footer rule catching certified printouts).
- The dry run reproduced production's exact input and predicted the live result almost exactly.

## What to do differently
- The grade rule changed four times in one hour. Show the owner a worked example (one row, each case) before
  briefing the builder, so the rule settles once.
- A builder copied a real IC into a test from a garbled corpus layer. Scan tracked files against the corpus
  values before every commit (done here; make it a habit, or a tool).
- Printing a service's env to read flag values also printed a secret into the session transcript. Filter
  env output to names, or to the specific flags, never values wholesale.

## Owed
- STPM documents in the SPM slip place still go to AI (vision.py is at its size ceiling).
- Owner to rule: the checker-page check in the SPM slip place too (recommended yes).
- Matriculation / Asasi / Diploma / MUET exact reads wait for more samples.
- The MPM transcript (cover letter on page 1) is never read beyond page 1.

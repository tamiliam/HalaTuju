# Retrospective — Reviewer-query automation S3: offer reporting-date (capture + persist)

**Date:** 2026-06-29
**Branch:** `feat/reviewer-query-s3-reporting-date`
**Migration:** `0080_reporting_date` (additive `DateField`, migrate-first)
**Roadmap:** `docs/scholarship/reviewer-query-automation-roadmap.md` (S3)

## What Was Built
Closes the reporting-date thread from the earlier table request (a sortable date) AND automates
the reviewer's "do you know when/where to report?" query (Shamalaa's case — offer didn't state it).

- **Normaliser** `pathway_engine.parse_reporting_date(raw)` — turns the messy offer-letter date
  strings into a real `datetime.date` (Malay/English month names, leading day-ranges
  "8 HINGGA 9 JUN 2026" → the 8th, trailing time/day-of-week noise stripped). Unreadable → None.
- **Persisted column** `ScholarshipApplication.reporting_date` (DateField) — populated by
  `autofill_pathway_from_offer` (the existing post-offer-extraction hook, runs on upload + re-run),
  so the date is stored once and sortable, not re-parsed on every read. Exposed on the admin
  serializer. A **backfill command** (`backfill_reporting_dates`, wired into `CronRunView` as
  `backfill-reporting-dates`) seeds the existing rows on deploy.
- **Clarify** `reporting_date_unknown` (check2, capped, pathway-fact) — fires when an EXTRACTED
  offer carries no parseable reporting date → asks the student when/where they report. Gated on
  the offer actually being read (`student_verdict` present), so an unread offer is a different gap.

## What Went Well
- The post-extraction hook (`autofill_pathway_from_offer`) was already the right place — it runs on
  every offer (re)extraction and already writes pathway fields, so the date populate was a 4-line add.
- Reused the established check2 clarify plumbing (S1/S2) — the clarify was one detector + one
  `_CLARIFY_ORDER`/`CLARIFY_SPECS` entry.

## What Went Wrong
1. **First cut of the "unread offer" guard keyed off name/ic being 'pending' — wrong.** *Symptom:*
   the unread-offer test failed (the query fired on an unread offer). *Root cause:* `_name_status`
   doesn't return 'pending' purely from the missing extraction (a present candidate_name made it
   match). *Fix:* gate directly on the extraction verdict (`vision_fields.student_verdict`), mirroring
   the engine's own `extracted` flag. Caught + fixed by the test before close.

## Design Decisions
- **Store the normalised date, don't re-parse on read.** The offer string is OCR'd free text; parsing
  it once into a DateField makes it sortable/queryable (the table use-case) and cheap.
- **Populate from the offer only; the clarify answer is the human fallback.** When the offer has no
  date, the column stays null and the student is asked; their free-text answer lives in the
  resolution (not auto-parsed into the column) — keeps the column meaning "what the offer states".
- **SPM subject-count nudge dropped from S3** — it isn't cleanly deterministic (the reviewer
  eyeballed an odd grade count); needs a clearer signal before automating. Logged, not built.

## Numbers
- Migration `0080_reporting_date` (additive, migrate-first) + a backfill command.
- Tests: backend 1739 pytest (+10 `test_reporting_date.py`), frontend 387 jest. i18n parity 2964×3 (+3).
- Files touched: ~12.

## Next
S4 — interview (Check 3): structured guide + AI gap-spotter seeding + the high-utility reviewer probe.
S5 — final-profile prompt restructure.

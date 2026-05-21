# Retrospective — B40 Assistance Programme, Phase 1 Sprint 1

**Date:** 2026-05-21
**Sprint goal:** Scholarship app scaffold + application intake API (backend only).
**Branch:** `feature/b40-assistance` (not merged, not deployed)

## What Was Built
- New `apps/scholarship/` Django app, registered in `INSTALLED_APPS` and URL-wired.
- `ScholarshipCohort` model — per-round config holding the tunable shortlisting thresholds
  and funding/workflow params the Sprint 3 rules engine will read.
- `ScholarshipApplication` model — one application per student per cohort (partial unique
  constraint), explicit shortlisting inputs + a `form_data` JSON blob for everything else.
- Intake API: `GET/POST /api/v1/scholarship/applications/` + own detail. Resolves the open
  cohort, snapshots the SPM A-count from the linked profile, sends a trilingual acknowledgement
  email, stamps `acknowledged_at`. Rejects anonymous / duplicate / closed-round.
- Trilingual (EN/MS/TA) acknowledgement email, best-effort (never blocks recording).
- RLS deny-by-default SQL for the two new tables (apply before deploy).

## What Went Well
- Heavy reuse paid off: the HS256-token test pattern, default-deny permissions, the NRIC-gate
  middleware and the `send_mail` infra all dropped in cleanly — the intake endpoint needed
  zero new auth code.
- Reading `lessons.md` / `decisions.md` up front meant explicit `db_table` names, `BooleanField`
  flags, and the service-module split were right on the first pass — no rework.
- Golden masters untouched (no eligibility logic touched), so the 1023-test suite gave high
  confidence with no engine risk.

## What Went Wrong
- **Symptom:** During planning I asserted "WhatsApp-first; email is dead — 0 of 91 students have
  email" and wrote it into the PRD, then had to reverse it when the user pointed out all students
  authenticate via Google Sign-In (so every account has a verified Gmail).
- **Root cause:** I treated a back-office MySkills admin spreadsheet — where the Email column was
  simply left blank/"N/A" — as authoritative evidence of contact-data absence, without checking
  how HalaTuju accounts actually capture email (Google OAuth).
- **System change:** Added a `lessons.md` entry — before drawing a data-driven conclusion that
  changes architecture, verify the *authoritative* source (how the live system captures the
  field), not a convenience export. A blank column is not evidence of absence.

## Design Decisions (logged in `docs/decisions.md`)
- Separate `apps/scholarship/` app rather than extending `apps/courses/`.
- Explicit shortlisting fields + `form_data` JSON blob on the application.
- RLS deny-by-default (no policies) — Django service role bypasses, direct PostgREST denied.
- PII source docs (`docs/scholarship/*.pdf|xlsx|txt`) gitignored — real student NRICs/names/
  financials must never enter the repo.

## Numbers
- ~16 files added (app package, 2 models, migration, serializers, service, emails, views, urls,
  RLS SQL, 2 test modules) + 2 edits (settings, root urls).
- Tests: 17 new; full backend suite **1023 pass / 0 fail**.
- Golden masters: SPM 5319, STPM 2026 (unchanged).

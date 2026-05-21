# Retrospective — B40 Assistance Programme, Phase 1 Sprint 3

**Date:** 2026-05-21
**Sprint goal:** Mechanical shortlisting engine + Bucket A/B + pass/fail emails.
**Branch:** `feature/b40-assistance` (not merged, not deployed)

## What Was Built
- `shortlisting.py` — pure `evaluate(app, cohort)` → status/bucket/reason; thresholds from the cohort.
- `shortlist_application()` wired into intake (synchronous; pass email immediate).
- Trilingual pass + fail emails via a shared `_send` helper.
- `send_pending_decision_emails` command for the delayed fail email.
- Model fields `shortlisted_at`, `decision_email_sent_at`, `locale`, `notify_email` (migration 0002).

## What Went Well
- The pure-engine design made the rules a deterministic golden master — 19 unit tests pin every
  bucket boundary with no DB and no mocking.
- Storing `locale` + `notify_email` at submit made the deferred command fully self-contained — it
  needs no request context at send time.
- Running the full suite (1048/0) confirmed the new intake behaviour didn't disturb the engine.

## What Went Wrong
- **Symptom:** adding shortlisting to the intake path silently changed an earlier sprint's test
  expectations (Sprint 1's "submit → `submitted`, 1 email" became "`shortlisted`, 2 emails").
- **Root cause:** a later sprint extended a code path that an earlier sprint's tests asserted on.
- **System change:** `lessons.md` entry — when a sprint changes behaviour in an earlier sprint's
  code path, update that sprint's tests in the same sprint and run the **full** suite (not just the
  new tests) to surface the drift.

## Design Decisions (logged in `docs/decisions.md`)
- Synchronous shortlist on submit; pass email immediate, fail email deferred via command.
- Store `locale` + `notify_email` on the application so the deferred command needs no request context.

## What's Not Verified
- The command works (tested via `call_command`), but its scheduler (Cloud Scheduler) is not wired —
  deploy work, deferred with the Supabase migration/RLS.

## Numbers
- ~13 files. Tests: 25 new; backend suite **1048 pass**. Golden masters unchanged.

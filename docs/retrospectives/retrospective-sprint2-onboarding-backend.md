# Retrospective — B40 Phase E/F Sprint 2: Student post-match onboarding, backend (F8a)

**Date:** 2026-06-08
**Branch:** `main` (held local, not pushed — ships dark; deploy owner-gated)
**Migration:** `0049_f8a_onboarding` (additive — apply migrate-first at deploy)

## What Was Built

The backend half of student post-award onboarding, on the existing award path.

- **Award-confirmed email** — `send_award_confirmed_email` (trilingual `AWARD_CONFIRMED_SUBJECTS/BODIES`), fired from
  `respond_to_award` on accept, after the `sponsored` status flip. Carries **no sponsor identity** (B4) — only that
  funding is confirmed + the onboarding link. Best-effort (a mail failure never blocks the accept).
- **`onboarded_at` gate** — new nullable `ScholarshipApplication.onboarded_at`, mirroring `profile_completed_at`. The
  hard gate the disbursement flow will check; surfaced read-only in `ApplicationReadSerializer`.
- **`student_onboarding_ack` consent** — recorded via `record_consent` (`granted_by='self'` — the award acceptance
  already ran the guardian gate for minors). Bumped `CONSENT_VERSION` → `2026-draft-4` (nothing gates on version
  equality, so the bump is safe — it only stamps new consents).
- **`OnboardingResponse` model** — one per application (`OneToOne`), JSON `answers`, FK to the ack `Consent`,
  `submitted_at`/`updated_at`. A dedicated row (not a JSON blob on the application) for a clean audit trail.
- **`complete_onboarding(...)` service + endpoint** — `POST /applications/<id>/onboarding-complete/` records the
  consent, upserts the response, stamps `onboarded_at`. Refuses unless the award is accepted (`400 not_awarded`).
  `update_or_create` makes a re-submit idempotent (latest answers win, no duplicate row).

## What Went Well

- **Clean hook points.** `respond_to_award` and `record_consent`/`confirm_profile` were the right seams — the email
  is one call after the existing status flip, and the consent reuses the versioned `record_consent` machinery.
- **No migration churn.** The enum-like `consent_type` is an open `CharField`, so the new consent value needed no
  migration; only the genuinely new column + table did. One clean `0049`.
- **Anonymity verified by test, not by reading.** `test_accept_emails_award_confirmed_without_sponsor_identity`
  asserts the sponsor's name/email never appear in the sent mail — the B4 guarantee is now a regression test.

## What Went Wrong

- **The award-email test first failed (`0 != 1`) because the fixture's `notify_email` was blank.**
  *What happened:* `_send` no-ops silently when `to_email` is empty, and `_fundable_app` never set `notify_email`, so
  the best-effort send returned False and `mail.outbox` was empty. *Why:* a best-effort email swallows the "no
  recipient" case, so a fixture gap looks like a code bug. *Fix:* populated `notify_email` on the fixture (realistic —
  a real accepted application always has it). *Lesson (captured):* when testing that a best-effort email fires, ensure
  the recipient field is populated in the fixture, or the send silently no-ops and the assertion misreads as a code
  failure.

## Design Decisions

- **`OnboardingResponse` as a dedicated model, not a JSON blob on `ScholarshipApplication`.** (Logged in
  `decisions.md`.) The questionnaire is an audit artifact; a row with its own consent FK + timestamps reads cleaner
  than a column, and keeps the application table from accreting onboarding-shaped JSON.
- **Bump `CONSENT_VERSION` globally rather than version per consent type.** The codebase uses one global student
  consent version stamped on every consent; the roadmap calls for the bump, and nothing gates on equality.

## Numbers

- **Backend:** 873 scholarship pytest (5 new) green; migration check clean (`0049`).
- **Frontend:** none this sprint (F8b is Sprint 3) — jest/build untouched.
- **Files touched:** 8 (models, services, emails, sponsorship, serializers, views, urls, tests) + 1 migration.
- **Migrations:** `0049` (additive: column + table). **Deploys:** 0 (held; ships dark).
- **Carried:** TD-093 (enable RLS on `onboarding_responses` at the migrate-first deploy).

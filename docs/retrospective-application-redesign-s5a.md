# Retrospective — Step-4 Redesign S5a: Completeness finalise + "What happens next" (v2.4.4)

**Date:** 2026-05-28
**Shipped:** web `halatuju-web-00217-7t7`, api `halatuju-api-00173-4nm` (both builds SUCCESS, 100% traffic, smoke 200). **No migration.**

## What Was Built

S5 was split into **S5a (applicant-facing)** — this sprint — and **S5b (admin + AI)**, queued.

- **Completeness loop closed.** `application_completeness` gains `consent_done` (an active `Consent` row exists) and `complete` is now the full 5-part rollup: quiz + story + funding + compulsory-docs + consent. This **supersedes S4's interim** state where `complete` deliberately excluded documents/consent.
- **`notify_email` exposed** read-only on `ApplicationReadSerializer` — the address decision/comms emails are actually sent to (resolved at submit).
- **Real step ticks.** `ScholarshipNextSteps` now maps Documents → `documents_done` and Consent → `consent_done`; these had been hardcoded to `false` since S4 added the backend signal but never wired the UI.
- **A reassuring finish.** When all five steps are done, the intro banner switches to a green **"You're all set!"** state and a **"What happens next"** card appears — a 3-step plain-language timeline (we review → we may call you in your preferred language → decision by email) plus a note stating the exact email updates go to.

Progress bar, "Step X of 5", per-step ticks and the desktop 2-column rail were already delivered in S1 — this sprint only wired the remaining signals and added the finish panel.

## What Went Well

- **Small, contained — done in the main thread.** ~8 files, no migration; no subagent needed. Stitch-prototyped + signed off first, then built straight through.
- **S4's regression test paid off.** The S4 test `test_complete_not_affected_by_documents_done` (which asserted the interim contract) failed loudly the moment `complete` changed — exactly the signal to update the contract deliberately rather than by accident. Replaced it with `test_complete_requires_documents_and_consent`.
- **`notify_email` was already on the model** (stored at submit since the Sprint-3 decision) — the comms-email note needed only a read-only serializer field, no new data capture.

## What Went Wrong

1. **The full backend suite reported 24 "errors" that weren't real.**
   - *Symptom:* `pytest` (full suite) finished `1104 passed, 24 errors`, all 24 in `apps/courses/tests/test_api.py::TestEligibilityEndpoint`.
   - *Root cause:* I ran the full backend suite **concurrently with `next build`** on an 8GB-RAM machine. `TestEligibilityEndpoint` loads the large course DataFrame at app init (`AppConfig.ready()`); under memory/CPU contention from the Node build, its setup raised `ERROR` (not assertion failures). Re-running the class in isolation gave **24 passed**. My change touched only the scholarship app — it could not have affected courses.
   - *System change:* added a lesson — don't run the full backend `pytest` (it loads the heavy course DataFrame) at the same time as `next build` on this machine; serialise them, or run the eligibility tests alone. Treat a burst of *setup ERRORS confined to one heavy test class* as a contention smell, not a regression — re-run in isolation before believing it.

## Design Decisions

- **`consent_done` = any active `Consent` row** (`consents.filter(is_active=True).exists()`). The consent step records a single type (`share_with_sponsors`), so "any active consent" is equivalent today and robust to the type-string; if a second, independent consent type is ever added, this would need to gate on the specific required type.
- **`complete` finalised to the 5-part rollup** (supersedes the S4 interim). Documents + consent are genuine gates before a profile is sponsor-ready; S4 deferred them only to keep sprints independently shippable.
- **`notify_email` exposed read-only** (declared `EmailField(read_only=True)`) rather than reusing the logged-in user's email client-side — the application's resolved `notify_email` is the truthful "where updates actually go" value, and read-only prevents the read serializer from ever accepting a write to it.

(Logged in `docs/decisions.md`.)

## Numbers

- Files changed: 8 (`services.py`, `serializers.py`, `test_details.py`, `api.ts`, `ScholarshipNextSteps.tsx`, en/ms/ta.json) + CHANGELOG. No migration.
- Backend: 1128 pytest (the 24 "errors" were contention — clean in isolation).
- Frontend: jest 125; `next build` clean (38 routes).
- i18n parity: 1235 keys × {en, ms, ta} (+8). Tamil copy first-draft — flagged for the user's refinement (with the S4 copy).
- Deploys: 1 (web + api together).

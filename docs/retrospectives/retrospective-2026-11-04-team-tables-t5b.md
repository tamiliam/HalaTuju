# Retrospective — Team tables T5b (QC self-sufficient + widened self-QC guard) — 2026-11-04

Live 2026-11-04: main f44f0a8b; api halatuju-api-01248-ggf, web halatuju-web-01076-gr4. Both Cloud Builds passed
first time. Commits 2a41c5e6 (feat), 730a7216 (fix, review round 1); merges 54a77ec1 and f44f0a8b. Live access is
unchanged for every live shape.

## What was built
- `qc` now implies `see_all` (`staff_permissions.IMPLIES`, replacing `DEPENDS_ON`). A stored `['qc']` reads as
  `see_all + qc`, so every `see_all` reader opens for it by construction. The editor saves `['qc']` as `see_all + qc`.
  It never seats anyone at Admins.
- The QC decision (accept, reopen, reject) refuses anyone who was ever assigned the case, sat as interviewer or
  proposed its interview times (a draft counts), verify-accepted it, recorded its verdict, or has review work in their
  activity list (`apps/scholarship/qc_separation.refusal`). A super stays exempt.
- Round 1: the activity verb `interview_drafted` (migration 0202, choices only), so an author whose interview credit
  was later overwritten by a colleague is still refused. Shown on My activity in en / ms / ta.

## What went well
- The adversarial review found the interviewer-overwrite door that the builder's door list missed. It was fixed in
  730a7216 in the same sprint (TD-482 closed).
- Both new guards were proved by deliberate breaks: each test went red with the guard removed.
- The production data check was done before release: 3 custom permission rows, none holding `qc` without `see_all`,
  so no live access changed.

## What went wrong
- **The migration's ledger row went in after the push.** Symptom: `0202_staff_activity_interview_drafted` was
  recorded in production `django_migrations` just after the push, not before it as the migrate-first rule says.
  Harmless, because the migration is choices only and has no DDL. Root cause: the lead did not re-read the
  migrate-first rule after review round 1 added a migration; the first build had none, so the step was not on the
  checklist in mind. Fix: a review round that adds a migration re-runs the migrate-first step (apply, verify, ledger
  row) before the push. Added to `docs/lessons.md`.

## Design decisions
- Implication, not dependency: `qc` carries `see_all` itself, so no reader needs a special case for QC.
- The guard lives in one module, so a new kind of review work is added in one place with its test.
- Review answers: should-fix 1 fixed (730a7216); should-fix 2 checked on production (no change); should-fix 3 is
  TD-484; the notes are TD-485, TD-483 (extended) and TD-481 (the reviewer's Decline door skips QC; old behaviour).
- Owner ruling 2026-11-04: TD-481 is fixed in its own small sprint next, with an adversarial review.

## Numbers
- api: 12,107 passed, 3 skipped (`pytest -n auto`); `manage.py check` and `makemigrations --check` clean.
- web: `npm run gates`, 411 suites / 6,376 jest passed; `bundle-budget --gate` passed; `next build` passed.
- Open debt raised: TD-481, TD-483, TD-484, TD-485. Closed: TD-482.

## Next
TD-481 (awaiting-QC Decline goes through the QC gate; adversarial), then T5c.

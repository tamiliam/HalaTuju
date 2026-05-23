# B40 Redesign — Sprint 8 Retrospective (2026-05-24)

The deterministic decision engine + silent-score + delayed reveal. Branch `feature/b40-redesign`, not deployed.

## What Was Built
- `shortlisting.py` rewritten to the settled rule (gates → academic floor 4A-+1B+ / PNGK 2.9 → income
  STR-or-per-capita < RM1,584); `evaluate()` returns verdict + bucket + reason. No score / weights / hardship.
- Submit scores **silently** (`score_application`): verdict + `decision_due_at` stored, status stays `submitted`,
  acknowledgement email only. `release_decision` (scheduler) flips status + sends the verdict email at the due time.
- Delays: **+2h** shortlist (invitation), **+48h** decline (warm email with seminar-invite wording, EN/MS/TA).
- Cohort thresholds + delays; application verdict/timing fields. Migration scholarship `0008`.

## What Went Well
- The settled rule is far simpler than the earlier weighted-score sketch — less code, fewer config knobs, easier
  to test and to defend. Dropping hardship flags + the 0–100 score removed a whole swathe of planned work.
- Baseline-first + a targeted run-then-fix surfaced exactly the 22 affected tests (engine / scheduler / submit /
  defaults) with no hidden breakage.

## What Went Wrong
- **(Expected) 22 tests failed on first run** — the entire old engine test file, the deferred-fail-email tests,
  two submit assertions, and the cohort-defaults test. *Root cause:* S8 replaced the engine wholesale and changed
  the submit contract (instant → silent) plus cohort defaults. *Fix:* rewrote `test_shortlisting` to the new rule,
  rewrote `test_decision_emails` to the release-due model, updated the submit + defaults tests; full suite green.
- **Watch-out → lessons.md:** the pure-engine `SimpleNamespace` fixture silently returns `None` for any attribute
  the engine reads but the fixture omits (e.g. the new `household_size`, `upu_status`) — no loud failure. Rebuilt
  the fixture to include every input the engine now reads.

## Design Decisions
- Deterministic per-capita + STR + academic-floor rule supersedes the weighted score — see `docs/decisions.md` (2026-05-24).

## Numbers
- Backend tests **1091 → 1093**, 0 failures, golden masters intact (SPM 5319, STPM 2026).
- Files: ~10 (shortlisting, models, migration 0008, services, views, scheduler command, emails, 4 test files).

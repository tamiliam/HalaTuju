# Retrospective — Code-health Sprint 4: income/STR consistency (2026-07-03)

## What Was Built

Findings #13–#20 of the code-health roadmap — the cluster of inconsistencies the STR-proof
commits (8b4686b1/97b59918/7a7586e7) left across their consumers:

1. **#13** `STR_RED_STATES` / `STR_COACH_STATES` in income_engine are now the single source of
   truth for the cluster coach, the re-upload reconcile (resolution.py) and the submission
   blocker (services.py). The coach now covers `wrong_type`/`unreadable`; the blocker gains
   `wrong_type`.
2. **#14** Salary-route I4 runs through `income_headroom` — gross ceiling honoured, boundary
   inclusive. `income_headroom` itself now tolerates a cohort without a gross ceiling.
3. **#15** `_cluster_docs`: the legacy-blank fallback attaches to the named earner only
   (fully tolerant reading preserved for blank-wizard legacy apps).
4. **#16** `profile_engine._income_evidence` uses `effective_working_members` (the missed #90
   call site).
5. **#17** The STR-route verdict selects the earner's IC via `_member_ic_doc` (was
   member-agnostic latest).
6. **#18** `income_cluster_advice` only blames the relationship doc when the earner IC has
   actually been read (`ic_ran` gate) — a pending IC is silent, not a false re-upload demand.
7. **#19** The STR fall-through headroom assesses every member with income evidence.
8. **#20** `income_declared_needs_evidence` is decided before the blue `review` return.

## What Went Well

- The shared-tuple refactor immediately surfaced its own calibration question (below) via the
  test suite — 18 failures on the first run were all genuine semantic questions, not noise.

## What Went Wrong

- **First cut of #13 put 'unreadable' in the RED tuple and broke 18 consent/verdict tests.**
  Root cause: a never-scanned legacy doc ALSO reads 'unreadable', so blocking on it would gate
  consent on our own extraction backlog — and per the spec 'unreadable' is amber (misread ≠
  disproven). Fix: RED = (wrong_type, rejected, stale); the coach separately covers
  unreadable/unconfirmed. The failing tests were the spec doing its job.
- **First cut of #15 removed the blank-tag fallback for blank-wizard legacy apps** — the
  consent fixtures (real legacy shape) caught it; the earner-only restriction now applies only
  when an earner is actually named.
- **First cut of #14 mapped headroom's thin-margin 'unsure' to amber on the salary route**,
  demoting historically-green verdicts beyond the finding's scope. Settled: I4 keeps its
  binary green (the cluster is fully confirmed on that path); band-grading remains the
  fall-through's compensation for an unverified household — revisit in the salary-track
  redesign. Lesson: when unifying two code paths on a shared helper, port the TEST the
  finding names, not the whole band semantics.

## Design Decisions

Logged in `docs/decisions.md` (S4 entry): red-tuple membership ('unreadable' amber),
earner-only blank fallback with legacy tolerance, I4 binary-green vs fall-through grading.

## Numbers

- 3,215 backend tests (2,016 scholarship + 1,199 courses/reports), 0 failures; +10 net new.
- No migration, no FE change, no i18n change.
- Reviewer-visible on deploy: a wrong_type/unreadable STR now nudges the student; some
  previously "over the line" small households read verified (gross-ceiling rescue) — both intended.

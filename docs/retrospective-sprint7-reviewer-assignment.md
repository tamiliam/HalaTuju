# Retrospective — B40 Phase E/F Sprint 7: Reviewer assignment / reassignment (F7)

**Date:** 2026-06-09
**Branch:** `main` (held local, not pushed — deploy owner-gated, batched for go-live)
**Migration:** `0052` (`assigned_at` field + new `AssignmentEvent` model — apply via MCP + enable RLS at deploy; TD-100)

## What Was Built

A super admin assigns / reassigns / unassigns a submitted application to a reviewer, audited and gated.

- **`services.assign_reviewer(application, *, reviewer, by_admin)`** — one service for all three operations: validates a
  non-null target is an active reviewer/super (`not_reviewer`), gates the **first** assignment of an unassigned app on
  `is_ready_for_assignment` (`not_ready`), allows reassign/unassign any time, writes an `AssignmentEvent` (from → to,
  by-whom) on every change, stamps `assigned_at` (null on unassign), and no-ops silently when the target is unchanged.
- **`POST .../applications/<id>/assign/`** (`AdminAssignReviewerView`) — super-only; resolves `reviewer_id`
  (null/''/0 = unassign), maps `AssignmentError` → 400 `{code}`.
- **`AssignmentEvent`** audit model (`application`, nullable `from_admin`/`to_admin` FKs, `by_email`, `created_at`);
  `ScholarshipApplication.assigned_at`.
- **Removed** the loose reviewer-gated `PATCH assigned_to` branch — assignment now has exactly one super-only audited path.
- **Cockpit:** the "Assign a reviewer" card is super-only, lists only reviewers/supers, disables the first assignment
  (with a reason tooltip + amber hint) until the app is ready, shows the current assignee, and surfaces the server
  error codes. Trilingual `admin.scholarship.assign.*`.

## What Went Well

- **One path, not two.** Collapsing assign/reassign/unassign into one service + one endpoint (vs the roadmap's
  two-endpoint sketch) keeps the validation/gate/audit logic in a single place and removed a real gap — the old PATCH
  let any reviewer reassign with no audit and no target-role check.
- **Audit by construction.** Every state change goes through the service, so there is no way to mutate `assigned_to`
  without an `AssignmentEvent` — proven by the no-op and reassign tests.
- **Earlier-sprint tests updated in lockstep (lesson #48).** Removing the PATCH-assign branch broke two Phase-C tests;
  they were repointed to the new endpoint in the same sprint, and the full suite (not just the new tests) was run.

## What Went Wrong

- **Two Phase-C tests failed after the PATCH branch was removed.** *Symptom:* `test_reviewer_can_assign` /
  `test_assign_unknown_admin_400` failed because they drove the now-deleted `PATCH assigned_to` path. *Root cause:* the
  old assignment tests lived in the Phase-C file and weren't surfaced until the full suite ran — the exact
  "new-tests-only run hides the drift" pattern lesson #48 warns about. *Prevention (already the rule):* run the full
  app suite, not just the new test file, before committing — which is what caught it. Repointed both to the new
  endpoint; a local-only `timezone` import then bit the helper (caught immediately by re-running).

## Numbers

- **Backend:** 1945 pytest (901 scholarship + 1044 courses/reports; +9 new assignment tests + 3 repointed Phase-C) green.
- **Frontend:** `next build` clean; 276 jest green (cockpit is render-only).
- **i18n:** parity 2338 × en/ms/ta (+5 `admin.scholarship.assign.*`).
- **Files touched:** 13 (6 BE + 2 BE tests + migration; api-client + cockpit + 3 message files).
- **Migration:** `0052` (new model). **Deploys:** 0 (held). **Carried:** TD-100 (apply `0052` via MCP + RLS at deploy).

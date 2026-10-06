# Retrospective — rejection record shows the decision trail (2026-07-15)

Branch `feat/decision-trail` (worktree `.worktrees/decision-trail`, off `origin/main`). A
display-only change; no migration, no student-facing email, no deploy yet (owner-gated).

## What Was Built

The officer cockpit's rejection record collapsed a multi-step decision into one line — "Declined
by {name}" — while the "Justification and conclusion" box still showed the *reviewer's
recommendation* text. On a case that a QC reopened and re-declined (applicant #51: Kaneswaran
recommended → Ve. Elanjelian reopened on a "5A- is the absolute minimum" merit reason → declined),
the record read as self-contradictory and the QC's real reason — recorded on the `DecisionReopen`
row — was nowhere on the surface.

- **Backend:** `AdminApplicationDetailSerializer.last_decision_reopen` exposes the most recent
  reopen (open OR closed) as `{reopened_by, reopened_by_name, reviewer_name, reason, created_at,
  resulted_in_change}`, or null. New `reopen.latest_reopen()` helper (sibling to `open_reopen`).
- **Frontend:** the rejected record card renders **Recommended by {reviewer} → Reopened by {who} ·
  {date} — "{reason}" → Declined by {who} · {date}** when a reopen exists; a straight decline with
  no reopen keeps the single line. One new i18n key (`reopenedBy`, en/ms/ta).

## What Went Well

- **The data was already there.** The reviewer attribution, the reopen reason, and the decline
  stamps were all recorded (`DecisionReopen` + `verdict_decided_by`/`rejected_by`); the whole fix
  was a serializer field + a render change. No schema, no backfill.
- **Grounded the test in the real case.** The serializer test uses #51's actual values (its NRIC,
  reviewer name "Kaneswaran Sinakalai", and the real "5A- absolute minimum" reopen reason), so the
  three passing tests confirm the exact shape #51 will render — not a synthetic stand-in.

## What Went Wrong

- **Scope was cut twice before it settled — but that was the process working, not a failure.**
  The original two-part proposal (Part 2: a reviewer decline-reason dropdown + varied decline
  emails) was designed, approved, then withdrawn by the owner ("the existing interview rejection
  email is sufficient"). *Root cause:* the email-copy inventory that showed the existing `interview`
  template already reads as a "limited funds" message only surfaced *during* the Part-2 design, not
  before it — so the owner couldn't judge "is the generic enough?" until the copy was on the table.
  *Prevention:* when proposing a differentiated-messaging feature, pull the existing copy into the
  proposal up front, so the "do we even need variants?" call is made before design effort is spent.

## Design Decisions

- **Surface the LATEST reopen (open or closed), not only the OPEN one.** The existing
  `decision_reopen_reason` returns '' once a reopen is closed, which is right for the "held from
  sponsors" banner but wrong for a historical trail. `latest_reopen()` is a separate helper so the
  banner keeps its live-only semantics and the trail gets the last correction whether or not it's
  still open. Minor, but recorded so the two reopen readers aren't later "unified" by mistake.

## Numbers

- `pytest apps/scholarship/tests/test_decision_reopen.py` **19 passed** (+3 new trail tests).
- jest i18n parity/orphan **7 passed**; `next build` **exit 0**.
- Files: 2 backend (`reopen.py`, `serializers_admin.py`) + 1 test, 2 frontend
  (`[id]/page.tsx`, `admin-api.ts`), 3 i18n one-liners. No migration.

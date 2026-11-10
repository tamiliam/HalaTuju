# Sprint T1 — The Assign picker offers only Reviewers who cover the gift (brief, 2026-11-09)

Executor: Opus agent. Architect: main session. Roadmap: `docs/plans/2026-11-08-activity-box-roadmap.md` (T1, D7).
That roadmap lives on the `activity-box` branch, not on main. Read it from
`/Users/elanjelian/Python/Production/HalaTuju/.worktrees/p1-activity-box/docs/plans/2026-11-08-activity-box-roadmap.md`.
Branch `t1-assign-picker`, cut from `origin/main` (3565011c), which already holds G6 A2.3 (the background assign email
and the slim assign reply). Local only: no push.

## Goal
Only someone in the **Reviewers table** who **covers the case's gift** can be given a case, whoever is assigning (a
super included). Cases already held stay with their holder and still show that holder's name.

## Facts (verified by the architect; confirm before relying on them)
- **The rule today** (`scholarship/services/assignment.py`):
  - `may_assign_to(caller, target)` (~56-72):
    - a super caller gets `is_review_target(target)`, which is `review`, OR the R1 override: role admin / qc /
      org_admin holding `see_all`;
    - an org_admin caller gets an own-organisation, non-super `review` holder;
    - anyone else gets nobody.
  - `is_review_target` (~40-53) is ALSO read by `scheduling._can_review` (scheduling.py:133), `_can_review`
    (assignment.py ~124, ~150) and `reviewers.py:373` (`pausable`). **Do not change `is_review_target`.**
    - Narrowing it would strand a case an admin holds today: they could no longer act on it.
    - `R1_SUPER_TARGET_ROLES` stays for it and for the listing query.
  - `assign_reviewer` (~231) re-asks `may_assign_to` on the LOCKED target row and raises `not_reviewer`. It then
    checks `_can_review` (revoked / paused), then `gift_allows` (`gift_mismatch`, already enforced for every caller
    since 2026-11-06).
- **The Reviewers table:** `courses/staff_tables.in_reviewers(admin)` (~79).
  - It covers an active team member (`_team_member`: never a super) whose role is reviewer / qc, or who holds
    `review` or `qc`.
  - It also covers an org admin who joined Reviewers (`staff_permissions.lead_reviews`).
  - **A super is not in Reviewers**, so after T1 a super can assign but is never assigned.
- **Endpoints:**
  - `AdminAssignCaseView` area, `views_admin/verdict.py` ~515-535: an org_admin's refused target gets `bad_assignee`
    (400); a super's target is the service's to judge.
  - `AdminAssignableAdminsView`, `views_admin/lifecycle.py:299`:
    - It LISTS everyone who could hold a case, so a held case's assignee never vanishes (bug #66).
    - It serves `assignable` (= `may_assign_to`) and `gifts` per row (`[]` = every gift).
- **Web:**
  - The applications list dropdown, `app/admin/scholarship/page.tsx` ~430-450:
    - it filters by `rv.assignable` (the current assignee is always kept);
    - it orders by language (`orderReviewersFor`, ✓ / ⚠);
    - it does NOT filter by gift today.
  - The case page picker is `app/admin/scholarship/[id]/view/AssignAndWitness.tsx`. It already reads `gifts` and
    greys a reviewer of another gift.
  - The error codes are mapped at `page.tsx` ~227 and `[id]/view.tsx` ~500. `not_reviewer` and `gift_mismatch` are
    already translated in en/ms/ta.
- **Production count (2026-11-09, read-only):** cases held by someone outside Reviewers: 1 awarded (an org_admin)
  and 1 rejected (a super). **No open case is affected.**

## Settled decisions
| # | Decision |
|---|---|
| T1-a | `may_assign_to(caller, target)`:<br>• a super caller gets `in_reviewers(target)`;<br>• an org_admin caller gets `in_reviewers(target)` AND the target is of the caller's own organisation (never a super, which `in_reviewers` already excludes);<br>• anyone else gets nobody.<br>The R1 override is retired for ASSIGNING only. `is_review_target` is untouched (see Facts). |
| T1-b | The gift stays where it is: `gift_allows` in `assign_reviewer`, for every caller. `may_assign_to` does not take the case. |
| T1-c | The refusal code stays `not_reviewer` (the roadmap's `not_a_reviewer` is not a new code). It is already translated and mapped, so no API break. The org_admin endpoint path keeps `bad_assignee`. |
| T1-d | A held case is kept. Nothing reassigns or unassigns it, and its assignee still shows in both pickers. Re-picking the current holder skips `may_assign_to` (only the holder): an active holder is the existing no-op, and a paused or revoked holder is refused as before. The web never sends a same-value pick. |
| T1-e | **The applications list dropdown:** it shows the current assignee, plus every row that is `assignable` AND covers THAT case's gift (`gifts` empty = every gift). It hides the rest.<br>• If the list rows do not carry the case's gift ids, add the smallest field that does (the programme and the cohort's programme, as `services.assignment.case_gifts` reads them). Keep the list query budget.<br>• ✓ / ⚠ keep meaning the call language. Add one legend line under the dropdown or in the table header, whichever passes mobile-check: "✓ speaks the student's language · ⚠ does not". Write it in en/ms/ta. |
| T1-f | **The case page picker** follows the same rule:<br>• `assignable` false: hidden, except the current holder;<br>• another gift: it keeps today's greyed row with its reason (no change), so the case page still explains a missing gift reviewer. |
| T1-g | `docs/decisions.md`: a new entry that supersedes the R1 super-target override (the 2026-10-19 lead ruling recorded in `services/assignment.py` and decisions.md ~489-498) for assignment. Note that supers are no longer assignment targets. |

## Build
- **API:**
  - `may_assign_to` per T1-a. Rewrite its docstring and the R1 comment block to say what is true now.
  - Leave `is_review_target`, `_can_review` and `scheduling._can_review` as they are.
- **Tests:** update the tests that encode R1 (grep `may_assign_to`, `R1_SUPER`, `assignable-admins`). The known ones are
  `test_assignment.py`, `test_gift_scoping_sources_and_assignment.py`, `test_permission_combinations.py`,
  `test_org_gates.py`, `test_qc_gate.py`, `test_team_tables_t2.py` and `test_role_is_display_only.py`. The fixtures
  `team_tables_access_*before.json` must only change where the rule truly changed: list each changed cell in the
  commit message.
- **New API tests:** as a super caller, each of these is `assignable: false` AND refused by `POST assign` (`not_reviewer`):
  - an admin with `see_all`;
  - an org admin not in Reviewers;
  - a qc-role person without `review`/`qc` (if constructible);
  - another super.
  As an org_admin caller: an own-organisation Reviewer is accepted; another organisation's is refused. Also:
  - an org admin who joined Reviewers (`lead_reviews`) is assignable;
  - a case held by an admin (set directly) still lists that admin, and the holder can still act on it:
    `scheduling._can_review` stays true;
  - a reviewer of another gift is refused `gift_mismatch` (exists; keep it).
- **Web:** T1-e and T1-f, with tests:
  - the list dropdown hides a non-assignable row and a row of another gift;
  - it keeps the current holder even when they are neither;
  - an every-gift reviewer shows for any case;
  - the legend renders.

## Done when
- The new tests above pass, and the R1 tests are rewritten to the new rule (not deleted without a replacement).
- **Gates:** targeted tests while building, then once through
  `python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <cmd>`:
  - API: pytest, `manage.py check`, `makemigrations --check`;
  - web: `npm run gates`, bundle-budget, mobile-check.
  - mobile-check needs `halatuju-web/.env.local`: copy it from the main checkout and delete it afterwards.
- **Docs:** CHANGELOG, `docs/decisions.md` (T1-a to T1-g), and the `docs/scholarship/role-matrix.md` row for assignment
  if it names R1.

## Rules
- Commit locally on `t1-assign-picker`.
  - Stage explicit paths only (never `git add -A`); no bare `git stash`.
  - Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - **No push.** Never touch main, other worktrees, `.venv` or untracked files.
- Never deploy. Make no production read or write.
- Use no real names, emails or other PII in fixtures, logs or commits.
- Write British English in plain language.
- Bash: absolute paths, no inline `VAR=`, no `$()`.
- Sprint S1 (`s1-scholars-access`, in flight) edits `staff_permissions.py`, `staff_tables.ADMIN_KEYS`, the Scholars
  views and permission labels in `messages/*.json`.
  - T1 must not edit those beyond what T1 needs.
  - It must never touch the `see_all` / Applications labelling.

## Risks
- **Supers stop being assignable.** One rejected case sits with a super, and it stays. Say so in the report.
- **Both pickers depend on `assignable`.** If a page loaded before the change sends an old target, the server
  refuses with `not_reviewer`, which is already worded.
- **List payload growth** (if a gift field is added): keep the list query budget and the bundle budget, and never
  raise either.

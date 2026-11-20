# Sprint S1 brief: case and team leftovers (ACCESS-BY-SWITCHES)

**Parent plan:** `docs/plans/2026-11-19-access-by-switches-roadmap.md`, section S1. **Template:** `docs/plans/2026-11-14-m3-lead-keys-brief.md`.
**Branch:** `access-s1-leftovers` (worktree `.worktrees/access-s1-leftovers`, cut at origin/main `dbbf1de88`).
**Brief written 2026-11-19, from reads only.** Every file:line below was checked against `dbbf1de88`. Re-check them before you edit.

## 1. Context and outcome

POST-AWARD-CUT made `may_write_case` the one write rule and served `can_write`, `can_cancel_decline` and `can_tranche` to the cockpit. Some loose ends remain:

- The cockpit still works out three controls from the role:
  - the QC panel;
  - the pre-award Close card;
  - the phone's decision bar on a reopened past-award case.
- Twelve write replies still send back the bare serializer.
- The finalise cron can still make a paid Gemini call for a case that is no longer open.
- Six small team debts and four stale register headings are left.

**Outcome:**
- Every case control is drawn from a flag the server serves.
- Every case write reply carries those flags.
- The cron makes no paid call for a case that is not OPEN.
- The scholar activity box is drawn from a served flag, which S4 needs before it moves the write key.
- TD-627, 616, 634, 630 and 618 are fixed. TD-615 waits for an owner answer.
- TD-621, 622, 631 and 633 are closed with live evidence.

There is no money effect and no migration, except under the TD-603 option in §3.

**One principle:** serve, never derive. Each new flag is computed by the same function the door asks, and that function has one home.

## 2. Verified facts (file:line at `dbbf1de88`)

### 2.1 TD-664 (f): the finalise cron's paid leak
- **Code:**
  - `halatuju_api/apps/scholarship/profile_finalise.py` (225 lines).
  - `claimable(now)` at :90-92 is only the claim-age Q.
  - `_claim_row` at :95-99 is the conditional update.
  - `run_finalise(sp_id)` at :175-196: claim, load, `refine_sponsor_profile` (paid), `_write_result`.
  - `run_pending` at :199-225 takes the oldest `BATCH` (3) pending ids, and runs `counts[run_finalise(sp_id)] += 1` (:219).
- **Wrong:** nothing re-checks `staff_lifecycle.case_stage` (`staff_lifecycle.py:118-139`). A profile queued while the case was open is still refined, and paid for, after an award, decline, withdrawal or close.
  - The doors already refuse to queue past the award (`profiles.py:81-82`).
  - Decisions 2026-11-17/18 left the cron unchecked on purpose ("Left as it was: the cron (`run_finalise`) does not check the case"). TD-664 (f) is the follow-up to that.
- **Plan correction:** do NOT put the test in `claimable`.
  - It is shared with `assign_draft.py` (:36 import, :77, :119), so the draft queue would change too.
  - A Q filter cannot hold `case_stage` without a second home for the rule.
  - Rows left pending would block the oldest-first batch of 3 for good.
  - Also, :175 is `run_finalise`, not `_claim_row`.
- **Change:** in `run_finalise`, after a won claim and before the refine:
  - if `case_stage(app) != OPEN`, drop the job and return a new outcome `'case_closed'`, with no Gemini call.
  - Do the drop in a new helper `_drop_closed(sp_id, app_id, token)`. Lock the app row, then the profile row (the `_write_result` lock order, :143-146). Check `_still_ours(sp, token)`, then set `finalise_state=''` and `finalise_claimed_at=None`, saving `QUEUE_FIELDS`, as `supersede_pending` (:78-87) does.
  - Add `'case_closed': 0` to the `counts` dict at :206. Otherwise the new outcome raises KeyError and is miscounted as `error`.
  - Update the `run_finalise` docstring's outcome list.
- **Not OPEN, rather than "past the award" (the TD's wording).** The plan says not OPEN, and that is right. A rejected, withdrawn, expired or closed-before-award case is just as wasted a paid call. A super reopen sets the case OPEN again, and the re-recorded verdict re-queues.
- **Accepted window:** a case can move stage during the Gemini call (claim, then award, then write). The call is already paid, and `_write_result` never publishes. Note it in the docstring; do not add a second check.
- **Report only (possible new debt, number at push):** `assign_draft.run_draft` has the same shape and no stage check either.

### 2.2 TD-664 (a): the QC controls come from the role
- **Web:**
  - `app/admin/scholarship/[id]/view.tsx:108` `const canQc = hasPerm(role, 'qc')`, passed to `ReverifyIcCard` (:344) and `QcPanel` (:346).
  - `view/ReverifyIcCard.tsx:21-22` `needsIcReverify(app, canQc)`.
  - `view/QcPanel.tsx` uses `canQc` at :67, :72, :95, :103 and :105.
- **Plan correction:** `QcPanel.tsx:33` is not a `canQc`. It is `qcRefusalFor`'s fallback (:30-35) for a reply without `qc_refusal`, and it re-derives the self-QC rule from the role and `assigned_to_id`. The flag itself is already served (`views_admin/applications.py:54`, `qc_separation.for_viewer`, `qc_separation.py:84-91`).
- **Server door:** `_require_qc` (`views_admin/base.py:450`) asks `admin.has_perm('qc')` at :466, then the org fence, then `status == 'interviewed'`, then `qc_separation.refusal`.
- **Change:**
  - Add `may_qc(admin)` to `views_admin/base.py` beside `served_write_flags` (:172). It returns `bool(admin and admin.has_perm('qc'))`. `_require_qc` :466 calls it, so the door and the flag share one home.
  - Serve `'can_qc': may_qc(admin)` in `served_write_flags`.
  - Web: `canQc` comes from the served ref (below).
  - Once §2.5 lands, every cockpit reply carries `qc_refusal`. `qcRefusalFor` then becomes `return app.qc_refusal || null`, and its `role` parameter and `hasPerm` import go.
  - Builder check: list every `setApp(` source in `view.tsx` and `view/*.ts(x)`, and confirm each reads a `_detail_payload` reply. The assign reply already reloads (`useCaseActions.ts:93`). Report any reply that does not.

### 2.3 TD-664 (b): the pre-award Close card is drawn from the role
- **Web:**
  - `view.tsx:380-381` passes `orgSuper={holdsDoor(role, 'decide')}` to `PostAwardPanels`.
  - `view/PostAwardPanels.tsx` (428 lines) feeds `orgSuper` to `closeOffer(app.status, orgSuper)` at :338, :360, :378 and :392.
  - `closeOffer` is defined at `lib/closeOffer.ts:45`.
- **Server door:** `AdminCloseApplicationView.post` (`views_admin/lifecycle.py:177-190`).
  - It runs `_require_app_write` (= `may_write_case`), then `closure_service.close_application(..., pre_award_allowed=surface_gates.may_decide(admin))`.
  - Owner 18 Nov: the ended-before-award writer is the `students.approve` holder, the `decide` door (`surface_gates.py:97-99`).
- **Change:**
  - Serve `'can_close_pre_award': may_write_case(admin, app) and surface_gates.may_decide(admin)`. That is exactly what the door needs for a pre-award close.
  - The close view reads `surface_gates.may_decide(admin)` itself, so both read the same function.
  - Web: rename the prop `orgSuper` to `canClosePreAward`, fed from the served ref.
  - Rename `closeOffer`'s second parameter the same way (`lib/closeOffer.ts:45`, 98 lines). Its body is unchanged.

### 2.4 TD-664 (c): the phone decision bar on a reopened past-award case
- **Web:** `view/DecisionBar.tsx:28` `decisionBarShows({ app, decisionReopened, decisionRecorded, decisionLocked, canWrite })`.
  - Its callers are `view.tsx:394` and `view/DecisionCard.tsx`.
  - Tests: `view.decisionBar.test.tsx` and `lib/__tests__/mobileStandard.test.ts`.
- **Wrong:** on a reopened awarded, active or maintenance case:
  - `decisionReopened` is true;
  - `can_write` is true (super, or a scholars holder past the award);
  - so Save shows, but the verdict door answers 400 `case_closed` (`base.py:442-448`).
  - `case_stage` returns PAST_AWARD whatever a reopen says (`staff_lifecycle.py:118-139`).
- **Change:**
  - Serve `'case_stage': case_stage(app)` (`'open' | 'past_award' | 'pre_award_end'`) from `served_write_flags`. It is not a write flag, but it is the stage the write rule reads. Say so in the docstring.
  - `decisionBarShows` takes `caseOpen` (served `case_stage === 'open'`) and returns false when it is not.
  - `DecisionCard` passes the same argument. It is one rule, so the card's Save hides too.

### 2.5 TD-664 (e): write replies without the flags
`_detail_payload(app, admin)` is at `views_admin/applications.py:44-58`. It is already imported by `lifecycle.py:18`, `interviews.py`, `verdict.py` and `award_withdrawal.py`. These twelve replies still use the bare serializer:

| File (lines now) | Line | View | Note |
|---|---|---|---|
| `views_admin/applications.py` (**599**) | :291 | `AdminApplicationDetailView.patch` | PATCH |
| same | :379 | `AdminVerifyAcceptView.post` | verify-accept, also the IC re-verify card |
| same | :537 | `AdminNudgeStudentView.post` | nudge |
| `views_admin/lifecycle.py` (402) | :130 | `AdminDisbursementScheduleView.post` | |
| same | :161 | `AdminDisbursementActionView.post` | `disb.application` |
| same | :218 | `AdminMaintenanceSubstateView.post` | has the admin context, but no flags |
| `views_admin/sponsors.py` (514) | :249 | `AdminReleaseNricLockView.post` | NRIC lock release |
| `views_admin/sponsorships.py` (193) | :154 | `AdminSetAwardAmountView.post` | the TD's "sponsorship override" |
| `views_admin/profiles.py` (176) | :146 | `AdminSuggestGapsView.post` | not in the TD list |
| `views_admin/resolution.py` (144) | :41 | `AdminRequestInfoView.post` | not in the TD list |
| same | :96 | `AdminResolutionItemView.post` | |
| same | :144 | `AdminResolutionItemActionView.post` | `item.application` |

- **Change:** replace each with `_detail_payload(<app>, admin)`. Every view already has `admin` in scope.
  - The TD's fix says every write reply, or none of them.
  - Each replacement is the same line, so `applications.py` stays at 599. Do not add lines there.
  - Where `AdminApplicationDetailSerializer` is then unused in a module, remove the import, so flake8 passes.
  - Import `_detail_payload` from `.applications`, as `lifecycle.py:18` does.
- **Plan correction:** the profile PUT (`AdminProfileEditView`, `profiles.py:149-162`), publish (`AdminPublishProfileView`, :165-176) and anon-publish (`AdminPublishAnonProfileView`, :93-121) do not return the case detail. They return `SponsorProfileSerializer`, a different shape, and no web caller of the three endpoints was found in `halatuju-web/src`. Leave them unchanged.
  - Decisions 2026-11-17/18 keep them open to past-award file writers ("they make no paid call"). That ruling is about access, not the reply shape.
- **Query cost:** `_detail_payload` adds `qc_separation.for_viewer` (queries only at `interviewed` for a `qc` holder) and `withdrawal_chain.payload_for` (no query unless awarded), all inside `snapshot_unless_open`.
  - Before the run, grep the tests for `assertNumQueries` on these twelve endpoints.
  - If one is pinned, stop and report. Never raise a pin.
- **Not in S1:** TD-664 (d), the PATCH's `vircle_id` role check (`applications.py:272`, `admin.role == 'org_admin'`). It is S3 (M4b).
  - It is GATE-LEFT `'scholarship/views_admin/applications.py::AdminApplicationDetailView.patch'` (owner M4) in `apps/courses/tests/test_role_is_display_only.py:264` and `GATE_LEFT_PINNED`.
  - Do not move `AdminApplicationDetailView` out of `applications.py`: the allowlist key is the file path.

### 2.6 The served ref in the cockpit
- `view.tsx:118-120` holds `served = useRef({ write, cancelDecline, tranche })`.
- `lib/__tests__/appMirrorDrift.test.ts:157-181` pins that exact line, and the three `served_write_flags` entries in `base.py`.
- **Change:**
  - Widen the ref to `{ write, cancelDecline, tranche, qc, closePreAward, caseOpen }`.
  - Widen the type at `lib/admin-api/applications.ts:317` with `can_qc?: boolean; can_close_pre_award?: boolean; case_stage?: 'open' | 'past_award' | 'pre_award_end'`.
  - **That file is 600 lines**, at the cap. Extend the existing line 317, or wrap it to a second line and remove one blank line elsewhere in the same type. Net growth must be 0.
  - Update the drift test to pin the new entries (`'can_qc': may_qc(admin)`, `'can_close_pre_award': ...`, `'case_stage': case_stage(app)`) and the new ref line.
  - Add `expect(view).not.toContain("hasPerm(role, 'qc')")` and `not.toContain("holdsDoor(role, 'decide')")`.
  - Strengthen pins only; never loosen them.

### 2.7 The activity box on the scholar page (`can_write_activity`)
- **Web:** `app/admin/scholars/[id]/page.tsx` (362 lines), at :329 and :359. `ScholarActivity ... readOnly={asMentor || !file.in_maintenance}` derives the write.
- **Server door:** `AdminScholarActivityView.post` (`views_admin/scholars.py:308-326`) checks `_may_write_file(admin, app)` (`base.py:394` → `may_write_file`, `base.py:98-103`: the `scholars` key and the org fence), then `is_in_maintenance(app)`, else 409 `file_closed`.
- **Change:**
  - `scholars.controls` (`apps/scholarship/scholars.py:370`, 464 lines) takes `can_write_activity=` and serves `'can_write_activity': bool(can_write_activity and maintenance_scope.is_in_maintenance(app))`.
  - `AdminScholarFileView.get` (`views_admin/scholars.py:172-175`, 326 lines) passes `can_write_activity=writes and self._may_write_file(admin, app)`.
  - Web: `readOnly={!file.controls?.can_write_activity}` at both sites. Add the field to the controls type in `lib/admin-api/scholars.ts` (~:123, 283 lines).
  - It equals `can_review_results` today. It is its own key because S4 moves the file write key and S5 (owner Q4, 19 Nov) gives mentors activity notes only.

### 2.8 Team debt
- **TD-627** (`docs/technical-debt.md:9074`).
  - Code: `services/assignment.py` (547 lines) `may_hand_to` :88-103 ends `surface_gates.may_assign(caller) and target.owning_organisation_id == caller.owning_organisation_id` (:102-103).
  - Change: also require `caller.owning_organisation_id is not None`, as the TD says.
- **TD-634** (:9040).
  - Code:
    - `assign_reviewer` refuses a new holder from another organisation with `not_reviewer` (`services/assignment.py:396-399`).
    - The picker, `AdminAssignableAdminsView` (`views_admin/lifecycle.py:321`), serves `assignable: may_assign_to(admin, a)` (~:397), not per case.
    - The web reads the code at `view/useCaseActions.ts:97` and `app/admin/scholarship/page.tsx:239` (581 lines).
    - The words are at `admin.scholarship.assign.error.not_reviewer` (en.json:4219).
  - Change (the plan asks for both):
    - (1) Raise `AssignmentError('wrong_organisation')` at :399.
    - Add `'wrong_organisation'` to both `known` lists.
    - Add `admin.scholarship.assign.error.wrong_organisation` in en, ms and ta:
      - en: "This reviewer is in another organisation. Choose someone from this case's organisation."
      - ms: "Penyemak ini dari organisasi lain. Pilih seseorang dari organisasi kes ini."
      - ta: "இந்த மதிப்பாய்வாளர் வேறு நிறுவனத்தைச் சேர்ந்தவர். இந்த விண்ணப்பத்தின் நிறுவனத்திலிருந்து ஒருவரைத் தேர்ந்தெடுக்கவும்."
    - (2) The picker takes an optional `?application=<pk>`.
      - Resolve the case with `_get_application` and `_org_allows`. Ignore the parameter if the case is not readable.
      - Serve `assignable = may_assign_to(admin, a) and a.owning_organisation_id == app.owning_organisation_id`.
      - Keep every row LISTED (bug #66: never drop a holder).
    - `view.tsx:169` passes the case id. `getAssignableAdmins(options, application?)` is in `lib/admin-api/applications.ts:575-591`, at 600 lines, so net growth must be 0.
    - The list page's bulk assign stays not-per-case; the new code covers it.
- **TD-630** (:9044).
  - Code: the banner is `views_staff_list.py:55-56` (57 lines). It sums `work.reviewers.open_cases` over the listed rows where `suspended`. An archived holder is not listed.
  - The counts come from `staff_tables_admin.open_case_counts` (:432-443, 558 lines), through `staff_work.open_cases_counts` (:46-48).
  - Change: count open cases held by archived people of the listed organisation inside that same single query. Do not add a query. The TD forbids raising `test_m1a_staff_list.TestQueryBudget` and `test_m2c_members_lifecycle.test_the_query_count_does_not_change`.
  - `open_case_counts` is shared with `row_fields` and the Reviewers list (its query budget is frozen). Change its shape only through an optional argument.
  - **If it cannot be done at the same query count, stop.** Leave TD-630 open with a dated status line in its body.
- **TD-616** (:8944).
  - Code: `courses/staff_delete_rules.py:78-91` `delete_fields` has no `in_a_group` check. Its callers:
    - `courses/views_staff.py:516`
    - `scholarship/staff_list.py:67`
    - `views_admin/reviewers.py:232`
    - `views_admin/staff.py:154`
  - The mentors payload `_delete_fields` (`views_admin/mentors.py:211-220`, **599 lines**) is separate and lacks it too. The refusal it misses is `mentor_invite.py:524-526`.
  - Change:
    - `delete_fields` serves `deletable: not never and not work and not staff_tables.groups_to_leave(target)`.
    - Mentors' `_delete_fields` does the same for `login`, as an edit within the existing lines.
    - `groups_to_leave` reads columns only (`staff_tables.py:76-105`), so no query is added.
- **TD-615** (:8940). See OWNER Q1. Do not build it before the answer.
- **TD-618** (:8954).
  - Code: `halatuju-web/src/lib/permissionLayout.ts:55` (`orgOverview`) and :66 (`programmeOverview`), 98 lines.
  - The wording has changed since the TD:
    - en.json:8587 says "Opens with any switch on this tab."
    - en.json:8611 says "Every gift once any switch in these two boxes is on; otherwise only the gifts with cases assigned to them."
  - The facts are in the server:
    - `views_admin/my_programmes.py:48-56` (`sees_every_gift`: b40 scope `all` or `staff_tables.in_admins`; `lands`);
    - the Organisation Overview's own gate (builder: find it from the `/admin/org` page key, `staff_tables.page_keys`).
  - Change: a drift test beside `lib/__tests__/permissionLayout.test.ts` (85 lines). It reads those server functions with `readApi`, as that file does, and pins each sentence's fact.
  - If the test shows a sentence is wrong, fix its en, ms and ta words in the same commit.
- **TD-603** (:8795). See the lead call in §3. Out of S1 by default.

### 2.9 Register hygiene
The release log is root `CHANGELOG.md`; `docs/releases/` holds drafts only. Commit ancestry was checked with `git merge-base --is-ancestor`.

| TD | Heading line | Today | Live evidence |
|---|---|---|---|
| TD-621 | :8981 | `~~...~~ — BUILT 2026-11-16 (sprint LABELS, ...)` | LABELS published 17 Nov 11:00, live `e4d81a8fc..d991c39e8`, api-01307-76l, web-01127-g47 |
| TD-622 | :8991 | same | same |
| TD-631 | :9014 | **no marker**; the body says "Status 2026-11-15: BUILT" | published 16 Nov 11:00, live `4619e1af1..b3b4c6114` (c7559d5e2, 31e738a14 in b3b4c6114), api-01304-45w, web-01125-npt |
| TD-633 | :9032 | `~~...~~ — BUILT 2026-11-16 (sprint NAVKEYS, on main, not live...)` | published 16 Nov 16:00, live `b3b4c6114..119ffd0d3` (c556294b2, 823162bee, c54e49b22), api-01305-cfk, web-01126-5dd |

- **Change:**
  - On each defining heading line only, replace the `BUILT ...` tail with `— RESOLVED 2026-11-19 (live <window>, <range>, <api rev>, <web rev>)`.
  - TD-631: strike through the title with `~~` and add the same tail.
  - The `TD_MARKER` regex matches `— RESOLVED`; it does not match `BUILT`.
  - Never write inside the Open Items Index.
  - Owner band ruling 2026-11-16 (`docs/debt-band.json`): close only with proof.
- **This sprint's own TDs** get a dated "Status 2026-11-xx: BUILT (sprint S1, …)" line in their bodies, not on the heading. The heading is closed after the S1 publish goes live, as with the four above.
  - **TD-664 stays open:** item (d) is S3's.

## 3. Owner questions and lead calls

**OWNER Q1 (TD-615):** "Someone invited and placed in a group who has never signed in can be deleted today without leaving the group first. The debt fix (TD-615) would make Delete ask them to leave the group first, but Remove refuses anyone who has not signed in yet ('cancel their invitation instead'), and cancelling an invitation keeps their account, so they could then never be deleted. Which do you want: (A) keep today's rule, so a never-signed-in invitee can be deleted while in a group, and TD-615 closes as decided; or (B) Delete asks for No group, and Remove is allowed for someone who has not signed in yet?"

- **Rulings it touches:**
  - R2 "Delete only from No group" (`docs/decisions.md:20575`).
  - O1 "pending invitations stay on Invitations" (`docs/plans/2026-11-10-team-membership-roadmap.md:17`).
  - `staff_tables.groups_to_leave` docstring (`courses/staff_tables.py:119-129`): "the narrow 'never started' Delete stays theirs".
  - Remove's refusal `not_arrived` (`staff_tables_admin.py:332`; `staff_mentor.py:159` for Mentors).
  - Also relevant: `first_seen_at` NULL also marks staff who predate the column (`decisions.md:847`).
- **Default if there is no answer by build time:** TD-615 is not built in S1. TD-616 ships regardless: it serves whatever `groups_to_leave` answers.

**Lead call for the architect (not the owner): TD-603.**
- The M1a lead decision says "No new activity verb for archive / restore: AUDIT log lines only (TD-603)" (`docs/decisions.md:1011`). The TD's own trigger is "when the Staff tab or the activity box needs to show them", and no S1 screen needs them.
- Building it means:
  - two verbs in `StaffActivityVerb` (`models/staff_activity.py:114`, choices);
  - WIRED writers in `courses/staff_archive.py` (219 lines) and `scholarship/mentor_archive.py` (72);
  - the `WIRED` table (`staff_activity.py:121`);
  - a filter kind (`staff_activity_read.py`).
- A choices change makes `makemigrations --check` fail, so it needs a **state-only migration**. That breaks "Migration: none".
- A backfill can only rebuild archives (from `archived_at`), never restores. Running it in production needs the owner's yes.
- **Recommendation:** take TD-603 out of S1 into its own small step, or leave it open until a screen needs it. If the architect keeps it in, the trailer becomes `Migration: 1 (state-only, StaffActivity.verb choices)`, and the backfill runs dry only.

## 4. Phases

**Phase 0: read and baseline (no edits).**
- Re-check every line above.
- Run the gates once on the untouched branch (§5) and record any failures that were there before the sprint.

**Phase 1: server.**

| Item | Files (lines now) | Tests to add |
|---|---|---|
| (f) cron | `profile_finalise.py` (225) | `tests/test_s1_finalise_case_stage.py`: OPEN still refines; each of awarded, rejected, withdrawn and closed-before-award drops with `case_closed` and **no refine call** (mock `refine_sponsor_profile`, assert not called); a stale token is not dropped; `run_pending` counts `case_closed`; `assign_draft` is unchanged |
| flags `can_qc`, `can_close_pre_award`, `case_stage`; `may_qc` | `views_admin/base.py` (512), `views_admin/lifecycle.py` (402, close view reads the same `may_decide`) | `tests/test_s1_served_flags.py`: per stage and holder, each flag equals what its door does (QC door 403 vs `can_qc`, pre-award close refusal vs `can_close_pre_award`, verdict `case_closed` vs `case_stage`) |
| (e) twelve replies | `applications.py` (**599**, same-line edits only), `lifecycle.py`, `sponsors.py` (514), `sponsorships.py` (193), `profiles.py` (176), `resolution.py` (144) | `tests/test_s1_write_replies_serve_flags.py`: each of the twelve replies carries `can_write`, `can_cancel_decline`, `can_tranche`, `can_qc`, `can_close_pre_award`, `case_stage` and `qc_refusal`; a source test that no `AdminApplicationDetailSerializer(` reply is left in `views_admin/` outside `_detail_payload` |
| activity flag | `scholarship/scholars.py` (464), `views_admin/scholars.py` (326) | in `test_s1_served_flags.py`: `controls.can_write_activity` equals the POST door (`scholars` holder in maintenance true; closed file false; mentor false; holder without the key false) |
| TD-627 | `services/assignment.py` (547) | `tests/test_s1_team_leftovers.py`: no-organisation caller and target refused |
| TD-634 | `services/assignment.py`, `views_admin/lifecycle.py` | same file: a super handing to another organisation's reviewer gets `wrong_organisation`; `?application=` serves `assignable` false for another organisation while keeping the row listed |
| TD-616 | `courses/staff_delete_rules.py` (91), `views_admin/mentors.py` (**599**, no growth) | same file: every `delete_fields` caller says not deletable while in a group; the mentors row too |
| TD-630 | `staff_tables_admin.py` (558), `staff_work.py` (142), `courses/views_staff_list.py` (57) | same file: an archived holder's open case is counted in `suspended_cases`; the two pinned query counts unchanged |

**Phase 2: web.**

| Item | Files (lines now) | Tests to add |
|---|---|---|
| served ref + type | `view.tsx` (401), `lib/admin-api/applications.ts` (**600**, net 0) | update `lib/__tests__/appMirrorDrift.test.ts` (249) pins |
| (a) QC | `view.tsx`, `view/QcPanel.tsx` (172), `view/ReverifyIcCard.tsx` (56) | `view.s1Flags.test.tsx`: QC panel and re-verify card follow `can_qc` whatever the role; `qcRefusalFor` reads only `qc_refusal` |
| (b) close | `view/PostAwardPanels.tsx` (428), `lib/closeOffer.ts` (98) | same file: Close card follows `can_close_pre_award`; update `PostAwardPanels.noFile.test.tsx` / `.phone.test.tsx` props |
| (c) bar | `view/DecisionBar.tsx` (74), `view/DecisionCard.tsx` (325) | extend `view.decisionBar.test.tsx`: reopened past-award case, no bar and no Save; check `lib/__tests__/mobileStandard.test.ts` still passes |
| activity | `app/admin/scholars/[id]/page.tsx` (362), `lib/admin-api/scholars.ts` (283) | `app/admin/scholars/[id]/activityFlag.test.tsx`: the box is read-only unless `controls.can_write_activity` |
| TD-634 | `view/useCaseActions.ts` (110), `app/admin/scholarship/page.tsx` (581), `messages/{en,ms,ta}.json` | extend `view.decision.test.tsx` or the assign test: `wrong_organisation` shows its words |
| TD-618 | new `lib/__tests__/permissionLayoutOverviewDrift.test.ts` | the drift test itself |
| allowlist | `lib/__tests__/roleIsDisplayOnly.test.ts` (334) | **delete** the `QcPanel.tsx` entry at :112 (`"!!role?.is_super_admin \|\| role?.role === 'super'"`), because the fallback that held it goes. Never reclassify it. The scan floor `HITS.length >= 140` (:300) must still hold: report the count |

**Phase 3: register.**
- Edit the four headings (§2.9), and add the S1 status lines to the bodies of TD-664, 627, 634, 616, 630 and 618.
- TD-615 gets the OWNER Q1 status line.
- Any new debt (e.g. the `assign_draft` stage gap): take its number only at push (`release_queue.py next-td`).

**File-size and ledger risks.**
- None of the touched files is in either `code-standards.json` oversize ledger. The 600-line cap applies to all of them.
- At the cap now:
  - `views_admin/applications.py` 599
  - `views_admin/mentors.py` 599
  - `lib/admin-api/applications.ts` 600
- Make same-line edits there.
- If growth cannot be avoided, do a pure move first, as a separate commit in the same push (code standards: split first, in its own commit). Name it in the report. Never raise a budget.
- Moving `AdminApplicationDetailView` would orphan its GATE-LEFT key, so move something else.

## 5. Gates and pins
Run each through the queue. Paths are from the repo root.

- `python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <cmd>` for every heavy command below.
- api:
  - `python manage.py check`
  - `python manage.py makemigrations --check --dry-run` (must say "No changes"; see the TD-603 lead call)
  - the full api suite
- Named:
  - `apps/scholarship/tests/test_access_matrix.py`
  - `apps/courses/tests/test_role_is_display_only.py`: the GATE-LEFT count only falls. S1 converts no GATE-LEFT entry; if one converts, **delete** it, never reclassify it.
  - `apps/scholarship/tests/test_technical_debt_register.py`
  - `test_profile_finalise.py`
  - `test_post_award_cut.py`
  - `test_post_award_cut_round2.py`
  - `test_a111a_reject_reason_qc_refusal.py`
  - `test_m1a_staff_list.py`
  - `test_m2c_members_lifecycle.py`
  - `test_team_tables_t2.py`
- web:
  - `npm run gates`
  - `node scripts/bundle-budget.mjs --gate` (or the repo's bundle-budget command)
  - mobile-check for the cockpit and the scholar page (UI changes)
  - jest, including `appMirrorDrift`, `roleIsDisplayOnly`, `permissionLayout` and `mobileStandard`
- At close: code_health (register count; the band is 100-150).

## 6. Commit plan
- One squash on `access-s1-leftovers`, plus a pure-move commit before it only if §4 forces one.
- Subject: `fix: sprint S1 case and team leftovers (TD-664, TD-627, TD-634, TD-616, TD-630, TD-618)`.
  - `fix:` is honest: (f) is a live paid-call leak, and TD-634, 616 and 630 are live wrong answers.
- Trailers:
  - `Phone-check: <the line in §7>`
  - `Migration: none`
  - `Services: both`
  - plus the attribution line the session gives.
- Stage explicit paths only. No bare `git stash`. Leave `.venv` and untracked files (including the roadmap file) alone. No workflow or tool edits.
- The push follows the release train and the builder slots. A push to main saves only; `live` moves with the owner's yes in a publish window.
- Add a CHANGELOG entry (on main, not live) and a release-note draft.

## 7. Phone check (for the owner, after live)
"On your phone, as a QC person, open a case waiting for QC: the QC panel shows as before. As someone without 'Reject or close applications', open a submitted case: there is no Close card. Open a funded scholar's file: you can add an activity note only while the file is open. As a super, try to give a case to a reviewer from another organisation: you are told they are in another organisation."

## 8. Hours estimate

| Part | Hours |
|---|---|
| (f) cron + tests | 0.75 |
| Flags (a)(b)(c) server + web + drift pins | 1.5 |
| (e) twelve replies + tests | 1.0 |
| Activity flag | 0.5 |
| TD-627, TD-634 (both halves, three languages) | 0.75 |
| TD-616, TD-630 | 0.75 |
| TD-618 drift test | 0.4 |
| Register hygiene | 0.25 |
| Gates, review fixes | 0.6 |
| **Total** | **~6.5h** (plan ~6h). Add 1h if TD-603 stays in, and 0.5h for TD-615 under owner answer (B) |

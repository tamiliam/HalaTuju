# Sprint M3 brief: lead powers become keys; the org admin's powers are explicit (DRAFT)

Parent plans: `docs/plans/2026-11-01-team-tables-roadmap.md` (T5 rulings 1-8; T5e "lead powers to keys"),
`docs/plans/2026-11-11-m2-team-pages-brief.md`, `docs/plans/2026-11-12-m2b-admin-permissions-brief.md` (its M3 hand-off
list, D3, D12), `docs/plans/2026-11-13-m2c-members-tab-brief.md` (C5), `docs/plans/2026-11-13-m2d-permissions-tab-brief.md`
(D4). Owner rulings: O13 and O15 (decisions.md "Owner rulings"), R6 (decisions.md 2026-11-12 "Members tab and the lifecycle
rules").

Runs after M2d is live. Build in worktree `.worktrees/m3` (branch `m3`, cut from main 37192bfa7, which holds M2d).
Rebase on main before each part ships. **Do not push.** This brief is a DRAFT: the owner's decisions (D1-D7 below) come
first; nothing is built until they are answered.

## The one principle

On ship day nobody's access changes unless the owner names it. Every org admin can do exactly what they did the day
before, every team member exactly what they did, every super exactly what they did. A nobody-changes test per live row
shape proves it (the `apps/scholarship/tests/test_m2b_nobody_changes.py` pattern: build the row as it stood, read it with a
hand-written copy of the OLD rule, put it through the data step, read it with the NEW code, compare).

## What M3 is

- **R6:** no implicit powers, org admin included. An org admin's powers come from explicit keys, per group, like everyone
  else's. Only the O15 three stay with the org admin by role: `manage_team` (changing other staff's permissions),
  `billing.edit` (paying the platform bill), `requests.approve` (approving requests that commit paid hours).
- **O13 / T5e:** every "lead only" check (a role test on `org_admin`) becomes a key test. The keys that are lead-only today
  become assignable to team members (the M2d padlocks come alive), except the O15 three.
- A data step writes each org admin row's keys, so nothing changes on the day.
- M4 (T5d, money) follows. Money is out of scope here (see Out of scope).

## Verified facts (main 37192bfa7); re-check each before building on it, stop and report if one is wrong

### How the org admin's powers are implicit today

- `staff_permissions.resolve` (`halatuju_api/apps/courses/staff_permissions.py:145-168`): an `org_admin` row gets
  `LEAD_TIER` = `see_all, scholars, qc, spending, award_withdraw_approve, manage_team` (:93), plus `review` when its stored
  list names `review` (`lead_reviews`, :106-111). Anything else in its `permissions` column is IGNORED. `clean` (:120-129)
  drops `manage_team` (`LEAD_TIER_ONLY`, :74) from any stored list.
- `staff_permissions_v2.effective_v2` (`apps/courses/staff_permissions_v2.py:236-264`): an active `org_admin` gets
  `lead_v2` (:229-233), which is EVERY v2 key plus the `qc` hat (and `review` when it reviews). It is the only way an org
  admin holds the money v2 keys `payments.view/.prepare/.check/.approve` and `sponsors.check`: their old-key equivalents
  (`payments_*`) are not in `LEAD_TIER` (ALIASES, :117-130).
- `stored_v2` (:185-195) reads only `GRANTABLE_V2` (:170, not lead-only and not an alias). `refusal_reason` (:173-182)
  answers `never_grantable` (billing.edit, requests.approve, `NEVER_GRANTABLE` :161), `lead_only`, or `alias`.
- 13 v2 keys are lead-only (:42-66): `invitations.edit, sponsors.approve, billing.view, billing.edit, requests.view,
  requests.edit, requests.approve, settings.edit, students.edit, students.approve, contracts.view, contracts.edit,
  programmes.edit`. Two are O15. **M3 makes the other 11 assignable.**
- There is no v2 key for team management: `manage_team` is an old key, aliased to nothing (:127). There is no
  "change" key for Scholars (`scholars.view` only, :60).
- `staff_tables.in_admins` (`apps/courses/staff_tables.py:72-81`) seats an org admin at Admins by role.
  `groups_to_leave` (:113-122) skips that seat (M2c C5, "until M3"). `in_reviewers` (:84-89) reads the stored `review`.
- `staff_tables.invite_permissions` (:230-236) writes NULL for a new `org_admin` invitation. An org admin is only ever
  made by a super's invitation (`apps/courses/views_staff.py:270`); a role switch never reaches or leaves `org_admin`
  (`apps/scholarship/staff_lifecycle.py:5`).

### Who can change whose keys today

- The permission editor refuses any non-team target, so an org admin's set is "fixed"
  (`apps/scholarship/staff_permissions_admin.py:180-186`). It refuses your own set (:182).
- `asked_set` (:75-113) refuses `manage_team` and every `lead_only` v2 key with code `lead_tier` (:105-108, "until M3",
  :89), and `NEVER_GRANTABLE` with `never_grantable` (:100-104).
- The staff fence stops an org admin reaching another org admin: `_ORG_ADMIN_MANAGEABLE_ROLES` has no `org_admin`
  (`apps/courses/staff_fence.py:14`). Only a super can reach an org admin's row.
- **Team -> Reviewers Add / Remove OVERWRITES an org admin's stored list:** Add writes `['review']`, Remove writes NULL
  (`apps/scholarship/staff_tables_admin.py:203-206`, :261-263). Harmless today (the list is ignored). After M3 it would wipe
  the org admin's keys. M3 must change it (decision A6).

### The lead checks: count against "~44"

The scanner `apps/courses/tests/test_role_is_display_only.py`, run today, sees 199 role-read sites in 161 functions:
DISPLAY 82, OVERRIDE 45, GATE-LEFT 72. GATE-LEFT T5e is **51 functions, 65 sites** (T5d 6, TD-496 1). The "~44" came
from T5c P3's 45. Since then M1 and M2 added gates. **The scanner does not see three kinds of lead check:**
- calls to `is_lead_tier(...)`
- the implicit grants inside `resolve` and `lead_v2`
- the web.

Counting those too:
- **Server:** 51 scanned functions plus 15 unscanned places (list S below).
- **Web:** 21 sites in 18 files.
- **Of the 51 scanned:** 46 move to keys and 5 stay label-based on purpose.

Each row below gives the key it should read (NEW = not in the catalogue today) and who passes today. "OA" = org admin;
"super" passes every check unless the row says otherwise. Lines are where the role is read.

**G1 Team management -> `manage_team` (O15: stays with the OA by role, now read as a key). 17 functions.**
Today: super + OA. Each gate asks `has_perm('manage_team')` (a super passes) instead of the role. The TARGET rules inside
them (an OA may not touch another OA, never a super) stay label-based (list K).
- `courses/views_staff.py`:
  - `AdminDeleteView.delete` :145, `_delete_locked` :171
  - `AdminInviteView.post` :214, :234, :260, :270 (staff invitations; only a super may invite an `org_admin`, which stays)
  - `AdminResendView.post` :380
  - `AdminRevokeView.patch` :535, `_revoke_locked` :577
- `courses/staff_fence.py`: `_deletable_now` :40, `manageable_if_restored` :66-67, `staff_target_readable` :85 (the
  caller arm only)
- `courses/staff_gift.py`: `staff_invite_org` :69
- `scholarship/staff_tables_admin.py`: `may_act` :105-115
- `scholarship/views_admin/staff.py`:
  - `AdminStaffRoleView.patch` :43
  - `AdminStaffPermissionsView._target` :107
  - `AdminTeamTableView.post` :247
  - `AdminTeamCandidatesView.get` :297
- `scholarship/views_admin/reviewers.py`: `AdminReviewerPauseView.post` :419, `AdminReviewerProgrammeView.post` :460
  (who gets work; owner decision D4)

**G2 Invitations -> `invitations.edit`. 4 functions.** Today: super + OA.
- `views_admin/invitations.py`: `AdminInvitationsView.post` :202, `AdminInvitationCancelView.post` :291, :311
- `mentor_invite.py`: `manageable` :111
- `source_invite.py`: `manageable` :69

The `invitations` door already exists (`staff_tables.py:167`).

**G3 Organisation settings -> `settings.edit`. 4 functions.** Today: super + OA.
- `views_admin/org_config.py`: `AdminOrganisationConfigurationView._gate` :53 (`ROLES` :47)
- `views_admin/theme.py`: `_gate` :77 (`ROLES` :71)
- `views_admin/overview.py`: `AdminOverviewLayoutView._gate` :129 (`ROLES` :123)
- `programme_overview.py`: `may_customise` :92

**G4 Programme settings -> `programmes.edit`. 2 functions.** Today: super + OA.
- `views_admin/org_config.py`: `AdminProgrammeConfigurationView._gate` :240 (`ROLES` :234)
- `views_admin/gift_programmes.py`: `_ProgrammeScopedBase._gate` :34 (`ROLES` :28)

**G5 Applications -> `students.edit` / `students.approve`. 9 functions move, 2 stay.** Today: super + OA.
- `views_admin/verdict.py`: `AdminAssignReviewerView.post` :516, :529 -> `students.edit`. Ruling 6: never to yourself;
  the service already refuses that.
- `services/assignment.py`: `may_hand_to` :92 -> `students.edit`, and the target in the CALLER's organisation for a
  non-super.
- `views_admin/applications.py`:
  - `AdminNudgeStudentView.post` :518 -> `students.edit`
  - `AdminApplicationListView.get` :141 (`?parent_call=needed`) -> `students.edit`
  - `AdminOrgRejectView.post` :462 (drops a shortlisted applicant) -> `students.approve`
- `views_admin/lifecycle.py`: `AdminCloseApplicationView.post` :163 (close before award) -> `students.approve`
- `views_admin/guardian_contact.py`: `_guardian_gate` :33 (correct the guardian, record a call) -> `students.edit`
- `views_admin/reviewer_notes.py`: `_may_write` :36 (notes for the reviewer) -> `students.edit`
- `views_admin/letters.py`: `_LettersBase._senior` :47 (suspension and termination letters, on the Scholars page) ->
  **NEW `scholars.approve`** (owner decision D5)
- STAYS: `services/assignment.py` `is_review_target` :54 (`R1_SUPER_TARGET_ROLES` :38). See list K.
- STAYS: `AdminApplicationDetailView.patch` :270 (the Vircle ID correction). This is money (M4). See list K.

**G6 Sponsors -> `sponsors.approve`. 3 functions.** Today: super + OA.
- `views_admin/sponsors.py`: `AdminSponsorReviewView.post` :260 (vet: approve, reject or suspend). ⚠ **This vets a sponsor
  ACCOUNT for every organisation** (`sponsorships.py:60-66`). Owner decision D6.
- `views_admin/sponsorships.py`: `AdminSponsorMembershipView.post` :81 (accept a sponsor into a gift)
- `views_admin/sponsor_terms.py`: `AdminSponsorTermsPublishView.post` :250 (publish terms; drafting is already
  `sponsors.edit`)

**G7 Billing -> `billing.view`. 3 functions.** Today: super + OA, while billing is live. Paying the bill is `billing.edit`
(O15), and no endpoint pays yet.
- `views_admin/billing.py`: `AdminBillingUsageView.get` :54, :57
- `surface_gates.py`: `may_read_invoices` :40 (`views_admin/invoices.py` `_InvoiceBase._caller` :143)
- `views_admin/build_hours.py`: `AdminOrgBuildHoursView.get` :32-33 (recording hours stays super only)

**G8 Requests -> `requests.view` / `.edit` / `.approve`. 2 functions, 12 callers.** Today: OA only for writes; super + OA
for reading.
- `surface_gates.py`: `requests_role` :55 (via `views_admin/requests.py` `_org_side` :76-84). GETs -> `requests.view`.
  Create (the list POST) -> `requests.edit`. Also read by `my_pending.py:156` and `staff_activity_read.py:230`
  (-> `requests.view`).
- `views_admin/requests.py`: `_requestee` :86-97 takes the key per caller:
  - Answer :260, Defer :319, Modify :337 -> `requests.edit` (OA only today; a super stays out, as now)
  - Approve :294 -> `requests.approve` (O15: the OA by role, plus super)
  - Decline :358 -> `requests.approve` (decision D5)
  - Comment :435 and the three attachment endpoints in `requests_delivery.py` (:321, :356, :415) -> `requests.edit`
    (plus super, as now)
- The `_super_side` endpoints stay super only (list K).

**G9 Contracts -> `contracts.view` / `contracts.edit`. 1 function.** Today: super + OA.
- `surface_gates.py`: `may_open_contracts` :45. The builder splits reads from writes in `_ContractsBase`. Deploying a
  template stays super only (OVERRIDE).

**Totals.** G1 17, G2 4, G3 4, G4 2, G5 9, G6 3, G7 3, G8 2, G9 1, giving 45 moving. Add `programme_overview.may_customise`,
counted in G3, and the 5 that stay: **51**.

**List S: lead checks the scanner does not see (server). M3 changes each.**
1. `staff_permissions.resolve` :160-163: the OA reads its stored keys, plus `manage_team` by role (A2).
2. `staff_permissions_v2.lead_v2` / `effective_v2` :229-264: the OA reads stored keys, aliases, table grants, the O15 two
   by role and the money carry-over (A2, A3). `lead_v2` goes.
3. `staff_permissions_v2.GRANTABLE_V2` :170 / `refusal_reason` :173: `lead_only` shrinks to nothing. NEVER_GRANTABLE
   stays.
4. `staff_permissions_admin.asked_set` :105-108: `lead_tier` is refused only for `manage_team` (M3c).
5. `staff_permissions_admin` :180-186: an OA target becomes editable by a super (D1; M3c).
6. `staff_tables_admin.py:203-206, :261-263`: an OA's Reviewers Add / Remove adds or removes `review` only (A6).
7. `staff_tables_admin.py:125` `table_keys`: an OA's keys per table come from its stored set.
8. `staff_person.py:84`: the viewer arm (`is_lead_tier(viewer)`) -> `manage_team`. :71 and :130 are display.
9. `staff_tables.invite_permissions` :230: a new OA starts with the OA set (D3).
10. `staff_tables.in_admins` :75 and `groups_to_leave` :121: the OA's Admins seat stays by role (A4). The docstrings stop
    saying "until M3".
11. `programme_overview.SECTIONS_BY_ROLE` :77-85: the `org_admin` row is read from keys (A7).
12. `my_pending.py:145-146`: the `sponsors_to_vet` card (D12, TD-503 part 1; owner decision D7).
13. `views_staff_list.py:55`: the suspended-cases banner already reads `has_perm('manage_team')`. No change; the
    nobody-changes test covers it.
14. `staff_permissions.preset_for('org_admin')` and `PRESETS`: a named OA set, `ORG_ADMIN_SET`, for the data step, the
    invitation and the editor's "Reset".
15. `test_role_is_display_only.py`: the scanner is widened to see `is_lead_tier(` and `LEAD_ROLE` reads, so this list can
    never grow unseen again (A10).

**List W: web lead checks (M3c). 21 sites in 18 files.** Each reads the served keys (`permissions` or `page_keys`) instead of
the role. Lines are in `halatuju-web/src/`.
- `lib/navigation.ts`: rows billing :151, requests :154, orgSettings :169, contracts :288, programmeConfig :290. Each
  gains a `door` on the server's key, and the role list stays only as the older-payload fallback.
- Assigning:
  - `app/admin/scholarship/page.tsx:61` `canAssign`
  - `app/admin/scholarship/[id]/view.tsx:99` `canAssign`
  - `app/admin/scholarship/[id]/view/BlockersPanel.tsx:85` (nudge)
  - all three -> `students.edit`
- `app/admin/scholarship/page.tsx:65` `canFilterByAssignee`: the `org_admin` arm -> `students.edit`. The `admin` arm is a
  display filter the server does not gate; it stays (TD-623).
- `lib/cockpitTrail.ts:86` `canOrgReject` -> `students.approve` (keep `officerGateDrift.test.ts` in step).
- `app/admin/requests/page.tsx:38` `isOrgAdmin` (the submit form) -> `requests.edit`.
- `app/admin/requests/[id]/page.tsx:57, :232` and `lib/requestStatus.ts:142` -> `requests.edit` / `requests.approve`.
- `app/admin/sponsors/terms/[id]/page.tsx:39` `canPublish` and `lib/sponsorDetail.ts:201` `canSetMembership` ->
  `sponsors.approve`.
- Team management, each -> `manage_team`:
  - `app/admin/organisation/team/page.tsx:131` `canManage`
  - `app/admin/organisation/staff/page.tsx:101` `canManage`
  - `components/admin/person/useTeamPerson.ts:100` `mayManage`
  - `components/mentors/MentorsAdmin.tsx:136` `mayManage` (check: if it only invites, `invitations.edit`)
- `components/admin/person/ReviewerGroupPage.tsx:27`, `MentorGroupPage.tsx:46`: an OA target stays read-only for an OA
  (the fence), editable for a super (D1).
- `components/admin/PermissionEditor.tsx:95` and `components/admin/PermissionBox.tsx:17`: the `lead_only` padlock goes.
  The card for an OA target is editable for a super (D1). `lib/permissionLayout.ts` gains the `scholars.approve` row if
  D5 holds.
- `lib/profileCards.ts:110, :113, :140`: the `org_admin` arms go. An OA's stored keys already pass `CASE_PERMS` and
  `MONEY_PERMS`. The "You can" line for an OA names the O15 three.
- `lib/admin-api/admins.ts:312, :319`: `lead_only` leaves the `reason` type.
- `src/test/staffPresets.ts:32` (the `LEAD_TIER` mirror) follows the server.

**List K: checks that STAY label-based on purpose (with the reason).**
- **Super-only platform powers.** These are the OVERRIDE sites, 45 in the scanner:
  - the `views_admin/base.py` fences
  - billing rates, corrections and platform costs
  - recording build hours
  - contract deploy and templates
  - graduation countersign and witness
  - the sponsors list scope and the NRIC lock
  - set award amount, and reopen / cancel-reopen of a decision
  - the requests `_super_side`
  - the `_organisation_for` scope helpers
  - `scheduling.propose_slots`

  A super is platform staff, not an organisation's member; R6 is about organisations.
- **The O15 three.** `manage_team`, `billing.edit` and `requests.approve` are held by the OA BY ROLE, never stored,
  never assignable. G1 and G8-Approve read them as keys, so the gate is a key gate. Only the HOLDING is by role, as O15
  rules.
- **Target rules** (who may be acted on, not who acts):
  - `staff_delete_rules.py` `_live_org_admin` :27, `_org_admins` :32, `sole_org_admin_ids` :70 (never strand an
    organisation without an OA)
  - the target arms of `staff_fence.py`
  - `views_staff.py:228` (only a super invites an OA)
  - `staff_tables_admin.py:224, :392` `LEAD_FIXED` (the OA always sits in Admins; A4)
- **`awaiting_qc`** (`my_pending.py:56`, `programme_overview.attention`). The M2b hand-off says leave it. It is a count,
  read through `SECTIONS_BY_ROLE` and the `qc` key, and TD-503 part 2 is the owner's.
- **`R1_SUPER_TARGET_ROLES`** (`services/assignment.py:38`). It decides who may keep HOLDING a case handed out before T1
  retired the R1 override (one awarded case sits with an OA). It does not decide who acts. Changing it to keys would
  move qc and finance rows in or out. It retires with TD-613 (TD-622).
- **M4 money:**
  - `credit_steps.step_refusal` :64-68
  - `payments_chain` `_is_lead_tier` :87-89 (used at :203, :226, :234, :240, :272)
  - `sponsorship/credits.py` :42, :154
  - `applications.py:270` (the Vircle ID)
  - `payments.py`
  - web `canRecordCredit`, `isFinanceViewer`, `lib/sponsorDetail.ts:146-161`

  T5d owns all of these.
- **DISPLAY recipient routing.** `send_review_nudges` escalation and `payment_mail._instruction_cc` send mail to the OA.
  They are not access.
- **Web older-payload fallbacks.** `opensDoorOr` lists and `MAKER_ROLES`, `POSTER_ROLES`, `MENTORING_ROLES`,
  `MENTORS_READ_ROLES`, `CAN_EDIT_EMAILS`, `EMAIL_EDIT_ROLES`. They answer only when the server sends no `page_keys`, so
  they are dead on a current server. They retire in TD-623.

## The data step (M3a; migration `courses/0098_store_org_admin_keys.py`, by hand, migrate-first)

The next number is 0098: the last is `0097_store_admin_v2_keys.py`. Check production's `django_migrations` first (count Q7).

**Rows:** every `partner_admins` row with `role = 'org_admin'`: active, revoked and archived, and a pending invitation
too (the 0097 amendment: a later Restore must give back what the role gave). Not a super, not any other role.

**What each row gets (REPLACE, not merge):**
- old keys `see_all, scholars, qc, spending, award_withdraw_approve`, plus `review` when the row's list holds `review`
  today.
- v2 keys: every `CATALOGUE_V2` key that is neither NEVER_GRANTABLE nor an alias:
  - `invitations.view`, `invitations.edit`, `team.view`
  - `sources.view`, `sources.edit`
  - `sponsors.view`, `sponsors.edit`, `sponsors.approve`
  - `billing.view`, `requests.view`, `requests.edit`, `settings.edit`
  - `students.edit`, `students.approve`
  - `contracts.view`, `contracts.edit`, `programmes.edit`
  - `announcements.view/.edit`, `surveys.view/.edit`, `development.view/.edit`, `mentoring.view/.edit`
  - `scholars.approve` if D5 adds it

  Not written:
  - `students.view`, `scholars.view` and `spending.*` come from the old keys through ALIASES.
  - `billing.edit`, `requests.approve` and `manage_team` come by role (O15).
  - `payments.*` and `sponsors.check` come by role until M4 (A3).

**Why replace.** An OA row's list was never read except for `review`. A row appointed after holding a team role may keep
old keys (for example a `payments_approve`). Reading them would GIVE that OA a payment seat and so change the payment
chain, which is M4. Replace writes exactly today's `resolve` output, less `manage_team`. Count Q1 says whether any such
row exists.

**Safe under the old image** (migrate-first): the old code ignores an OA's list except `review`, and that is kept. In the
old image `holders` and `team_holding(with_lead)` read the OA through `resolve` / `lead_reviews`, so they answer the same.

**Audit, reverse, re-run:**
- One `staff_permission_changes` row per row changed: before, after, `changed_by_role='migration'`, kind `edit` or
  `edit_null`, as in 0097.
- Reversible from those rows, and idempotent: a row already equal is not written.
- The frozen constants are pinned to the live ones by `test_m3_migration_0098.py`, with the CASE and WHERE text of the
  hand SQL, as in `test_m2b_migration_0097.py`.

**Re-run after deploy.** An invitation sent between the hand migration and the deploy is written NULL by the old image.
The new code reads a NULL OA row as `ORG_ADMIN_SET` (fail-safe, no lock-out), and the POST-DEPLOY block re-runs DATA and
checks: zero OA rows NULL.

**Read-only counts for the architect** (production, counts only, no names or emails):

```sql
BEGIN READ ONLY;
-- Q1 org admin rows by state and by what their list holds today
SELECT is_active, (archived_at IS NOT NULL) AS archived, (first_seen_at IS NOT NULL) AS signed_in,
       CASE WHEN permissions IS NULL THEN 'null'
            WHEN jsonb_typeof(permissions) <> 'array' THEN 'not_array'
            WHEN permissions = '[]'::jsonb THEN 'empty'
            WHEN permissions = '["review"]'::jsonb THEN 'review_only'
            ELSE 'other_keys' END AS stored,
       count(*)
  FROM partner_admins WHERE role = 'org_admin'
 GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4;
-- Q2 organisations by how many ACTIVE org admins they have (D1: can one org admin edit another?)
SELECT n AS org_admins, count(*) AS organisations
  FROM (SELECT owning_organisation_id, count(*) AS n FROM partner_admins
         WHERE role = 'org_admin' AND is_active GROUP BY owning_organisation_id) t
 GROUP BY n ORDER BY n;
-- Q3 org admin rows with no organisation (expect 0)
SELECT count(*) FROM partner_admins WHERE role = 'org_admin' AND owning_organisation_id IS NULL;
-- Q4 non-lead rows already storing a key M3 unlocks, or manage_team (expect 0: today's code refuses them)
SELECT count(*) FROM partner_admins
 WHERE role NOT IN ('org_admin', 'super') AND jsonb_typeof(permissions) = 'array'
   AND permissions ?| array['manage_team','invitations.edit','sponsors.approve','billing.view','billing.edit',
       'requests.view','requests.edit','requests.approve','settings.edit','students.edit','students.approve',
       'contracts.view','contracts.edit','programmes.edit','scholars.approve'];
-- Q5 active supers (who can edit an org admin's keys under D1's recommendation)
SELECT count(*) FROM partner_admins WHERE role = 'super' AND is_active;
-- Q6 cases held by an org admin: open (R5) and any status (R1_SUPER_TARGET_ROLES, TD-613)
SELECT count(*) FILTER (WHERE a.status IN ('submitted','shortlisted','profile_complete','interviewing',
                                           'interviewed','recommended') OR a.decision_reopened_at IS NOT NULL) AS open,
       count(*) AS any_status
  FROM scholarship_applications a JOIN partner_admins p ON p.id = a.assigned_to_id
 WHERE p.role = 'org_admin';
-- Q7 the last courses migration recorded (expect 0097_store_admin_v2_keys)
SELECT max(name) FROM django_migrations WHERE app = 'courses';
-- Q8 active team rows by role (D7: who sees the sponsors_to_vet card today)
SELECT role, count(*) FROM partner_admins
 WHERE is_active AND role IN ('admin', 'finance', 'qc', 'reviewer', 'member') GROUP BY role ORDER BY role;
ROLLBACK;
```

The M2c brief's out-of-scope line names "the 2 org_admin data rows". Q1 confirms or corrects that number.

## Decisions

### For the owner. Each changes what someone can do or see, now or later

| | Question, in plain words | Recommended | The alternative |
|---|---|---|---|
| D1 | Who may change an organisation admin's permissions? | **Only a platform super (you), never their own.** No change to the fences, and an org admin cannot cut back another org admin. | Another org admin of the same organisation may too (the staff fence widens for the permissions page only; one org admin could then take powers from another). |
| D2 | Who may give a team member the 11 powers that become assignable (invitations, sponsor approval, usage and billing view, requests, organisation settings, assigning and deciding applications, contracts, programme settings)? | **The organisation admin, and a super as today, and an org admin may give only powers they hold themselves.** | The organisation admin only (the roadmap's ruling 3 word for word); a super could not tick them. |
| D3 | What does a NEW organisation admin start with? | **Everything today's org admins have.** | Only the three fixed powers; you tick the rest for each new organisation. |
| D4 | Team changes: invite, suspend, remove or delete staff; add to or remove from a group; pause a reviewer; set a reviewer's gifts. Assignable or not? | **They stay with the organisation admin always**, as part of O15's "changing other staff's permissions": since M2b, a person's group IS their permissions. | A new assignable "Team: change" power. Today's O15 three would become four, or O15 would be read more narrowly. |
| D5 | What each new box means. | **As in G5 to G9:** Applications "change" = assign, nudge, guardian contact, reviewer notes, the parent-call list. Applications "approve" = reject or close before award. Requests "approve" also covers decline. One NEW box, **Scholars: "suspend or end a scholarship"** (the senior letters). | No new box: the senior letters go under Applications "approve". |
| D6 | Sponsor vetting approves a sponsor's ACCOUNT, which every organisation then relies on. Should "Sponsors: approve" be assignable? | **Yes**, with the box's help text saying it vets accounts for the whole platform (R6: only the O15 three stay fixed). | Vetting stays with org admins and supers, a fourth fixed power (amends R6). |
| D7 | The "Sponsors to vet" card (D12, TD-503 part 1). Today two admins and finance see it but cannot vet. | **Leave the card as it is**: whoever sees Sponsors sees the count, and only vetters act. Nobody changes. | The card shows only to those who can vet. The two admins and finance lose it unless you give them "Sponsors: approve". |

### Architect (do not re-open; flag if one cannot hold)

| | Decision |
|---|---|
| A1 | The data step replaces each OA row's list with the OA set (above): active, revoked, archived and pending, with an audit row. It is reversible and idempotent, and migrate-first. |
| A2 | The O15 three are held by role: `resolve` adds `manage_team` for an OA; `effective_v2` adds `billing.edit` and `requests.approve`. They are never stored, never assignable, and hidden on the tab (M2d D3). The code `lead_tier` stays, for `manage_team` only. |
| A3 | **Money carry-over until M4.** `LEAD_MONEY_UNTIL_M4 = ('payments.view', 'payments.prepare', 'payments.check', 'payments.approve', 'sponsors.check')` is added for an active OA by role in `effective_v2`. No gate reads these v2 keys today; storing their old-key equivalents would arm or disarm the payment chain (`holders`, the fallback), and that is M4. This is the one implicit grant left. It is named and logged as TD-620, and M4 removes it. |
| A4 | The OA keeps the Admins seat by role (`in_admins`, `LEAD_FIXED`): the OA holds the O15 three, which are Admins powers. M2c C5 stops being "an exception until M3" and becomes the rule. `groups_to_leave` is unchanged; only its docstring changes. |
| A5 | The 11 keys become assignable LAST (M3c), in the same release as the web padlocks. Until then the server still refuses them for team members, and `stored_v2` still ignores them on a team row. So a ticked box always opens something. |
| A6 | Team -> Reviewers Add / Remove on an OA adds or removes `review` in the stored list and keeps the rest. `staff_tables_admin.py:203-206, :261-263` must never write `['review']` or NULL over an OA's keys. |
| A7 | `SECTIONS_BY_ROLE`: the `org_admin` row is read from keys. `funnel`, `attention` and `applications_series` need `see_all`; `money` and `money_series` need `spending`. The data step gives every OA both, so FULL, as today. The other rows stay as they are (TD-621: converting them changes what admins, finance and qc see, so it is the owner's later). |
| A8 | TD-613 stays its OWN sprint, after M3b and before M4. It changes case flow (reopen, revert, `ASSIGNABLE_STATUSES`), not who holds which key. It has its own adversarial angle (a funded case changing hands). It shares `services/assignment.py` with M3b, so it waits for M3b to land. `R1_SUPER_TARGET_ROLES` retires after it (TD-622). |
| A9 | M2b D3, revisited: `lead_tier` refuses only `manage_team`. NEVER_GRANTABLE is unchanged. `refusal_reason` loses `lead_only`; the web type loses it in M3c. |
| A10 | The scanner widens: `test_role_is_display_only.py` also reports `is_lead_tier(` and `LEAD_ROLE` reads. Each GATE-LEFT T5e entry is DELETED when its gate converts, never reclassified to pass. The ones that stay are re-labelled with list K's reason (`O15`, `target rule`, `M4`, `TD-613`). |
| A11 | A new door per page power in `staff_tables.DOOR_KEYS` (for example `settings`, `programme_settings`, `billing_read`, `requests_read`, `requests_write`, `requests_decide`, `contracts_read`, `contracts_write`, `assign`, `decide`, `sponsor_vet`, `senior_letters`). The web mirror `lib/pageDoors.ts` follows. `opens_door` raises on an unknown name, as today. |
| A12 | "Only powers you hold" (D2) is checked in `plan_change` under the target's row lock, after `asked_set`. A super is exempt. The refusal code is `not_held`. |

## Size: split into three parts, each under the ~40-file cap, each shipped on its own

- **M3a: explicit keys and the data step (server, about 16 files).**
  - Code: `staff_permissions.py`, `staff_permissions_v2.py`, `staff_tables.py`, `staff_tables_admin.py`, `staff_person.py`,
    the 0098 migration.
  - Tests: `test_m3_nobody_changes.py`, `test_m3_migration_0098.py`, and the updates to `test_permission_catalogue_v2.py`,
    `test_m2b_stored_v2.py` and `test_role_is_display_only.py` (A10).
  - Docs: CHANGELOG, decisions, technical-debt.
  - Nothing a person can do changes.
- **M3b: server gates read keys (about 34 files).** G1 to G9 (45 functions), the new doors (A11), `SECTIONS_BY_ROLE`
  (A7), D7, and the scanner entries deleted. The 11 keys are still not assignable, so every OA passes by the keys M3a
  stored, and everyone else is refused as today.
- **M3c: granting and the web (about 25 files).**
  - `asked_set` / `plan_change` (A9, A12, D1)
  - `invite_permissions` (D3)
  - list W, `permissionLayout.ts`, i18n en/ms/ta
  - the Guide and FAQ lines on what an organisation admin does
  - web tests

Why not one sprint: about 75 files. Why not two: M3a with M3b is about 50 files, and M3b's adversarial review needs its
own diff. M3a can ship with no owner-visible change. M3b and M3c each need the owner's phone check.

## Out of scope (do not touch)

- **M4 money:**
  - `credit_steps.py`, `sponsorship/credits.py`, `payments.py`, `payments_chain.py`
  - web `canRecordCredit`, `isFinanceViewer`, `lib/sponsorDetail.ts:146-161`
  - the Vircle ID correction
  - the A3 carry-over's removal
- TD-613 (A8). `awaiting_qc` and TD-503 part 2.
- `SECTIONS_BY_ROLE` rows other than `org_admin` (TD-621). The web older-payload fallbacks and `canFilterByAssignee`'s
  `admin` arm (TD-623).
- T5f (gift limits as a fence).
- Anything that changes a super's powers.
- Budgets: `courses/views_admin.py` is at 765/765 and courses -> scholarship imports at 16/16. Neither is ever raised. A
  gate that needs a new import in `courses` goes through the existing leaf modules (`staff_tables`,
  `staff_permissions_v2`).

## Tests (targeted while building; full suites once at the end of each part)

- **`test_m3_nobody_changes.py`.** One row per live shape, built as it stood before M3 and read with a hand-written copy
  of the OLD rule (`resolve`, `lead_v2`, the role gates), then put through 0098's `plan_row` and read with the NEW code.
  - Shapes:
    - OA NULL; OA `['review']`; OA with leftover team keys (`['payments_approve', 'see_all']`)
    - OA revoked; OA archived; OA pending (never signed in)
    - two OAs in one organisation
    - super
    - every M2b team shape (from `test_m2b_nobody_changes.py`)
    - a team row with a stored lead-only key (stays ignored until M3c)
  - Compared for each shape:
    - `resolve`, `effective_v2`, `page_keys`, `tables`, every door in `DOOR_KEYS`
    - every converted gate's predicate (M3b)
    - `my_pending` cards, `sections_for`, `in_reviewers`, `is_review_target`, `may_hand_to`
    - `holders(org, k)` for each payment and withdrawal key
    - `payments_chain.fallback_approvers` (the money must not move)
  - M3b and M3c each add their gates to it.
- **The role-is-display-only pin** is updated, never weakened (A10). The GATE-LEFT T5e count falls to the entries list K
  keeps, and a new assertion fails if an `is_lead_tier(` gate appears outside the allowlist.
- **`test_m3_migration_0098.py`.** Frozen constants equal the live ones; the SQL text is pinned to `plan_row`;
  forward, reverse and re-run are exact; revoked and archived rows are written; a non-OA row is untouched.
- **Permission save (M3c).**
  - Each of the 11 keys is saved for a team member by an OA who holds it.
  - Refused `not_held` when the OA lacks it.
  - `manage_team` -> `lead_tier`; `billing.edit` / `requests.approve` -> `never_grantable`.
  - A super edits an OA's set; an OA editing another OA -> 404 (D1); own -> `own_permissions`.
  - An OA's Reviewers Add / Remove keeps the other keys (A6).
- **Per gate (M3b).** A team member given the key passes, the same member without it is refused (403, or a 404 where the
  fence says so), and an OA without the key (edited by a super) is refused. The OA always passes the O15 three.
- **Web (M3c).** The padlocks are gone for the 11 keys; the OA card is editable for a super and read-only for an OA. Each
  list W site follows `page_keys` / `permissions`. `officerGateDrift.test.ts` and the navigation tests are updated.
- **Gates.** These run from the API folder:
  - `python3 manage.py check`
  - `python3 manage.py makemigrations --check` (M3a adds only the data migration; no schema change)
  - the full pytest `-n auto` through `python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <pytest command>`
  - web: `npm run gates`, then `npm run bundle-budget -- --gate`, both through the queue

## Release order (architect and owner, not the builder). Per part

1. Adversarial review of the part's diff (auth). A fresh reviewer gets the code, not this brief's conclusions.
2. The owner's yes.
3. **M3a only: migration 0098 by hand, before the push.**
   - Pre-check: Q1, Q7.
   - The DATA block, then the LEDGER block (the `django_migrations` row in the same transaction).
4. Push and deploy.
5. **M3a only:** re-run the DATA block and the POST-DEPLOY check (zero OA rows NULL; each OA's list equals the OA set,
   plus `review` where it had it).
6. **The owner's phone check:**
   - M3a: an org admin's pages and buttons are all as before.
   - M3b: the same, plus one team member who sees no new page.
   - M3c: give a test team member one new power, see it open, take it away, see it close.

## Risks

- **Wiping an OA's keys** through an old writer (A6), or through Restore / re-invite (`staff_archive.py:212`,
  `staff_reinvite.py:253, :314` call `invite_permissions(role)`). For an OA they must write the OA set, never NULL.
  The nobody-changes test covers Restore.
- **Leftover keys on an OA row** would be read for the first time. A1 replaces the list, and Q1 sizes it.
- **The money carry-over (A3)** is an implicit grant that R6 forbids. It is named, tested and dated to M4. If M4 slips,
  R6 is not complete.
- **Sponsor vetting is platform-wide (D6).** A team member with "Sponsors: approve" can vet an account other
  organisations see. The help text and the owner's decision carry it.
- **Escalation through granting.** Without A12 an OA could give a power they lack. A super is exempt; that is accepted,
  because a super already passes every gate.
- **Two OAs in one organisation.** Under D1's recommendation neither can cut the other back. Q2 says whether that case
  exists today.
- **The scanner's blind spot.** The 15 unscanned server places would have shipped unseen. A10 closes the blind spot
  before M3b converts anything.
- **A deploy between the hand migration and the image.** The new code reads a NULL OA row as the OA set, and the
  post-deploy re-run writes it.

New technical debt to log when building (from TD-620):
- **TD-620:** the A3 money carry-over (M4).
- **TD-621:** the non-OA rows of `SECTIONS_BY_ROLE`.
- **TD-622:** `R1_SUPER_TARGET_ROLES` retires after TD-613.
- **TD-623:** the web older-payload role fallbacks and `canFilterByAssignee`'s `admin` arm.

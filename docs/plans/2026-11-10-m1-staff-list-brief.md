# M1 brief: Staff list and membership rules (O1-O7, plus O9/O10 follow-ups)

Roadmap: `docs/plans/2026-11-10-team-membership-roadmap.md`. Written 2026-11-10 against `d6fd0761`.
Each rule is labelled **owner** (a ruling O1-O11) or **lead** (the architect's call in this brief).

## 0. Preconditions (owner)
- **G10 deploys BEFORE M1.** The M1 build starts only once G10 is live AND the owner approves this brief.
- **Step 1 of the build is a rebase on G10.** G10 changes these paths (old import paths keep working through re-exports):
  - `scholarship/serializers.py` becomes the package `serializers/`.
  - `scholarship/serializers_admin.py` becomes the package `serializers_admin/`. The name-by-email lookup moves to `names.py::_admin_name_by_email`.
  - `courses/models.py` becomes the package `models/`: catalogue, organisations, student, outcomes. `tenants()` lazy-imports PartnerAdmin.
  - `contracts.py` and `sponsorship.py` become packages. M1 touches neither.
  - `models_staff.py` is unchanged, and G10 adds no migration, so **courses 0096 is ours**.
- File references below are to `d6fd0761`. A reference into a G10-moved file says **(verify after rebase)**, with the module it most likely lands in.
- Put every edit in the new module file, never in the re-export `__init__`. Point every `mock.patch` target at the new module.
- **STOP AND REPORT before editing anything under `serializers_admin/` or `courses/models/`.** M1 needs no edit there (§5 only reads them).
- Before building on `courses/views_staff.py`, confirm G10's A3.8 left it alone.

## 1. Split decision (lead)
The full M1 is about 36 API files and about 22 web files, roughly 58 in all. That is over the 40-file solo cap, so M1 is split in two.

**M1a: API, archive and migration (about 36 files).** It ships alone safely: every new power is opt-in by a request field that only the M1b web sends.
- `DELETE admin/admins/<id>/` and mentor delete archive only with body `{"archive": true}`. Without it they behave exactly as today: erase, or 409 `has_work`.
- Team-table Remove and the mentor `remove` action leave a person with no group only with `{"to_no_group": true}`. Without it they answer `LAST_TABLE` as today.
- Live from M1a alone, all safe or an improvement:
  - the archive readers;
  - restore on re-invite (through today's Invitations page);
  - the O10 read fence (today's web already links the page);
  - phone dropped from the list (today's web already ignores it);
  - the Mentors Remove refusal while they mentor anyone (owner O5; today's web shows the server's message).

**M1b: web (about 22 files).** It needs M1a live, and it ships the Staff tab, the moved actions and the reduced group tables.

**Order:** G10 live → M1a (build, review, migrate-first, deploy, phone check) → M1b.

## 2. The no-group shape (O6). Lead decision: a new role `member`, labelled "No group"
- **Shape:**
  - `role='member'`;
  - `permissions` NULL;
  - `is_active` kept, so sign-in is kept;
  - any mentor link kept, with the Mentor deactivated, as `finance` keeps one today.
- **Why not reuse the mentor-login shape (role `mentor`, no mentor record):**
  - It needs the `partner_admin_mentor_iff_mentor` check relaxed (`models_staff.py:230-233`).
  - It puts a mentor-less `mentor` row behind the 23 views that already opt in through `mentor_methods`: letters, mentor_students, mentoring, surveys, development, my_pending, my_programmes, scholars ×6, reviewers:529 and me ×4. Each of those scopes by the mentor, and a `None` mentor reaching a `filter(mentor=...)` can read the scholars with NO mentor.
  - A new role opted in NOWHERE except Profile has zero such views to audit. Deny-by-default (`views_admin.py:89-97`) does the work.
- **What a member may open:**
  - `me.py:144` (profile GET/PATCH);
  - `me.py:251` (photo POST/DELETE);
  - `me.py:301` (own activity GET);
  - `me.py:343` (POST);
  - `views_admin.py:291` (`admin/role/` GET);
  - `views_admin.py:688` (set-password POST).
  - Nothing else.
- **Landing:** `/admin/profile`. The menu shows Profile only.
- **Every place that must treat `member` correctly (each one is a test):**
  1. `models_staff.py`:
     - add `MEMBER_ROLE`, the choice and an `is_member` property;
     - add `member` to `MENTOR_LINK_ROLES` (`:33`), so the link is kept;
     - do NOT add it to `NOT_STAFF_ROLES` (`:24`): a member IS listed on Staff;
     - check that `mentors_now` (`:261`) stays False for a member (the role is not in `STAFF_MENTOR_ROLES`).
  2. Migration 0096 (§7): recreate `partner_admin_mentor_iff_mentor` with the widened role list.
  3. `get_admin` (`views_admin.py:89-97`): deny by default for `is_member`, with `member_methods = ()` on the same line as the existing tuple. **The line count must not grow** (oversize ledger).
  4. `member_methods` opt-ins on the six views listed above, and only those. Test: one member request to every admin URL, where only those six answer anything other than refused.
  5. `staff_tables.py`: `_team_member` (`:55`) and `tables()` give `()` for a member. `staff_permissions.resolve` / `preset_for` give no keys for a member.
  6. Fence role sets (after the §6 split, in `courses/staff_fence.py`): add `member` to `_ORG_ADMIN_MANAGEABLE_ROLES` (`views_admin.py:588`), `PROGRAMME_STAFF_ROLES` (`:594`) and `_DELETABLE_ROLES` (`:599`).
  7. `staff_tables_admin.py`:
     - `_refuse_basic` (`:139`) admits a member;
     - `_plan_add`: a member joins Admins with the `admin` preset, or Reviewers with the `reviewer` preset;
     - `candidates` (`:383`) offers members.
  8. `staff_mentor.py`: a new `add_member(caller, target)` for Add to Mentors. It reactivates the kept Mentor, or makes one, and sets `role='mentor'` (the T3 mentor-login shape).
  9. `AdminStaffRoleView` (`views_admin/staff.py:45`): a member is neither a target nor a new role. It refuses `not_eligible` ("Add them to a group from the Staff list").
  10. Person page GET (`views_admin/staff.py:110`): `editable` is False for a member. The Permissions tab says "No group".
  11. Web:
      - `navigation.ts:47,50` (the role union and list);
      - `adminLanding.ts:50` (`OUTSIDER_ROLES` gains `member`, which lands on `/admin/profile`);
      - `AppShell.tsx:176` (no probes for a member);
      - the i18n role label in en/ms/ta.
  12. Assignment pools, nudges and payment checkers are role- or key-gated and admit no member. Grep `role__in=` in `send_review_nudges.py:74`, `lifecycle.py:319`, `payments_chain.py:202` and confirm.
- **Doors into `member`:**
  - Remove of the last group from Admins/Reviewers (`staff_tables_admin._plan_remove`, `:184`);
  - Remove from Mentors by a mentor login (new `mentor_invite.remove_from_mentors`).
- **Doors out of `member`:**
  - Add to any group;
  - Suspend/Restore (the role is kept);
  - Delete (erase or archive).
- A no-group person never becomes `member` silently. Today's T3 rule stands: a staff person who still mentors and leaves their last staff table becomes a mentor login (`_plan_remove:192-216`).

## 3. Staff list endpoint (O2, O3). Lead decision
- **Route.** `GET /api/v1/admin/staff/`, in a NEW module `courses/views_staff_list.py`. `views_staff.py` is at 579 lines against the 600 standard.
- **Read gate.** The same as `AdminListView` (`views_staff.py:424`): a super (with `?organisation=`), or the caller's own organisation. A finance or other `team_read` reader gets every row with `manageable:false`.
- **Rows.** A row is listed when ALL of these hold:
  - `archived_at IS NULL`;
  - role is not `super` and not `source_partner` (a sponsor is never a PartnerAdmin);
  - the person has accepted: `first_seen_at IS NOT NULL` (O1: before that, they live on Invitations only).
- This covers active staff, suspended staff (`is_active=False`, not archived), mentor logins and members.
- **Fields per row:**
  - `id`, `kind` (`staff` | `mentor`), `mentor_id`, `name`, `photo_url`, `last_seen_at`;
  - `groups`: `admins` / `reviewers` / `mentors`, from `staff_tables.tables`, with mentors read from `mentors_now`;
  - `lead`, `suspended`, `manageable`;
  - `work: {admins: {runs_in_progress}, reviewers: {open_cases}, mentors: {scholars_now}}`;
  - `deletable`, `delete_outcome` (`erase` | `archive` | null) and `delete_never` (a reason code: `self`, `sole_org_admin`, `has_unfinished_work`, `not_manageable`);
  - `revocable`.
- **No phone and no email** (O9).
- **Query budget: fixed, never per row.** Use:
  - `staff_footprint.footprints` (one query);
  - `staff_tables_admin.open_case_counts` (one);
  - a new `staff_work.runs_counts(emails)` (one);
  - a new `staff_work.scholars_now_counts(mentor_ids)` (one);
  - `staff_photo.team_cards` (one), reading `photo_url` only.
  - Add a route-level query-budget test. lessons.md: "a shared predicate needs a budget of its own".
- **Actions** (web M1b, endpoints unchanged except §5): Suspend/Restore and Delete live ONLY on the Staff tab (owner O3).
  - Staff rows call `admin/admins/<id>/revoke/` and `DELETE admin/admins/<id>/`.
  - Mentor-login rows call `admin/mentors/<pk>/deactivate|reactivate/` and the mentor delete.

## 4. Group tables: Add / Remove only (O4, O5)
- **Owner rules.**
  - Admins, Reviewers and Mentors offer only Add and Remove.
  - Revoke, Delete, Restore and the mentor-login Deactivate/Reactivate/Delete leave `StaffAdmin.tsx`, `reviewers/page.tsx:231-240` (StaffActions on the Admins table) and `MentorsAdmin.tsx:62-90,144,275`.
- **What Add picks from (lead).** Active, accepted, non-archived members of the organisation the caller may act on (`staff_tables_admin.candidates`, `:383`, plus members). Mentors' Add keeps today's "Mentored before" resume (`staff_mentor.resume`) and adds members (`add_member`).
- **Remove refusals per group (owner O5; lead for the exact list):**

| Group | Refused while | Proof (model.field) | Code |
|---|---|---|---|
| Reviewers | open cases | `ScholarshipApplication.assigned_to` with `IN_PLAY_STATUSES` or `decision_reopened_at` not null (`staff_lifecycle.open_cases`) | `has_open_cases` (exists, `:68`) |
| Mentors | scholars mentored now | open `Mentorship` of their Mentor (`mentoring.scholars_now`) | NEW `has_scholars` |
| Admins | (a) a payment run they made or maker-signed is unfinished | `PaymentRun.created_by` / `admin_signed_email`, `status in ('draft','admin_signed','finance_checked')` (`staff_lifecycle.runs_in_progress`, `:92-103`) | NEW `run_in_progress` |
| Admins | (b) the stranding rule (exists) | `spa._refuse_stranding` | exists |
| Admins | (c) lead: org admin | `is_lead_tier` | `lead_fixed` (exists) |

- **Considered and NOT blocking (lead), because each waits on SOMEONE ELSE:**
  - `AwardWithdrawalRequest` `status='pending'` (`models/withdrawals.py:42,48`): any other checker decides.
  - `OrgRequest` `status='quoted'` (`models/tenant_requests.py:122`): any org admin approves.
  - `ContractTemplate` `pending_deployment` (`models/agreements.py`): a super deploys.
  - The last `payments_approve` holder: this stays the existing `finance_check_off` consequence on the confirm (`staff_tables_admin.py:262`), not a block.
- **Today's `staff_mentor.stop` (`:98`) ENDS open assignments; it must now REFUSE `has_scholars` instead (owner O5).** The refusal says where scholars are moved. The builder confirms that path exists (`grep -n "def assign\|def end" apps/scholarship/mentoring.py`).
- **Last group (owner O6):** with `to_no_group: true`, `_plan_remove` returns `{role:'member', stored:None, becomes_member:true}` instead of `LAST_TABLE` (`:196`). The same applies in `_cheap_refusal` (`:288`).
- **Mentor login Remove from Mentors:**
  - action `admin/mentors/<pk>/remove/` (in `AdminMentorActionView`);
  - it refuses `has_scholars`;
  - it stamps the Mentor deactivated and sets `role='member'`, keeping the link.

## 5. Delete as archive (O7)
- **Owner.** Delete is refused while there is unfinished work in ANY group (the union of §4's three counts).
  - With no records, the person is erased, by today's path (`views_staff.py:112-197`, `mentor_invite.delete_mentor:459`).
  - With records (`staff_footprint.footprint` non-empty), the person is archived.
- **Lead.** Archive, in one transaction, under the row lock (`views_staff.py:164`) and `lock_org_admins_of`:
  1. Keep the sole-org-admin refusal.
  2. Call `staff_mentor_leaves` / `staff_mentor.leave`.
  3. Set `is_active=False`, `archived_at=now`, `archived_by_email`.
  4. Mark pending staff `Invitation` rows cancelled.
  5. Retire the login with `staff_lifecycle.plan_login_retirement` / `retire_login`, exactly as delete does, then `supabase_user_id=NULL`.
  6. Keep the row, the role, `permissions`, the mentor link, the profile and the gift rows.
  7. Write a staff activity line.
- **Re-invite restores the same row (owner; closes TD-484).**
  - It goes through `views_staff.py:241` (staff) or `mentor_invite.py:209` (mentor). A row that is archived and in the inviter's organisation goes to a NEW `staff_archive.restore(row, role, ...)`.
  - It does not go through `bring_back` (`staff_reinvite.py:266`, which must REFUSE archived rows).
  - `restore` does this:
    - clears `archived_at`;
    - sets `is_active=True`, the role and `invite_permissions(role)`, and `first_seen_at=NULL`, so the person waits on Invitations again;
    - provisions a new login through `provision_for_invite`;
    - adds a new Invitation;
    - keeps the mentor link with the Mentor deactivated. Mentoring comes back only through Add to Mentors.
  - Another organisation's archived email keeps `not_invitable`.
  - A mentor invite of an archived staff row with no mentor link refuses `use_staff_invite`.
  - `AdminInviteView.post` is on the long-function ledger (`code-standards.json`: 151). The branch is ONE call into `staff_archive`, so the function must not grow.
- **QC separation keeps its evidence.** `qc_separation.py:50-109` matches on `admin.id` and email, and both survive archive and restore. Test: archive a reviewer who verified case A, restore them as QC, and A stays barred (`refusal`, `barred_ids`).
- **Every reader that must skip, or branch on, an archived row. 27 sites:**
  - **Lists (5):**
    - `courses/views_staff.py:438` (AdminListView);
    - `scholarship/views_admin/reviewers.py:276` (`include_revoked`);
    - `courses/staff_gift.py:219`;
    - `scholarship/views_admin/mentors.py:148` (the Mentors tab and its Mentor query above it; also exclude a Mentor whose login is archived);
    - `scholarship/views_admin/invitations.py:53`.
  - **Targets by id. Each gives 404 for an archived row (17):**
    - `views_staff.py:164` (Delete), `:380` (Resend), and `:543` (Revoke/**Restore**, which must never revive an archived row);
    - `views_admin/staff.py:45`, `:103` and `:240`;
    - `staff_tables_admin.py:348`;
    - `staff_lifecycle.py:195`;
    - `staff_permissions_admin.py:243`;
    - `staff_mentor.py:69` (add), `:109` (stop) and `:128` (**resume**);
    - `views_admin/mentors.py:346` and `:530`;
    - `mentor_invite.py:115` (`login_of`, behind **reactivate**) and `:481`;
    - `views_admin/invitations.py:296` (resend/cancel).
  - **Email lookups that branch to restore or refuse (3):**
    - `views_staff.py:241`;
    - `mentor_invite.py:209`;
    - `staff_reinvite.py:266` (refuse).
  - **Maintenance (2):**
    - `management/commands/backfill_invitations.py:49` (it would mint Invitations);
    - `backfill_admin_seen.py:47/73` (it would stamp `first_seen`).
  - **Must KEEP reading archived rows**, because the name stays on the records:
    - `serializers_admin.py:31`, which moves to `serializers_admin/names.py::_admin_name_by_email` (verify after rebase; READ ONLY);
    - `views_admin/scholars.py:39`, `scholars.py:136`, `views_admin/staff.py:195`, `mentoring_read.py:25`, `mentoring.py:243`, `activity_people.py:94`, `staff_activity_read.py:152`, `views_admin/lifecycle.py:351`, `award_withdrawal_chain.py:438`;
    - `staff_reinvite.py:37/41` and `:277`, `mentor_invite.py:396`, `source_invite.py:143` (collisions still count);
    - `staff_lifecycle.py:343`;
    - `staff_mentor.py:155` (archive calls `leave` first).
  - **Already safe because they are active-only** (an archived row is `is_active=False`):
    - `views_admin.py:107/117` (`get_admin`, including the email fallback);
    - `staff_tables_admin.py:383`;
    - `staff_mentor.py:55`;
    - `views_admin/mentors.py:60` (via `eligible`);
    - `lifecycle.py:319`, `payments_chain.py:202`, `send_review_nudges.py:74`, `bursary.py:650`, `staff_permissions.py:200`, `staff_delete_rules.py:32/70`;
    - `courses/models.py:379`, which moves to `courses/models/organisations.py` `tenants()` (verify after rebase; READ ONLY).
- **Census test (lead).** Add `test_m1_archive_reader_census.py`, on the pattern of `test_t2_footprint_drift.py`. It greps every non-test `PartnerAdmin.objects` / `Invitation.objects` site and fails on one not classified in its table. This is the door that is not on the list.

## 6. O10 completion: the person page read fence (lead)
- **Split first (moves only, own commit).** Move `_ORG_ADMIN_MANAGEABLE_ROLES`, `PROGRAMME_STAFF_ROLES`, `_DELETABLE_ROLES`, `_deletable_now` and `_staff_target_manageable` (`views_admin.py:588-668`) to a new `courses/staff_fence.py`, re-exported in `views_admin.py`. Lower `oversize_files` for `apps/courses/views_admin.py` (795) to the measured size. Then edit in the new module.
- **The new `staff_target_readable(caller, target)`:**
  - a super reads anyone;
  - an org admin reads any non-archived row of their own organisation in a manageable role, plus `org_admin` (a fellow one, or themselves) and `member`;
  - it never reads a super or a source user;
  - mentor logins keep their own page.
- `AdminStaffPermissionsView._target` (`views_admin/staff.py:95-108`) uses `readable` for GET and `manageable` for PATCH. The GET answers `manageable` and `editable=False` when not manageable, and `delete_fields` then gives no delete and no revoke.
- **No self-delete and no self-suspend:** `delete_fields` and `AdminRevokeView` refuse `target.pk == caller.pk` (`delete_never:'self'`, 403 `self`).
- A fellow org admin stays **view-only**. That is the default, pending Owner question 1.

## 7. Phone (O9 follow-up, owner)
- `AdminListView` (`views_staff.py`, the `**cards` merge) serves `photo_url` only. Drop `phone` from `AdminItem` (`admin-api/admins.ts:37-38`).
- The person page `person` block (`staff_person.person`) keeps the phone under `share_phone_with_team` (`staff_photo.py:140`). The Reviewers list is unchanged.

## 8. Migration 0096 (MIGRATE-FIRST by hand)
- **`courses/migrations/0096_partneradmin_archive_member.py`:**
  - `archived_at` (DateTimeField null);
  - `archived_by_email` (CharField 254, blank, default '');
  - `AlterField role` choices (+`member`, state only);
  - `RemoveConstraint` and `AddConstraint` `partner_admin_mentor_iff_mentor` with the widened `MENTOR_LINK_ROLES`.
- **Steps:**
  1. Render the SQL with `sqlmigrate courses 0096`.
  2. The owner applies the SQL and the `django_migrations` row in ONE transaction, before the deploy.
  3. Run the Security Advisor afterwards (lessons.md: migrate-first SQL lacks the Supabase half).
- The new constraint must pass on today's rows. The builder proves it on a test DB with every current shape.

## 9. Coordination (owner and audit agent)
- `courses/views_staff.py` is ours. TD numbers start at **TD-603**.
- No PII in fixtures or commits: use invented names and `@example.test` emails.
- UI text is in British English, with ms/ta through i18n (`src/messages/{en,ms,ta}.json`), every new key in all three.
- No push and no force-push while the audit agent integrates. Rebases stay local, and every push needs the owner's yes.

## 10. Code-health pre-flight
- **Oversize and hotspot.**
  - `courses/views_admin.py`: hotspot #9 and oversize 795. It is split first (§6) and ends smaller.
  - `serializers_admin` and `courses/models`: read only.
- **Near the 600-line standard (API and web both 600):**
  - `views_staff.py` (579): net change ≤ 0, with new code in `views_staff_list.py` and `staff_archive.py`;
  - `views_admin/mentors.py` (541) and `mentor_invite.py` (504): logic goes in `staff_archive` / `staff_work`;
  - `reviewers/page.tsx` (533): the Staff tab is a lazy `components/admin/StaffList.tsx`, and removing StaffActions shrinks the page;
  - `MentorsAdmin.tsx` (533): shrinks.
- **Budget greps done:**
  - API `oversize_files`: `courses/models.py` 1051, `views_admin.py` 795, `serializers_admin.py` 1006;
  - `long_functions`: `views_staff.py::AdminInviteView.post` 151;
  - web: `eslint_disable_without_reason` on `reviewers/page.tsx` (1). Keep that line's disable intact.
  - Re-grep after the G10 rebase.
- **Measure baselines yourself before any edit**, writing the command and the count into the sprint log:
  - `python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <full API pytest>`;
  - `npm test` and `npm run gates` in `halatuju-web`.

## 11. Build steps
**M1a** (one Opus builder, under 120k; Haiku runs the gates):
1. Rebase on G10 once it is live. Re-grep the budgets and re-verify every "(verify after rebase)" reference.
2. Measure the baselines (§10).
3. Split commit: `courses/staff_fence.py` (moves only), then lower the budget.
4. `models_staff.py` and migration 0096, with the constraint test.
5. `member` shape: §2 items 1-10, with the deny-by-default sweep test.
6. `scholarship/staff_work.py`: the per-group counts, single and batched.
7. Remove rules: §4, including `stop` → `has_scholars`, the `to_no_group` flag and mentor `remove`.
8. `courses/staff_archive.py`: archive, restore and the erase/archive decision. Wire up Delete (`{"archive":true}`), mentor delete, and the two invite lookups. `bring_back` refuses archived rows.
9. The 27 reader sites (§5) and the census test.
10. The Staff list endpoint and its query budget.
11. O10 read fence and the self guards. Drop the phone.
12. Docs: CHANGELOG, TD-603+ in `technical-debt.md` (close TD-484), `decisions.md` entries (lead rules labelled lead), and `ARCHITECTURE_MAP.md`.

**M1b** (one Opus builder; Sonnet is acceptable for copy-only follow-ups):
1. `admin-api/admins.ts` and `admin-api/mentors.ts`: types, `getStaffList`, delete `archive`, mentor `remove`.
2. `StaffList.tsx` (the first Team tab, the default `?tab=staff`), using `StaffActions` for Suspend/Restore and Delete. The confirm names the outcome ("Archive: their name stays on past records" / "Erase").
3. Strip the actions from `StaffAdmin.tsx`, `reviewers/page.tsx` and `MentorsAdmin.tsx`. Remove sheets (`TeamTables.tsx`) show the new refusal codes and "becomes No group".
4. Member: `navigation.ts`, `adminLanding.ts`, `AppShell.tsx`, and the person page read-only state. i18n en/ms/ta.
5. Gates.

**Adversarial review:** a fresh Opus agent for each half. It gets the diff, §2 and the §5 door lists, and is asked for **the door not on the list**.

## 12. Test plan (hardest risks first)
1. **Member shape.**
   - A member gets refused on every admin URL except the six.
   - `admin/role/` gives empty tables and keys.
   - The landing page is Profile.
   - Add to each group works from member, and Remove of the last group lands on member.
   - Neighbouring states: suspended member, member with a kept link, member of another organisation.
2. **Archive readers.**
   - Each of the 27 sites has a test with an archived row present.
   - Restore (`views_staff.py:543`), mentor reactivate, `resume` and `bring_back` all refuse an archived row.
   - The census test is green.
3. **Re-invite restore.**
   - The same `id` comes back, with a new login and `first_seen_at` NULL.
   - Another organisation gets `not_invitable`.
   - A mentor invite of an archived mentor login works.
   - `AdminInviteView.post` does not grow.
4. **QC separation after archive and restore** (§5).
5. **Remove refusals:** each row of the §4 table, and `stop` no longer ends assignments.
6. **Delete:** erase versus archive versus refused, sole org admin, self.
7. **O10:**
   - An org admin GETs a fellow org admin's page (200, view-only).
   - PATCH, role, team, revoke and delete stay 404/403.
8. **Gates:**
   - `npm run gates`, bundle-budget and mobile-check;
   - the full API suite via `python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <cmd>`.

**Owner phone check (after each half is live):**
- **M1a:**
  1. Re-invite a test person who was revoked earlier, and see them come back in Invitations.
  2. Open a fellow org admin's page: read-only, no buttons.
  3. Remove from Mentors someone with a scholar: refused.
- **M1b:**
  1. Team opens on Staff, showing groups as chips and no phones.
  2. Suspend a test person, then Restore them.
  3. Remove a test person from their last group: they stay on Staff as "No group". Sign in as them: Profile only.
  4. Delete a person with past reviews: they are gone from Team, and their name is still on the case.
  5. The group tables show only Add and Remove.
  6. Everything also works at phone width.

## 13. Lessons applied (`docs/lessons.md`)
- **Owner/lead labels on every rule; an inventory does not share a builder's agent** (TD-481). The §5 census was done here, read-only, and the builder gets the fix.
- **A new shape needs every reader checked, not only the writer** (one-application-per-organisation). Hence the 27-site list and the census test.
- **Put the refusal guard at the view that receives the request** (TD-481). The archived 404s go at each view's target lookup.
- **Test the neighbouring states** (gift context): suspended versus archived versus member, and own versus other organisation.
- **A shared predicate needs its own query budget** (TD-285): the Staff list budget.
- **Migrate-first SQL lacks the Supabase half** (the Security Advisor).

## Owner answers (2026-11-10; brief APPROVED)
1. A fellow organisation admin's page is **view only**: no edit, suspend or delete of a fellow org admin, and no self-suspend or self-delete (§6 as written).
2. A re-invited archived person comes back with **fresh defaults**: `invite_permissions(role)` for the role they are invited to, history kept; the org admin adjusts powers afterwards (§5 `restore` as written).
3. Brief approved. The build starts once G10 is live (Requests reports it): M1a first, then M1b. Every push still needs the owner's direct yes.

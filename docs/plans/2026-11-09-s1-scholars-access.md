# Sprint S1 — a Scholars permission of its own (brief, 2026-11-09)

Executor: Opus agent. Architect: main session.
Branch: `s1-scholars-access`, cut from `p1-activity-box` (824baf62). P1 edits `scholars.py` (the activity view) and `role-matrix.md`, so building on top of it avoids a collision. This sprint is independent of:
- T1 (no `is_review_target` / `may_assign_to`);
- G6/A2.3 (no `services/assignment.py`: do not touch it).
- T3 (no person-page files). But T3's Permissions tab must show the new switch once both merge; see Risks.

## Goal (owner, 2026-11-09)
- **Two permissions, one per page.**
  - "See all students" is confusing. Rename it **Applications**: it reads every application in the organisation.
  - Add a new permission, **Scholars**: it reads every scholar's file in the organisation.
  - "Those with permissions for these will be able to see the details in these pages."
- **Reviewers and QC have no access to Scholars**, because their presets do not hold the new key. A reviewer's work is in Applications.
- **Semester results are reviewed by admin and org admin**, that is, by holders of Scholars.
- **Mentors have no access to Applications.** This is already true; pin it with a test.
- **Mentors see the scholars assigned to them on the Scholars page, with the full file**, just as reviewers see the applications assigned to them.
- **Access comes from permissions, not from a role label or a table.**
  - Owner: "We do not have a concept of permanent reviewers. They are team members. They get their power from permissions."
  - A person in two groups (for example Admins and Reviewers) holds the union of both groups' permissions.

Enforce all of this in the API first; the web follows.

## Facts (verified by the architect and a read-only analysis; confirm before relying on them)
- **Keys** (`courses/staff_permissions.py`):
  - `CATALOGUE` / `PERMISSIONS`.
  - `IMPLIES = {'qc': ('see_all',)}` (line 56).
  - `PRESETS` (75-79): reviewer `('review',)`, qc `('see_all','qc')`, admin `('see_all','spending','payments_prepare')`, finance `('payments_approve',)`.
  - `LEAD_TIER` is a fixed tuple (line 88): `('see_all','qc','spending','award_withdraw_approve','manage_team')`.
  - `resolve` keeps only saved keys that are `in CATALOGUE` (line 122). So an old image ignores an unknown key in saved JSON.
- **`see_all` today** opens:
  - the Applications scope (`b40_scope`, `views_admin/base.py:31-55`; also `staff_activity_read`, `verdict.py:520`, `my_programmes`, `award_withdrawal_chain`);
  - the Mentors admin read (`mentors.py:214`);
  - the assignment override (`services/assignment.py`, G6 territory);
  - the Admins table (`staff_tables.ADMIN_KEYS`, line 45; `INVITE_START = {'admin': ('see_all',)}`, line 196);
  - and **Scholars** (`_ScholarsBase._scholars_admin`, `scholars.py:40-48`, through `b40_scope`).
  This sprint takes only the last one away from `see_all`.
- **v2 catalogue** (`courses/staff_permissions_v2.py`): `'students.view'` is commented "Applications + Scholars", and `ALIASES` maps `see_all` to it.
- **The Scholars fence:**
  - `_file_for` (`scholars.py:54-65`) narrows `'assigned'` to `assigned_to == admin` (line 63).
  - Behind it: list, file, results, money, contract, result-review POST and activity.
  - Also behind it: letters (`letters.py:42`), growth (`development.py:297`), surveys (`surveys.py:199`) and the mentoring tab (`mentoring.py:45`). Find every user; don't trust this list.
- **Result-review writes** go through `_can_review_app` (`base.py:~284`), which is shared with Applications: super; then the org fence; then `qc` org-wide; else the assignee.
- **Web:**
  - Labels are `admin.permissions.see_all.{name,desc}` in `messages/en.json` (~8342), currently "See all students" / "Read every student's file in this organisation".
  - `lib/staffPermissions.ts` holds the key list (line 25), `ADMIN_KEYS` (105) and `admitsRow` (65-90).
  - The `scholars` nav row is `lib/navigation.ts:245-247`.
  - "Open scholar file" is in `PostAwardPanels.tsx:111-116`.
- **Mentors:**
  - `mentor_desk.current_assignments` / `mentor_of` define a mentor's current students. The rules are S7c in `decisions.md` (~1426) and the header of `mentor_desk.py`.
  - A mentor login passes `get_admin` only on views that list the method in `mentor_methods`. `test_mentor_denied_everywhere.py` pins the list.
- **Access matrix:** `test_team_tables_matrix.py`. Moved cells go in `EXPECTED_CHANGES`; never regenerate the fixture.
- **Live counts** (production, read-only, counts only, 2026-11-09):
  - Saved-key rows (`permissions` not null) that hold `see_all`: 2 admins, and 2 people labelled reviewer who are in both Admins and Reviewers (`review` + `see_all`; one also `spending`).
  - 1 finance row without `see_all`.
  - 25 reviewers and 2 org admins are on presets.
  - No active login holds `qc`.
  - 25 preset reviewers hold 53 awarded cases.
  - 2 mentor logins and 1 org admin have a mentor record.

## Settled decisions
| # | Decision |
|---|---|
| S1-a | **A new key `scholars`, labelled "Scholars".** It reads every scholar's file in the organisation: the list and every per-scholar endpoint and tab. Super has it. It is added to the admin preset and to `LEAD_TIER`, so admin and org admin hold it. It is not in the reviewer or qc preset, and no key implies it. It joins `staff_tables.ADMIN_KEYS`, so holding it puts a person in the Admins table, and `INVITE_START['admin']` becomes `('see_all','scholars')`. In the v2 catalogue it gets its own key (e.g. `scholars.view`, Programme group); `students.view` then means Applications only. Fix the comment and `ALIASES`. |
| S1-b | **Rename `see_all`'s label only.** "See all students" becomes **"Applications"**, with the description "Read every application in this organisation." Do the same in ms and ta, and on the v2 label if it has one. The stored key stays `see_all`: no key rename and no change to what it opens, apart from S1-c. |
| S1-c | **Scholars asks `scholars`, not `see_all`.** Add `scholars_scope(admin)` beside `b40_scope` in `base.py`, returning `'all'`, `'mentor'` or `'none'`. `'all'` means super, or the person holds `scholars`. `review`, `qc` and `see_all` alone give 403. Drop the `'assigned'` branch of `_file_for`. `b40_scope` and Applications are unchanged. No role-label read (`test_role_is_display_only.py`). |
| S1-d | **Writes on a scholar file are for `scholars` holders across their organisation.** These are semester-result review (accept/query), letters and activity notes. They are no longer limited to the assignee, and `qc` no longer writes here. `_can_review_app` is shared with Applications, so leave it alone and add a scholar-file write check. The org fence stays, and a closed file stays read-only. |
| S1-e | **Union by keys.** A person in two groups holds both groups' keys. The 2 live people in both Admins and Reviewers get `scholars` through the data migration (S1-g) and keep their assigned applications through `review`. The web gate must admit by key: the `scholars` row drops `reviewer` from `roles`, so confirm `admitsRow` lets a saved-key team member through on `perms` whatever the label. Add a test for the shape "label reviewer, keys `review` + `see_all` + `scholars`". |
| S1-f | **Mentors and Applications:** no code change. A test pins that a mentor login gets 403 on the Applications list and detail, through both the API and the web `canAccess`. |
| S1-g | **Data migration (additive), so nobody who reads Scholars today loses it at deploy.** Every saved-key row that holds `see_all` gains `scholars`; live, that is 4 rows. Preset rows need nothing, because presets carry it. The owner can then untick it on the Permissions tab. Follow MIGRATE-FIRST from `docs/deployment.md`: a reversible data migration in the repo, applied to production by hand before the push, with the `django_migrations` row in the same transaction. The old image ignores the unknown key (`resolve`, line 122): prove this with a test or by reading the code. Keep the permission-change audit (`models/staff_permission_changes.py`) truthful: record the migration's additions, or document why not. |
| S1-h | **Mentors on Scholars** (owner, "Scholars, full file"). Applies to a mentor login, and to staff who mentor (`mentor_desk.mentor_of`).<br>• **Scope:** only their CURRENT students (`current_assignments`: open, own organisation, in maintenance, never their own application). Every per-scholar door gives a single 404 for anything else. Access ends when the mentoring ends.<br>• **What they see:** every tab a `scholars` holder sees: results, money, contract, documents, letters, activity, growth, surveys and mentoring. Exception (architect's default): activity notes marked **Staff only** stay hidden, with their counts, because a mentor is not staff.<br>• **Read-only:** none of S1-d's writes. They keep logging meetings on **My students**, which is unchanged.<br>• **Server:** add `GET` to `mentor_methods` on exactly the Scholars read views. Each checks the mentor scope first. Update `test_mentor_denied_everywhere.py`.<br>• **Combined:** a person who holds `scholars` and also mentors gets `'all'`.<br>• **Supersedes** S7c point (2), the "never" list, and point (7), "My students and Profile only". Mark both "Superseded 2026-11-09 (S1)". |
| S1-i | **Supersede** `decisions.md` 2026-10-29 "The Scholars list and file read by the Applications rule", and the Scholars cell of T5c ("Applications and Scholars keep their rules"). Mark both "Superseded 2026-11-09 (S1)". |

## Build
- **API:**
  - The `scholars` key per S1-a: catalogue, presets, `LEAD_TIER`, `ADMIN_KEYS`, `INVITE_START` and v2.
  - `scholars_scope` per S1-c, and the scholar-file write check per S1-d.
  - The data migration per S1-g.
  - Make sure no other door lets a non-holder reach scholar data, for example document downloads keyed by scholar. Exception: the Payments funding-summary allowlist stays as it is.
  - For a mentor: filter "Staff only" activity rows and their counts on the server. Check the P1 actor rule, so a mentor reading the log gets no email that P1 withholds. Give document signed-link views the same mentor scope.
  - Fix the "same as Applications" comments: `scholars.py:6-12`, `letters.py:7`, `test_scholars_endpoints.py:5-6`, `staff_permissions_v2.py` (students.view).
- **Web:**
  - Add the new key to `staffPermissions.ts` (list, `ADMIN_KEYS`), with en/ms/ta labels:
    - name "Scholars";
    - description "Read every scholar's file in this organisation."
  - Relabel `see_all` per S1-b.
  - The Permissions editor shows the new switch where Applications sits. Check its group and order.
  - On the `scholars` nav row:
    - set `perms` to `['scholars']` and `roles` to `[super, org_admin, admin, source_partner, mentor]`;
    - a mentor login gets the row through its role;
    - a staff member who mentors without `scholars` gets it through their mentor record, the same signal My students uses;
    - mentor nav becomes My students, Scholars and Profile.
  - The mentor's file view hides every write control. The server refuses them anyway.
  - Keep `source_partner`, which renders `components/source/*`. Confirm what it shows.
  - Gate "Open scholar file" on `canAccess('/admin/scholars', …)`, and find any other link into `/admin/scholars`.
  - Fix the comment at `navigation.ts:238-243`.

## Done when
- **API tests:**
  - Reviewer-only, QC-only and `see_all`-only (no `scholars`) each get 403 on the Scholars list, a file, every tab (results, money, contract, activity, letters, growth, surveys, mentoring) and the writes.
  - A holder of `scholars` alone (without `see_all`) reads Scholars but gets 403 on Applications. This proves the two keys are separate.
  - Admin, org admin and super read and write as before. An admin who is not the assignee can accept or query a semester result in their organisation, and gets 404 cross-organisation.
  - The migration adds `scholars` to every saved-key row that holds `see_all`, touches nothing else, and reverses cleanly.
  - A mentor gets 403 on the Applications list and detail.
  - **Mentor on Scholars:**
    - only current students;
    - every tab 200;
    - a single 404 for an ended assignment, another mentor's student, another organisation's file, their own application and an unknown id;
    - every write refused;
    - no "Staff only" rows or counts;
    - a mentor who holds `scholars` sees the whole organisation.
  - The matrix diff equals `EXPECTED_CHANGES` exactly.
- **Web tests:**
  - The new switch and both labels in en/ms/ta.
  - The nav row by key: reviewer, QC and `see_all`-only see none; admin, org admin, `scholars`-only and "label reviewer + `scholars`" see it; a mentor sees it.
  - "Open scholar file" is hidden without the key.
  - A source_partner keeps its row.
- **Gates:** run once through `test_queue.py`:
  - API pytest, `check`, `makemigrations --check`;
  - `npm run gates`, bundle-budget, mobile-check (copy `.env.local` from main and delete it afterwards).
- **Docs:**
  - `decisions.md`: the S1 entry, and the S1-h and S1-i supersede marks.
  - `role-matrix.md`:
    - the permission list;
    - Scholars access;
    - result-review writer;
    - mentor reads;
    - the P1 activity paragraph, dropping "a reviewer or QC".
  - CHANGELOG.
  - A release-note draft line with the hand-applied migration SQL. Do not apply it.

## Risks
- **Migration:** a data change on production, migrate-first by hand. The owner must say yes before it is applied. Never apply it from this sprint.
- **T3 merge:**
  - T3's Permissions tab (`t3-person-page`) lists keys. Once T3 and S1 both merge, the new switch must appear there.
  - The builder notes in the CHANGELOG how T3 renders keys, so the merge author knows whether anything is needed.
  - Do not edit T3's branch.
- **Results work moves:** semester results on the 53 awarded cases now fall to the 2 admins, the 2 people in both groups, and the 2 org admins. Put it in the release note.
- **Mentors now read documents, money and family data** for their own students. This is a deliberate PII widening by the owner. Record it in `role-matrix.md`, with the scope and the end condition.
- **Size:** if the work runs long, split it:
  1. S1a: the key, the relabel, the migration, and reviewers and QC off.
  2. S1b: mentors on.
  Commit each separately.
- **Bundle headroom** is about 0.7 kB. Never raise a budget.

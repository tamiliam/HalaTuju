# Sprint S1 — Scholars is for admins only (brief, 2026-11-09)

Executor: Opus agent. Architect: main session.
Branch: `s1-scholars-access`, cut from `p1-activity-box` (824baf62). P1 edits `scholars.py` (the activity view) and `role-matrix.md`, so building on top of it avoids a collision. This sprint is independent of:
- T1 (no `is_review_target` / `may_assign_to`);
- G6/A2.3 (no `services/assignment.py`);
- T3 (no person-page files).

## Goal (owner, 2026-11-09)
- **Reviewers have no access to Scholars.** A reviewer's work is in Applications.
- **QC has no role in Scholars either.** QC keeps Applications.
- **Semester results are reviewed by admin and org admin.**
- **Mentors have no access to Applications.** This is already true for a mentor login; pin it with a test.
- **Mentors see the scholars assigned to them on the Scholars page, with the full file**, just as reviewers see the applications assigned to them. This reverses the S7c "never" list for those students (owner, 2026-11-09).
- **Access comes from permissions, not from which table a person is in.** "We do not have a concept of permanent reviewers. They are team members. They get their power from permissions." (owner, 2026-11-09)

Enforce all of this in the API first; the web follows.

## Facts (from a read-only analysis; confirm before relying on them)
- **One API fence.** `_ScholarsBase._scholars_admin` (`scholarship/views_admin/scholars.py:40-48`) calls `b40_scope`. `_file_for` (54-65) narrows `'assigned'` to `assigned_to == admin` (line 63).
  - Behind the fence: list, file, results, money, contract, result-review POST and activity (`scholars.py`).
  - Also behind it: letters (`letters.py:42`), growth (`development.py:297`), surveys (`surveys.py:199`) and the mentoring tab (`mentoring.py:45`). Find every user of the fence; don't trust this list.
- **`b40_scope` (`views_admin/base.py:31-55`) is the Applications rule. Do not change it.** It returns:
  - `'all'` for `see_all` or `qc`;
  - `'assigned'` for `review`;
  - `'none'` otherwise.
- **`qc` implies `see_all`.** See `courses/staff_permissions.py:56`, `IMPLIES = {'qc': ('see_all',)}`, and the qc preset `('see_all','qc')` at line 77. So "holds `see_all`" alone still admits QC. That is the main design point (S1-b).
- **Presets** (`staff_permissions.py:75-79`):
  - reviewer `('review',)`;
  - qc `('see_all','qc')`;
  - admin `('see_all','spending','payments_prepare')`;
  - finance `('payments_approve',)`;
  - the lead tier (org_admin, super) holds everything.
- **Result-review writes** today go through `_can_review_app` (`base.py:~284`): super; then the org fence; then `qc` org-wide; else the assignee only. A plain admin with `see_all` can therefore only write on cases assigned to them.
- **Web:**
  - The `scholars` nav row is at `lib/navigation.ts:245-247`: roles `[super, org_admin, admin, qc, reviewer, source_partner]`, perms `['see_all','review']`. Its comment at 238-243 says "same as Applications, on purpose".
  - Pages gate with `canAccess('/admin/scholars', …)`.
  - "Open scholar file" in Applications is in `PostAwardPanels.tsx:111-116` (shown when `app.has_file`).
- **Access matrix:** `test_team_tables_matrix.py`. Moved cells go in `EXPECTED_CHANGES`; the fixture is never regenerated. The mixed fixture has a `reviewer_mentor` shape.
- **Live counts** (production, read-only, counts only, 2026-11-09):
  - 25 active reviewers on the preset lose Scholars. They hold 53 awarded cases between them.
  - 2 active reviewers hold `see_all` as explicit keys, and so keep Scholars by key (S1-e).
  - No active login holds `qc` today.
  - 2 admins (explicit `see_all`), 2 org admins and 1 super keep it.
  - Mentors: 2 mentor logins and 1 org admin are linked to a mentor record.

## Settled decisions
| # | Decision |
|---|---|
| S1-a | **Scholars**, meaning the list and every per-scholar endpoint and tab behind the fence, opens for super and for anyone holding `see_all` in their own right. `review` alone → 403. `qc` alone → 403. Applications and `b40_scope` are unchanged. |
| S1-b | **"In their own right"** means the key comes from the person's preset or saved keys, not from the `qc → see_all` implication. Do not invent a role-label gate (`test_role_is_display_only.py`). Prefer reading the unimplied key set if `resolve` can expose one cheaply. Otherwise use `see_all` and not "`qc` without a direct `see_all`". Name the helper `scholars_scope(admin)` beside `b40_scope` in `base.py`. If neither way is clean, stop and report: the fallback is a new key (`scholars`), which would need a data migration for the 6 rows with saved keys, and that needs the owner. |
| S1-c | **Semester-result review** (the result-review POST and any other result accept/query write) is open to everyone S1-a admits, across their organisation: admin, org admin and super. It is no longer limited to the assignee. `qc` no longer writes here. The org fence stays. |
| S1-d | **Letters and activity notes** on a scholar file: anyone S1-a admits (any admin or org admin in the organisation) may write them (owner, 2026-11-09). A closed file stays read-only as today. |
| S1-e | **People in several tables:** the union is taken by keys (owner, 2026-11-09: team members "get their power from permissions"). Anyone who holds `see_all` is an admin for Scholars, whatever their stored role label says. The 2 live people whose label is still `reviewer` but who hold `see_all` (plus `review`; one also holds `spending`) are admins in the owner's words, and keep Scholars, result review and letters like any admin. The web gate must admit them by key: the `scholars` row's `roles` list drops `reviewer`, so check that `admitsRow` lets a team member with saved keys through on `perms` regardless of the label, and add a test for exactly this shape (label `reviewer`, keys `review` + `see_all`). A mentoring assignment opens Scholars only for that mentor's own students (S1-h), and never opens Applications. |
| S1-h | **Mentors on Scholars** (owner, 2026-11-09, "Scholars, full file"). Applies to a mentor login, and to staff who mentor (`mentor_desk.mentor_of`).<br>• **Scope:** the Scholars list holds only their CURRENT students, as decided by `mentor_desk.current_assignments`: an open assignment, in their own organisation, in maintenance, and never their own application. Every per-scholar door gives a single 404 for anything else. That includes ended mentoring, another mentor's student, another organisation's file and an unknown id. Access ends when the mentoring ends.<br>• **What they see:** every tab an admin sees: results, money, contract, documents, letters, activity, growth, surveys and mentoring. One exception, the architect's default: activity notes marked **Staff only** stay hidden from a mentor, because a mentor is not staff. The mentoring tab shows as staff see it.<br>• **Read-only:** no result review (S1-c), no letters and no activity notes. A mentor keeps logging meetings on **My students**, which stays as it is (meeting log, modules, concern flag).<br>• **Enforced on the server:** add `GET` to `mentor_methods` on exactly the Scholars read views. Each must check the mentor scope before anything else, and `test_mentor_denied_everywhere.py` gets the new list.<br>• Supersedes S7c point (2), the "never" list, and point (7), "My students and Profile only". Mark both "Superseded 2026-11-09 (S1)". |
| S1-f | **Mentors:** no code change. A test pins that a mentor login gets 403 on the Applications list and detail, through both the API and the web `canAccess`. |
| S1-g | **Supersede** `docs/decisions.md` 2026-10-29 "The Scholars list and file read by the Applications rule", and the Scholars cell of T5c ("Applications and Scholars keep their rules"). Mark both "Superseded 2026-11-09 (S1)". |

## Build
- **API:**
  - Add `scholars_scope(admin)`, returning `'all'` or `'none'`, and use it in `_scholars_admin`.
  - Drop the `'assigned'` branch of `_file_for`.
  - Give the result-review write the S1-c rule. Check whether `_can_review_app` is shared with Applications writes. If it is, do not change it for Applications: add a scholar-file write check instead.
  - Make sure no other door lets a reviewer or QC reach scholar data, for example document downloads keyed by scholar, or payments reads of a scholar file. Exception: the Payments page's funding-summary allowlist stays as it is.
  - **Mentor scope (S1-h):**
    - `scholars_scope(admin)` returns `'all'`, `'mentor'` or `'none'`. `'mentor'` narrows the list and `_file_for` to `current_assignments`.
    - A person who holds both `see_all` and a mentor record gets `'all'`.
    - Every write path refuses `'mentor'`. That covers result review, letters, activity POST, contract, money and documents.
    - Filter "Staff only" activity rows, and their counts, out for `'mentor'` on the server.
    - Check the P1 actor rule: a mentor reading the log must not get any email that the P1 rules withhold.
    - Document reads (signed links): if the scholar file opens documents through another view, that view needs the same mentor scope.
  - No migration.
- **Web:**
  - On the `scholars` row, set roles to `[super, org_admin, admin, source_partner, mentor]` and perms to `['see_all']`.
    - A mentor login gets the row through its role (mentors have no team keys).
    - A staff member who mentors but has no `see_all` gets it through their mentor record, the same signal the nav already uses for My students.
    - The mentor's file view hides every write control: composer, letters, result review and contract actions. The server refuses them anyway.
    - Mentor nav becomes My students, Scholars and Profile.
  - Keep `source_partner`: it renders `components/source/*` (role-matrix ~531). Confirm what it shows.
  - Make sure the web `canAccess` matches S1-b for a QC-only person, whose resolved permissions include `see_all`. If the client cannot tell, gate on `qc` absence the same way as the API, with no role-label read.
  - Gate "Open scholar file" (`PostAwardPanels.tsx`) on `canAccess('/admin/scholars', …)`.
  - Find any other web link into `/admin/scholars` that a reviewer or QC can see.
- **Comments:** fix the ones that say "same as Applications": `scholars.py:6-12`, `navigation.ts:238-243`, `letters.py:7`, `test_scholars_endpoints.py:5-6`.

## Done when
- **API tests:**
  - A reviewer gets 403 on the Scholars list, a file, every tab (results, money, contract, activity, letters, growth, surveys, mentoring) and the result-review POST.
  - A QC-only person gets 403 on the same.
  - A reviewer holding `see_all` gets 200.
  - Admin, org admin and super are unchanged for reads.
  - An admin who is not the assignee can accept or query a semester result in their organisation, and gets 404 cross-organisation.
  - A mentor gets 403 on the Applications list and detail.
  - Mentor on Scholars:
    - The list holds only their current students.
    - Every tab reads 200 for a current student.
    - 404 for an ended assignment, another mentor's student, another organisation's file, their own application and an unknown id.
    - Every write is refused.
    - "Staff only" activity rows and their counts are absent.
    - A staff member who mentors and holds `see_all` keeps the full organisation.
  - The matrix diff equals `EXPECTED_CHANGES` exactly: reviewer, qc, reviewer_mentor and mentor Scholars cells, and nothing else.
- **Web tests:**
  - A reviewer and a QC have no Scholars row and no "Open scholar file" link.
  - An admin and a reviewer holding `see_all` keep both.
  - A source_partner keeps its row.
- **Gates:** run once through `test_queue.py`:
  - API pytest, `check`, `makemigrations --check`;
  - `npm run gates`, bundle-budget, mobile-check.
  - mobile-check needs `.env.local`: copy it from main and delete it afterwards.
- **Docs:**
  - `decisions.md`: the S1 entry plus the S1-g supersede marks.
  - `role-matrix.md`:
    - the Scholars access section;
    - in the P1 activity paragraph, drop "a reviewer or QC", since only admins read the file now;
    - the result-review writer.
  - CHANGELOG.

## Risks
- **Work in flight on the 53 awarded cases.** Semester results that reviewers would have reviewed now fall to the 2 admins and 2 org admins. The release note must say so. Before release, count the results awaiting review (architect, read-only).
- **Live reviewers lose the file mid-work.** Tell them in the release note.
- **S1-b subtlety:** a gate on `see_all` alone silently keeps QC in. The tests must include a QC-only person.
- **Mentors now read documents, money and family data** for their own students. This is a deliberate PII widening by the owner. Record it in `role-matrix.md`, with the scope (current students only) and the end condition (access ends with the mentoring). Every new mentor door gets the 404-for-all test.
- **Size:** this sprint is larger than the reviewer change alone. If it runs long, split it: S1a (reviewers and QC off), then S1b (mentors on). Commit each separately.
- **Bundle headroom** is about 0.7 kB. This sprint should shrink the web, not grow it. Never raise a budget.

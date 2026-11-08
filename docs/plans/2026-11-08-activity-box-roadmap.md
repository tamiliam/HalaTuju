# Activity box and Team pages (roadmap, 2026-11-08)

Status: **DRAFT — awaiting the owner's decisions D1–D9 and approval.** Branch `activity-box` (from main
`0fec1c69`), docs only. Nothing is built, pushed or deployed until the owner approves; the audit agent sets the pace.

## Why
The owner, 2026-11-08, comparing Podio's activity/comment panel with ours: *"I like how the activity/comment box is
done in podio. Can ours copy its best features?"* — then *"Write this up as a plan. I have a few other suggestions for
improvement. I want to bundle them as well."*

## What exists (measured 2026-11-08)
- **Web:** `halatuju-web/src/components/admin/ScholarActivity.tsx` (133 lines), used twice on
  `app/admin/scholars/[id]/page.tsx`: the Overview side panel (`compact`, newest 6) and the Activity tab (all).
  Composer on top: Note / Call / Meeting pills, a 3-row box, the Staff only toggle, Save. Each row: a coloured dot,
  the text, then `kind · actor email · date and time` and a Staff only chip. Wording from `lib/scholarActivity.ts`.
- **API:** `GET/POST admin/scholarship/scholars/<pk>/activity/` (`views_admin/scholars.py:214`), payload
  `scholars.activity_dict` — `actor_email` only, no name or photo. Writers in `activity.py`: `log_event` (system,
  inside the caller's transaction) and `add_entry` (manual).
- **Model:** `StudentActivity` (`models/activity.py`, table `student_activity`): kind, event, body, meta, actor_email,
  internal, created_at. 15 system events, all about staff or system actions (status, payments, results, letters,
  mentoring, closure). **Nothing the scholar changes on their own file is logged.**
- **Names and photos exist elsewhere:** `PartnerAdmin.name` (by email); `StaffProfile.photo_path` with
  `staff_photo.signed_url` (~1 hour signed link).
- No relative-time helper in `lib/formatDate.ts`; no @mentions anywhere.

## Podio compared with ours

| Podio | Ours | Decision |
|---|---|---|
| Name + photo per entry; a group icon for automatic entries | Email address, or "System" | **Copy** (P1) |
| "9 days ago", exact date on hover | Full date and time only | **Copy** (P1) |
| Activity / Comments tabs: what people wrote apart from what the system did | One mixed list | **Copy as a filter**: All · Notes · System (P1) |
| Comment box is one line until you click it | 3-row box, pills and toggle always open | **Copy** (P1) |
| The person's own edits appear (e.g. a scholar updating details) | Not logged | **Copy, with care** (P2) |
| Field values shown in full (a whole card number in the owner's screenshot) | — | **Do not copy.** Log "Bank details changed", at most the last 4 digits. No PII in logs. |
| A lightning icon on every row | — | Do not copy: noise. |
| Pale grey text | — | Do not copy: fails our contrast checks. |
| Tasks inside the stream | No tasks on a scholar file | Not a copy — a new feature. Only if the owner adds it below. |

Also found: the side panel shows 6 entries with no way to the full list — add **"See all (n)"** to the Activity tab.

## Owner's further suggestions — Team tables, person pages, the Assign picker (2026-11-08)
The owner, with screenshots of Team → Admins, a reviewer's page and the applications list's Assign dropdown:
1. *"Team member tables and profiles to be similar. Each must have Revoke and Delete. The delete however will be
   greyed out if there is work on record. When hovered … it may say there is work on record. For org admins, the
   delete button should be visible only to super admin."*
2. *"Suresh has reviewer and QC permissions, but his entry is missing from reviewer table. It should be."*
3. *"REMOVE Reviewer/Admin/Mentor from below the name. If they are in Reviewers table, they are reviewer."*
4. *"Add Last Seen after Joined Date."*
5. *"Admin doesn't have profile tab, whereas mentors do not have permissions tab."*
6. *"Ve. Elanjelian and Poongulali are not Reviewers, but they show up in the Assignment drop down. Only those
   assigned to the gift should show up and they also must be reviewers first, and be included in the Reviewer table."*

### What exists (measured 2026-11-08, code only)
- **Tables** (`app/admin/organisation/reviewers/page.tsx`; Admins via `components/admin/StaffAdmin.tsx`; Mentors via
  `components/mentors/MentorsAdmin.tsx`):
  - Admins: Revoke; Delete only when the server says `deletable`, otherwise the grey words "Has work on record —
    revoke instead" (counts on hover); Remove from Admins.
  - Reviewers: Revoke (not for the org admin) and Remove from Reviewers. **Never Delete** — the server's
    `_DELETABLE_ROLES` is `admin`, `finance`, `org_admin` only (`courses/views_admin.py:599`; owner 2026-09-09:
    never a reviewer).
  - Mentors: Revoke / Restore / Stop mentoring. No Delete.
  - Delete of an org admin: the server already lets only a super do it (`_staff_target_manageable` — an org admin
    may not act on a fellow org admin), so ruling 1's last part is already true on the server; the screen needs only
    to match it.
- **Person pages — three different pages for one kind of thing:**
  - Reviewer (`reviewers/[id]`): Profile + Permissions tabs; header "Reviewer · Active · Joined …" (the role label
    `admin.reviewers.role.<role>`), Pause new cases, Covers (gifts), case counts.
  - Admin (`reviewers/admins/[id]`, 105 lines): **Permissions tab only**, no Profile.
  - Mentor (`reviewers/mentors/[id]` → `MentorDetail`): **no Permissions tab**.
  - None shows Last seen (the tables do).
- **Suresh (item 2):** an organisation admin. The lead tier holds `qc` (`staff_permissions.LEAD_TIER`), but by the
  owner's 2026-10-19 ruling that does NOT seat the lead in Reviewers; an org admin sits there only after
  Team → Reviewers → **Add** stores `review` for them (`staff_permissions.lead_reviews`, Team tables T2). His Admins
  row shows no "Reviewer" chip, so he has not been added. (His live row was not read: a named production read was
  not allowed this session.)
- **The Assign dropdown (item 6)** — applications list `app/admin/scholarship/page.tsx:436`, fed by
  `AdminAssignableAdminsView` (`views_admin/lifecycle.py:299`), each row's `assignable` = `may_assign_to`
  (`services/assignment.py:57`):
  - **Caller is a super:** anyone `is_review_target` — `review`, OR role admin / qc / org_admin holding `see_all`
    (the "R1 super override"). That is why an org admin and an admin who are not Reviewers are offered.
  - Caller is an org admin: only own-organisation team members holding `review` (correct already).
  - **The gift is ignored in this dropdown.** ✓ / ⚠ is the CALL LANGUAGE match, not the gift. The applicant page's
    picker (`AssignAndWitness.tsx`) greys "Does not cover <gift>", and the server refuses `gift_mismatch` on save
    (TD-501), so a wrong pick fails only after it is made.
  - The same name listed twice (one ✓, one ⚠) is most likely two accounts with one name (e.g. a super login and an
    org admin login) — to confirm during the build.

### Decisions needed (Team)
- **D5. Suresh.** Recommend: **no rule change — use Team → Reviewers → Add on his row** (works today, no code). Making
  every org admin a Reviewer by their lead-tier `qc` would also make every org admin assignable, which item 6 asks
  to narrow.
- **D6. Delete for reviewers and mentors** (reverses 2026-09-09 "never a reviewer"). Recommend yes, under the same
  test as admins: no work on record (`staff_footprint`: never assigned a case, never reviewed, never mentored).
  Otherwise Delete shows greyed with the reason on hover/tap.
- **D7. Retire the R1 super override.** Recommend: a case may be assigned only to someone in the Reviewers table
  who covers the case's gift — for every caller, super included. Cases an admin holds today are kept and still
  shown as the current assignee; only NEW assignments follow the rule. (Count of such open cases taken before build.)
- **D8. A mentor's Permissions tab.** A pure mentor holds no keys (My students and Profile only). Recommend: the tab
  shows that, read-only, with the same Add-to-table path the Team page offers.
- **D9. The header under the name.** Recommend: Status · Joined · Last seen · Pause (reviewers), with the person's
  tables shown as the existing "Also in"-style chips, not as a role word.

### T1 — The Assign picker offers only Reviewers who cover the gift · complexity: high (who gets cases: Opus build + Opus review, phone check)
- **Goal:** item 6 and D7.
- **API:** `may_assign_to` / `is_review_target`: target must be `staff_tables.in_reviewers` and, when the case is
  known, cover its gift (`staff_gift`); the R1 override goes; `assign_reviewer` refuses the same
  (`not_a_reviewer`). The assignable list serves `gifts` already — the list page uses it.
- **Web:** applications list dropdown hides anyone not assignable for THAT case's gift (the current assignee is
  still shown); ✓ / ⚠ keep meaning the language, with a legend line.
- **Files (≈10).** **Done when:** as a super, an org admin who is not in Reviewers and an admin are absent from the
  list and refused by the server; a reviewer of another gift is absent for this case; a held case still shows
  its assignee.

### T2 — Revoke and Delete on every table and person page · complexity: medium-high (deleting people)
- **Goal:** item 1 and D6.
- **API:** `_DELETABLE_ROLES` gains reviewer and qc; a mentor's delete under the same footprint test (a mentor has
  its own door — `MentorsAdmin` today has none); the payload carries `deletable` and `work` on every table.
- **Web:** one action cell for all three tables and the person pages: Revoke/Restore, then Delete — enabled when
  `deletable`, otherwise greyed with "Has work on record" and the counts on hover (and on tap on a phone); hidden
  on an org admin's row unless the viewer is a super.
- **Files (≈14).** **Done when:** a rendered test per table shows Revoke + Delete; a person with work shows Delete
  greyed with the reason; an org admin viewer sees no Delete on a fellow org admin; the server refuses as before.

### T3 — One person page for every team member · complexity: medium (Stitch first)
- **Goal:** items 3, 4, 5 and D8, D9.
- **Web:** the three pages become one layout: header (name, Status · Joined · Last seen, table chips, Pause for a
  reviewer), the T2 actions, then **Profile** and **Permissions** tabs for everyone; reviewer-only parts (Covers,
  case counts) and mentor-only parts (scholars) appear by table. The three routes stay (links keep working) and
  render the one component.
- **API:** the admin and mentor detail payloads gain the profile fields and `last_seen` where missing.
- **Files (≈18).** **Done when:** a test per kind of person shows both tabs, Last seen after Joined, and no role
  word under the name; mobile-check passes.

## Decisions needed from the owner
- **D1. Which scholar edits are logged (P2)?** Recommend: bank details, phone, email, home address, guardian contact
  — the fields an officer must know changed. Not every profile field.
- **D2. How much of a value is shown?** Recommend: bank account — last 4 digits only; phone/email/address — "changed"
  with no value (the current value is on the file already).
- **D3. Newest first stays?** Podio lists oldest first with the box at the bottom. Recommend we keep newest first with
  the box on top — officers want the latest; the side panel shows only the newest few.
- **D4. Can a scholar's edit be Staff only?** Recommend: these rows are always staff-only (`internal`), as a status
  change is today, until a student view of the log exists.

## Sprints
Each sprint: own commit(s) on its branch, targeted tests while building, full API + web gates once, a fresh reviewer
on the diff, CHANGELOG + decisions.md. Nothing pushed without the owner.

### P1 — Who, when, and a lighter box · complexity: medium
- **Goal:** each entry shows a name and photo and "9 days ago"; a filter separates notes from system rows; the box is
  one line until used; the side panel links to the full list.
- **Stitch first** (house rule for a layout change): one screen of the panel and one of the tab, phone and desktop,
  for the owner's approval before coding.
- **API:** `activity_dict` gains `actor` = `{name, photo_url, role}` — looked up once per distinct email per request
  (staff and mentors by their `PartnerAdmin` login row, the scholar as "the scholar"; an unknown email shows as
  written), photo signed once per person, never
  per row. No migration.
- **Web:** `ScholarActivity.tsx` — avatar (photo, or initials; a system icon for system rows), name in bold, text
  under it; relative time with the exact time as `title` and screen-reader text; All · Notes · System filter (the
  Activity tab only; the side panel stays mixed); collapsed composer that opens on focus and closes on Save or Esc
  when empty; "See all (n)" in compact mode. New `relativeTime` in `lib/formatDate.ts` (en/ms/ta).
- **Files (≈12):** `scholars.py`, its test; `ScholarActivity.tsx`, `lib/scholarActivity.ts`, `lib/formatDate.ts`,
  `admin-api.ts` (type), en/ms/ta.json, tests; CHANGELOG.
- **Done when:** a test asserts name + photo for a staff row, initials when no photo, the system icon for a system
  row, and no email shown; the filter hides and shows the right rows; mobile-check passes on the scholar file; the
  read makes one photo signing per person, not per row.

### P2 — The scholar's own edits appear · complexity: high (personal data: Opus build + Opus review, phone check)
- **Goal:** when a scholar changes the fields ruled in D1, a staff-only system row says so, per D2.
- **API:** new events (e.g. `details_changed` with `meta.fields` = the field names, and `meta.last4` for a bank
  account only), written by `log_event` inside the save that changes them; a guard test that no event's meta carries
  a full account number, phone, email or address.
- **Web:** `activityText` sentences for the new event; en/ms/ta.
- **Migration:** none (the event list is code; `meta` is JSON).
- **Files (≈12).** **Phone check before go-live.**
- **Done when:** a scholar changing their bank account produces one row "Bank details changed (…1234)" visible to
  staff only; changing a field outside D1 produces none; the PII guard test passes.

## Order and rationale
1. **T1** — live harm: today the wrong people are offered cases and the gift is checked only after the pick.
2. **T2** — a rule change about deleting people; small and separate so it is reviewed on its own.
3. **T3** — the person page, built on T2's action cell. Stitch first.
4. **P1** — the Activity box display; shares the avatar and name style with T3, so it follows it.
5. **P2** — the scholar's own edits; personal data, its own sprint and phone check.

Five sprints rather than fewer: T1, T2 and P2 each change a rule (who gets cases, who may be deleted, what is logged
about a scholar), and none should be buried in layout work. T3 and P1 could merge if the owner wants fewer handoffs.

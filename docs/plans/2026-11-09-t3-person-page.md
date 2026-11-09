# Sprint T3 — One person page for every team member (brief, 2026-11-09)

Executor: Opus agent. Architect: main session. Roadmap: `docs/plans/2026-11-08-activity-box-roadmap.md` (T3,
D8, D9). Mockup (owner-approved 2026-11-09, private): https://claude.ai/artifact/MyoodecZzV61mScKfopuCw
Branch `t3-person-page`, cut from `t2-revoke-delete` (fdc27aa2): T3 reuses T2's `StaffPersonActions`.

## Goal
The owner's items 3, 4 and 5, and D8 / D9:
- No role word under the name ("If they are in Reviewers table, they are reviewer").
- Last seen right after Joined.
- Every person has a **Profile** tab and a **Permissions** tab.

## Facts to verify first (the architect read these; confirm before relying on them)
- Three pages today:
  - Reviewer `app/admin/organisation/reviewers/[id]/page.tsx` (410 lines), fed by `AdminReviewerDetailView`
    (`scholarship/views_admin/reviewers.py:340`). Its payload already carries `last_seen_at` (via `_reviewer_dict`),
    the credentials, phone (`assigner_sees_phone`), languages, figures, outcomes, reopens, `pausable`, footprint.
  - Admin `reviewers/admins/[id]/page.tsx` (116 lines), fed by `getStaffPermissions` only; Permissions tab only;
    role word from `teamLabelRole` at line ~79.
  - Mentor `reviewers/mentors/[id]/page.tsx` (30 lines) renders `MentorDetail` in `components/mentors/MentorsAdmin.tsx`,
    fed by the mentor detail view (`scholarship/views_admin/mentors.py:317`); no Permissions tab.
- `PartnerAdmin.first_seen_at` / `last_seen_at` exist (`courses/models_staff.py:195-200`).
- `ReviewerProfile` is the "common profile" (common profile S1–S4). Find out whether an admin or finance person
  without `review` has one, and what fields they can fill in. Do not create rows on a GET for people who have none
  (show "Not given"), unless a GET already does that today for that kind of person.
- Which tables a person is in: `staff_tables` (`in_reviewers` etc.); the tables already serve "Also in" chips —
  reuse that source, do not invent a second one.

## Settled decisions (owner)
| # | Decision |
|---|---|
| D9 | Under the name: table chips (the same chips/labels the tables use for "Also in"), then Status pill · Joined · Last seen. No role word. Pause new cases only for a reviewer (`pausable`). |
| D8 | A pure mentor's Permissions tab is read-only: they see My students and Profile only; offers the same Add-to-table path the Team page offers (only to a viewer who may add). |
| M1 | Last seen shows relative ("2 days ago"); exact date and time on hover / focus (`title` is fine). Never signed in → the existing "Invited, no sign-in recorded yet" wording. |
| M2 | An org admin's Permissions tab shows their keys as locked switches with one line saying they cannot be changed here (reuse the existing "You cannot change your own permissions or an organisation admin's." string if it fits). |
| M3 | Profile fields a person has not filled in show "Not given", not hidden. The home address is never shown (as today). |
| M4 | The reviewer's Covers and figures stay in the header card, above the tabs. |
| M5 | Revoke / Restore / Delete: T2's `StaffPersonActions` unchanged in behaviour, same place on every page. |
| M6 | A person in several tables sees every part that applies (reviewer parts and mentor parts together). |

## Build
- **One component** (e.g. `components/admin/person/TeamPersonPage.tsx` plus small parts) that takes a normalised
  person view. The three routes stay (links keep working) and each renders it. Keep each file under the repo's
  size rules; split by part (header, profile, permissions, reviewer parts, mentor parts).
- **API:** only what is missing. The admin detail gains the profile fields (same PII rules as the reviewer detail:
  phone only under `assigner_sees_phone`, never the address) and `last_seen_at`, and the tables the person is in.
  The mentor detail gains `last_seen_at` if absent and the tables. No new endpoint unless one route truly has no
  detail view; prefer extending existing payloads. Keep within existing query budgets (assert them).
- **i18n:** en, ms, ta for every new string; reuse keys; delete keys that become unused (role word under name).
- **Mobile:** works at 360 px; tap targets as the repo's mobile-check requires.

## Done when
- A rendered test per kind of person (reviewer, admin, finance, mentor, org admin, someone in two tables) shows
  both tabs, Last seen after Joined, the table chips, and no role word under the name.
- The mentor's Permissions tab is read-only with the Add path; the org admin's shows locked switches.
- API tests: admin and mentor detail payloads carry the new fields; PII rules hold (no address; phone gated);
  org fence still 404s cross-org.
- Targeted tests while building; then the full gates once: API pytest + `check` + `makemigrations --check`;
  `npm run gates`; mobile-check. Heavy runs through
  `python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <cmd>`.
- CHANGELOG and `docs/decisions.md` updated (D8, D9, M1–M6).

## Risks
- PII widening on the admin detail: record it in `docs/scholarship/role-matrix.md` as the reviewer detail did.
- Bundle headroom is ~0.6 kB after T2: lazy-load the new tab bodies (as `LazyPermissionEditor` does) rather than
  raising the budget. Never change a budget without the owner.
- Don't change `is_review_target` / `may_assign_to` (T1 owns them).

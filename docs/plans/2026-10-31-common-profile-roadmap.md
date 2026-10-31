# Common profile page + My activity — roadmap (2026-10-31)

**Status:** APPROVED 2026-10-31 (roadmap + mock-ups https://claude.ai/artifact/2w7vJhKNhjpkNuy8oa5582).
**S1 + S2 LIVE 2026-10-31** (main `3ad1f387`, migration scholarship 0193; retro
`docs/retrospectives/retrospective-2026-10-31-common-profile-s1-s2.md`). Next: S3.

## Why

Every admin-platform user (super, org_admin, admin, finance, reviewer, qc, partner, source_partner) has
a Profile page, but it is two separate screens (staff `app/admin/profile/page.tsx`, source
`components/source/SourceProfile.tsx`) with extras switched on by **role**, while real powers are
switched on by **permissions** (`staff_permissions.CATALOGUE`). Most people see only name + email.

Owner rulings (2026-10-31):
- One profile page built from **one list of cards**, each card switched on per person (borrowing from
  Podio: photo, job title, About, contact, activity).
- The reviewer cards follow the **`review` permission**, not the Reviewer role.
- **My activity:** a new append-only activity list that every action writes to, **back-filled** from the
  records that already exist (option 1, not "read the 40 stamps live").
- The Source profile is rebuilt on the same base.

## The card list

| Card | Holds | Switched on by |
|---|---|---|
| You | photo, name, job title, About, sign-in email (read only) | everyone |
| Contact | phone; "show my phone to my team" toggle; "share with students I interview" (review power only) | everyone |
| Your access | role, organisation, programmes, what you can do in plain words (read only) | everyone |
| Sign-in | Google or password, change password (password users only), last signed in | everyone |
| My activity | own actions, newest first, filters | everyone (own rows only) |
| Qualifications and languages | today's reviewer credentials | `review` permission |
| Address | street, postcode, city, state (private) | `review` permission |
| Taking part | pause / resume new cases | `review` permission |
| Organisation | name, contact person, email for updates, phone, website | role `partner` or `source_partner` |

Lead decisions (owner may overturn):
- **The first-sign-in hold stays Reviewer-role only.** Anyone else given `review` sees a reminder banner,
  not a block (an org admin must never be locked out of the console by a missing graduation year).
- **Photos are seen by staff only** (header, Team page, own profile) — never by students or sponsors.
- **Team page shows a phone only when its owner switched "show to my team" on.** This revises the old
  rule "reviewer phone/address is exposed by no other serializer" for phone only; address stays private.
- A source's phone is seen by the inviting organisation (Sources page), as the organisation contact is today.
- **Activity rows store ids, never copied text.** A student's name is looked up when the list is read,
  and shown only if the viewer may still see that student now; otherwise "a student". A purged student
  leaves "a student (removed)".

## Conflicts / doors (sprint-start 3b)

| # | Door or conflict | Handled in |
|---|---|---|
| D1 | `ReviewerProfileView` gate is `has_role('reviewer')`; web `isReviewer = role === 'reviewer'` | S1: both move to the `review` permission; super keeps passing |
| D2 | Onboarding hold (`reviewer_onboarding.reviewer_profile_complete`, `adminLanding`, `navigation.ts:632`) is role-based | S1: unchanged on purpose (hold = Reviewer role); test pins it |
| D3 | Source users are DENY BY DEFAULT (`source_partner_methods`) | S1/S2/S4: every new `admin/me/...` endpoint opts in explicitly; `noStaffCalls.test.tsx` extended to the shared shell |
| D4 | Losing `review` (permission edit, `staff_permissions_admin`) | S1: the cards hide; data is kept, not deleted |
| D5 | Photo upload = file into storage | S2: through the API only, ≤2 MB, jpg/png/webp checked by content; private bucket, signed URLs; key not under any org/app prefix that `resolve_org_for_path` reads as a tenant file |
| D6 | Staff deleted / revoked | S2/S4: photo removed with the row; activity rows go with the person (own-only list) |
| D7 | Student purge (PDPA) | S4: rows hold ids; reader renders "a student (removed)" |
| D8 | An unassigned reviewer reading old rows | S4: name shown only if still visible to them now |
| D9 | Activity write must never break the action | S4: best-effort `record()`; failure logged, action still succeeds; test proves it |
| D10 | Bundle budget (TD-427: 0.25 kB headroom) | every web sprint: cards lazy-loaded; measured on the merged tree before push |

## Sprints

### S1 — One page, one card list (no new data) — medium, ~25 files
**Status:** BUILT 2026-10-31 on branch `profiles` (not pushed; lead verification pending). `admin/me/` landed in
`apps/scholarship/views_admin/me.py`, not `apps/courses` (the `courses -> scholarship` import budget is full).
- Backend: `GET admin/me/` (opted in for `source_partner`): name, email, role + label, organisation,
  source name, programme scope, permissions as plain-word keys, `first_seen_at`, `last_seen_at`.
  `ReviewerProfileView` gate → `review` permission (D1).
- Web: `lib/profileCards.ts` — the registry (id, order, `show({role, permissions, isSuper})`), with a
  drift test like `navigation.test.ts`. Profile page = one shell rendering the cards; one Save that saves
  every changed card. Cards: You (name/email only for now), Your access, Sign-in (method from the session;
  change password via Supabase for password users), Organisation (partner: existing fields; source:
  existing `admin/source/profile/`), the four reviewer cards (moved, unchanged).
- `SourceProfile.tsx` retired; a source gets the same shell (D3).
- Tests: every role renders exactly the matrix's cards; a source's page calls no staff endpoint;
  an admin with `review` gets the reviewer cards; a reviewer is still held on first sign-in.

### S2 — Photo, job title, About, phone for everyone — medium, ~25 files
**Status:** BUILT 2026-10-31 on branch `profiles` (not pushed). Migration `scholarship/0193_staff_profile_card`
(ADD COLUMNs only, `db_default`); the model kept its name with `StaffProfile` as an alias, not renamed. Owner
addition: one optional fourth language (name + fluency) on the Qualifications and languages card.
- Migration (additive): the personal-profile row (today `reviewer_profiles`, one per person) gains
  `job_title`, `about`, `photo_path`, `share_phone_with_team`. The model is renamed in Python to
  `StaffProfile` with the same table (no data moves); `ReviewerProfile` stays as an alias.
- `PATCH admin/me/` (name, job title, About, phone, show-to-team); `POST/DELETE admin/me/photo/` (D5).
- Header avatar shows the photo; Team page shows photo, and phone when shared.
- **First deploy point** (owner go): migrate first, then API, then web.

### S3 — The activity list, part 1: the list and the case actions — high, ~30 files
- Model `StaffActivity` (actor FK, organisation, `verb` from a closed list, subject type + id, small
  `meta` with no free text, `created_at`, `backfilled`). Helper `staff_activity.record(...)` (D9).
- Wired into: invitation accepted, first sign-in, profile updated, verify-and-accept, verdict, decline,
  query raised/resolved, interview submitted, QC decision, reopen, assign/unassign, close a case,
  witness a contract, permission change, invitation sent.

### S4 — The activity list, part 2: money, contracts, requests + back-fill — high, ~30 files
- Wired into: payment run created / signed (maker, checker, approver), tranche release / withhold / return,
  credit recorded / checked / confirmed, contract template create / vet / submit / deploy, countersign,
  benefactor vetting, invoice issue / send / void, payment declared / confirmed / rejected, org request
  raised / approved / declined, merchant flag opened / closed.
- `GET admin/me/activity/` (own rows, cursor paging, filters; opted in for sources; D7, D8).
- Back-fill command `backfill_staff_activity --dry-run | --apply`, idempotent, from the history tables
  (AssignmentEvent, StaffPermissionChange, StudentActivity, DecisionReopen, org requests, invitations)
  and the single stamps (verified, rejected, verdict, QC, recommended, closed, queries, results,
  interviews, payment signatures, tranches, credits, witness, contracts, sponsors, invoices, receipts,
  merchant flags, guardian changes). Name-only stamps (countersign name, vetted-by name) are skipped.
- **Adversarial review** (money + identity).

### S5 — My activity on the page + close — medium, ~20 files
- The activity card (day groups, filters "All / Students / Money / Profile and sign-in", Show older,
  "only you can see this"; back-filled rows marked as rebuilt).
- en / ms / ta text (Tamil style guide), Guide + FAQ for every role, decisions, CHANGELOG,
  ARCHITECTURE_MAP, retrospective.
- **Second deploy point** (owner go): migrate first, run the back-fill dry run, then apply, then web.

## Execution
Sequential: an Opus subagent builds each sprint in the `profiles` worktree; the lead verifies the diff
and re-runs every gate (full pytest, full jest, `next build`, bundle budget on the merged tree).
Another session shares the main checkout: explicit paths only, never `git add -A`; the migration number
is settled against `origin/main` on the day it is written.

# Invitations — five tabs that read alike (roadmap, 2026-11-08)

Status: **DRAFT — awaiting owner approval.** Branch `invitations-consistency` (from main `6c58efae`), not pushed.

## Why
The owner, on Organisation → Invitations (2026-11-08): *"There are a number of inconsistencies. Sponsor gift
assignment should be similar to reviewers. Mentor's is missing. Source org shouldn't be in the drop down for invite
once the org rep has joined. Source button is on the right, unlike others. Signed in is listed unlike others."*

## What exists (measured 2026-11-08)
Page: `halatuju-web/src/app/admin/organisation/staff/page.tsx`. Admin, Reviewer and Sponsor share the page's own
form and `components/admin/InvitationsTable.tsx`; Source (`components/sources/SourceInvite.tsx`) and Mentor
(`components/mentors/MentorInvite.tsx`) each bring their own form and table.

| # | Difference | Admin / Reviewer / Sponsor | Source / Mentor |
|---|---|---|---|
| 1 | Field labels | placeholder text only | label above each box |
| 2 | Send Invite | left, under the form | right, beside a note (Mentor's long note wraps it left) |
| 3 | Explanation | Admin above fields; Reviewer under gifts; Sponsor none | beside the button |
| 4 | Waiting table | Name · Email · Status "Waiting (date)" · Action; title-case headings; red Cancel; paged | own columns; ALL-CAPS headings; bare date ("Sent" / "Invited"); no Action heading; blue Cancel; not paged |
| 5 | Cancel wording | "Cancel invitation" | Mentor says "Revoke" (same job) |
| 6 | On a phone | scrolls sideways | rows become cards |
| 7 | Gift | Reviewer: tick list + "Every gift"; Sponsor: one-gift dropdown, shown only with 2+ gifts | Mentor: no gift at all |
| 8 | Who has joined | not listed (owner ruling 2026-09-09: this page lists the waiting only) | Source lists "Signed in" too — and it holds the ONLY Remove for a source's person |
| 9 | Source dropdown | — | every active source, joined ones included (2026-10-30: several people per source) |

Data (production, counts only, 2026-11-08): no source has more than one active person; 5 mentors; 0 open mentor
assignments. So rulings 3 and 2 below need no data repair and strand nobody.

Model facts: a sponsor invitation holds ONE gift (`Invitation.programme`); on registering, `sponsorship.signup_programme_for`
returns that one gift and one `SponsorProgrammeMembership` is made (3 call sites: `views_sponsor` ×2, the admin
accept in `views_admin/sponsors`). Reviewer gifts live in `reviewer_gifts` (`courses.staff_gift`, `[]` = every gift).
`Mentor` has no gift link; `mentoring.assign` / `assignable_mentors` do not look at gifts.

## Owner rulings (2026-11-08)
1. **Sponsor invite: several gifts or Every gift**, like a reviewer's (a true multi-gift invite, not only the look).
2. **Mentors get gifts, and a gift LIMITS who they mentor**: a mentor can be assigned only scholars in their gifts.
3. **One person per source.** A source whose person has joined leaves the Source dropdown, and the server refuses a
   second invitation for it. *Revises the 2026-10-30 S2 ruling "several people may sign in for one source".*
4. **Remove for a source's person moves to the Sources page**, on that source's row beside its Joined badge; the
   "Signed in" table leaves Invitations (the 2026-09-09 "waiting only" rule now holds on every tab).
5. Differences 1–6 are tidied to one form and one waiting table (no ruling needed; the plan below says which way).

## Open points (lead recommendations — confirm with the roadmap)
- **A. A source with a WAITING invitation** (ruling 3 names only "joined"). Recommend: the server refuses any second
  ACTIVE person (waiting or joined), so "one person" really is one; the dropdown hides joined sources and shows a
  waiting one greyed, "Invited, waiting — resend or cancel below". A switched-off person of the same source may still be
  re-invited (unchanged).
- **B. Sponsor "Every gift"**. A sponsor's acceptance is per gift and vetted per gift, so "every gift" cannot be a live
  rule the way it is for reviewers. Recommend: it means *every gift active when they register* — one pending
  membership per gift, each vetted as today; a gift started later is not joined automatically.
- **C. Mentor "Every gift"** — recommend the reviewer rule exactly: no gift rows = every gift, including later ones.
  The 5 existing mentors start as Every gift, so nothing changes for them until someone ticks.
- **D. A mentor's gifts are narrowed while they mentor someone outside them** — recommend refuse
  (`mentor_has_scholars_outside`, naming how many), never end the assignment silently.

## Sprints
Each sprint: own commit(s) on this branch, targeted tests while building, full API + web gates once, a fresh
reviewer on the diff, CHANGELOG + decisions.md. Nothing is pushed or deployed without the owner; the audit agent sets
the pace.

### I1 — One form, one waiting table (web only) · complexity: medium
- **Goal:** all five tabs share one form layout and one waiting table.
- **Form:** label above every box; the tab's note sits under the fields; Send Invite at the left, under the note
  (the layout three of five tabs already use). Mentor's note shortened.
- **Table:** Source and Mentor render through `InvitationsTable`, which gains an optional leading column (Source) and
  the phone-card layout (`phoneRows`) the newer tables have; headings in the one `TH` style; Status keeps
  "Waiting (date)"; Resend + red **Cancel invitation** everywhere (Mentor's link calls the mentor revoke endpoint as
  today — only the word changes); paged everywhere.
- **Files (≈12):** `staff/page.tsx`, `InvitationsTable.tsx`, `SourceInvite.tsx`, `MentorInvite.tsx`, `TableFrame.tsx`
  (if needed), en/ms/ta.json, their tests, CHANGELOG.
- **Done when:** a rendered test per tab asserts the same labels, button position and table headings; phone
  mobile-check run on the page; Source's "Signed in" table is untouched (I2 moves it).

### I2 — One person per source; Remove on the Sources page · complexity: medium
- **Goal:** rulings 3 and 4.
- **API:** `source_invite.invite` refuses a source that already has an active person (`source_has_person`, per open
  point A); the invitations payload marks such sources; the Sources list payload gains the source's person
  (name, email, joined date, `manageable`) — sources page today carries only `sign_in`.
- **Web:** the dropdown drops joined sources (and greys waiting ones, per A); the "Signed in" table and its Remove go
  from Invitations; the Sources page row shows the person and a Remove link (same confirm, same endpoint
  `admin/source-users/<id>/revoke/`).
- **Files (≈14):** `source_invite.py`, `views_admin/sources.py`, `views_admin/invitations.py`, tests;
  `SourceInvite.tsx`, `admin/sources/page.tsx`, `admin-api.ts`, en/ms/ta.json, tests; decisions.md (revises
  2026-10-30), CHANGELOG.
- **Done when:** a second invite for a joined source is 409 from the server and absent from the dropdown; Remove
  works from Sources; nothing about a source's person remains on Invitations except the waiting row.

### I3 — Sponsor invite: several gifts or Every gift · complexity: high (money-adjacent: Opus build + Opus review)
- **Goal:** ruling 1.
- **API:** the invitation holds several gifts (new `invitation_gifts` table, or `Invitation.programmes` M2M;
  `Invitation.programme` kept as the rollback mirror, as `PartnerAdmin.programme` is for reviewers); `programme_ids`
  (`[]` = Every gift, per B) on the sponsor invite; `signup_programme_for` becomes "the gifts they were invited to" and
  its three callers make one pending membership per gift; the resend still never re-homes a sponsor.
- **Web:** the Sponsor tab uses the reviewer `GiftTickList`, always shown; the waiting row lists its gifts.
- **Migration:** additive (new table + backfill from `Invitation.programme`); no data rewritten.
- **Files (≈16).** **Phone check before go-live** — it decides which students a sponsor may browse.
- **Done when:** an invite for gifts A+B yields two pending memberships on registration, each vetted on its own;
  a one-gift invite behaves exactly as today; the stranger-off-the-public-form case still yields none.

### I4 — Mentors have gifts, and a gift limits who they mentor · complexity: high (Opus build + Opus review)
- **Goal:** ruling 2.
- **API:** `mentor_gifts` table (mirrors `reviewer_gifts`; no rows = every gift, per C); the mentor invite takes
  `programme_ids`; `mentoring.assign` refuses `mentor_not_in_gift`; `assignable_mentors` filters by the scholar's
  gift; editing gifts refuses narrowing past a current scholar (per D).
- **Web:** Mentor invite tab gets the tick list; Team → Mentors details box shows and edits the mentor's gifts
  (as the reviewer details box does); the assign picker lists only mentors in the scholar's gift.
- **Migration:** additive; existing mentors get no rows = Every gift.
- **Files (≈20).** **Phone check before go-live.**
- **Done when:** a mentor limited to Sabah is not offered, and is refused by the server, for a flagship scholar;
  existing mentors are unaffected.

## Order and rationale
I1 first — no rules, and it builds the shared form and table the others drop into. I2 next — small rule change, and
it finishes the table work by removing "Signed in". I3 before I4 — riskier (money), so earlier. Four sprints rather
than two because I3 and I4 each carry a migration and a phone check, and bundling either with layout work would bury
a money/eligibility change in a cosmetic diff. I1 and I2 could merge into one if the owner wants fewer handoffs.

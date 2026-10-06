# Retrospective — Seeing is not managing, and Resend was a footgun

**Date:** 2026-09-09 · **Branch:** `feat/people-actions` · **Worktree:** `.worktrees/people-actions`
**Base:** `origin/main` @ `81bfcb29` · **Migration:** none

---

## What Was Built

The owner reviewed the People page shipped that morning and reported three faults plus two copy
changes. All three faults were real.

| # | What they said | What it actually was |
|---|---|---|
| 1 | The link lands on the wrong tab | True. The tab is now in the URL (`?tab=admins`). |
| 2a | The Admins tab is missing the org admins | A regression I introduced: the roster moved onto an endpoint whose filter was written for ACTING, not listing. |
| 2b | Resend is a bug | Worse. It **rotates the password** of a working admin and mails them a temporary one. |
| 2c | Add a delete | Built, but with a different guard than either of us first proposed. |
| 3 | Reviewers need Last seen + Revoke | Built, with a warning that names what a revoke strands. |

Plus: the "1 no longer has access" line removed, and "waiting to reply" → "Awaiting reply".

---

## What Went Well

- **Measuring beat reasoning, twice.** "Reviewers are shown in two places" became actionable only
  after counting: 13 accounts, 13 invitations, empty set difference. And 2c only became correct
  after counting what each admin had *done* — 25 payment runs against one name.
- **`StaffTable` absorbed Delete with no new table**, and `AdminRevokeView` needed no change at all
  for the reviewers' Revoke: it already accepted reviewer targets and already refused the last
  org_admin.
- **The owner's own precedents settled two designs.** The two People tabs are their 2026-08-03
  ruling on categories; the delete's shape started from their gift-programme rule and was then
  corrected off it — see below.
- **Every one of the six bite-checks bit**, including the two "drive over the bump" pairs (a
  `manageable` flag read backwards empties every row of controls; a delete guard left on refuses
  the fresh admin too).

---

## What Went Wrong

**1. I recommended a delete rule that would have offered to delete the person who runs the money.**

- *Symptom:* I proposed "let the database's own protections decide", citing the owner's gift
  programme precedent, and measured cases and interview slots. The owner rejected it with a
  specific counter-example — Kulaly creates the payment runs — and they were right.
- *Root cause:* I reused a rule from a domain where it holds (a gift is protected by real foreign
  keys) in one where it does not. **A `PaymentRun` records its author as `created_by`, an email
  string with no foreign key at all.** Nothing points at that account, so every FK check says
  "safe". Measured afterwards: she has created **25 of 27 runs** and signed 8. My check scored her
  0 and 0.
- *System change:* the guard is `staff_footprint`, which counts BOTH kinds of trace — foreign keys
  *and* recorded emails — and its docstring leads with why the FK version is wrong, with the
  production numbers in it. A test creates a payment run by email and asserts the delete is
  refused, so the FK-shaped version cannot come back quietly.

**2. My Resend fix worked on half the screen, and the wrong half.**

- *Symptom:* three tests still failed after a fix I was confident in.
- *Root cause:* `StaffTable` renders each person twice — a phone card and a desktop row — and the
  desktop row held an **inline copy** of the action buttons while the card called `actionsFor`. I
  changed the helper. The owner looks at the desktop table.
- *Why it is worth writing down:* the module's docstring says it exists to stop the staff table
  being copied across pages, and it had been copied **inside itself**, four months later, by the
  phone-cards sprint. Extracting a helper does not remove a duplicate unless every renderer is
  moved onto it — and nothing failed at the time, because both copies were correct then.
- *System change:* the inline copy is deleted and both renderings call `actionsFor`; the tests
  assert through the desktop table, which is where the divergence was.

**3. I broke the org-admin listing the previous morning and did not notice.**

- *Symptom:* the owner's two fellow organisation admins disappeared from the console.
- *Root cause:* Invitations fenced on the invitation's ORGANISATION; the staff endpoint fences on
  ROLE, because it is the endpoint you act through. Moving the roster from one to the other
  silently inherited the stricter rule. The sprint that moved it had no test asserting *who is
  listed*, only that reviewers were not duplicated.
- *System change:* `PROGRAMME_STAFF_ROLES` (see) is now distinct from `_ORG_ADMIN_MANAGEABLE_ROLES`
  (act), with a `manageable` flag per row and a test that a peer org_admin is **listed and not
  manageable** — both halves, because either alone is a different bug.

**4. A scoping bug in my own new tests briefly read as a product bug.**

- *Symptom:* three assertions failed against markup they were never looking at.
- *Root cause:* the file's existing `ui()` helper reaches for the first `[data-testid=
  "table-scroller"]` in the **document**, which is fine for a file where one test renders once.
  Mine each rendered their own table.
- *System change:* the new tests scope to their own render's container, with a comment saying why.

---

## Design Decisions

Logged in `docs/decisions.md`. In brief:

- **Seeing is not managing.** Listing everyone and flagging who is actionable, rather than hiding
  people you may not touch. The fence stays at the write endpoints.
- **A footprint, not foreign keys**, for the delete guard — and never for a reviewer.
- **Once you have done work you are revoked, not deleted, permanently.** The owner asked for
  "until someone else is assigned"; the system holds no assignment (payment-run authorship is
  granted by ROLE, never to a person), so there is no handover it could verify. The stricter rule
  is the honest one, and it was stated as such rather than approximated.
- **A revoked reviewer stays listed** — reversing the 2026-08-02 ruling that they are "not staff to
  look at", because Revoke now lives on that table.
- **Resend belongs to somebody who has not arrived**, on all three staff pages — the platform pages
  keep a working Resend for a genuinely waiting invitee, which a blanket removal would have taken.

---

## Numbers

| Gate | Result |
|---|---|
| pytest | **6094** passed (+13) |
| jest | **1932** passed (+13), 118 suites |
| `tsc --noEmit` | **24** — unchanged baseline (TD-221) |
| `next lint` | **0** errors |
| `check-i18n` | ALL PASSED, **4926 × 3** |
| `next build` | exit 0 |
| `makemigrations --check` | No changes detected |
| Migrations added | **0** |
| Bite-checks | 6, all bit |

**Files touched: 17.**

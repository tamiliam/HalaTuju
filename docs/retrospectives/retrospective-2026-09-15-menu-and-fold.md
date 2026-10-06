# Retrospective — The menu says what the pages do, and the Programme group folds away (2026-09-14)

Closed on 2026-09-15 alongside the Programme Overview close. One commit, `f44d9d11`.

## What Was Built

The owner asked for seven menu changes from a screenshot. Six shipped as one change; the seventh
became the Programme Overview sprint.

- **Renames:** Overview → Programmes; Settings → Organisation Settings; People → Team; Billing &
  usage → Usage & Billing. Page headings, hub tiles and the manual follow, so nothing names the old
  word (the manual grep in `navigation.test.ts` proves it).
- **Order:** Organisation Settings last in its group; Sources before Sponsors.
- **The Programme group folds away** until you are inside a gift, keyed on the PATH. Two roles are
  exempt because they have no other door: a reviewer's and a QC's only row is Applications; a plain
  admin or finance never sees a gift card to click. The exemption is keyed on `programmeConfig`'s
  roles, not a second role list.

## What Went Well

- **The exemption was derived, not listed.** "Whoever may open a gift's configuration is exactly
  whoever the Programmes page offers a gift to" — one fact stated once, so the day the cards open
  to another role the fold follows without a second edit.
- **The manual grep guard did its job**: three chapters still said "Overview", "People" and
  "Billing & usage" and the test named them.

## What Went Wrong

1. **The fold was first keyed on `programmeChosen`, and on that signal it would never have folded.**
   - *What happened:* the group stayed open on every organisation page in the first build.
   - *Root cause:* `programmeChosen` fills itself in whenever a tenant has exactly one gift — which
     is production today. A derived flag that is vacuously true in the commonest deployment cannot
     drive a rule that must sometimes be false.
   - *System change:* keyed on `pathname` via `activeItem(pathname)?.scope`; six tests fail if
     the fold stops working, including one on a single-gift tenant. Lesson recorded.

## Design Decisions

Recorded in `docs/decisions.md` (2026-09-14): the Programme group folds by path, with the exemption
derived from `programmeConfig`'s roles.

## Numbers

- 9 files, +242 / −56; no migration; no new endpoint.
- Deployed with the billing-costs fixes; verified live by the owner's screenshot round.

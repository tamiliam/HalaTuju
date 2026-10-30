# Retrospective — Student maintenance Sprint 5b: her Funds and Contract tabs on My Bursary (2026-10-30)

Roadmap: `docs/plans/2026-10-29-student-maintenance-roadmap.md` (Sprint 5, student half — Sprint 5 is now complete).
Shipped as `f9c484df` (feature) and `2b62a6f8` (fixes for the 7 adversarial review findings, 0 HIGH); live as
api-01202-bvg. No migration.

## What Was Built

- **`GET scholarship/bursary/funds/` and `.../contract/`** (`views_bursary`) — her OWN file only, through the S3 hub's
  one door (`_own_file`: `has_file_q` + her login; anything else 404 `no_file`); a closed file reads.
- **Funds tab** (`scholar_money.student_funds`): received, award, what is still to come, her last 3 payments, and
  her spending as **totals plus categories — owner ruling (a), 2026-10-30: the sponsor's card, no merchant, no
  transaction, no transaction date** — every category by code, all time ("since your award began"), `left` floored
  at zero, `null` until a report arrives. A closed file says the bursary has ended and what she received.
- **Contract tab + Overview card**: the platform-signed agreement (countersigned; the witness optional), the parties
  without IC numbers, View PDF minting a 300-second link on her tap only, opened in a tab opened on the tap (a link to
  tap if the browser blocks it — the page is never navigated away).
- **Overview**: her top four categories and "See all spending".
- **One truth**: her tab, her S3 summary, the officer's Money tab and the sponsor card hold the same received /
  remaining / spent / left — and a test pins that her all-time Spent and the officer's THIS-TERM Spent differ on
  purpose.

## The slice move (and why)

The student's new words first went into the `scholarship` message slice. The bundle gate refused it:
`/scholarship/apply` +0.043 kB and `/scholarship/application` +0.255 kB over their first-load budgets, `/profile`
left with 0.047 kB of room — for words none of those routes shows, because the scholarship slice is loaded by every
student scholarship route. **The budget was not raised.** The words moved to their own namespace and slice
(`bursaryTabs` / `bursary`, `lib/messagesBursary.ts`), imported only by the bursary PAGE (rule D); the slice loader,
`messageChunks`, the type declarations, `messagesSlice`, the namespace i18n guard, the one-locale guard and (after
review) `sliceReach` all know it. `SpendingCard` now takes its words from the caller (`copy`, required) so her page
never needs the sponsor slice either.

## What Went Well

- The bundle gate did its job: it named the two routes and the cause, and the fix moved weight to the one route that
  reads it rather than buying room with a raised line.
- The owner's ruling (a) was settled before building, so the payload was designed narrow (codes and totals, no
  passthrough) and a planted-merchant test could prove nothing finer leaks.
- S5a's lesson held: the contract reader reused `platform_signed` (the activation rule), not a model property.

## What Went Wrong — the 7 adversarial review findings

1. **MED — a closed file promised money.** "RM X still to come" was drawn from `payments._remaining`, which is the
   right figure for the OFFICE (what the award still allows) and a false promise to a STUDENT whose file is
   terminated or withdrawn. **Root cause:** a figure was reused across audiences without asking what it means to
   the new reader in every status. **System change:** `student_funds` sends `closed: true` and `remaining: null` once
   the file is out of maintenance (`_remaining` unchanged — Payments shares it); the tab says the bursary has ended.
   Tests: terminated, and withdrawn with a returned tranche.
2. **LOW — the new slice was unguarded.** `sliceReach` had no `bursary` rule and the one-locale loop skipped it, and
   the components imported the loader (rule D: only route files may). **System change:** the rule (owners
   `/scholarship/bursary`, per-slice floors — a one-route slice cannot meet the wide slices' 10-file floors), the
   loop entry, and the import only in `page.tsx`.
3. **LOW — "exactly what your sponsor sees".** True of the categories, untrue of the wording around them. **System
   change:** "your sponsor sees only totals by category — never the shops or what you bought" (en/ms/ta); the Guide
   line too.
4. **LOW — the as-at date printed as ISO.** `SpendingCard` now formats it (`formatDate`) — the sponsor page too.
5. **LOW — two Spent figures with no label.** Her card is "since your award began"; the Guide says the officer's tab
   is this term; a test holds the difference.
6. **LOW — a blocked pop-up navigated her away.** Now a tappable link, never `location.assign`.
7. **LOW — `formatDate` showed a date-only value a day early west of Greenwich.** `new Date('2026-10-01')` is UTC
   midnight; a bare `YYYY-MM-DD` is now read by hand as the local calendar day (tested under America/New_York, with
   a bite check that the naive parse WOULD have been the 30th).

**Main lesson (lessons.md):** a figure that is true for the office can be a false promise to the person it is about —
audience-facing copy must read the record's STATUS, not only the number.

## Design Decisions

- Owner ruling (a), 2026-10-30: her spending is totals plus categories — no merchants, transactions or dates.
- Her card is all time ("since your award began"); the officer's is this term.
- A closed file promises nothing; the shared `_remaining` stays the office's figure.
- Her words ride their own slice on her one route; budgets are never raised to fit words a route does not show.

## Numbers

- Lead's run on the rebased tip: **10,534 pytest** passed (3 skipped); **5,081 jest / 328 suites**; i18n ALL PASSED;
  bundle ok (median 146.745 kB; `/scholarship/bursary` 193 kB first-load); `makemigrations --check` clean.
- Adversarial review: 0 HIGH, 1 MED, 6 LOW — all fixed, each with a regression test.
- Two commits (29 + 20 files). No migration. **Student maintenance Sprints 1–5 are all live.**

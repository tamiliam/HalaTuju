# Retrospective — billing settings move to the screens whose scope they match (2026-10-28)

Written late: the sprint shipped and was verified live before the close was done, and the owner moved straight on
to back-issuing July and August. Recorded here in full rather than folded into the next sprint's retro, because
two of its lessons are about how the work was done and not about billing at all.

## What shipped

`06757a61` (merge `10152d00`), api-01170-lv6 / web-01004-fsp, digests matched to builds `693793d8` / `0d701119`.
No model, no migration, no data move.

- **Who is BILLING** → Platform ▸ Billing, first of two tabs beside Rates. One row for the whole platform,
  super-only. `AdminInvoiceIssuerView`.
- **Who is BILLED** → Organisation ▸ Settings, a third tab beside Colours and Configuration, keyed on the
  organisation code exactly as its two siblings are. `AdminOrgBillingDetailsView`. An organisation may now edit
  its own bill-to (owner ruling); it may not touch what it is billed FOR or AT.
- The Settings tab left Billing & usage; the readiness link now opens the page that can actually fix the
  problem, naming the organisation. "Bank" became "Bank name", and the nine boxes sit under four headings so the
  address column visibly ends.

The trigger was one sentence from the owner: filling the form in for the first time, the address spilled across
three boxes — the postcode landed in Phone and the city in "Bank". That was a form-grouping failure, not user
error, and the form was in the wrong place as well.

## What went well

- **The fence was tested from the WIDENING side.** `_TwoTenants` creates alpha AND beta, because with a single
  tenant every fence passes. `test_the_widening_side_one_tenant_cannot_read_or_write_anothers` is the test that
  means anything; the narrowing-side one passes either way.
- **Adversarial review earned its place again.** It found three 500-class faults the tests had not: a JSON array
  body reaching `.get`; no cap on invoice recipients, where the Brevo quota is platform-wide and SHARED, so one
  tenant could spend everyone's; and a `bill_to_name` over the column's length. All three are now refusals with
  codes.
- **Twelve bite-checks, twelve caught** — after they were re-run properly (see below).

## What went wrong

- **A guard that could never fire.** `AdminOrgBillingDetailsView` carried its own `ROLES = ('org_admin',)` check.
  A bite-check deleted it and nothing failed: `_InvoiceBase._caller` had already refused every other role one
  call earlier. Third instance of a dead safeguard in this codebase. The guard was removed and the docstring now
  names the real gate.
- **I reported a shared-state bug that was mine.** Two tests failed only in full-suite runs. I told the owner it
  looked like "a real shared-state problem in the code". It was not: I had started the full pytest suite in the
  background and then run a bite-check script, which spawns its own pytest. Two pytest processes, one test
  database. Run alone: 9,444 passed, 0 failed.
- **I gamed a size guard before I noticed.** A FAQ entry pushed `faq.tsx` to 607 lines against a 600 limit. I
  shaved two answers to 603, then recognised that trimming prose to fit is not what the guard asked for, reverted
  the FAQ entirely and put the content in `role-org-admin.tsx` instead. Logged TD-413 — the file is still one
  line from the limit.
- **A test of mine was meaningless.** It mocked the server refusing with `organisation_required` *while also*
  passing an organisation code, so it asserted a state the server cannot be in. Rewritten.

## Lessons

1. **Never run a bite-check while a test suite is running.** Both are pytest and they share one test database.
   The failure does not look like a collision — it looks like a real, interesting bug in the code you just
   wrote, which is why it cost a wrong report to the owner before it cost a re-run.
2. **A guard that asks you to split a file is not asking you to trim it.** The 600-line standard exists so that
   no human or agent has to hold a file in one head. Shortening the newest prose until the number passes leaves
   the file exactly as hard to read and removes the signal. Split, or put the content where it belongs.
   *(Applied in the very next sprint: `views_admin/invoices.py` reached 591 and `AdminOrgBuildHoursView` moved
   to its own module rather than anything being trimmed.)*

## Debt raised

- **TD-412** — three copies of the `_organisation_for(admin, code)` pattern now exist.
- **TD-413** — `src/content/manual/faq.tsx` sits one line under the 600-line limit.

# Retrospective — Tenant invoices and receipts (2026-09-14 → 2026-09-15)

## What Was Built

The owner's screenshot of Billing & usage said *"We have the usage but not the billing."* The money
side existed, but only on a super-only section; the screenshot was the organisation view. The real
gap was one layer down: nothing was ever ISSUED. No invoice, no receipt, and a charge recomputed on
every page load.

- **Invoices** — numbered `INV-YYYY-NNNN` gap-free from a locked counter, frozen at issue (lines,
  discount, issuer, bill-to). Void-and-replace, never edit.
- **Receipts** — `RCP-YYYY-NNNN`, bank reference required, no overpayment, no future dates.
- **The 15th's run** — `issue_monthly_invoices` bills the PREVIOUS month, sends nothing, never
  overrides; Cloud Scheduler `halatuju-issue-monthly-invoices` at 09:00 MYT on the 15th.
- **Readiness** — refuses a month with a supplier missing versus the month before, an unconverted
  cost, a missing rate, unrecorded request hours, blank billing details, or a month not yet closed.
- **Held until sent** — Send behind a confirm that names the inboxes; the tenant sees nothing earlier.
- **PDFs** for both documents (xhtml2pdf), an Invoices section with super and tenant views and phone
  cards, en / ms / ta text, Guide and FAQ updates.
- Migration `0160` migrate-first, with RLS on every new table — and on `org_billing_adjustments`,
  which had shipped without it.

## What Went Well

- **Reading the ledger before accepting the brief.** "Issue on the last day of the month" would have
  under-billed every month; one query showed September holding RM3.25 on the 14th. The owner moved
  the date to the 15th in one sentence.
- **Bite-checks found no silent test** — 10 backend and 5 web faults injected, all caught, every
  file restored byte-for-byte and verified.
- **The existing guards did their job.** The org-fence guard forced the new money tables onto its
  watch list and a pragma at every query; the table-frame guard refused a list with no phone layout
  and an unframed table, and both were right.
- **Digest-matched deploy**, migration applied and verified BEFORE the push, ledger 160/160.

## What Went Wrong

1. **Stitch saved no screens — the same failure as July.**
   - *What happened:* both generations reported the usual timeout; the project's update time moved but
     no screen instance was added, across two polls.
   - *Root cause:* the memory note already recorded this failure mode on 2026-07-21, but the workspace
     rule ("prototype in Stitch first") was followed literally before the note's own advice ("reserve
     Stitch for genuinely new designs; an approved artifact mock meets the rule's intent").
   - *System change:* for a code-generated document, render the REAL output for approval; for a
     screen, an artifact mockup is the fallback after one failed Stitch attempt. Lesson recorded.

2. **The first real PDF had three layout bugs.**
   - *What happened:* Hours / Rate / Amount headings overlapped, the "How to pay" box split in two,
     labels were letter-spaced apart.
   - *Root cause:* the template was written from browser-CSS habits; xhtml2pdf ignores widths on
     `<th>`, draws a bordered `<div>` inside a cell as its own box, and implements `letter-spacing`
     literally. The unit tests assert text, which was all correct.
   - *System change:* rendered the actual PDF and looked at it before asking for approval; widths now
     sit on every `<td>`. Lesson recorded ("approve the real output, not a drawing of it").

3. **The new tables would have been created without row-level security.**
   - *What happened:* the Postgres DDL generated from the Django migration contains no RLS. Checking
     the sibling tables before applying it showed the house convention (RLS + a service_role policy)
     and that `org_billing_adjustments` (0157) had already shipped without it — the Security
     Advisor's only ERROR, readable with the publishable key.
   - *Root cause:* RLS is a Supabase concern Django does not model, so migrate-first SQL generated
     from the migration is structurally incomplete, and the convention lives only in other
     migrations' docstrings. Nothing checks it.
   - *System change:* run the Supabase Security Advisor after every migrate-first apply and treat an
     ERROR as blocking; the exact SQL run, RLS included, is now in the 0160 docstring. Lesson recorded.

4. **The guards that caught the phone layout ran late.**
   - *What happened:* the table-frame guard failed on the full jest run, after the screen was
     otherwise finished.
   - *Root cause:* only the focused test files were run while building the component.
   - *System change:* when a component adds a `<table>`, run `pageWidth.test.ts` with it — noted here
     rather than as a lesson, because the guard already states its own rule.

## Design Decisions

Recorded in `docs/decisions.md` (2026-09-14): issued on the 15th for the previous month and held
until sent; frozen, void-and-replace, gap-free numbers, derived status; readiness refuses rather than
under-bills; the tenant copy shows no cost or margin; no seeded legal identity.

## Numbers

- 29 files, +4,260 lines; migration `0160` (6 tables) + RLS on 7 tables.
- **6617 pytest** (+78 invoice tests), **2217 jest** (+21), tsc 24 baseline, lint 0 errors,
  `next build` exit 0.
- Bite-checks: 15 injected, 15 caught.
- Deploy: api `halatuju-api-01040-grq`, web `halatuju-web-00889-qw6`, digests matched to `b09b8217`;
  no ERROR logs after deploy.
- No time estimate was given for this sprint, so there is no planned-versus-actual figure.

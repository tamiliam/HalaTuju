# Retrospective — back-issuing July and August, and what a line says (2026-10-28)

The owner asked for the first real invoices: *"I want to issue Invoice from the the month of July
onwards, issued on the 15 of the following month. But for July, it is fully discounted… Upon
receiving payment… I click a button and issue receipt. Now, can you create invoices for the months
of July and Aug as pdf copies? I want to see the layout as well, and see what items are still
missing there."*

So the sprint began by **rendering the real documents from the real figures** before writing any
code. That is what found the work.

## What the previews found

Five PDFs, built from production's own ledger in a throwaway SQLite database — nothing issued.

- **July 2026** — RM256.98 of cost, 100% discounted, charged **RM0.00**. No development line: no
  request was worked in July, which is correct and not a bug.
- **August 2026** — **RM1,722.36**: infrastructure RM163.89, metered RM5.97, and 27.0 hours at
  RM57.50 = RM1,552.50.
- Three faults, none of them visible from the code alone:
  1. **July loses a whole line.** The metered margin's `effective_from` is 1 August, so July's
     metered cost cannot be priced at all and the invoice prints RM227.62 instead of RM256.98.
     The money is the same (zero) but the owner's July requirement is *"show it in full"*.
     Fixed by a rate row, not by code.
  2. **No way to back-date.** July would have said "Issued 28 October" with a 27 November due date.
  3. **The lines read like a bug tracker**: `[REQ-10] A new page to review and manage reviewers`.

The receipt button was already built and correct; it is hidden when nothing is owed, so a fully
discounted July offers none — which is right.

## What shipped

- **`invoicing.issue_date_for`** — a super may set the printed issue date, inside three bounds:
  never after today, never on or before the last day of the billed month, never in a closed
  calendar year. `due_on` and the invoice number's year both follow it. The monthly job passes
  nothing and is unchanged.
- **`invoicing.printable_module`** — the `[REQ-n]` tag is stripped from the printed description and
  stays in `OrgBuildHours.module`, which is what makes a request countable as billed.
- **A month picker on "To issue"** — the endpoint had taken `?month=` since it shipped; the screen
  never sent it, so July and August were unreachable from the browser.
- **`invoice_parsers`: Supabase's INVOICE parses, not just its RECEIPT** — "Amount due" as well as
  "Amount paid". The owner supplied September as an invoice and every field failed at once.
- Moves only, in the same sprint: `AdminOrgBuildHoursView` → `views_admin/build_hours.py`
  (that file was at 591 of 600), and the months/dates/numbering block → `invoice_dates.py`
  (`invoicing.py` reached 634 while the back-date rules were being added).

## What went well

- **Rendering the real PDF first.** Every one of the three faults came from reading the document,
  not from reading the code. The same lesson as the September PDF-layout work.
- **Adversarial review earned its fee again** — nine findings, five of them fixed here. The two
  that mattered most were ones no test of mine could have reached, because they were about what the
  *screen* made reachable: the month picker offered November 2025, whose prefilled date would have
  minted `INV-2025-0001` and reopened a closed, filed run of numbers; and clearing the date box
  silently meant "today", producing the exact failure the panel exists to stop.
- **Eighteen bite-checks, eighteen caught**, run with nothing else running (the lesson from the
  previous sprint, which cost a wrong report to the owner).
- **The size guard was obeyed, twice, by splitting** — not by trimming prose, which is the other
  lesson from the previous sprint. Both files ended smaller than they started:
  `views_admin/invoices.py` 591 → 503, `InvoicesSection.tsx` 577 → 478.

## What went wrong

- **Two of my own tests asserted things the fixture did not do.** One claimed July already carried
  readiness warnings; one claimed two months' problems differ. Neither was true of `InvoiceWorld`,
  so one passed vacuously and the other failed. Both rewritten to CREATE the difference and assert
  it before relying on it. Written up in `docs/lessons.md`.
- **I asked the owner for a document I did not need.** Anthropic's September row has no exchange
  rate; I asked for the invoice PDF. The rate is public and fetched automatically — the row simply
  needs re-converting, which nothing could do. That gap is now `--convert-held`.
- **A pre-existing receipt test dated a payment five days before the invoice it paid.** Impossible,
  and only caught because back-dating made the rule worth writing.

## Lessons

1. **Render the artefact before planning the work.** Three faults, zero of them visible in code.
2. **A fixture that happens to agree proves nothing** — if a test needs two states to differ, make
   them differ in the test. (Added to `docs/lessons.md`.)
3. **A settable date on a money document is a door, not a field.** It reaches the numbering series,
   the due date, the receipt rules and the year's books. Each of those needed its own bound, and
   only one of them was obvious when the work started.

## Open

- ⚠ **The bundle budget is 0.118 kB under its line on `main`** — measured on both `main` and this
  branch, byte-identical, so it is not this sprint's weight. The deploy gate prints and passes at
  this margin, but main is one non-admin string away from a red gate for every session.
- **Twilio June (RM32.19) is new to the ledger**; June is not billed to anyone.
- **Google Workspace's one-day June invoice (RM0.63)** uses a part-month layout the parser does not
  read. June is not billed, so it is reported and left.

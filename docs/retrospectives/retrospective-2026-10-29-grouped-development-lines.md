# Retrospective — grouped development lines, and bug work charged at zero

**Date:** 2026-10-29
**Branch:** `feat/back-issue-invoices` (same branch as the back-issue sprint, deliberately — see
*One branch, one deploy* below)
**Migration:** `scholarship/0181_invoice_line_parent`
**Owner asks, verbatim:**

1. *"the development reqs, I think it'll be good if the list of items are listed as subitems under,
   say, feature request, instead of main items. And each feature request, too, include the req no
   in brackets."*
2. *"And, include bug report as well, and state the hours and rate which is zero, but these need
   not be itemised."*
3. *"create an estimated invoice for Oct so I see how much it would come"*
4. *"reduce the hourly rate to RM20"* — from *"the beginning - July (discounted)"*

---

## What shipped

A *"Feature requests, <month>"* line carries the group's hours, the billed rate and the group's
amount. One sub-item per request sits under it, showing its own hours and its request number in
round brackets. A *"Bug reports, <month>"* line carries its hours at a rate of RM0.00 and is not
itemised. `InvoiceLine.parent` holds the structure; the payload sends a boolean `is_sub_item` and
the admin screen indents on it, so screen and PDF read the same.

The hourly rate became RM20 from 1 July 2026 (RM20 + 15% = RM23.00 billed), a production data
change, not code.

Ten preview PDFs went to the owner: July, August, September, an October estimate and a receipt,
each rendered twice — once as the requests are triaged today, once with the seven filed as bugs
re-triaged — so the money difference could be read off the paper rather than argued about.

---

## What the work actually turned out to be

**The second ask was not a new pricing rule. It was a bug report about the old one.**

The owner's own note on the 15% development margin, written on 2026-09-11, says: *"The margin
should help cover bug fixing which is not billed separately."* So bug work was always meant to be
free. The invoice had been charging it as feature hours anyway, which collects for the same work
twice — once inside the hourly rate, once as a billed line.

Nothing had gone out yet, so nobody was over-billed. But the only reason is that the invoices had
not been issued, not that anything caught it.

**The finding underneath it is worse than the fault.** `billable_kind` had to choose which of three
fields decides whether a request is a bug: Gemini's `ai_draft_kind`, the submitter's `kind`, or the
owner's `triaged_kind`. Only the owner's ruling may move money. But on production `triaged_kind`
reads `'feature'` for **all sixteen** finished requests — including **seven filed as bugs**, 58.0
hours, RM1,334 at the new rate. The model's own comment had predicted this exact failure: *"came to
sit on 'feature'/'sprint' for every bug, one press away from charging for free work."* The comment
was right and nothing enforced it.

So the feature the owner asked for prints nothing until those seven are re-triaged. That is
reported, not patched: re-ruling a customer's work is the owner's call, not mine.

---

## The owner's challenge, and what it was actually worth

The owner read the report above and pushed back: *"I checked 5. It is labelled as bug report. So,
what do you mean by retriage 7 reqs filed as bugs?"*

They were right and the claim was wrong. I had said the seven were a form default pressed through.
Checking properly:

- The triage dropdown **does** seed itself from the engineer's analysis, then the AI's draft
  (`page.tsx`, the `triageTouched` effect). It is not hard-coded. My first grep for that effect was
  truncated by `head` and I read absence into it — the exact failure
  `feedback_grep_absence_is_not_evidence` exists to stop, committed by the person who wrote it down.
- Of the seven, **six** were read as features by Gemini or by the engineer's own code analysis, and
  the owner accepted that reading. That is the adjudication rule working, not a defect.
- **One** — request 14 — was filed as a bug, read as a bug by the engineer, and triaged as a
  feature. That one was worth finding. It is now a bug.

So the real defect was neither the data nor the triage step. **The request pill printed `kind`
(filed) while the invoice priced on `triaged_kind` (adjudicated), and nothing on the page said they
disagreed.** The owner could not have discovered that except by asking. Both screens now show the
deciding field, with an amber chip naming the filed one when they differ, and a drift test reads
both server resolvers so the three definitions cannot separate again.

The lesson that cost the most here is not technical: **a confident wrong diagnosis sent to the owner
is worse than a slower right one.** The data was one query away the whole time.

## What went well

- **Rendering before pricing, again.** Every fault this sprint and the last came out of printing
  real documents from real figures into a throwaway database. The code read correctly each time;
  the output did not. This is now a lesson.
- **Both passes, not one recommendation.** Rather than ask the owner to imagine the difference
  between charging and not charging the seven bug-filed requests, both versions were rendered. The
  decision is now a comparison of two PDFs.
- **The adding-up invariant held.** Grouping created a real way to double-count: money at the
  parent and money at the children. Sub-items carry `amount_myr` 0.00 by construction and
  `build_lines` sums children too, so the day that stops being true the guard fires rather than an
  invoice that does not add up reaching a customer.
- **Only four existing tests broke**, all of them asserting the old flat shape, and each was
  rewritten to the new intent rather than loosened.

## What went badly

- **The back-issue sprint closed with no CHANGELOG entry.** The retrospective, lessons, CLAUDE.md
  and the TD register were all updated; the changelog was simply missed, and the project rule says
  every task appends to it. Caught only because this sprint went looking for the heading to append
  under. Fixed here with one entry covering both.
- **A documented command did not work.** `halatuju_api/CLAUDE.md` said
  `record_platform_cost --convert-held <month>`; the month is a separate required option. Written
  from memory the day before instead of from the command's own arguments, and it would have failed
  for whoever typed it next. Found by running it.
- **One guard was written badly and cried wolf.** A test asserting the printed document never says
  "margin" failed on the stylesheet's `@page { margin: ... }`. Now it strips `<style>` and the tags
  and searches the text a reader sees.
- **Two guards fired on text rather than meaning, and both were my doing.** The "document never
  says margin" test matched the stylesheet's `@page { margin: ... }`. Then the suppression-count
  budget matched the marker text written *inside a comment explaining why no suppression was
  used*. Both cost a cycle; both are now lessons.
- **The split was needed and was nearly missed.** `platform_cost.py` went from 681 to 760 lines
  against a 701 allowance once `billable_kind` and its reasoning were added. The guard caught it,
  the request/hours block moved verbatim to `request_hours.py` (141 lines), and the ledger entry
  was LOWERED 681 → 659. It is worth noting the first instinct was to look for lines to trim — the
  exact thing TD-413's lesson exists to stop.
- **The RM50 rate row had to be amended, against the model's own doctrine.** `BillingRate` says a
  new value is a new row with a later date, never an edit. But `rate_in_force` takes the latest row
  on or before the month start, so adding RM20 at 1 July would have left RM50 at 1 August still
  winning for August onward. Amending it was safe *only* because no document had ever been priced
  at RM50 — and that is written into the row's note and into CLAUDE.md so the exception is not read
  as precedent.

---

## One branch, one deploy

This work went onto the already-closed, already-green `feat/back-issue-invoices` branch instead of
a new one. A HalaTuju push deploys, build minutes cost money, and the owner's changes land on code
that has not shipped yet — so one deploy covers both. The trade is that the branch now carries two
sprints' worth of change and one commit history to read; the CHANGELOG entry covers both under one
heading for that reason.

---

## Still open for the owner

| What | Why it matters |
|---|---|
| ~~Re-triage the 7 requests filed as bugs~~ | **Settled 2026-10-29.** The triage decision prices; six of the seven agree with the AI or engineer reading the owner accepted. Request 14, the one that did not, is now a bug. |
| TD-418: `approved_by` on an acceptance | An acceptance has a date and no name, so the customer's own acceptance cannot be told from the owner's on their behalf. A record-keeping gap, not an unknown fact: the owner attributed request 38 to BrightPath on 2026-10-29, and both its quote (82.0 h, 25 Oct) and acceptance (26 Oct) are on the row. |
| `metered margin_pct` effective 2026-07-01 | Without it July prints one line instead of two. Charges nothing either way — July is 100% discounted. |
| Import the September bills; record August's 27.0 h and September's 0.5 h | Without them the months bill short. |
| Drop the October Anthropic + Supabase bills | Both already issued (3 Oct, 8 Oct). Supabase is ~RM117 of October's invoice; Anthropic barely moves it. |
| Decide the tax question | Anthropic's SST is pooled and apportioned pro-rata, putting ~RM9 of tax on the tenant's infrastructure charge although Anthropic's own cost is excluded. Pre-existing. |
| Registration number, phone, tax status, logo on the invoice | All blank or absent today. The owner has seen the layout and not yet ruled. |

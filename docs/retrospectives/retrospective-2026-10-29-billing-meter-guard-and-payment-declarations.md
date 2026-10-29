# Retrospective — the busy-meter guard, the tenant payment declaration, and the owner's four readings

**2026-10-29.** Commits `dec989c6`, `b1045b8b`, `e20a3363`, `8e946874`, `6db38edc`, `77e62ace`
(plus `ceea94e0` and `cbe688e8` earlier the same day). Migrations `scholarship/0184` and `0185`,
both applied MIGRATE-FIRST by hand and recorded. Live: `halatuju-api-01184-w9l`,
`halatuju-web-01016-wbr`.

## What Was Built

**1. The busy-meter guard.** `invoicing.readiness` gained `metered_without_cost`: an invoice
REFUSES when the meter recorded this tenant's billable calls for a month whose metered cost reads
RM0.00. Overridable with a written reason — a free-tier month is real — but **the monthly job
overrides nothing**, which is the protection that matters, because an unattended run is how an
under-billed month reaches a customer. It stays silent when `fx_missing` already owns the month, so
one fault is reported once.

**2. The tenant payment declaration** (`0184`). `Unpaid → Payment declared → the owner checks the
bank → Paid`, with a reasoned rejection falling back to unpaid. **Date and bank reference only** —
no amount, no slip. The owner is emailed on a declaration; the email carries no amount, because
none was asked for.

**3. The owner's four readings of the live page**, after it shipped:
- nothing owed is never late — a zero balance reads "Nothing to pay", not a red "Overdue";
- the tenant's date box is DD-MM-YYYY;
- `(REQ-12)` links to the request, including on the three invoices already sent;
- the receipt is emailed with its PDF (`0185`), and the screen says whether it arrived.

**4. Two moves-only splits**, both forced by the 600-line standard: `metered_usage.py` (out of
`platform_cost.py`, which then LEFT the oversize ledger, 664 → 566) and `invoice_receipts.py` (out
of `invoicing.py`, 626 → 532).

## What Went Well

**Rendering the real document before writing code kept finding faults.** Every one of the owner's
four readings came from looking at the actual screen with real data. None would have been found by
reading the code.

**The project's own standards tests caught me twice on the full run** — a `# noqa` I did not need,
and `invoicing.py` crossing 600 lines. Both were mine, both were right, and the rule ("split it,
never trim it") produced a better file than I would have chosen under time pressure.

**Writing the wrong diagnosis into the code paid off.** The prepay-credit theory is recorded as
WRONG at `metered_activity_without_cost`, in the migration, in the CHANGELOG and in CLAUDE.md. It
is the kind of plausible story that regenerates.

**The migration-ledger reconcile found nothing, which is the point.** scholarship 185 files/185
rows, courses 88/88, both contiguous — checked by set, not by trusting a count.

## What Went Wrong

**1. I nearly shipped a guard that could not be proven.**
*Symptom:* the first bite-check run reported all four guards RED, with a `UnicodeDecodeError` in
the output.
*Root cause:* the harness captured the child process with `text=True`, which decodes using the
Windows locale (cp1252); the suite prints `⚠`, so the capture itself could raise — and a crash
produces a non-zero exit code that is indistinguishable from a guard correctly failing.
*Fix:* the harness now decodes child output as UTF-8 with `errors='replace'`, saves it, and prints
the assertion line behind each RED. **A bite-check must prove the guard failed for the right
reason, not merely that something failed.** Carried to `docs/lessons.md`.

**2. A JSON field default forced a database connection during an offline DDL render.**
*Symptom:* rendering `0185` for Postgres died with `OperationalError: connection refused`.
*Root cause:* `emailed_to = JSONField(default=list)` is a non-null field with a default, so Django
computes an "effective default" to backfill existing rows, and adapting a Python value to jsonb
goes through the live driver. The offline renderer has no server.
*Fix:* the column is `null=True, default=None`. That is also better modelling — NULL on both
`emailed_at` and `emailed_to` says "never emailed" more plainly than an empty list beside a NULL
timestamp. Written at the field and in the migration docstring so the next person does not retry
`default=list` and hit the same wall.

**3. Two of my own tests asserted yesterday's truth and had to be corrected.**
*Symptom:* `test_confirming_and_rejecting_send_nothing_to_the_owner` failed once confirming
started emailing the receipt; an `InvoicesSection` test matched a cell by its whole text and broke
when the request number became a link.
*Root cause:* both asserted on a PROXY (an empty outbox, an exact cell string) rather than on the
rule (nothing goes to the OWNER; the cell still reads the same sentence).
*Fix:* both now assert the rule — `[m.to for m in mail.outbox] == [[tenant]]`, and the cell's
`textContent` plus the link's href. **A test written against a proxy breaks when the feature grows
correctly, which is the expensive kind of failure.**

**4. I asked the owner about the receipt email instead of noticing it myself.**
*Symptom:* the declaration screen promised *"we will check it against our account and raise your
receipt"* and nothing was ever sent; the owner had to ask "will the receipt be sent via email?".
*Root cause:* I treated the receipt as already solved because it was stored and downloadable. I
never read the sentence the screen shows the customer against what the code actually does.
*Fix:* recorded as a lesson — **when a screen makes a promise to a customer, trace the promise to
the code that keeps it**. The wording was mine, written in the same sprint.

## Design Decisions

Logged in `docs/decisions.md`: a declaration never mints a receipt; date and bank reference only;
`payment_declared` is derived and a receipt outranks a claim; `email_receipt` is a separate call
outside the transaction; nothing owed is never late and is not "Paid"; day-first dates at the edge
only.

## Numbers

| | |
|---|---|
| Backend | **10,097 pass / 3 skipped** (`pytest -q -n auto -p no:cacheprovider`, the gate's own line) |
| Web | **4,888 pass / 311 suites** |
| New tests | 18 metered guard · 38 declarations + receipts · 11 web helpers · 4 web panel/section |
| Bundle | median 146.4 kB, **1.6 kB under** the 148 kB line |
| Migrations | `scholarship/0184`, `0185` — applied by hand, recorded, ledger reconciled |
| Files touched (this sprint's own commits) | 62 |
| Bite-checks | 4 guards injected, all RED, all restored against the original digest |
| Debt raised | TD-422, TD-423, TD-424 |

# Retrospective — What it cost, what we charge, and the invoices that read themselves (2026-09-11 → 2026-09-12)

Closed late: the work was deployed on 2026-09-11/12 and the close was written on 2026-09-15,
alongside the Programme Overview close. Nothing here was reconstructed from memory alone — every
figure is in `CHANGELOG.md` (entry of 2026-09-11) or in a commit message on `main`.

## What Was Built

The owner sent August's invoices and said none of it reached Usage & Billing, and neither did the
hours we work on requests. The investigation found the ledger, the BigQuery puller and the rates
endpoint had all shipped in July 2026 and had been **starved since** — nothing fed the ledger after
June and nothing had ever read it.

- **A reader for the ledger** (`AdminPlatformCostsView`, super-only, 403 not 404) and the **Billing
  rates screen** (`/admin/billing-rates`) against the endpoint that had waited six weeks. Saving
  never edits a rate; it adds an effective-dated one. An unset rate is DRAWN, not hidden. Four rate
  boxes, not six: infrastructure and metered carry no hourly rate.
- **`OrgBillingAdjustment`** — July is computed in full and charged nothing, with a required
  reason and the name of who set it. A boolean "not billed" flag was rejected.
- **Nothing is typed by hand.** `invoice_parsers.py` reads Workspace, Supabase, Twilio and
  Anthropic PDFs deterministically (no AI) and every parser reconciles to the printed total or
  refuses a row. `fx.py` fetches the ECB closing rate for the billed month's last day and records
  the date the ECB actually published on. A third provenance, `extracted`.
- **The GCP puller was overstating by 29% and had been since July** — fixed to Google's own
  `invoice.month` plus credits; it now reproduces three statements to the cent.
- **Claude is a development cost**, held out of the platform bucket so it is never marked up as
  infrastructure AND recovered through the hourly rate. Shown beside the hours, never added.
- **Request hours are filed by the month we WORKED**, not the month a request was raised — the
  owner caught July carrying hours we had not worked yet.
- Brevo, Cloudflare and GitHub named in the free-services footnote; Workspace removed from it (we
  pay RM18.90 a month for it). New sources `workspace`, `anthropic`, `openai`, `cloudflare`, `github`.
- Migrations `0157`, `0158`, `0159` — all additive, all applied to production.

## What Went Well

- **Reading the statements line by line before trusting the ledger.** The 29% overstatement was
  found only because the first reader made the figure visible, and the fix was verified against
  three real statements, not against the query's own output.
- **The parser self-check earned its keep on the first run.** Twilio's July invoice lists lines
  summing to $4.30 against a printed $4.29. The check refused, correctly; the resolution (a named
  `Rounding` line, one cent, visible) is better than either trusting the lines or the total.
- **The owner's three corrections were all one-commit fixes**, because each rule lived in one
  place: `worked_date()`, `RATE_SLOTS`, the console's own `disabled:opacity-50`.
- **A double-count was caught before it reached a charge** — July Supabase existed twice (an old
  hand-entered row filed by receipt month, the extracted row by usage window); realigned in one
  transaction, ascending, so no month held two rows at any moment.

## What Went Wrong

1. **The GCP ledger had been 29% too high for two months and nothing noticed.**
   - *What happened:* June recorded RM88.44; Google charged RM68.36. It was the only month synced.
   - *Root cause:* the puller grouped by `DATE(usage_start_time)` instead of `invoice.month` and
     summed `cost` without the `credits` array. Nothing compared the ledger to a statement because
     no screen read the ledger, so the number had no reader to be wrong in front of.
   - *System change:* the query matches Google's own month and includes credits; `import_invoices`
     cross-checks the GCP statement every run and alarms if the ledger exceeds it. Lesson recorded:
     a cost pulled by usage date will never match the bill.

2. **The cross-check then cried wolf every month.**
   - *What happened:* the new check compared the whole-account statement against the project
     ledger, and RM8.98 of FicusValue (a sibling project on the same billing account) read as a gap.
   - *Root cause:* the statement is per billing account; the ledger is per project. I compared
     two different scopes and called the difference an error.
   - *System change:* the gap is reported as "other projects on the account" and the alarm fires
     only when the ledger is HIGHER than the statement, which is the direction that can be wrong.

3. **A bite-check restore wrote real NUL bytes into a source file.**
   - *What happened:* `pypdf` returns Anthropic's en-dash as `\0`; I normalised it, and my
     restore step pasted the literal character back into `invoice_parsers.py` — SyntaxError.
   - *Root cause:* the fault injection and its restore were done by string replacement with the
     raw byte, in a file that must stay printable.
   - *System change:* every non-printing byte in source is spelled `chr(0)`; the normaliser's test
     constructs its input the same way. Lesson recorded.

4. **The migration numbers collided with another agent's.**
   - *What happened:* my `0156` met `0156_verdict_engine_version` from a parallel worktree that had
     already been applied to production.
   - *Root cause:* worktrees allocate sequence numbers offline; the first to reach `main` wins and
     the other must renumber after the fact.
   - *System change:* renumbered to `0157`–`0159`; from now on a sequence number (migration, TD)
     is taken from `origin/main`'s files at the moment of allocation, not from the worktree. Lesson
     recorded (it bit again on TD numbers on 2026-09-15).

5. **GitHub push protection blocked the push — a real Twilio Account SID sat in a fixture.**
   - *What happened:* the invoice text used as a test fixture was the real PDF's text, verbatim.
   - *Root cause:* lifting a real document into a fixture without redacting its identifiers.
   - *System change:* SID redacted to `ACxxxx…`, history rewritten with `filter-branch`, backup
     ref dropped. Rule: any real document becoming a fixture is redacted BEFORE the first commit.

6. **Three owner corrections that a closer read would have avoided.**
   - *What happened:* July showed 27.5 hours we had not worked (hours were filed by the month a
     request was raised); the rates grid drew six boxes where only four are real; the disabled
     Save was styled grey instead of the console's faded blue.
   - *Root cause:* two assumptions made silently (raised month = billed month; every category has
     an hourly rate) and one invented treatment where a house default already existed.
   - *System change:* `worked_date()` decides the month; `RATE_SLOTS` holds the four real slots;
     the disabled state uses the console's standard class. Lesson recorded: find the console
     default before styling any control state.

7. **The FX service refused with 403 until a `User-Agent` was sent.** Not a design fault, but it
   cost a debugging cycle; the header is set and the test fakes the transport.

## Design Decisions

Recorded in `docs/decisions.md` (2026-09-11): invoices are read deterministically and reconciled
to the printed total, with a named Rounding line for a one-cent gap; the exchange rate is the ECB
closing rate on the last day of the billed month, recorded with its publication date; Claude is a
development cost recovered through hours; request hours are filed by the worked month.

## Numbers

- 37 files across 11 commits (13 of them tests); migrations `0157`–`0159` applied to production.
- Production ledger at close: GCP Jun–Sep (corrected), Workspace / Supabase / Twilio Jul–Aug,
  Anthropic Aug–Sep, all `extracted`; July 100% discount recorded (RM227.62 → RM0.00); August
  charges RM163.89 at the 15% infrastructure margin.
- Still owner-set: the metered margin and the hourly rate. Still missing: Anthropic's July invoice.
- No time estimate was given for this sprint, so there is no planned-versus-actual figure.

# Retrospective — Billing: what it costs, who it belongs to, what to charge (2026-07-26/27)

Three connected arcs in one continuous stint. The through-line: **the platform could not say what
it cost**, so no fee could be set honestly. It can now, to the SKU, across both providers — and
the two largest lines on the bill turned out to be waste, both removed *before* any price was
derived from them.

## What Was Built

**1. The waste, found and removed (RM53/month).**
- Artifact Registry **77,576 MB → 15,943 MB** (79%, RM27 → ~RM6). The cleanup policy was working
  correctly the whole time; retention was simply 4× longer than any rollback needs.
- Cloud Run Jobs **RM33.12 → ~0**. `release-decisions` booted a 2 vCPU / 2 GiB job every 15
  minutes — ~51 s each, almost entirely Django start-up — for work the always-warm service does in
  **66 ms**. `decision-emails` was *already* registered in the HTTP cron endpoint that 22 of its
  23 siblings use. The Job is left **dormant, not deleted**: Jobs bill per execution, so the
  saving is banked and rollback is one scheduler edit.

**2. Metering that bills the right tenant.** 18 of 18 email events were org-NULL — an invoice
generated that day would have under-charged the tenant for every email sent on its behalf. Fixed
at the four seams that actually fire, plus a structural guard over the scheduling entry points.

**3. The cost ledger + the charge basis.** `PlatformCost` (0129), foreign-currency support (0130),
`BillingRate` + `OrgBuildHours` (0131). June 2026 loaded and reconciling: **RM190.71 = RM19.91
tenant + RM165.76 platform + RM5.04 tax.**

## Numbers

| | |
|---|---|
| Migrations applied migrate-first | `0129`, `0130`, `0131` (RLS + 1 policy each, advisor clean) |
| Combined pytest | **4859** (scholarship + courses + reports), 0 failed |
| Confirmed monthly saving | **RM53** (RM21 registry + RM33 jobs, measured) |
| GCP floor | RM88 → **~RM35** |
| Combined floor | **~RM137**; at +15% ≈ RM158 |
| Tenant-attributable share of cost | **10.4%** |

## What Went Well

- **The SKU-level query changed the ranking.** Artifact Registry was investigated first because it
  was visible on the dashboard; the *bigger* line (Cloud Run Jobs, RM33) only surfaced from a
  by-SKU BigQuery read. Measuring at the right grain was worth more than any optimisation.
- **Refusal as a feature.** `rate_in_force` raises rather than defaulting; an unconverted invoice
  is held with no ringgit figure and the month reports itself a floor. Every one of these was
  cheaper to build than the alternative and prevents a category of wrong invoice.
- **A pre-flight check stopped a production incident** — see below.

## What Went Wrong

**1. I diagnosed TD-178 from a misread field and shipped the wrong cause into two documents.**
- *Symptom:* logged "the cleanup policy is not reclaiming", citing images from 2026-03-14.
- *Root cause:* I read a **package**'s `createTime` as an **image**'s. The policy was enforcing to
  the second; the March images were real but sat in *dead* packages pinned by an unfiltered KEEP
  rule — a second, different cause. I then over-corrected, writing off the March images entirely,
  and only the owner's question ("would deleting these affect Lentera?") forced the re-check that
  found both causes were partly true.
- *Fix:* lesson added — an empty/old timestamp belongs to the object you queried, not the one you
  are reasoning about; and when a correction is issued, re-verify the *original* evidence rather
  than discarding it.

**2. I put a test count on the record without its scope, and another agent had to challenge it.**
- *Symptom:* reported "3584 passed at your HEAD" against a project baseline of 4809.
- *Root cause:* I ran `apps/scholarship` alone. Worse, the repo has **two live conventions** —
  commit messages quote scholarship-only, `MEMORY.md` quotes combined — so the number was correct
  by one and alarming by the other. The reviewing agent could not close the gap and (correctly)
  asked rather than assumed.
- *Fix:* every test count in a handoff now states its scope. Lesson added, because the ambiguity
  is structural and the next reader may resolve it by assuming instead of asking.

**3. I modelled money before checking what currency it arrives in.**
- *Symptom:* `PlatformCost` shipped with `amount_myr` only; the first real Supabase invoice was
  **USD**, and migration `0130` had to add currency/rate/original hours later.
- *Root cause:* I designed from the provider I had already measured (GCP, MYR) and generalised
  from a sample of one. A single glance at an invoice would have caught it.
- *Fix:* lesson added — before modelling a money column, confirm the denomination of *every*
  source it will hold, not just the one in front of you.

**4. I nearly scoped a KEEP rule that would have deleted a live production image.**
- *Symptom:* the planned "systemic" fix was to add `packageNamePrefixes` to
  `keep-most-recent-10` so dead packages would age out on their own.
- *Root cause:* the plausible model (KEEP protects redundant copies) was wrong for a
  low-deploy-frequency service. **`tamilnadai`'s live image is dated 2026-02-12** — five months
  old — and the *unscoped* KEEP rule is the only thing protecting it.
- *Fix:* caught by a pre-flight check, not by review. Recorded in memory as a standing rule
  (never scope `keep-most-recent-N`) and reinforced the habit of verifying live state before
  acting on a plausible model.

## Design Decisions

Four recorded in `docs/decisions.md`: the cron move to the warm service; the attribution ruling
(100% Supabase / 99.7% GCP, verified against the bill, with the project filter retained anyway);
the billing basis (calendar month, spot FX, cost + 15%); and the cost/charge split that keeps
`PlatformCost` (money out) separate from hours and rates (money in).

The load-bearing one is the last: **the meter answers "what did this org consume?", the ledger
answers "what did the platform cost?", and summing them in one table would make every total
meaningless.**

## Carry

- **BLOCKED on the owner:** development hourly rate, development margin %, BrightPath hours basis.
  `rate_in_force` raises without them — deliberately. **Do not seed placeholders.**
- The **August invoice** confirms RM35/RM137 as *money*; today's figures are measured *physical*
  facts. Do not fix the fee before it lands.
- Owed next: the metered price table (units → money) and the rates/hours UI (**Stitch pass first**).

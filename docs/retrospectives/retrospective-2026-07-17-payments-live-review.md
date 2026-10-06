# Retrospective — Payments live-review arc (post-P3 hardening) — 2026-07-16/17

The owner live-tested the freshly-cut-over Payments module with the real staff pair (Kulaly as
maker, Suresh as approver) and drove six deploy rounds in ~24 hours. This is the arc that turned
the shipped module into the one that actually matches how BrightPath pays students.
Commits `540f5a8c` · `cb22cf9a` · `b5fcf0d3` · `a765d419` · `1df757cf` · `d3a10f77`.

## What Was Built

1. **Pathway payment floors (hard)** — pay a pathway only from its start month, even for
   continuing students (STPM/Matric/Asasi July · Poly/UA Aug · PISMP Sep), AND never before the
   student reports. Replaced the reporting-date-only rule that let a continuing PISMP student
   into an August run.
2. **eWallet-confirmation gate** — an emailed-but-unconfirmed student is greyed
   (`vircle_unconfirmed`); the 8 legacy students (never emailed the task) pay on the ID alone.
3. **Month-tagged runs** (migration `0102`, migrate-first) — a run declares the month it pays;
   a student in a completed run for that month is greyed `already_paid`. Solves the
   double-payment the owner caught (the 30/6-dated run IS the July payment; a 17/7 run must not
   pay those 7 again). Run references now carry the pay date (`PR-2026-07-17`).
4. **Names in CAPS at the write boundary** — `StudentProfile.save()` normalises; 20 B40 rows
   backfilled. Chosen over display-time helpers ("we'll deal with this in perpetuity" — owner).
5. **The full send-to-Vircle chain** — maker-sign notifies the org admin(s) by email;
   countersignature emails Vircle the instruction with the CSV attached (default
   gokula@vircle.com) and files the CSV in `01 BrightPath/03 Vircle/01 Payment`; a maker-voice
   declaration above the signatures names the covered month + destination. CSV: `Wallet ID`
   header, no Phone, Excel-safe `="…"` ID.
6. **Award email as TWO explicit steps** + selective born-after-2008 guardian paragraph
   (`vircle.can_register`) + gear-icon instructions for finding the eWallet ID + the capture
   widened to prefix `800040017` + 4 typed digits.

## What Went Well

- **Live testing with the real actors found what tests couldn't.** Every round came from the
  owner (or Kulaly/Suresh) touching the real thing: the double-pay, the misleading reference,
  the skipped step 2, the E+12 Excel corruption, the demo account whose ID broke the 10-digit
  prefix assumption. The module's rules are now owner-verified, not just plan-verified.
- **Read-only simulations before every data-affecting change** (pooler + local code) let the
  owner see exact run compositions (11 payable / 7 already-paid…) before anything was written.
- **Sample-email-from-local** let the owner approve copy in their own inbox with zero deploys.

## What Went Wrong

1. **A `tail -4` on a background test run hid 7 of 18 failures.** Symptom: I "fixed all
   failures", re-ran, and found new ones twice. Root cause: the background task's output file
   only contained the last 4 lines (the command piped through `tail`), so `grep FAILED`
   under-counted; I treated a truncated slice as the full list. Fix: when counting failures,
   capture the FULL output (pipe to `grep -E "^FAILED|passed"`, never `tail`), and reconcile the
   grep count against the summary line before acting. (Recorded in lessons.md.)
2. **The 30/6 backfill imported a payment that had not happened.** Symptom: the owner had to ask
   for the 16/7 "backfill" run to be deleted — that batch was a plan for a FUTURE payment, not
   history. Root cause: the plan (and I) read the owner's CSV as a record of completed payments;
   only live review surfaced that one batch was pending. Fix applied: deleted the run + its 18
   disbursements; the system now generates that payment properly. Systemic lesson: before
   importing "history", confirm with the owner per batch that the money actually moved.
3. **Two separate Google gates for one capability.** Granting the Drive scope in Workspace DWD
   was not enough — the Drive API also had to be enabled in the GCP project (`accessNotConfigured`
   403 after a successful token grant). Cost one extra round-trip with the owner. Fix: recorded
   in lessons.md — check both gates when enabling a new Google API for the service account, and
   probe scopes empirically (token refresh per scope) rather than asking anyone to remember.

## Design Decisions

- **`period_month` on the run, dedup against COMPLETED runs only** — chosen over a recency
  guard (fragile) or calendar-month-of-payment-date (fails the 30/6-pays-July offset). The
  owner picks the month; drafts never block; the source of truth is what was actually paid.
- **CAPS at the model boundary, not at display sites** — the owner explicitly weighed the
  display-helper option (Option A) and rejected it for its in-perpetuity maintenance; the
  declaration signature (`declaration_name`) stays verbatim as the legal record.
- **9-digit prefix + 4 typed digits** — the demo account (`8000400111260`) proved Vircle's IDs
  are not all `8000400175…`; the cohort's are, but the narrower prefix buys headroom while
  still preventing most typos. Validation + fixtures updated everywhere in lockstep.
- **The guardian paragraph is targeted but keeps conditional phrasing** ("If you were born
  after 2008…") — robust to an NRIC misparse: a wrongly-included reader self-filters.

## Numbers

- 6 deploys (each owner-approved or owner-driven); migrations `0102` (migrate-first via MCP).
- Prod data ops: 2 stray drafts + 3 cancelled runs + the 16/7 pseudo-backfill deleted; 20 names
  uppercased; the 30/6 run tagged `period_month=July`; credits (100/100/200) intact throughout.
- Drive chain: DWD Drive scope (owner) + Drive API enabled + `01 BrightPath/03 Vircle/01 Payment`
  walk verified with the service account itself.
- Tests at close: full suite green (see CHANGELOG; ~3,9xx pytest + 573 jest), including new
  coverage for floors, both gates, month dedup, sign-off emails, CSV columns, guardian-note
  selectivity, and the 9-digit prefix.

## Carries

- **Owner:** trigger SRI UMAYAL's award email (`AWARD_EMAIL_APP_IDS=115` + the
  `send-award-offer-emails` job) — the two-step email + her Action-Centre card follow
  automatically. Kulaly generates the real 17/7 July run (11 students, RM2,200).
- **Tamil review** of the restructured award email + `admin.payments.*` + the eWallet-ID
  strings (all first-drafts).
- The Vircle relay sheet still lists the OLD 3-digit guidance in any historical copy; new
  emails/cards all say 4. No action needed unless the owner re-sends old-style instructions.

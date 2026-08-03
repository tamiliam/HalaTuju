# Retrospective — Invitations become a record (sprints 0–2), 2026-08-03

## What was built

Three shipments in one day, each deployed and verified before the next began.

**Sprint 0 — three live faults found by investigating, not by looking for them.**
- A sponsor invite code was **never captured**: `KEY_SPONSOR_REF` had a reader and a cleaner and no
  writer anywhere, so `referrals.attribute_referral(code, …)` could not fire from the live UI. The
  register page dropped it on a second path too.
- `paused_at` reached one of its two readers, so Staff and Reviewers disagreed about who had
  stepped back.
- The witness email told Source Partners to "log in to the partner console" — no such console, and
  the button pointed at a page their role is refused.

**Sprint 1 — the sign-in signal.** `first_seen_at` / `last_seen_at` on `PartnerAdmin`, stamped by
`AdminRoleView`, plus a Supabase backfill. Migration `courses/0069`.

**Sprint 2 (folded with 3) — the `Invitation` record and the Invitations page.** New table with a
derived status, a send record, a PII purge and a partial unique constraint; the page renamed and
rebuilt as a worklist over a roster. Migration `scholarship/0144`.

## What went well

- **Investigating first paid for itself immediately.** The owner asked for an investigation before
  planning. It surfaced three live faults that had nothing to do with the feature, and it changed
  the shape of the work: the central finding — an invitation was not a record — meant "cover
  invitations that are not acted on" was never a display change.
- **The two-kinds-of-partner ruling arrived exactly in time.** The owner corrected Referral Partner
  (platform) vs Source Partner (organisation) on the same day the `audience` enum was being
  written, so the vocabulary went into the schema rather than being retrofitted.
- **Deploying in three small pieces** meant each was verifiable alone. Sprint 1's stamp was
  confirmed working on production (Suresh, 06:31) before anything depended on it.

## What went wrong

**1. I claimed a guard was tested when the test passed without it.**
- *Symptom:* `test_it_reports_first_arrival_ONCE` was described as the guard on the once-only
  acceptance hook. Biting the conditional UPDATE out left it green.
- *Root cause:* the cheap `if admin.first_seen_at is None` short-circuit satisfies the sequential
  case, so nothing exercised the RACE the conditional exists for. I wrote a test for the behaviour I
  had in mind rather than for the mechanism I had written.
- *Fix:* `test_TWO_CALLERS_RACING_still_produce_exactly_one_first_arrival` drives two independent
  instances that both believe they are first; it fails when bitten. **And the general rule: bite
  every guard, because the bite is what distinguishes a test of the mechanism from a test of the
  happy path.** Only the bite caught this.

**2. The page put one person on screen twice.**
- *Symptom:* somebody with an unanswered invitation appeared in the outstanding table AND in their
  category, inflating "Reviewers (13)" with people who had never signed in.
- *Root cause:* I built both tables from the same unfiltered list, having read the owner's approved
  mock as two views rather than two disjoint sets.
- *Fix:* the roster excludes anyone still waiting, with a rendered test asserting exactly one
  occurrence. Caught by a rendered test, which a source-shape guard could not have seen.

**3. My own report conflated the two kinds of partner.**
- *Symptom:* I listed a platform Referral Partner account alongside a staff member as though both
  belonged on the Invitations page. They do not — the `partner` role never appears there.
- *Root cause:* I queried `partner_admins` wholesale for a backfill and then reported the result as
  though the backfill's scope and the page's scope were the same set.
- *Fix:* recorded in `docs/decisions.md` with the two names and the fact that one organisation
  (CUMIG) holds both relationships at once. The backfill's own docstring now states which roles it
  skips and why.

## Design decisions

- **`Invitation` is its own table**, not columns on `PartnerAdmin` — a sponsor invitation must
  create no account at all, and putting invitation state on the access row repeats the mistake being
  undone. Recorded in the model docstring.
- **Status is derived, never stored.** A stored "expired" is true only while a cron keeps it true;
  `temp_password_expired` already fails exactly that way in Supabase metadata nothing reads back.
- **`no_reply` is not `expired`.** A Google or already-registered invitee is issued no password, so
  nothing of theirs can lapse. On production this is the common case, not the edge one: **17 of 18
  staff were invited on Google addresses**, so "expired" will almost never appear.
- **`last_send_ok` is tri-state.** Null is "not recorded" — every backfilled row — never a failure.
- **The write path shipped before the backfill**, and the backfill names it in its docstring.

## Numbers

- `pytest` **5475** · `jest` **1410** · `next lint` 0 errors · i18n **4502 × 3** · build clean.
- Migrations `courses/0069` + `scholarship/0144`, both migrate-first with ledger rows; the new table
  has RLS enabled and one `service_role` policy. Ledger reconciled against production: courses
  **69/69**, scholarship **144/144**, no gaps.
- Production data: 21 staff rows, **19 with a recorded sign-in**, 2 with no Supabase account at all.
  18 invitations backfilled — 17 already accepted, **1 outstanding** (Yeoh Liew Se, invited 21 July,
  `no_reply`). **Zero emails sent by any backfill.**
- Deploys: 3 (api `00939`→`00941`, web `00785`→`00786`).

## Carried

- **ms/ta are first drafts** for the 19 new Invitations leaves.
- Owner: confirm `source_partner` as the role name; the dormancy threshold (90 days assumed); the
  `paused_by` ruling; quote request #2; Divya Adinarayanan's phone number.
- Owner ruled: **do not invite** Yeoh Liew Se, and **no Source Partner has ever been invited** —
  they are passive email recipients, so the console is a cold start.

# Retrospective — v2.26.1: Remove orphaned sponsor register-interest stack (TD-072b)

**Date:** 2026-06-01
**Type:** Cleanup patch (dead-code removal)

## What Was Built

Nothing new — this sprint **removed** the pre-feature sponsor "register interest" lead form
and its entire backend stack, which had been orphaned since the self-serve sponsor auth +
portal shipped (E1c, v2.23.0). Full removal (the user chose **Option B = delete**, not "keep
as a separate lead path"):

- **Frontend:** `app/sponsor/register-interest/page.tsx` (deleted), the `submitSponsorInterest`
  API helper in `lib/api.ts`, and the `sponsorInterest.*` i18n block in all three locales.
- **Backend:** `SponsorInterestView` + `AdminSponsorInterestView` and their two URL routes,
  `SponsorInterestSerializer`, the `SponsorInterest` model (table `sponsor_interests`), and the
  obsolete `test_sponsor_interest.py`.
- **Kept:** `emails.send_sponsor_interest_admin_email` — it had a second caller, the live
  `SponsorRegisterView`, so it stays (the removal pass had to distinguish "dead with the model"
  from "shared").
- **Migration `0035_remove_sponsor_interest`** (DeleteModel) — destructive, applied **deploy-first**.

## What Went Well

- **Verified empty before deleting.** Confirmed `sponsor_interests` held 0 production rows before
  committing to removal — no data-loss risk, and the migration is a clean DROP.
- **The shared-helper trap was caught.** `send_sponsor_interest_admin_email` looked like it belonged
  to the dead stack but is reused by live sponsor registration; grepping callers before deleting kept
  the live email path intact.
- **i18n parity preserved.** Removing 13 keys × 3 locales kept the three message files in lock-step
  (1675 → 1662, equal across en/ms/ta) — the parity check would have flagged a drift.

## What Went Wrong

Nothing broke. One judgement call worth recording:

- **What happened:** The register-interest page sat orphaned for ~1 release cycle (since v2.23.0)
  before removal, tracked only as a low-priority TD row.
- **Why:** When E1c superseded it, the old page was unlinked but not deleted ("decide later") — a
  soft-deprecation that leaves reachable-by-URL dead code and a live admin list pointing at a dead
  model.
- **System change:** When a feature is *superseded* (not just iterated), prefer deleting the old
  path in the same sprint that ships the replacement, or open the removal TD with a concrete
  trigger ("delete once self-serve proven") rather than an open-ended "decide whether to keep".

## Design Decisions

- **Deploy-first ordering for the destructive migration.** Deploys don't run `migrate`; an additive
  migration is applied to prod *before* push, but a DROP must be **after** the code that stops
  referencing the table is live — otherwise the running old image queries a dropped table. So: push
  code first, then `DROP TABLE sponsor_interests` + record the `0035` row in `django_migrations`.
- **Full removal over lead-path retention.** The user confirmed the self-serve flow makes a separate
  "not ready for an account" lead form redundant; keeping it would mean maintaining a second sponsor
  intake surface with its own admin list for no proven need.

## Numbers

- i18n: 1662 keys × 3 locales (was 1675; −13)
- scholarship tests: 410
- jest: 183
- Files touched: 9 modified, 2 deleted, 1 new migration
- Table dropped: `sponsor_interests` (0 rows)

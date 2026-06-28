# Retrospective — Post-award lifecycle Sprint 2: new statuses + re-gate (2026-06-28)

Roadmap `docs/scholarship/post-award-lifecycle-plan.md`. Migration `0074` (additive `closure_reason`
+ status choices). Built on the S2 branch; deploys with the S2 push.

## What Was Built
The status scaffolding for the whole post-award lifecycle: added `awarded`, `active`, `maintenance`,
`closed` to `STATUS_CHOICES`, and a `closure_reason` bucket (graduated/completed/withdrawn/lapsed/
terminated) mirroring the existing `rejection_category` pattern. Dropped the one-release `accepted`
alias from S1 (the 23 rows were migrated, so it's gone everywhere except the unrelated sponsor-feed
event type). Re-gated the consumers that keyed on the single `sponsored` value:
- **Pool discovery** now empties the moment a funder commits — `pool.IN_PROGRAMME_OR_BEYOND`
  (`awarded`/`active`/`maintenance`/`sponsored`/`closed`) excludes from `is_pool_eligible` +
  `eligible_pool_queryset` (was just `== 'sponsored'`).
- **In-programme gate** (`_require_in_programme`) + **progress band** (`derive_progress_state`) now span
  the funded states `pool.FUNDED_STATES` (`active`/`maintenance`/`sponsored`).
- Behaviour sets (DECIDED_STATUSES, QUERYING_LOCKED, _TERMINAL) + admin status maps (colour/order/label,
  i18n en/ms/ta) + `officerCockpit.QUERYING_LOCKED_STATES` learned the four new statuses.
`closure_reason` exposed on `AdminApplicationDetailSerializer` + the web admin type.

## What Went Well
- The S1 expand-contract paid off: dropping the `accepted` alias was a clean mechanical reversal with
  the data already migrated — no window, no data step needed beyond the additive `closure_reason` column.
- Mirroring `rejection_category` for `closure_reason` meant zero new patterns to invent or document.

## What Went Wrong
- **The same un-migrated `ScholarshipCohort.name` drift attached itself to `0074`** (exactly as in S1).
  *Root cause:* the upstream model edit is still un-migrated on `main`, so every `makemigrations`
  re-proposes it. *Fix:* dropped the foreign op again (the S1 lesson already covers this; the durable
  fix is for whoever owns that model edit to ship its own migration). No new lesson — S1's stands.

## Design Decisions (logged in decisions.md)
- A student leaves the discovery pool at **funder-commit (`awarded`+)**, not at `sponsored`.
- `closure_reason` mirrors `rejection_category` (a reason bucket on a terminal status) rather than a
  status-per-outcome.
- `sponsored` is kept VALID through S2 (the award-accept writer isn't rewired until S3) — sequenced to
  avoid breaking award acceptance; retiring it is TD-146.

## Numbers
- Backend `pytest apps/scholarship/tests/`: **1636 passed** (+8 `test_post_award_lifecycle.py`).
  jest **373**. `next build` clean. i18n parity **2880 × 3**. 1 migration (1 additive column + choices).

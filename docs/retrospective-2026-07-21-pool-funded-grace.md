# Retrospective — Sponsor pool: just-funded students linger as "Funded" cards — 2026-07-21

## What Was Built

A funded student now stays visible in the sponsor pool for a grace window (`POOL_FUNDED_GRACE_HOURS`,
default 48h) as a read-only "Funded" card — bar full, no fund button — then drops off. Previously
`fund_student` flipped them to `awarded` and the recommended-only pool query dropped them instantly.

- `pool.display_pool_queryset` = `recommended` ∪ funded-within-window (keyed on `awarded_at`), used by
  the pool list + detail views. The strict `eligible_pool_queryset` (recommended-only) still governs
  fundability, the public waiting-count, auto-sponsor allocation, and notifications.
- `funded` flag on the card serializer; frontend shows a greyed "Funded" chip (card) and a read-only
  funded state (detail) in place of the fund button.

## What Went Well

- **Reused existing machinery.** The funding bar already read `funded_amount / award_amount` and had a
  standing note that it would render full "with no frontend change" the day a funded student appeared —
  so the bar filled to 100% for free. The double-funding guard (`is_fundable` → recommended-only) also
  needed no change; keeping it strict is exactly what prevents a grace-window card being funded twice.
- **Split the query instead of loosening the gate.** Rather than widen `eligible_pool_queryset` (which
  four other call sites depend on — count, auto-sponsor, notifications, an audit command), a NEW
  `display_pool_queryset` was added for the two "what the sponsor sees" surfaces only. A pre-commit grep
  of both function names confirmed nothing else was accidentally widened.
- **No new state.** The 2-day hide is a query-time window on `awarded_at` — no cron, no flag, no
  migration, nothing to write or clean up. A funded student simply falls out once the window passes.

## What Went Wrong

- Nothing broke; full scholarship suite stayed green (2912). No rework this sprint.

## Design Decisions

- **Two querysets (display vs fundable), keyed on `awarded_at`, grace excludes `closed`** — see
  `docs/decisions.md`. The public waiting-count deliberately stays strict (funded excluded) so it reads
  honestly.

## Numbers

- Files touched: 11 (4 backend + 1 settings + 1 test + 5 web incl. 3 i18n). Commit `b0db516e`.
- Tests: full scholarship suite 2912 pass (4 new grace-window tests). No migration.
- Deploy: api + web Cloud Build (both surfaces changed).

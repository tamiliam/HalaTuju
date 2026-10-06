# Retrospective — Sponsor pool: sort unfunded-first + status filter + "Sponsored" — 2026-07-21

## What Was Built

Two discovery-pool display refinements plus a wording change:
1. **Sort** — the pool list orders unfunded (`recommended`) cards ahead of the just-sponsored
   grace-window cards (one list, no separator), newest-relevant-event first within each group.
   Server-side in `SponsorPoolListView` (Case/Coalesce annotations), so no timestamp leaks to the
   anonymised card.
2. **Filter** — a new dropdown (All students / Open for sponsorship / Sponsored) that filters the
   fetched cards client-side on the `funded` flag, matching the existing field/state/amount filters.
3. **Wording** — the sponsor-facing "Funded" chip/body is now "Sponsored" (en/ms/ta).

## What Went Well

- **Reused the `funded` flag** shipped in the previous sprint — the filter needed no new backend field,
  and the sort needed no new data (it keys on existing `awarded_at`/`recommended_at`).
- **Sort server-side, filter client-side — the right split.** The sort needs `awarded_at`/`recommended_at`
  which must not reach the anonymised card, so it belongs in the query; the filter is a pure view over
  already-fetched cards, so it belongs on the client next to the existing dropdowns. No timestamps leaked.
- **Scoped cleanly under pressure.** The request arrived interleaved with a larger label/detail-page
  design discussion on a *different* surface (the My Students portfolio). Keeping this branch to the
  discovery pool only meant it could ship independently while the bigger piece is still in design.

## What Went Wrong

- Nothing broke; full scholarship suite stayed green (2913). The one judgement call — server-side vs
  client-side sort — is recorded in decisions.md so it isn't re-litigated.

## Design Decisions

- **Sort in the query, filter on the client** — see `docs/decisions.md`. The public waiting-count and
  fundability were already split from the display set last sprint, so this only touched the display path.

## Numbers

- Files touched: 6 (2 backend incl. test, 4 web incl. 3 i18n). Commit `93aa9c44`.
- Tests: full scholarship suite 2913 pass (1 new ordering test). No migration.
- Deploy: api + web Cloud Build. Behind `SPONSOR_POOL_ENABLED`.

## Follow-on (next, already scoped in design)

- The **My Students portfolio** label rework (Semester-completed redefined, Needs-attention / Support-paused
  / Discontinued split) + a new **sponsored-student detail page** (full profile, reserved spending space)
  is a separate sprint — mock approved in principle, pending final label wording + a Stitch sign-off.

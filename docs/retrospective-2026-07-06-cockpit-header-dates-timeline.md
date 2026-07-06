# Retrospective — Cockpit header: British dates + lifecycle timeline (2026-07-06)

Two owner requests off a live cockpit screenshot (RUBESHAN, #—): (1) dates render American
`7/5/2026` — make them British DD/MM/YYYY throughout the site; (2) the header should show a lifecycle
timeline — Submitted·Recommended·Awarded once recommended, Awarded·Active·Maintenance once active.
Migration 0094 (four nullable stamps + backfill). ~15 files.

## What Was Built

**British dates (systemic)**
- New shared `lib/formatDate.ts` → `DD/MM/YYYY`, formatted by hand (zero-padded, local tz) so it's
  deterministic and hydration-safe rather than locale-dependent. A bare `toLocaleDateString()` was
  inheriting the server's US locale (month-first) — that was the actual bug. Every numeric date render
  (cockpit header + cool-off banners + verify/reject/verdict/closed chips, admin scholarship/students/
  sponsors lists, sponsor portal + account) now routes through it. Deliberate long-form letter dates
  (consent / award / report — "5 July 2026") were left alone: not ambiguous, not American, formal.

**Lifecycle timeline**
- Four transition stamps on `ScholarshipApplication` — `recommended_at` / `awarded_at` / `active_at` /
  `maintenance_at` — because the transitions recorded the new *status* but no *date*, and there is no
  status-history table. Each is stamped at the transition that MEANS that state (QC-accept + reopen;
  `fund_student`; agreement-executed both paths; first payout), **set-if-null** via a new
  `Application.stamp_first(field)` helper so a reopen / re-award keeps the original date.
- Header chips chosen by a pure `headerTimeline(app)` (jest-tested), labels reuse the existing
  `admin.scholarship.statuses.*` map — no new i18n keys, Tamil already covered.

**Migration 0094 (migrate-first + backfill in one step)**
- Four nullable columns; backfilled 24 `awarded_at` (first sponsorship offer) + 26 `recommended_at`
  (verdict-decided, best proxy). Zero live active/maintenance cases → those stamp forward only.

## What Went Well
- **One screenshot → a systemic fix.** "Dates are American" became a single `formatDate` helper routed
  through every date site, not 17 ad-hoc `'en-GB'` patches; the timeline became real auditable columns,
  not FE-derived guesses (owner explicitly chose real columns).
- **Backfill rode in the same migrate-first step** (lesson from the award-cron sprint): the 24 already-
  awarded students show their award date immediately, not blank.
- **Existing suites already guard the call-site wiring.** A typo'd field name in `stamp_first('…')`
  raises `AttributeError` inside each transition, so the QC / fund / disbursement suites would fail — the
  new tests could focus on the stamp VALUE + set-if-null, which nothing covered.

## What Went Wrong
1. **The "does-not-overwrite on re-entry" test used an unrealistic reverse path.** I simulated a re-award
   with `_revert_to_pool()` then `fund_student()` — which raised `SponsorshipError('not_fundable')`,
   because `_revert_to_pool` only flips the status back to `recommended`; it does NOT cancel the holding
   sponsorship, so the app is still un-fundable. **Root cause:** assuming a helper fully reverses a
   transition without checking its guards. **Fix:** to test a set-if-null invariant, drive the REAL entry
   function (`fund_student`) with the field pre-seeded, and assert it's unchanged — don't reconstruct a
   full reverse cycle whose preconditions you haven't verified. (Applied; green.)
2. **The project-tsconfig type-check surfaced a wall of pre-existing test-file errors that `next build`
   does not gate on.** `tsc --noEmit -p tsconfig.json` reported ~15 errors in `scholarship.test.ts` /
   `soft-evidence-drift.test.ts` / `officerCockpit.test.ts` — none mine. **Root cause:** the project
   tsconfig sets no `target`, so bare `tsc` defaults low and flags `Set` iteration (TS2802), and Next
   *injects* a higher target at build time that the bare invocation doesn't; plus the build's type-check
   effectively tolerates those test files (they've shipped for sprints). Running the raw project config
   over the whole tree is therefore noisy and does NOT mirror the build. **Fix:** type-check with Next's
   injected target AND scope to source — `tsc --noEmit --target es2018 --downlevelIteration --skipLibCheck`
   over `src/**` excluding `__tests__` — to faithfully mirror `next build`; separately eyeball new code
   for the one thing that override masks, a `[...set]` **spread** (none this sprint). This refines the
   2026-07-05 lesson, which said "use the project config" without noting the target-injection gap.

## Design Decisions (see decisions.md)
- Lifecycle dates as real columns (auditable) over FE-derived proxies; `recommended_at` backfilled from
  `verdict_decided_at` as the closest available signal (no true QC-accept timestamp exists historically).
- One `stamp_first` set-if-null helper on the model, folded into each transition's own `update_fields`,
  rather than a status-history table (overkill for a header timeline).

## Numbers
- **Jest 463** (455 + 8) · **scholarship pytest 2102** (2096 + 6). Golden masters untouched (courses).
- **Migration 0094**; 24 + 26 rows backfilled, 0 awarded rows missing a date, migration recorded.

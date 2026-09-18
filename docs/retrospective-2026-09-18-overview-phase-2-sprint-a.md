# Retrospective — Programme Overview phase 2, Sprint A (2026-09-18)

The organisation chooses which Overview panels show, and any role can narrow the page to one
intake round. Owner rulings before a line was written: per organisation, not per person; filter
first, switches second, drag-and-drop later (Sprint B).

## What Was Built

- **`OrganisationOverviewLayout`** — one row per organisation, an ordered `[{key, on}]` over the
  five widgets; migration `0161` applied to production migrate-first with RLS (ledger 161 = 161).
  The model's `save()` validates, so the fence is on the row, not on the endpoint.
- **`overview_layout.apply`** narrows and orders a role's sections and never widens; `mine` and
  `qc` are pages, not widgets. `build()` emits `sections` in layout order, `intake`/`intakes` on
  every payload, `layout` for org_admin/super only.
- **`?intake=<cohort id>`** narrows everything inside the fence (`_AdminBase._intake_narrowing`,
  404 for a round the caller may not see).
- **`AdminOverviewLayoutView`** GET/PUT, org_admin + super, all-or-nothing, one compact audit line.
- **Web:** Customise mode (switch per panel, the console's one save bar), the page renders
  `data.sections` in the server's order, an intake picker, the seven section blocks moved into
  `OverviewSections.tsx` unchanged; 31 locale keys ×3; manual, FAQ, role matrix, roadmap.

## What Went Well

- **Two halves built in parallel against a written contract.** The payload contract in the plan
  was exact enough that the web agent coded against it before the backend existed, and the two
  met without a single field renamed.
- **The migrate-first step was uneventful**: table, RLS, policy and ledger row checked in one
  query; the Security Advisor reported nothing new.
- **Nine bites, nine caught** (five backend, four web), including the two that matter most: a
  layout that widens, and a cross-tenant round answered with 403 instead of 404.
- **Merged `main` first, then gated** — the lesson from the 15th, applied twice today.

## What Went Wrong

1. **`get_or_create` created an EMPTY row first and the model's own fence refused it.**
   - *What happened:* the first PUT 500'd; the validator raised `missing_section` on the empty
     list the row was created with before the update.
   - *Root cause:* a fence on `save()` runs on the CREATE too, and `get_or_create` without
     `defaults=` saves a blank row.
   - *System change:* `defaults={'sections': …}` carries the list into the create; the test for
     the endpoint's happy path caught it on the first run. Noted in the view's comment.

2. **The old `intake` block's absence test had to be rewritten, not deleted.**
   - *What happened:* round six pinned "`intake` is not on the payload"; Sprint A puts an
     `intake` key back with a different meaning (the picker's echo).
   - *Root cause:* a key name was reused for a different fact three days apart.
   - *System change:* the test now asserts the old block's SHAPE (its window and switch) is gone
     and the new echo's shape is present. No lesson — a naming choice, recorded here.

3. **Two shell heredocs failed on quoting** and cost two round-trips; the fix each time was a
   scratchpad script file. Already the house pattern; noted as a reminder, not a lesson.

## Design Decisions

Recorded in `docs/decisions.md` (2026-09-18): the layout narrows and orders, never widens; under
an intake filter everything narrows, the money strip included.

## Numbers

- 31 files (10 backend, 12 web, 9 docs); one migration.
- **6714 pytest** (+27) · **2354 jest** (+38) · tsc 24 baseline · lint 0 · `check-i18n` pass ·
  `next build` exit 0.
- Bite-checks: 9 injected, 9 caught.
- Deploy: see the `Next Sprint` block in `halatuju_api/CLAUDE.md`.
- No time estimate was given, so there is no planned-versus-actual figure.

# Retrospective — Student self-serve income route switch (2026-06-12)

Sprint deliverable from the live-review backlog: a submitted student stuck on the wrong income
route (the #16 / "I have no STR" case) can switch it themselves from the Action Centre. BE + FE +
i18n, **no migration**. Shipped to `main` (`e1aff91`).

## What Was Built

- **Audited endpoint** `POST /api/v1/scholarship/applications/<id>/income-route/`
  (`IncomeRouteSwitchView`) + `services.switch_income_route` — own application, allowed across the
  editable + post-submit funnel (`POST_SHORTLIST_EDITABLE`). Flips `income_route` both ways
  (STR ↔ salary), sets the route's identifying fields (STR → `income_earner`, salary →
  `income_working_members`, clearing the inactive one), audits to the structured log, and calls
  `sync_resolution_items` so the old route's gap auto-resolves and the new route's document tasks
  appear. Returns the new route + `income_requirements`.
- **`IncomeRouteSwitchSerializer`** mirrors `incomeWizard.wizardComplete`: STR needs an earner;
  salary needs ≥1 working member (no duplicates).
- **FE `IncomeRouteSwitch`** — a self-contained mini-wizard mounted ONCE in the Action Centre when
  an income task is open post-submit (one entry for the whole income section, not per-ticket). Route
  choice → STR (whose name) or "We don't receive STR" (who works) → confirm → `switchIncomeRoute`
  client → refetch tasks. Built to the Stitch-approved, owner-corrected copy.

## What Went Well

- **Lesson #2 (enumerate every emitter of a shared code) caught the real trap before any code.**
  Tracing the route flip through `income_requirements` → details PATCH revealed that the obvious
  implementation (reuse the details PATCH to write `income_route`) would call
  `revert_if_profile_incomplete` and silently **un-submit** the student the instant the switch created
  a new requirement. That single trace turned "reuse the endpoint" into "build a dedicated one that
  never reverts" — the core design decision.
- **Backend-first while Stitch rendered.** The Stitch-first rule gates FE templates, not the API, so
  the endpoint + service + serializer + 11 tests + the API client were all built and green while the
  (flaky, ~5-min) Stitch render was in flight. No idle waiting.
- **The 11 APIClient tests are a real integration check** — they exercise the full
  request → switch → `sync_resolution_items` recompute path on the real ORM, including the no-re-block
  guarantee (a switch that creates new tasks keeps the student `profile_complete`).

## What Went Wrong

- **The first Stitch render had three copy/structure errors** (it said STR "simplifies", showed the
  salary "who works" chips under the STR option instead of STR's three earner options, and labelled
  the salary route "salary slips or EPF"). Symptom: a mockup that mis-framed the routes. Root cause:
  the generation prompt described the salary option by its documents ("salary slips or EPF") and
  didn't make the STR follow-up conditional, so Gemini rendered a blended card. Fix: the owner caught
  all three on review (exactly why the Stitch-first gate exists); the corrected copy frames the choice
  as STR-or-not and shows only the selected route's follow-up. **System note:** when prompting Stitch
  for a branching form, describe each branch's follow-up explicitly and avoid naming documents in the
  route-choice labels.
- **`list_screens` did not surface the new render for ~5 min** (the known Stitch eventual-consistency
  gotcha). Mitigated by waiting and fetching by title; no blind re-trigger. Already in
  `stitch_mcp_workflow.md`.

## Design Decisions

See `docs/decisions.md`:
- "Post-submit income route switch is a dedicated endpoint, not the details PATCH (no submission revert)".
- "Income route-switch audit is a structured log line, not a DB model (no migration)".

## Numbers

- 11 new backend tests (1167 scholarship pytest) · 303 jest · i18n parity 2560×3 · `next build` clean.
- 13 files, no migration. Verified via APIClient integration tests on the real ORM (both directions,
  validation, auth/scope/gate, audit, no-re-block).

## Deferred / Carried

- **Live browser click-through (TD).** The endpoint is integration-tested and the FE type-checks, but
  the in-browser switch flow on a real post-submit student isn't click-tested (the project's standard
  TD-070 pattern — verified on prod after deploy).
- **Salary-slip is a soft signal, not a hard task (TD).** Switching to the salary route tickets the
  earner IC + relationship docs, but a missing salary slip stays "assess at interview" (no Action-Centre
  task) — by design. The wizard's "we'll show you which documents to upload" sets the expectation. If
  stronger prompting is wanted, ticketing the salary slip is a small follow-up that touches the
  post-submit income policy (needs sign-off — it reopens the "never hard-block post-submit" line).
- **Tamil refine** of the new `incomeRouteSwitch.*` block (first-draft).

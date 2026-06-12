# Sprint plan — Student self-serve income route-switch

**Approved scope (owner, 2026-06-12):** BOTH directions; AUDIT-LOG ONLY (no officer pre-interview flag).
No migration. Single sprint, single agent. UI is **Stitch-first** before any template code.

## Problem
A submitted student on the wrong income route is stuck: `income_route` is only writable while
`status='shortlisted'` (details PATCH gates on `POST_SHORTLIST_EDITABLE`, `views.py:146`), the
/application form is locked post-submit (Action-Centre-only), and no switch endpoint exists. The
reported case: an STR-route student with no STR is told "Upload your STR" with no exit.

## Deliverable
A neutral **"Change how you prove your income"** action in the Action Centre that re-runs the income
mini-wizard in place, flips the route both ways (STR↔salary), and surfaces the new route's document
tickets — recomputed from the single source of truth (`income_engine.income_requirements`).

## Design
### Backend
- New endpoint `POST /api/v1/scholarship/applications/<id>/income-route/` — own-application
  (`SupabaseIsAuthenticated` + profile scope), allowed in the post-submit statuses
  (`profile_complete`/`interviewing`/`interviewed`) AND the shortlisted-era set. Body:
  `{income_route, income_earner?, income_working_members?}`.
- `services.switch_income_route(app, *, route, earner, members, by)` — validates route/earner/members
  (reuse the serializer choices), writes the fields, writes an **audit** record (mirror
  `AssignmentEvent`/the existing audit pattern — a `{from_route → to_route, by, at}` row), then calls
  `sync_resolution_items(app)`. Returns the refreshed open items + `income_requirements`.
- Narrow `IncomeRouteSwitchSerializer` (route + optional earner + optional working_members; validate
  earner required for STR, ≥1 member for salary — mirror `incomeWizard.wizardComplete`).
- **NOT** relaxing the broad details PATCH (writes the whole Story/funding bundle; shortlisted-only by
  design). A dedicated audited endpoint keeps this eligibility-touching change deterministic/auditable.

### Frontend
- Action Centre: a secondary "Change how you prove your income" link on the income doc ticket(s)
  (`income_proof_missing` on STR; `salary_slip_missing`/`earner_ic_missing` on salary). Opens an
  in-place mini-wizard reusing the pure `incomeWizard.ts` helpers (route Q → earner [STR] / member
  multi-select [salary]). On submit → `switchIncomeRoute()` client → refetch tickets.
- Reuse, don't rebuild: lean on `incomeWizard.ts` (`incomeRequirements`, `salaryMemberBlocks`,
  `wizardComplete`, `relationshipDocFor`). Extract a slim `<IncomeRouteWizard>` if the existing
  `IncomeWizard` (ScholarshipDocuments.tsx:921) can't be mounted standalone cleanly.

### i18n / tests
- en/ms/ta: the CTA, the mini-wizard prompts in the Action-Centre context, a confirm/success line.
- Backend tests (`tests/test_income_route_switch.py`): auth + own-scope; allowed post-submit, blocked
  for non-owner; STR→salary flips route + closes `income_proof_missing` + opens salary tickets;
  salary→STR reverse; validation (earner required for STR, ≥1 member for salary); audit row written.
- jest: the mini-wizard renders + calls the client. i18n parity.

## Lessons applied (from docs/lessons.md — MANDATORY notes)
1. **FE+BE needs a self-contained local stack, not "local FE → prod API."** Verify on a local backend
   (SQLite) + the prod **pooler** for real-data checks (aws-1). Do not point local FE at the live API.
2. **Relaxing/changing a gate that emits a shared code → enumerate every emitter.** A route flip ripples
   through `income_requirements` → `consent_blockers` (services), the verdict (`verdict_engine._verdict_income`
   / `_verdict_income_salary`), and `resolution.sync_resolution_items`. Trace all three; prove a switch
   recomputes cleanly (old ticket auto-resolves, new tickets appear) and CANNOT re-block an already-submitted
   student (the consent gate already passed; post-submit gaps are Check-2 tickets, not submission blockers).
3. **Route-specific requirement needs route-specific copy** (just shipped). The salary-route tickets must
   keep member-specific wording after the switch.
4. **Kill orphan node.exe before `next build`** on a long Windows session.

## Decision revisited
"`income_route` editable only while shortlisted" (POST_SHORTLIST gate) — relaxed ONLY via this audited
income-route endpoint, ONLY for the income fields, post-submit. Reason: the route-switch feature. Log in
decisions.md at close.

## Stitch (before coding the FE)
HalaTuju Stitch project = 10844973747787673276. Prototype the in-Action-Centre route-switch flow
(entry CTA + route question + the two follow-ups). Get visual approval before writing templates.

## Files (~12–16, no migration)
BE: `views.py` (+endpoint), `urls.py`, `services.py` (switch helper + audit), `serializers.py`
(IncomeRouteSwitchSerializer), `models.py` (audit row if no reusable model), `tests/test_income_route_switch.py`.
FE: `ActionCentre.tsx`, a route-switch component, `lib/api.ts` (client), `lib/incomeWizard.ts` (expose helper
if needed), `messages/{en,ms,ta}.json`, a jest test. + Stitch screen.

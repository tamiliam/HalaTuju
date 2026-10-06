# Retrospective — Now sprint 1 (2026-10-01): TD-255 and TD-257

**Scope (owner: "let's do the 11 first"; the lead chose these two to start):** move production web
off Node 18, and drive the wired admin endpoints no test had ever sent a request to. Built by one
agent; an adversarial reviewer who did not build it reads the diff before the lead commits, pushes
or deploys. No product code changed in Part 2; no migration; no ledger raised.

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-255 | Node **24** (Active LTS) in all four homes at once: `Dockerfile` `FROM node:24-alpine` (the `deps`/`builder`/`runner` stages build `FROM base`), `cloudbuild.yaml` test step `node:24-alpine`, new `.nvmrc` (`24`), `engines.node >=24` | `nodeVersion.test.ts` (3): one major in four places, floor 22 |
| TD-257 money | schedule a tranche; release / withhold / return / mark_due with each precondition; the on-hold brake; close | `test_endpoints_disbursements.py` (21) |
| TD-257 brakes | hold-award; reporting-date + its AUDIT line; sponsor membership | `test_endpoints_cooloff.py` (11) |
| TD-257 Requests | requote, modify, decline, ask, schedule, done | `test_endpoints_requests_verbs.py` (19) |
| TD-257 terms | sections PUT, generate-quiz, import-docx (a real Word file), the graduation relay | `test_endpoints_sponsor_terms.py` (12) |
| TD-257 applicant | verdict-summary, referee DELETE, document help | `test_endpoints_applicant_data.py` (10) |

**Why 24 and not 22.** Next 14.2.0's `engines` is `>=18.17.0`; a scan of all 785 installed
packages found none whose `engines.node` excludes 24 (or 22); the dev box has run jest and
`next build` on 24.13 every day. The lockfile is unchanged and `npm ci --dry-run` passes its sync
check, so the image installs exactly what it installed before.

**How the funded cases are made.** Not `status='active'`. The factory takes a case to `recommended`;
then a sponsor with money in that gift funds it (`fund_student`) and the student accepts
(`respond_to_award`) — with `AWARD_COOLOFF_DAYS=0` that finalises to `active` (the flag-off
production path), with 2 it stays `awarded` inside the window `hold-award` works in. That is what
let the tests assert the one thing a hand-set row cannot carry: the tranche links itself to the LIVE
sponsorship, and a held award puts the money back in the sponsor's wallet. No
`ScholarshipApplication` is hand-built; `hand_built_application_fixtures` is untouched.

## What bit

| Bite | Test | Result | Restore |
|---|---|---|---|
| guard: cloudbuild test image put back to `node:18-alpine` | `nodeVersion.test.ts` | RED (2 of 3) | SHA equal |
| `disbursement.schedule_tranche` -> `return None` | `test_the_assigned_reviewer_schedules_a_tranche_linked_to_the_live_sponsorship` | RED | SHA equal |
| `disbursement.release_tranche` -> return the row untouched | `test_mark_due_then_release_pays_the_tranche_and_moves_the_case_to_maintenance` | RED | SHA equal |
| `sponsorship.hold_pending_award` -> `return True` | `test_a_held_award_goes_back_to_the_pool_and_the_money_back_to_the_sponsor` | RED | SHA equal |
| `org_requests.requote` -> `return req` | `test_the_owner_requotes_a_deferred_request` | RED | SHA equal |

Each edit was made from a byte backup, the digest printed before the edit and after the restore.

## What is left, and why

- **One TD-219 ledger line: `applications/<pk>/interview-slots/<slot_id>/` (DELETE).** No screen
  calls it — `withdrawInterviewSlot` in `halatuju-web/src/lib/admin-api/interviews.ts` is exported,
  re-exported from `lib/admin-api.ts`, and called by nothing; no cron or command reaches the view. The
  brief said to report a dead route rather than test it for its own sake. The ledger comment now
  says so. **Owner/lead decision:** wire it into the cockpit (and test it), or delete the route
  (which empties the ledger and closes TD-257). TD-257 stays open on a dated Status line until then.
- **TD-255's local image proof.** There is no `docker` on the dev box, so the image was not built
  and no Playwright smoke ran on it. The deploy gate is the first run on `node:24-alpine`; the lead
  watches the `test` step, the `Build` step and the new revision. The live trigger needs no edit (it
  reads `filename: halatuju-web/cloudbuild.yaml`; the rollback export names no Node image).

**Follow-up, same day (owner's ruling): the dead route was DELETED** — route, view,
`scheduling.withdraw_slot`, its org-fence classification and the unused web client — so TD-257
closed with an EMPTY ledger, held by `test_the_ledger_stays_empty` and a ≥ 190-route floor (199
today; the "≥ 200" in the brief would have failed on day one, since the deletion itself took the
count from 200 to 199).

## What was learnt

- **Five of the twenty "untested" routes had in fact been REQUESTED before, and that is the guard's
  documented blind spot, not a defect.** `requote`, `modify`, `decline`, `schedule` and `done`
  were all named in `TestFlagOff.test_every_route_404` — inside a list the AST scan cannot
  reconstruct — so they read as unexercised; even if the scan had seen them, a 404 behind a dark flag
  never reaches the service. This is exactly blind spot 1 in the guard's own docstring. Nothing new
  for lessons.md: the TD-219 lesson already says a route-in-a-sweep is not a route that was driven.
- Two small fixture surprises, both caught by the first run: `maintenance_substate` defaults to
  `on_track`, not blank; the coach upper-cases the first name in its prompt (`KAVITHA`). Neither is a
  lesson; both are recorded in the assertions.

## Gates

| Gate | Before | After |
|---|---|---|
| `node -v` / `npm -v` | v24.13.0 / 11.6.2 | same (the dev box was already on 24) |
| api pytest (whole suite, `-n auto`) | 7,373 / 3 skipped (lead's baseline) | **7,446 / 3 skipped, 0 FAILED** (+73) |
| `test_endpoint_exercise.py` + `test_code_standards.py` | 57 passed | 57 passed (+ the register test, 60) |
| `manage.py check` | — | no issues |
| web `npm run gates` | jest 3,236 / 193 (lead's baseline) | **jest 3,239 / 194** (+3, `nodeVersion.test.ts`); tsc, lint, i18n clean |
| `npm run bundle-budget` | — | ok; `/profile` 310 (line 310), `/scholarship/apply` 271 (line 272), `/scholarship/application` 273 (line 274); median 227 vs 229 — unchanged |
| `code_health.py` td_open | 133 | **132** = the index |

## Time

Planned in the register: ~3 h (TD-255) + ~10 h (TD-257, five clusters at ~2 h) = ~13 h. Spent: one
builder session, most of its wall time in the whole api suite (~10.5 min), two web gate runs and
the `next build`. No re-scope, except that one of TD-257's twenty-one routes was reported instead of
tested, as the brief directed.

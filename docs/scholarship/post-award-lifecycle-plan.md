# Post-award student lifecycle — roadmap

**Approved 2026-06-28.** Extends the B40 pipeline past acceptance into a full funded-student
lifecycle. No single-sprint big bang — ships incrementally, mostly dark, near-zero live risk
(the post-award programme is dormant today; no real award accepted on prod, money rails unbuilt).

## The state machine

```
recommended → awarded → active → maintenance ─────────────→ closed
 (renamed       (offer +   (executed,  (funded; sub-states:    (MANUAL; closure_reason:
  accepted;      4-step     awaiting    on_track / probation /  graduated / completed /
  masked from    signing)   first       on_hold / ready-to-close) withdrawn / lapsed / terminated)
  student)                  payout)
              └ signing order: student → guarantor → witness → Foundation (executes last) ┘
                                                                  ↑ thank-you invited here, allowed after closed too
```

- **recommended** (rename of `accepted`): reviewer recommends; provisional; **masked** from the
  student (they keep seeing "in review") because it is reversible and no award is guaranteed yet.
- **awarded**: a funder commits (sponsor selects / Foundation allocates); the tri-partite bursary
  agreement is signed in order. Foundation's signature is **last and binding** → flips to active.
- **active**: fully executed, awaiting the first payout (the finance queue).
- **maintenance**: first tranche disbursed; the recurring per-semester loop. Sub-states:
  on_track / probation(at-risk) / on_hold(paused, resumable) / ready-to-close(fulfilled or graduated).
- **closed**: a deliberate **manual** admin close + `closure_reason`. `graduated` (finished the
  programme) and `completed` (contractual support period fulfilled — programme may continue) are both
  positive. Thank-you note invited at the closing point, allowed before AND after closure.

## Transition triggers

| Trigger | Status |
|---|---|
| Reviewer verify-&-recommend | recommended (masked) |
| Funder commits (sponsor / Foundation) | awarded |
| All signatures complete (Foundation executes last) | active |
| First tranche disbursed | maintenance |
| Support fulfilled / final result | maintenance sub-state: ready-to-close |
| Admin confirms closure (manual) | closed (+ reason) |

## External blockers (gate going LIVE, not building)
- **TD-140** — bursary lawyer-vet + Foundation entity → gates live signing (Sprint 3 ships dark behind
  `BURSARY_AGREEMENT_ENABLED`).
- **TD-075** — real money / toyyibPay → gates real disbursement (Sprint 4 builds the ledger + manual
  disburse; real rails deferred).

## Cross-cutting build rules
- Migrate-first via Supabase MCP (deploy does NOT run migrate); RLS on any new table.
- i18n en/ms/ta parity; Tamil first-draft acceptable, refine queued.
- HalaTuju deploys are owner-gated (push = deploy). Work in a worktree; another agent shares the repo.
- Sprint 1 **supersedes the unmerged `feat/mask-accepted-status` branch** — the student-masking change
  folds in here, retargeted `accepted → recommended`.

## Sprints — ALL SHIPPED (S1–S6, 2026-06-28)

The full `recommended → awarded → active → maintenance → closed` arc is live (dark). Per-sprint
detail lives in the retrospectives (`docs/retrospective-2026-06-28-post-award-s{1..6}-*.md`); the
migrations are `0073`–`0078`. Summary:

- **S1** — rename `accepted → recommended` (+ student masking). Migration `0073`.
- **S2** — new statuses `awarded`/`active`/`maintenance`/`closed` + `closure_reason`; re-gate pool /
  progress / in-programme; retire `sponsored` groundwork. Migration `0074`.
- **S3** — `awarded` + 4-step bursary signing (dark, flag-gated) → `active`; `sponsored` retired.
  Migration `0075`.
- **S4** — disbursement/tranche ledger; first release flips `active → maintenance`. Migration `0076`.
- **S5** — maintenance sub-states (on_track/probation/on_hold/ready_to_close); `on_hold` pauses
  releases. Migration `0077`.
- **S6** — manual closure + `closure_reason` + audit stamp; thank-you relay survives closure.
  Migration `0078`.

## Go-live (still gated — building was always decoupled from launching)
- **TD-140** — bursary lawyer-vet + Foundation entity → gates `BURSARY_AGREEMENT_ENABLED`.
- **TD-075** — real money / toyyibPay → gates real disbursement (the ledger is a mock until then).
- **TD-147** — retire the recurring `scholarshipcohort.name` migration drift (a standalone state-only
  migration), so future `makemigrations` is clean.

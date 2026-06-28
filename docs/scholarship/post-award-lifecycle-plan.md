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

## Sprints

### Sprint 1 — Rename `accepted` → `recommended` (+ fold in masking)
Behaviour-neutral rename + data migration. Scope: STATUS_CHOICES; sweep all `accepted` refs
(services/views `AdminVerifyAcceptView`/serializers mask/reopen/pool/frontend page+banner+cockpit/i18n);
`UPDATE status='accepted'→'recommended'`; verify-&-recommend copy. Complexity: Medium.

### Sprint 2 — New-status scaffolding + re-gate consumers
Add awarded/active/maintenance/closed + `closure_reason`; migrate existing `sponsored` rows
(expected 0 — verify) → maintenance, retire `sponsored` (expand-contract); re-gate
`pool.is_pool_eligible` / `derive_progress_state` / `in_programme._require_in_programme`; status
labels + masking confirm. Complexity: Medium-high.

### Sprint 3 — `awarded` + 4-step signing (dark, flag-gated)
Funder-commit → awarded; signing sub-states (student→guarantor→witness→Foundation) derived from the
existing bursary timestamps; enforce order; Foundation execution → active; cockpit progress card.
Behind `BURSARY_AGREEMENT_ENABLED`. Complexity: Medium.

### Sprint 6 — Manual closure + reasons + thank-you re-gating
Admin close (manual) → closed + closure_reason + offboarding checklist; graduated-vs-completed copy;
re-gate the graduation/thank-you relay to allow during ready-to-close and after closed. Complexity: Low-medium.

## Sequence & rationale
Dependency then risk: 1 (rename, de-risk) → 2 (status model everything needs) → 3 → 4 → 5 → 6 walk the
lifecycle forward, each a vertical demonstrable slice. Money sits at 4 (maintenance needs a disbursement
state to loop over) but defers the real gateway.

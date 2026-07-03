# V5 re-banding summary — owner checkpoint before deploy (2026-07-04)

V5 changes how some verdict tiles band and adds a QC gap floor. Roadmap gate: **the owner
sees this before the code ships** (the change is reviewer-visible). Prod queried live via
Supabase MCP (project `pbrrlyoyyiftckqvzvvo`) at authoring time.

**The verdict is computed live (`build_verdict`), not stored** — it can't be recomputed in
SQL. So the counts below use the stored proxies (system resolution items + the
`ai_verdict_snapshot` captured at each decision) to bound *who could* move; the authoritative
picture is the live cockpit after deploy.

## 1. Route-seam re-banding (V5.1) — effectively ZERO disruptive live impact

Three tile-band changes, and every current carrier is a closed or already-cleared case:

| Change | Old band | New band | Live carriers found | Verdict |
|---|---|---|---|---|
| Salary route, household income clearly **over the B40 line** | 🟡 amber (`recommend`) | 🔴 red (`gap`) | #11, #67, #87 — **all `rejected`** | No live effect (closed cases) |
| STR **recipient ≠ earner** (positive name/NRIC mismatch) | 🔵 blue (`review`) | 🟡 amber (`recommend`) | #51 — item **resolved**, app `interviewed` | Item already cleared; no live mismatch |
| **Wrong-person offer letter** (name/IC not the applicant's) | amber via empty-evidence `review` | 🟡 amber, explicit `recommend` | #6, #16 — items **resolved**, both `awarded` | Colour unchanged; just made explicit |

**Net:** no live application re-bands into a worse-looking state as a surprise. The over-line
salary apps that *did* band this way are already rejected; the STR/offer mismatch items are all
resolved. This is a **forward-looking** correctness/consistency change — future apps hitting
these conditions band per the single route-seam truth table (`str-proof-spec.md` §8), removing
the old three-way seam inconsistency.

## 2. QC gap floor (V5.2) — the material live change

QC-Accept is now **refused while any verdict fact is red (`gap`)**; a **super** may override
**with a recorded reason**. This is the audit #5 fix (owner decision 1): a red income/identity/
pathway fact must not reach `recommended` + sponsor publication unexamined.

**Who it gates now — the 10 apps currently awaiting QC (`interviewed`):**

> #20, #21 (salary route); #33, #35, #51, #53, #62, #72, #75, #76 (STR route) — all assigned.

I can't compute each one's live verdict in SQL (needs the engine + prod Storage). The
operational consequence for whoever QCs these (Suresh):

- On an app whose four tiles are all green/amber/blue → **Accept works as before.**
- On an app with a **red tile** → **Accept is blocked**, the cockpit lists which fact is red;
  the fix is to resolve the gap (get the missing/unreadable doc) **or**, if a super and the
  case is genuinely sound on offline evidence, use **"Record reason & accept"** (the reason is
  saved on the case).

This is the intended tightening — before V5 a reviewer's accept could carry a red fact straight
to the pool. Nothing auto-changes on these 10; the floor only bites at the next QC-Accept click.

## 3. What deploys with this

- **Migration 0092** (additive: `qc_override_reason`, `qc_override_by`, `qc_override_at` on
  `scholarship_applications`) — applied **migrate-first** before the code push (backward
  compatible; the live old code ignores the new columns).
- Code: the engine re-banding + QC floor + the SOFT_EVIDENCE guard test + doc/spec updates.
- Tamil strings for the QC floor UI are **my first draft** — flag for your review (they're
  officer-facing, low-traffic, and behind the super/QC role).

**Approve to proceed** → I apply 0092 migrate-first, then push (which deploys both services).

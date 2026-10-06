# Retrospective — Income Check-1: multi-earner + per-document verification arc

**Date:** 2026-06-05 · **Migration:** `0040` (additive, migrate-first) · **Commits:** `e197209`→`668676b` (11) on
`main` · **Status:** SHIPPED + DEPLOYED to prod.

This is the close retro for the whole income arc, which grew well beyond the original "single→multi-earner" scope it
started as (the stub written at `c83497d`). Income was the weakest of the four Check-1 facts; it is now the most
thorough.

## What was built
1. **Salary (non-STR) route → multi-select.** "Tick everyone who works" (father / mother / legal guardian / elder
   brother / elder sister), each contributing their own IC + salary slip + EPF. A `household_member` tag on
   `ApplicantDocument` lets several people's same-type docs coexist; single-instance is now per `(doc_type, member)`.
   New `income_working_members` JSON on `ScholarshipApplication`. Migration `0040`.
2. **Per-document IC / proof verification** to the Identity standard, but with **relationship** semantics: each income
   IC (`parent_ic`) shows IC No · Name · Address with a "linked to your family" badge (the earner's NRIC is shown for
   reference, **never** matched to the student); each salary slip / EPF / STR is read for name + **NRIC** + amount +
   period and cross-checked against *that member's* IC.
3. **Cluster-aware Cikgu Gopal** — one coach per member cluster, anchored on the member's IC, reasoning across
   relationship + coherence (is the IC + payslip the same person?) + completeness (a proof with no IC → "add their IC").
4. **STR document verification** — recipient name + IC + currency (status + year). STR is awarded annually, so a stale
   / rejected STR no longer auto-greens; STR-route green = the whole cluster adds up.
5. **I4 — per-capita amount gate.** Salary route goes `verified` only when the summed earner pay (payslip gross, or
   ≈24% of the EPF monthly contribution) ÷ household size clears `per_capita_ceiling` (RM1,584); at/above →
   `recommend` + interview, never auto-rejected.
6. **EPF facts** split (monthly contribution = income vs total accumulated vs year — "CARUMAN SEMASA" / "Tiada
   Transaksi") and **utility bills** (address check, current charge not arrears-total, unpaid-balance hardship) as
   officer-facing **soft signals**, never verdict gates.
7. **Birth-certificate + guardianship-letter checklists** surfaced (were used in the verdict but never shown).
8. **Single-instance everything** — a re-upload replaces in the same `(doc_type, member)` slot (user's call,
   superseding the S15 multi-instance salary/EPF decision).

## What went well
- **The `household_member` tag instead of ~15 new per-member doc types** kept the entire upload / OCR / verdict /
  serializer machinery intact — the multi-earner rebuild touched storage, not the pipeline.
- **Siblings verify for free via the shared patronymic** — an elder brother's IC carries the same father's name as the
  student, so `income_engine.father_relationship` works unchanged on siblings. Closed the borrowed-payslip hole with no
  special rule and no extra sibling document.
- **Route-aware `_cluster_docs(application, member, doc_type)`** unified the STR route (one untagged earner) and the
  salary route (tagged per member) so every income check works on both without a frontend change or an STR retag.
- **Migrate-first discipline held** — `0040` applied via Supabase MCP (two additive `ALTER`s + recorded migration row)
  before the deploy; verified columns on the right custom `db_table`.

## What went wrong
1. **The income verdict is wizard-route-driven, not document-driven — discovered only in live testing (app #21).**
   - *What happened:* a real STR-recipient student (`receives_str=true`, so the wizard defaulted `income_route='str'`)
     uploaded his father's **salary slip** instead of an STR screenshot. The earner relationship was confirmed (father's
     IC present) but the Income tile showed red *"no proof of income"* — the STR branch of `_verdict_income` only
     accepts an `str` document, so the payslip sitting in the drawer was ignored.
   - *Why it happened:* the income verdict was designed around the wizard answers (route / earner / member tags) as
     **hard gates**, on the assumption the student uploads exactly what the route expects. It trusts the declared route
     over what is actually in the drawer. The whole pipeline, moreover, submitted **before** the wizard existed, so 6
     submitted apps have `income_route=''` and untagged docs that the new cluster keying can't assemble.
   - *System change:* logged as **TD-085** (the user's explicit next sprint) — make the verdict **document-first**
     (verify whatever income proof exists, tagged or not, against the available parent ICs, with the wizard answers as
     hints not gates), backfill the 6 blank-route apps, and redesign the income cockpit tile so it never says "no proof"
     when a verified doc is present. Cross-cutting lesson added: a verdict that gates on *declared intent* must fall back
     to *observed evidence*, and any new gating field needs a legacy-data audit before it ships.
2. **The retro stub was written at the first commit and never updated mid-arc** — at close it described an arc 8×
   smaller than what shipped (it still listed I4 as "deferred" when I4 had landed). *System change:* don't pre-write a
   retro at sprint start as a stub; write it at close from the actual commit range.
3. **Test breakage from the per-capita gate landing after the multi-earner tests** — two multi-earner tests went red
   when I4's per-capita gate was added (they had no income amounts, so per-capita couldn't compute < ceiling). Fixed by
   giving them `gross_income` / `monthly_contribution`. *Root cause:* the verdict's "verified" precondition tightened
   under a later commit; the earlier tests encoded the looser contract. Acceptable within one arc, but a reminder that
   stacking verdict preconditions invalidates earlier same-arc fixtures.

## Design decisions (settled with the user)
1. **Siblings verify via the shared patronymic** — no special sibling rule, no extra doc.
2. **Dropped the forced non-earner-parent EPF** — EPF only exists for formal jobs; near-zero signal, real friction.
3. **Never-block by inference** — IC present + no payslip/EPF → informal → `recommend` + interview, never `gap`.
4. **"Verified" = the document DATA checks out** (identities + relationships + the per-capita amount now); the officer
   still owns the final B40 placement at interview for the recommend cases.
5. **Single-instance everything** (replace on re-upload) — "keep it simple", superseding S15 multi-instance.
6. **Soft signals stay soft** — utility per-capita + arrears are officer-facing evidence, never verdict drivers.

## Numbers
- **687 scholarship pytest + 250 jest** · 1037 courses/reports pytest (untouched) = **1724 pytest + 250 jest** total.
- `next build` clean · i18n parity **1930** (en/ms/ta) · scholarship migrations through **`0040`** on prod.
- Pipeline audit: 15 apps `income_route=''` → **only 6 submitted** (9 merely shortlisted, self-heal); + app #21 on the
  STR route = **~7 apps** for the TD-085 backfill.

## Residual / tech debt
- **TD-085** — document-first income verdict + legacy backfill (~7 apps) + income-cockpit redesign (the ▶ NEXT sprint).
- **TD-084** — `earner_work_status` / `household_other_earners` columns + `q2/q3/q4/work` i18n keys orphaned by the
  multi-select (kept; drop under expand-contract later).
- **TD-070** — the income arc is not yet click-tested end-to-end on live `/application` (BC + guardianship checklists in
  particular).
- Gopal income doc-coach copy + the orphaned `str_claimed_no_doc` reason code — minor cleanups queued.
- Two working elder brothers can't both be represented (one "brother" slot) — accepted as rare; logged.

# Retrospective — Reviewer-query automation S2: stale income doc + sibling-in-tertiary funding

**Date:** 2026-06-29
**Branch:** `feat/reviewer-query-s2-stale-sibling`
**Migration:** none (logic only)
**Roadmap:** `docs/scholarship/reviewer-query-automation-roadmap.md` (S2)

## What Was Built
Two more deterministic auto-queries from the manual-query corpus, on the S1 plumbing:

- **Stale income doc** (`income_engine.stale_income_proof`) — a salary slip is monthly, so if
  every one on file is older than ~3 months, ask for a current one. Uncapped doc-request
  `income_doc_stale` (kind=`doc`); auto-resolves when a current slip arrives. Reuses the
  existing tolerant month-year parser (`_parse_billing_month`); a slip whose period can't be
  read is never guessed stale.
- **Sibling-in-tertiary funding** (`income_engine.sibling_tertiary_funding_unknown`) — when
  `siblings_in_tertiary > 0`, ask which institution + how it's funded (scholarship / PTPTN /
  family / other). Capped clarify `sibling_tertiary_funding` (kind=`clarify`); resolves on the
  student's answer. Surfaces the household burden + the not-double-funded picture.
- Frontend: both codes in `actionCentre.ts` KNOWN_CODES + student `actionCentre.item.*` copy +
  admin cockpit flat copy, en/ms/ta.

## Scope change (flagged + agreed in-flight)
The roadmap's S2 also listed a **high-utility-bill probe**. Dropped from S2 and **moved to S4
(interview)**: the codebase already decided high utility is an *officer/interview signal, NEVER a
student query* (`income_engine.utility_reasonable`), which aligns with the pre-sprint decisions
#2 (need-signal principle — housing/consumption stays a judgement aid) and #3 (sensitive probes
→ interview). Making it a student self-report would be gameable and contradict that rule. So S2
shipped the two genuinely student-facing rules; the utility probe becomes a reviewer-facing item
in S4.

## What Went Well
- Pure reuse of S1's `check2_queries` doc/clarify plumbing — the two rules slotted in as one
  detector each + one `_CLARIFY_ORDER`/`DOC_SPECS` entry each. No new mechanism.
- No existing-test drift this time: the new rules only fire on stale-slip / tertiary-sibling
  states, which the existing fixtures don't set, so nothing shifted (unlike S1).

## What Went Wrong
- Nothing notable. The one judgement call (high-utility → S4) was a scope correction made by
  reading the existing design intent before coding, not a defect.

## Numbers
- Tests: backend 1724 pytest (+11 `test_reviewer_query_s2.py`), frontend 387 jest. i18n parity
  2961×3 (+6 keys). No migration.
- Files touched: ~8.

## Next
S3 — offer reporting-date: auto-ask when the offer has no reporting date + persist a normalised
`reporting_date` column on the application (sortable, not re-parsed); SPM subject-count nudge.
S4 now also carries the high-utility reviewer probe.

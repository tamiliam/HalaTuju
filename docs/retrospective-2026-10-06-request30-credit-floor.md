# Retrospective — request #30: a minimum number of SPM grades at C or better (2026-10-06)

Sprint (analysis #66, 7 h). **LIVE 2026-10-06** — pushed `c301220c..cd5dd6a8`; builds SUCCESS, web
`halatuju-web-00963-ndl`, api `halatuju-api-01110-6vd`; no 5xx on the new revision. Migration
`0169_cohort_min_spm_credit_count` (one nullable integer column) applied migrate-first by the owner;
read back (integer, nullable, no default; 0 of 3 intake years set; ledger 0167-0169 contiguous).

## What was built
`ScholarshipCohort.min_spm_credit_count` — the third SPM rung beside A- and B+: a TOTAL count of
grades at C or better (A+ … C) across every SPM subject; blank = off; no default; STPM untouched.
Admin box on the Rules tab and the create-year form. Adversarial review (separate agent): SHIP, three
low findings, all fixed before release — a typo in ANY requirement box was sent as NaN → null → the
rule silently switched OFF while the screen said Saved (now refused with an error); whole-number
counts (6.9 / true refused; NaN / Infinity refused for PNGK and merit too); a hint on the new box.

## What went wrong
1. **The approved analysis carried two stale or wrong premises.** It said the open intake had zero
   applications (it had two by build time), and it accepted the request's "C-" although SPM has no
   C- grade. Why: the analysis was written against the request's words and a one-off count, and
   neither was re-checked at build start. Fix: both re-checked before briefing (the C- question
   went to the owner, who ruled "C or better"); lesson below.
2. **A migration-number collision with another session** (0168 on both branches; earlier, 0167 on
   both). Why: two sessions each take "the next number" from their own base. Fix: agreed by message
   which session keeps the number BEFORE either gave the owner a ledger row; the second renumbers on
   rebase. The ledger row is only handed over once the number is settled.
3. **(Avoided)** The deploy gate runs `pytest -n auto`, which refuses things a serial run passes; the
   other session lost a build to it the same day. Ran the gate's own line before pushing: 8084 passed.

## Numbers
pytest 8084 passed / 3 skipped (serial and `-n auto`) · jest 4146 / 252 · i18n 5409 keys · bundle ok,
`/scholarship/application` 273.654 of 274. Time: planned 7 h, actual about 4 h.

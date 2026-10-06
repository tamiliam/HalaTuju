# Retrospective — Later-tier batch 1 (2026-10-03)

**Scope (the lead's brief):** ten small items from the Later tier of the debt register — TD-323,
TD-320, TD-290, TD-294, TD-287, TD-289, TD-162, TD-231, TD-293, TD-055. No owner ruling, no paid
reads, no migration. Built by one agent; not committed, pushed or deployed.

## What was built

| Item | Change | Guard |
|---|---|---|
| TD-323 | officer-only `figure_refused` on the document payload; amber "…looks misread" chip; the EPF estimate takes the RM100 floor as a BAND figure only (no ceiling) | `test_salary_plausibility.py` (one test per reader class); `view.figureRefused.test.tsx` |
| TD-320 | the EPF contribution fallback stores `capture='mixed'` → "Exact + AI" | `test_epf_contribution_fallback.py` (expectation superseded, note in the test); rendered test |
| TD-290 | `halatuju/logging_json.py`: JSON lines with `severity`, old keys and `message` unchanged, traceback in `stack_trace` | `test_log_severity.py` (formatter built from `base.py`'s own dict) |
| TD-294 | the auth lookup's ERROR names its caller | `test_log_severity.py` |
| TD-287 | the bills read once per income verdict on every path, STR precedence included (`utility=` handed down, deep-copied) | `test_utility_context_once.py`; `FALL_THROUGH_BUDGETS['taken']` 39 → 35 |
| TD-289 | `ToastContext.ts` holds the context and hook | `toastSplit.test.ts` |
| TD-162 | one `EXISTS` column for list readiness | `LIST_BUDGETS` (6/9 → 4/4); `test_list_shaped_readers.py` |
| TD-231 | one query for the gift list's delete blockers, from the shared holder table | `LIST_BUDGETS` (9/27 → 9/24); `test_list_shaped_readers.py` |
| TD-293 | `stored_status` / `stored_authenticity`; `canonical_status` refuses a non-string | `test_stored_genuineness_reader.py`; both shapes in the ON==OFF matrix |
| TD-055 | `merge_guardians`: the form owns name/phone on entry 0; its other keys survive only for the same name | `test_guardians_merge.py` (characterisation table first) |

## What bit

Sixteen injected faults, each restored from a byte backup with its SHA-256 checked afterwards:

| Fault | Went red |
|---|---|
| the salary reading ignores the caller's utility | the three call-count subtests + `FALL_THROUGH_BUDGETS['taken']` |
| readiness ignores the list annotation | both applicant `LIST_BUDGETS` readings |
| the gift list reads the blocker per gift | both gift `LIST_BUDGETS` readings |
| the holder table counts the column only (no cohort reach) | `test_list_shaped_readers` (the moved-cohort row) |
| one engine site back on the raw idiom | the idiom scan ⚠ see below |
| `canonical_status` strips a non-string | the endpoint's 200 test (both routes) + three reader subtests |
| the EPF window removed | five EPF tests + the served-refusal subtest |
| `figure_refused` never served | the two refused subtests |
| the guardians write-back back to overwrite | both write-back tests |
| the fallback labelled `ai` again | the fallback test |
| the web chip ignores `figure_refused` (amount; contribution) | one rendered test each |
| the formatter drops `severity` | 8 in `test_log_severity.py` |
| the traceback folded into `message` | the stack-trace test |
| `base.py` back to a format string | the severity subtests |
| the auth lookup's purpose dropped | the purpose test |

⚠ **One partial bite, written down rather than tidied away.** Putting `household.py` back on the
raw idiom turned only the source scan red — the endpoint's 200 test did not, because its two
malformed shapes sit on an IC and an electricity bill, and `household` only reads slips and EPFs.
The scan is what holds that site; the endpoint test holds the two shapes.

## The adversarial review (FIX-THEN-SHIP; F1 HIGH, F2 MED, F3–F7 LOW/NIT — all applied)

- **F1 (HIGH):** the EPF window sat inside `_epf_monthly_salary`, which has FIVE readers. A ceiling
  turned a RM25,000 EPF into "no figure": the band could fall to a declared amount (a false green
  was reachable), the payslip/EPF divergence check went silent beside a doctored small slip, and
  three evidence/gate readers could newly BLOCK submission; the RM100 floor did the same to an
  irregular worker's single contribution. Lead's ruling: no ceiling; the floor only, on the BAND
  figure only (`epf_band_salary` in `earner_monthly_income`). One test per reader class on both
  shapes. Its first evidence bite was SILENT — `member_income_evidenced` reaches EPF through
  `income_shown`, not `_member_has_epf_value` — so that reader is now asserted on its own.
- **F2 (MED):** `figure_refused` rode on the STUDENT's `income_proof_check`. Moved to the officer's
  `AdminApplicantDocumentSerializer` beside `sgd_conversion`; its absence on the student payload is
  pinned.
- **F3 (LOW):** two STR-breach readers now read a malformed status as no breach — raised as TD-330
  with the owner's choice.
- **F4 (LOW):** the merge keyed on position, so a NEW guardian inherited the old one's relationship,
  occupation and income. Other keys now survive only for the same name; the test that pinned the
  mixed entry was superseded, with a note.
- **F5 (LOW):** STR precedence still read the bills twice; it now takes the caller's reading.
- **F6:** the unused `io` import went.
- **F7 (NIT):** `offer_official_status` read a malformed status as `not_genuine`; aligned to the
  one reader (`unknown`).
- Production counts (the lead, read-only): 0 of 64 live EPF estimates outside the old window; 1 of
  89 payslip chips turns amber; 0 of 815 profiles with a richer guardians list.

## Measurements

- Gift list, measured BEFORE the change by running the old per-gift blocker through the same
  fixture (9/27), not inferred.
- **Bundle (TD-289): a control build decided it.** The split's build showed `/` 232 → 231 kB and
  four routes ONE kB heavier, with the "routes that may cross" count falling 5 → 4. A third build
  of the same tree WITHOUT the split showed the heavier four came from the batch's six new
  message strings (TD-323, TD-320), not from the split — which only made routes lighter (`/` and
  six others). Median 228 kB throughout; the ledger line is unchanged.
- Gates after the review: see the CLAUDE.md block (the numbers there are the final ones).

## What was learnt

- **A guard on a shared helper changes every reader of it.** The EPF window was right for the band
  and wrong for four other readers that ask "was a figure read?". Before narrowing a helper, list
  its readers and ask each one's question — the reviewer found five; the builder had looked at one.

- **A list-shaped reader is the same rule asked about many rows, or it is a second rule.** TD-231's
  entry had refused annotations because they would be "the rule in two places". Building the
  annotations FROM the one holder table, and making the single-gift reader call the list function,
  kept one rule and still gave one query.
- **A tightness count can fall for a reason unrelated to the change you are measuring.** Without the
  control build, TD-289 would have been reverted for worsening the median's headroom — for weight
  the i18n strings added. Measure the counterfactual, not the before/after of a mixed tree.
- **A guardrail block is a question.** The security hook blocked the first write of the logging test
  over `ast.literal_eval`; the work stopped, the lead asked the owner, and the file went in as
  written. It was not reworded to get past.

## Left open

- TD-290 and TD-294 close on the live proof (see `halatuju_api/CLAUDE.md`, the block at the top of
  `## Next Sprint`).
- The two management commands that print `authenticity` (`reextract_documents`, `reextract_offers`)
  still use the raw idiom; they print, they do not decide.

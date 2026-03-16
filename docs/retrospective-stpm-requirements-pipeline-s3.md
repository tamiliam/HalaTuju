# Retrospective — STPM Requirements Pipeline Rebuild Sprint 3

**Date:** 2026-03-17
**Sprint:** Validator + Workflow (Stage 3 tool + reusable SOP)

## What Was Built

1. **Validator tool** (`Settings/_tools/stpm_requirements/validate_stpm_requirements.py`) — 6 automated quality checks: completeness, subject key validity, grade validity, count sanity, cross-reference with source CSV, sample audit against raw HTML
2. **Test suite** (`tests/test_validator.py`) — 49 tests covering all 6 checks (pass/fail cases), validate(), format_report(), CLI
3. **Reusable workflow** (`Settings/_workflows/stpm-requirements-update.md`) — annual STPM refresh SOP, 5 stages with checkpoints, failure modes, tool inventory

## What Went Well

- **Subagent-Driven Development** worked smoothly — implementer built both files, spec reviewer confirmed compliance, code reviewer caught 3 real issues
- **Code review caught important gap** — the `VALID_STPM_KEYS`/`VALID_SPM_KEYS` sets were computed but never used. Validator only checked `UNKNOWN:` prefix, missing typo keys like `TYPO_BIOLOGY`. Fixed by adding full key validation.
- **Real-data validation** immediately proved value — found 1 empty course (UP6640001) and 3 courses with legacy grade `E`. Both are known exceptions, now documented.
- **Workflow document** follows WAT framework conventions and is immediately usable for next year's refresh

## What Went Wrong

1. **Named subjects data format mismatch**
   - *Symptom:* Validator crashed with `AttributeError: 'dict' object has no attribute 'startswith'` on real data
   - *Root cause:* Tests used synthetic data with `stpm_named_subjects` as a list of strings, but real Stage 1 output uses list of dicts (`{subject, min_grade}`). The implementer never ran against real data before claiming done.
   - *Fix:* Added `isinstance(item, dict)` check to extract `item["subject"]` from dicts. Also added grade validation for the dict-format named subjects.
   - *System change:* Future pipeline tool implementations must include a "run against real data" step before marking task complete. Added this to the workflow document's test commands section.

## Design Decisions

- **Key validation beyond UNKNOWN: prefix** — The validator now checks against the full canonical key sets, not just the `UNKNOWN:` prefix. This catches typos and stale keys that the parser might produce if subject_keys.py is edited incorrectly.
- **Isolated PRNG** — `random.Random(42)` instead of `random.seed(42)` prevents global state pollution when `validate()` is called as a library function.
- **Graceful CSV error handling** — Missing CSV files return a FAIL result instead of crashing with a traceback, making the CLI more robust for automation.

## Numbers

| Metric | Value |
|--------|-------|
| Tasks completed | 2 (Task 14 + Task 16) |
| Pipeline tool tests | 248 (199 existing + 49 new) |
| Django tests | 590 pass, 0 fail |
| Real data validation | 3 PASS, 2 known FAIL, 1 SKIP |
| Files created | 3 (validator, tests, workflow) |

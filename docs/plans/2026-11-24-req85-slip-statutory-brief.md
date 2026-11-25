# #85 — a payslip with two statutory deductions is a payslip (brief, 24 Nov 2026)

Request #85 (org 11), case 242. Scheduled by the owner 24 Nov; analysis 195 approved and posted (bug, free, 2.5 h, small change).
Branch `req85-slip-stat` in worktree `.worktrees/req85-slip-stat`, cut from side/laptop c9fb43ab8 (contains #78, unreleased, which set VERDICT_ENGINE_VERSION 2026-11-23.1).

## The fault

`halatuju_api/apps/scholarship/genuineness/salary_doc.py` (~line 131): the `wage == 0` reject runs BEFORE the
`stat >= 2` → genuine/private branch. A slip whose text shows two statutory deductions (e.g. KWSP plus SOCSO/EIS/PCB)
but none of the wage labels is scored `not_salary` (p=0.10, "no recognisable payslip fields").
Downstream: `income_shown.py:106-112` proof_flagged → `income_engine/evidence.py:158-167` usable_salary_slip False →
`services/blockers.py:328-338` emits `income_evidence_missing:mother` → the student is stuck at Documents.

This contradicts decisions.md "Salary-slip genuineness = statutory-grammar cascade, soft, wrong-type-only chip — 2026-07-09":
`private` = ≥2 of KWSP/SOCSO/EIS/PCB; `not_salary` = a MyKad or no payslip fields; a misread genuine slip is "never a hard trap".
The posted answer told the org: "A slip that shows two or more statutory deductions will count as a payslip, as our design
says. A copy of an identity card in the salary-slip slot will still be refused, as now." Build exactly that.

## Steps

1. **Scorer.** In `salary_doc.py`: keep the MyKad reject first (unchanged). Then `stat >= 2` → genuine/private (works with
   wage 0; keep the probability formula, check it stays sensible). Only then `wage == 0` → not_salary. Order of the other
   genuine families unchanged. Bump `MODEL_VERSION` 1.2.0 → 1.3.0.
   **First check what reads MODEL_VERSION** (re-score sweeps, staleness checks, `rescore_unscored_documents.py`, any
   "model older than current → re-run" logic). A bump must NOT trigger a mass re-read, an AI call, or a re-score that
   needs OCR text we do not hold (slips read before 18 Nov have no stored OCR text). If it would, stop and report.
2. **Tests** in `halatuju_api/apps/scholarship/tests/test_salary_signatures.py`: ≥2 statutory + 0 wage → genuine/private;
   MyKad + 0 wage still not_salary (MyKad wins even with statutory markers — decide from the code which order is right
   and pin it); 1 statutory + 0 wage still not_salary; existing cases unchanged. A regression test that fails on the old order.
3. **Re-score from stored markers** — a small management command next to `rescore_unscored_documents.py`
   (e.g. `rescore_salary_statutory.py`). It selects live (not superseded) `salary_slip` documents whose stored genuineness
   result is `not_salary` from a model < 1.3.0 with stored markers `statutory >= 2` and a reason that is NOT the MyKad
   reason, and re-writes the result as the new scorer would, from the stored markers alone (no read, no AI, no OCR).
   Dry-run by default (prints document id + case number + old → new, counts only, no personal data); `--apply` writes.
   Use the same write path/service the scorer uses, not raw SQL. Tests for the selector and the dry run.
   We expect two live documents today (case 242 doc 4431; case 861 doc 8406). **Do not run it against production** —
   the lead runs it after the landing, on the owner's word.
4. **Version.** Bump `VERDICT_ENGINE_VERSION` in `verdict_engine.py` to `2026-11-24.1` (sorts after 2026-11-23.1), with a
   one-line comment. Run `test_model_versions` and `test_model_digest`; update the digest/registry the way the guard asks.
   Do not move any golden unless a test proves it must, and then say which and why.
5. **Docs.** decisions.md: a dated entry (24 Nov 2026, #85) — ≥2 statutory deductions win over missing wage labels; MyKad
   still refused first; why (the 2026-07-09 rule + case 242). CHANGELOG under a #85 heading. Log as `TD-NEW-netpay-not-salary`
   the follow-up NOT built here: 9 live `not_salary` slips with zero statutory markers (plus one with one) had a net pay
   figure read — should a read net pay stop "not a salary slip"? Owner to rule.

## Rules

- Opus build. Targeted tests while building; the full API suite ONCE at the end through the queue:
  `caffeinate -i -m -s python3 /Users/elanjelian/Python/Settings/_tools/test_queue.py -- <cmd>` with
  `/Users/elanjelian/.venvs/halatuju-py311/bin/python -m pytest` run from `halatuju_api` (the 3.12 .venv exits 4).
  No web change is expected; if you change web, say so (web gates + bundle then apply).
- No production writes, no paid calls, no re-reads, no document downloads. Production DB (Supabase MCP, project
  pbrrlyoyyiftckqvzvvo) only `BEGIN READ ONLY; SELECT …; ROLLBACK;`, counts and ids only. No personal data in code,
  tests, docs or output: case numbers only.
- Bash: absolute paths; no `VAR=` at the start of a command; no `$()`; never `git add -A`; never bare `git stash`;
  no push. Work only in this worktree. No `halatuju-web/node_modules` symlink.
- Commits: honest type, the word "sprint", e.g. `fix: sprint #85 - ...`. Trailers on the final commit:
  `Phone-check: case 242 no longer owes the mother's income after the re-score` /
  `Migration: none` / `Services: api` / `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Report back (≤ 30 lines)

Commits (sha + one line), what reads MODEL_VERSION and why the bump is safe, test counts (targeted + full suite),
version/digest changes, the dry-run expectation for the re-score, TD-NEW logged, anything the owner must rule on, run time.

Stop at 120k. Commit your work. Send back a split plan.

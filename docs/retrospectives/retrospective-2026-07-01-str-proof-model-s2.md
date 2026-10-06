# Retrospective — STR-proof model, Sprint 2 (salary spillover, 2026-07-01)

Worktree `.worktrees/str-salary` (branch `feat/str-salary`). No migration. Commits `97b59918`
(income core) + `7a7586e7` (verdict fall-through + extraction + FE). Built against
`docs/scholarship/str-proof-spec.md` §6/§7.

## What shipped
- **Evidence-driven route fall-through** (`verdict_engine._verdict_income`): a `wrong_type`/`rejected`
  STR no longer freezes the income fact — it assesses the salary docs on file via `income_headroom`.
- **`income_headroom(application, members)`** — margin-graded band (`unknown`/`over`/`unsure`/`probable`).
  B40 holds while gross ≤ `max(gross_ceiling, per_capita_ceiling × size)`; `breach_room` = how much more
  income tips it out. Thin (or an unread earner) → Unsure; large → Probable. #13 → Unsure, SARA → Probable.
- **YTD-annualised pay** (`gross_income_ytd ÷ 12`, captures O/T) + **pension/benefit as income** (PERKESO),
  both via the salary_slip extraction + reader.
- FE income-tile copy (`income_salary_probable`/`unsure`, en/ms/ta).

## What went well
- **The Sprint-1 structured states made the fall-through trivial** — `_str_currency` already returns
  `wrong_type`/`rejected` as data, so the verdict just keys off it. The S1 investment paid off in S2.
- **Roster-independent headroom.** Grading by *margin* (breach-room) rather than a roster-based
  unaccounted-member count means it ships now and still separates #13 from SARA correctly; the roster,
  when it lands, only sharpens it.

## What went wrong / the subtle one
- **A `review` fact reads BLUE off ANY verified evidence** (the "blue needs a green" rule), and the
  earner-IC / relationship greens are verified — so routing an *unsure* income through `review` would
  have shown #13 as 🔵, overstating it. Fix: unsure/over return **`recommend`** (→ amber unconditionally);
  only `probable` returns `review` (+ a green salary-evidence item) to earn its 🔵. The income tile's band
  must be driven by the income CONCLUSION, not by incidental identity greens.

## Carry / dependencies
- **Annualisation + pension take effect on a document RE-RUN** (the new `gross_income_ytd` field + the
  pension read only populate on re-extraction) — the owner deferred that to one post-Sprint-2 pass
  (`memory/halatuju.md`). Until then the headroom band runs on the single-month figure already stored.
- **GREEN for the salary route is deferred** to the structured family roster (corroborated household
  size) — today the salary route caps at 🔵 Probable. The full salary-track redesign remains a separate spec.
- **Fall-through scoped to `wrong_type`/`rejected`** (STR present but failed). An *absent* STR on the STR
  route keeps the `income_proof_missing` gap (ask for the STR) rather than silently assessing salary.

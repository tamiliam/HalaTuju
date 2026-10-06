# Retrospective — STR-proof model, Sprint 1 (2026-06-30)

Worktree `.worktrees/str-model` (branch `feat/str-model`). `MODEL_VERSION` 1.1 → 1.2. No migration.
Built against `docs/scholarship/str-proof-spec.md` (the accepted design from the #112/#13/SARA review).

## What shipped (Sprint 1 — STR read honestly + rate decisively)
- **Structured currency states** (`income_engine._str_currency`): `wrong_type` / `rejected` /
  `unreadable` / `stale` / `unconfirmed` / `current`, replacing the single `unconfirmed` bucket. The
  **format gate runs first** — `source_type='unknown'` (a non-STR: SALINAN / SARA / payslip) →
  `wrong_type`, never softened.
- **Dateless approved STR demoted** `current` (GREEN) → `unconfirmed` (BLUE). A year-old dashboard/
  Semakan screenshot also reads "Lulus"; without a date the cycle can't be confirmed. This re-bands
  the existing dateless-approved STR verdicts from Certain → Probable on deploy (intended).
- **verdict_engine** recognises the states (the `str_not_current` item carries the state param);
  the **`document_not_genuine` caveat is suppressed for `wrong_type`** (a genuine payslip in the STR
  slot is the wrong KIND, not a forgery — `_str_wrong_type`).
- **Extraction (vision.py):** read the status **value** not the "Status Permohonan STR" **label**
  (#112 leak), dates only from the letter date / Maklumat-Pembayaran payment date (never the FAQ-nav
  "2026" chrome), sharper dashboard-vs-semakan signatures.
- **FE:** the officer verdict line is an **ICU `select`** on the state — one decisive sentence each
  (a `wrong_type` reads "This is not an STR document"), EN/BM/TA; the STR doc-status chip maps
  green/amber/red via `strCurrencyFactStatus`.
- **Profile honesty:** claim STR only on a confirmed-**current** (dated) STR, not a dateless one.

## What went well
- **Spec-first paid off.** The whole build was mechanical execution against `str-proof-spec.md` —
  the design debate (with the owner, over #112/#13/SARA) was done, so the code had no open questions.
- **ICU `select` = zero renderer change.** The verdict item already passed `params` (incl. `status`)
  to next-intl, so per-state copy is pure i18n — no component logic, all three languages in one key.

## What went wrong / watch-outs
- **The smarter document read wasn't reaching the decision.** The model already *wrote* "salary slip,
  not an STR" in prose, but the verdict only consumed the coarse `unconfirmed` signal. The fix was to
  lift the insight into a **structured state** the verdict engine consumes — prose is not a decision input.
- **A pre-existing i18n-orphan blind spot surfaced** (on main): the orphan guardrail only recognised
  dynamic prefixes ending in `.` before `${`, so `noAmountReason_${code}` read as an orphan. Extended
  the guardrail to also capture `_`-suffixed dynamic prefixes.
- **Fresh worktree had no `node_modules`** — `npm install` needed before jest/build.

## Numbers
- Backend 1827 scholarship pytest (states + wrong_type/no-double-flag regressions). Web jest 395 +
  `next build` clean. 2 commits (backend `8b4686b1`, FE `0f1e09ba`).

## Carry → Sprint 2 (the salary spillover)
Evidence-driven **route fall-through** (a `wrong_type`/`rejected` STR → assess the salary docs on
file, don't freeze); **pension/benefit counts as income**; **annualised income incl. O/T**; the
**headroom-graded** household-corroboration rule (#13 → Unsure vs SARA → Probable). The full salary
track is a larger, separate spec.

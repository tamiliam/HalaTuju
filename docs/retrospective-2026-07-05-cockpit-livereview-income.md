# Retrospective — Officer-cockpit live-review round (2026-07-05)

Document verification + income-model hardening. A live-testing pass driven by reviewing real applicants
(#80, #66, #63, #51, #50, #62, #99, #105, #36). All FE/BE — **no migration**. Shipped incrementally
(commits `e4eeaa0a` → `efa3157f`), each fix deployed and, where prod data was affected, backfilled.

## What Was Built

**Income model / B40 integrity**
- **SGD → MYR conversion.** A cross-border (Singapore) payslip is now converted to ringgit before the B40
  band. Detection is STRUCTURAL: the `Pte Ltd` / `Private Limited` employer suffix (regex, spacing-tolerant)
  OR `currency=SGD` (the extractor sets it from S$/CPF/SDL/Pte-Ltd/Singapore-address markers — so a
  co-operative / statutory board is caught without hard-coding a company name). Rate `SGD_TO_MYR_RATE`
  (env-overridable, default 3.15). **Gated to in-review apps** (a decided case keeps its as-recorded basis).
  `gross_income` also fixed to read the TOTAL earnings (basic + OT + allowances), not the basic alone.
- **STR present (not breached) → salary docs SUPPORTIVE, route-agnostic.** `incomeSubSections` no longer
  demands salary-route docs (red "Missing") when a genuine non-breached STR is on file, whatever the
  declared route (#63 was on the salary route with a valid Lulus STR). A breached STR still → full salary docs.
- **One-live-copy dedup** (salary / STR / EPF) — collapse a person's copies to the single newest, rest →
  Old/Replaced, ranked **genuineness-first** so a fake never supersedes a real proof. Cohort backfilled.

**Document verification**
- **Correcting tag-guard** (`name_contradicts_tag`) — an income doc whose read name unambiguously
  contradicts its tag is re-attributed (closes the #80/#112 class).
- **Doc-driven STR salary layout** — SALARY sub-section members derived from the docs present.
- **Genuineness wrong-type chip cap** extended to str/salary/EPF/results; light NEGATIVE wrong-type check
  for salary slips (`misfiled_as`). MODEL_VERSION 1.2.1 → 1.3.0.
- **Semester-result Name/IC/CGPA chip** + name/nric/cgpa extraction.
- **Parent-name validator** (reject an IC/number in a name box; FE inline + serializer 400).
- **Optional-field warnings suppressed** across salary / semester / offer docs (NRIC, YTD, CGPA,
  institution, offer_date, address, stream, elektif/aliran …) — kept the core-field warnings.

**Check-2**
- **Clarify "N waiting" over-count fix** — stopped counting already-answered clarifies as waiting (#36).

**Data (prod, MCP):** mistag retags (#80/#112), #66 parent names, #51 IC swap, `other`→proper-type
re-files (#30/#50/#62/#99/#110/#112), dedup + warning-noise backfills, #105 SGD gross restore.

## What Went Well
- **Owner-in-the-loop, one case → systemic fix.** Every fix generalised from a single flagged case to a
  rule (e.g. "#105 Singapore payslip" → structural SGD detection for all; "#63 Missing" → STR-validity gate).
- **Re-banding discipline held.** Each prod data change was audited band-neutral before applying (retag,
  dedup, EPF), and the one genuinely re-banding change (SGD conversion) was owner-gated on scope + rate.
- **No-cost backfills.** Warning-noise and dedup corrections were applied via MCP SQL mirroring the deployed
  Python rule, so existing cases went clean without billable re-runs.

## What Went Wrong
1. **The web build broke on a `Set` spread** (`[...set]`) that my local `tsc --target es2018
   --downlevelIteration` accepted but `next build`'s tsconfig rejected. **Root cause:** verifying types with
   an OVERRIDDEN target instead of the project's own config, which masked a build-breaker. **Fix (adopted
   mid-sprint):** verify web types with `npx tsc --noEmit -p tsconfig.json` (project config), never an
   overridden target. Recurred once more as narrow-union comparison errors (`current_status`/`authenticity`)
   — same lesson, caught by the project-config check the second time.
2. **The SGD conversion "changed on re-run."** After deploy, re-running #105's slip flipped the finding.
   **Root cause 1:** the re-extract read the BASIC salary (S$2,420), not the total (S$3,114) — the prompt said
   "gross/basic". **Root cause 2:** `_slip_is_sgd` trusted Gemini's `currency` guess over the employer, so a
   re-run misreading `currency=MYR` could un-convert. **Fix:** gross = TOTAL earnings; employer/structural
   suffix is the primary anchor and overrides the currency guess (stable across re-runs).
3. **Hard-coded company names in the SGD detector.** First cut matched `ntuc`/`fairprice`/`singapore` — useless
   as a general rule. **Root cause:** chasing the one visible case (#105 = NTUC) instead of the structural
   signal. **Fix:** `Pte Ltd`/`Private Limited` regex + CPF/SDL/S$-driven `currency=SGD`; a test now asserts a
   bare company name is NOT enough.
4. **A warning-suppression regex over-matched.** The salary/offer "optional field" drop used a loose
   `year AND date` (dropped a legit "pay period (month/year) … pay date" note, #66). **Root cause:** matching
   on incidental token co-occurrence. **Fix:** require explicit "year-to-date" phrasing; restored the one
   backfilled row.

## Design Decisions (see decisions.md)
- SGD income conversion: auto-convert (not flag-only), env-configurable rate, gated to in-review apps.
- Singapore detection is structural (Pte Ltd + CPF/SDL/S$ → currency), never company-name-based.
- STR-validity (not the declared route) gates whether salary docs are required in the cockpit layout.

## Numbers
- **2096 scholarship pytest + 455 jest**; golden masters intact (SPM 5319 / STPM 2026 — courses untouched).
- **No migration.** MODEL_VERSION 1.2.1 → 1.3.0.
- ~18 commits; ~10 prod data backfills (all audited band-neutral except the owner-gated SGD conversion).

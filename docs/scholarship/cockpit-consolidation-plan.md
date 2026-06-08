# Officer cockpit consolidation — build spec

**Status:** Approved by owner (2026-06-08). Not yet built. Its own sprint (UI redesign →
**Stitch-prototype first** per the workspace UI rule, then code).
**Goal:** one cockpit, no duplicated questions, no lost signals. Today ~11 action panels
overlap (old Phase-C panels layered under the verdict redesign). Collapse to ~7.

## Target layout

```
Header (name · status · merit · bucket)
About the student — FACTUAL cards, KEPT VISIBLE (not collapsible):
  Contact · Family (income/STR/JKM) · Academic (grades/merit)

Two columns (right is sticky):
  LEFT                          RIGHT (sticky)
  1. Verification verdict       1. Decision (+ Estimated need beside it)
  2. Sponsor profile            2. Assign a reviewer  (viewer-HIDDEN)
     └ "Show the student's own words" reveal → Note + Story + Funding (hidden by default)
  3. Outstanding
  4. Interview findings
  5. Documents
```

## GONE as standalone (functions survive, merged elsewhere)
- **Pre-interview flags** → merged into **Outstanding** (de-duped).
- **Verify & accept** → merged into **Decision**; its OCR / parent-IC extracted display → **Documents**.
- **Record your verdict** → merged into **Decision**.
- **Ask for more documents** → folded into per-item **Ask** (Outstanding) + Decision tools.
- **Consent** panel → removed (the consent RECORD + downstream gating stay; only the cockpit line goes).

## NEW (merged) panels
- **Outstanding** = Caveats (`resolution_items`) + Pre-interview flags (`anomalies`) + AI interview-gap
  suggestions, as ONE list. Each row tagged 🟠 *student to-do* (Resolve/Ask) vs ⚠️ *ask at interview*.
  **Dedupe rule:** an anomaly that already has a caveat/verdict home is NOT also shown as a flag —
  specifically the identity `vision_nric_mismatch` / `vision_name_mismatch` (the caveat + verdict tile are
  authoritative). Flags carry only signals with no caveat/verdict equivalent (utility-vs-income,
  jkm-high-income, household-size-1, funding-other-blank, address-state, declaration-name, parent-ic-underage…).
- **Decision** = Record-your-verdict + Verify-&-accept, ONE panel, the two-step logic PRESERVED:
  (1) audit the 4 facts Pass/Fail → records the verdict (`verdict_decided_at`); (2) confirm the MyKad
  checklist → accept (locks NRIC, `status=accepted`), still gated on (1). The 4 MyKad checkboxes collapse
  into the matching fact rows instead of repeating them. **Estimated need** sits beside this panel
  (award-sizing input; it is NOT raw narrative and is NOT captured by the AI profile, so it is NOT hidden).

## KEPT
- Verification verdict tiles · Sponsor profile · Interview findings (reads its flag list from Outstanding) ·
  Documents (absorbs the OCR/parent-IC display) · factual About cards · Consent record+gating (just no panel).

## Hide raw inputs behind the profile
- **Note + Story + Funding** collapse behind a **"Show the student's own words"** link **under the Sponsor
  profile** (reveal on demand). Rationale: the reviewer's job is to *check & sign off the AI profile*, not
  re-read raw inputs; the reveal is the safety valve; as the AI improves they lean on it less.

## Profile generation triggers (already built; confirm in build)
- **First cut (STEP 3):** `generate_ready_profile` when ready-for-assignment (manual button now; auto behind
  `CHECK2_AUTO_GENERATE`, off). Claim-gated.
- **Final (STEP 4):** at the Decision — "Save verdict & generate final profile" (`record-verdict` finalise) →
  `refine_sponsor_profile` with the submitted interview. **OPEN:** should the refine also fire when there is
  NO formal interview (use the verdict reason/notes), so the profile always reflects the human's assessment?
- **PARKED (b):** tiered models — cheap model first cut, premium (e.g. gemini-2.5-pro) for the final/refine.
  Decision deferred; measure flash-vs-pro on a real student in the running cockpit before committing.

## Risks to respect while building
1. **Decision merge** must keep the audit→accept gate intact (accept stays gated on a recorded verdict; NRIC
   lock preserved). Don't loosen it.
2. **One "ask the student" endpoint** — collapsing 3 ask paths to one must not silently break any.
3. **Lose no signal** — the flags survive inside Outstanding; dedupe removes only true duplicates.

## Suggested build order (one sprint, maybe split)
1. Backend: flag-dedupe (suppress identity anomalies that have a caveat/verdict).
2. FE: hide Note/Story/Funding behind the reveal; relocate Estimated need beside Decision; remove Consent panel;
   Assign-reviewer → right column below Decision, viewer-hidden.
3. FE: build **Outstanding** (merge caveats+flags, tagged, per-item Ask).
4. FE: build **Decision** (merge verify-accept + record-verdict; estimate beside).
5. Documents absorbs the OCR/parent-IC block. Reorder columns. i18n + tests + gates. Stitch sign-off first.

# Retrospective — Verification-model V5: verdict evenness + QC gap floor (2026-07-04)

Roadmap `docs/plans/2026-07-03-verification-model-roadmap.md` §V5; audit
`docs/plans/2026-07-03-check-model-audit.md` findings #5, #10–#14; owner decision 1.
Ran across two model sessions (Fable 5 → Opus 4.8) via the mid-sprint handoff file.

## What Was Built

1. **One route-seam truth table (#10).** `str-proof-spec.md` §8 rewritten as the single source
   for the income band across both routes; `verdict-confidence-bands.md` now defers to it. The
   engine (`_verdict_income` / `_verdict_income_salary`) aligned:
   - Salary-route over-the-line → RED (`gap`), matching the STR fall-through — the three-way
     seam inconsistency (amber on salary, red on STR, for identical economics) is gone.
   - STR positive recipient-mismatch → amber (`recommend`), never blue off the earner-IC green.
   - The salary-route thin-headroom binary green kept as a **documented deliberate exception**
     (a fully-corroborated cluster has nothing for the headroom grading to hedge).
2. **QC soft floor (#5, owner decision 1).** `AdminQcDecisionView.accept` refuses
   `400 verdict_gap_floor` (naming the red facts) while any verdict fact is red; a super
   overrides only with a recorded reason (`qc_override_reason/_by/_at`, migration 0092
   additive/migrate-first, + AUDIT log). Cockpit: Accept disabled + red facts listed for
   non-super; super gets a record-reason override panel. i18n ×3.
3. **Wrong-person offer → explicit amber (#12).** `offer_name_mismatch` now `recommend`, not
   the accidental-amber `review` that one added green would have silently flipped blue.
4. **SOFT_EVIDENCE guard (#11).** Two Phase-2B/2C soft codes added to the FE denylist; a new
   jest guard reads `verdict_engine.py` and pins the FE↔backend mirror both ways off `# SOFT`
   markers, with a parse-sanity floor (mirrors `test_subject_drift.py`).
5. **Doc-rot (#14).** Engine status/colour-map + `_verdict_pathway` docstrings corrected;
   bands-doc self-contradiction fixed; `check2_queries` i18n namespace pointer corrected; the
   #13 genuineness-skew recorded as a known limitation (no code) in decisions.md.

## What Went Well

- The route-seam re-banding turned out to have **zero disruptive live impact**: the live prod
  query (Supabase MCP) showed every carrier of the three affected codes was already
  closed/resolved. The owner checkpoint became a clean "forward-looking only" sign-off.
- The `# SOFT` marker + jest guard is a cheap, durable fix for the exact rot that caused #11
  (the denylist drifted because nothing enforced the mirror).

## What Went Wrong

- **The QC gap floor broke a decision-reopen test on the full-suite run** — `test_decision_
  reopen.py::test_rerecord_counts_correction_then_republishes_at_qc` does a real QC-Accept on a
  fixture with no documents, whose live `build_verdict` is all-gaps, so the new floor refused it
  (400). Symptom: 1 failure in an unrelated test file. Root cause: I re-pinned the QC-gate tests
  (patched `build_verdict`) but didn't grep for **every** test that drives a real QC-Accept —
  the decision-reopen suite also does, and it wasn't on my radar. Fix applied: patched the
  verdict seam for that one call, with a comment pointing at where the floor is actually tested.
  System change (lessons.md): when a gate is added to a shared endpoint, grep the whole test
  tree for every caller of that endpoint, not just the endpoint's own test file.
- **A regex char-class dropped digits in evidence codes** — the guard test's `_item('([a-z_]+)'`
  captured `utility_percapita_b` instead of `utility_percapita_b40`, failing the mirror on first
  run. Trivial, caught immediately by the test itself, but a reminder that codes carry digits.

## Design Decisions (logged in full in decisions.md)

- Over-the-line = RED on both routes (advisory); the salary thin-headroom green is the one
  documented exception. QC floor is SOFT (super override with recorded reason), not a hard block.
  Wrong-person offer stays amber with no submission block. #13 skew left as a recorded limitation.

## Numbers

- 2064 scholarship pytest (+9 net) + 1202 courses/reports; 416 jest (+3, the new guard);
  tsc clean for production code (only the pre-existing test-file errors remain).
- 1 prod DDL: migration 0092 (3 additive columns), migrate-first via Supabase MCP, verified
  (columns live + single `django_migrations` row + `makemigrations --check` clean). No new
  tables → no RLS/advisor change.
- Reviewer-visible re-banding: 0 live apps move disruptively (all affected carriers
  closed/resolved); QC floor newly gates the 10 awaiting-QC apps at their next Accept click.

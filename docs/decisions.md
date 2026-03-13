# Architectural Decisions — HalaTuju

## Separate STPM ranking module — STPM Sprint 3, 2026-03-13

**Decision:** Created `stpm_ranking.py` as a standalone module rather than extending the existing `ranking_engine.py`.

**Alternatives considered:** Adding STPM scoring to `ranking_engine.py` with a pathway-type switch.

**Rationale:** The SPM ranking engine handles merit tiers, credential priority, pathway scoring, and category caps — none of which apply to STPM. Merging would require branching on every scoring step, making both paths harder to test and reason about.

**Trade-offs:** Two ranking modules to maintain. Some scoring concepts (CGPA margin, field match) are duplicated at the constant level but with different values.

**Revisit if:** A unified ranking API is needed that handles both SPM and STPM in a single call, or if a third pathway (e.g. UEC) is added and a shared abstraction becomes worthwhile.

## Legacy grade aliases in GRADE_ORDER — STPM Sprint 5, 2026-03-13

**Decision:** Keep E and G as legacy aliases at the end of `STPM_GRADE_ORDER` in `stpm_engine.py`, even though the real STPM scale uses D+ and D instead.

**Alternatives considered:** (1) Remove E/G entirely and migrate parsed CSV data to use D/F. (2) Map E→D and G→F at CSV parse time.

**Rationale:** The parsed CSV requirement data (`stpm_subject_group` JSON fields) contains `min_grade: 'E'` in many records. Removing E from GRADE_ORDER causes `meets_stpm_grade()` to raise ValueError, breaking 48 programmes. Migrating the source data is risky and the CSVs are externally maintained.

**Trade-offs:** GRADE_ORDER has 13 entries instead of 11. The user-facing grade dropdown (`STPM_GRADES` in `subjects.ts`) correctly excludes E/G. There's a semantic gap between what users see and what the engine accepts.

**Revisit if:** The STPM CSV data is re-parsed with corrected grade codes, or if a data migration script is built to normalise all `min_grade` values.

## Merit traffic light thresholds — STPM Sprint 6, 2026-03-13

**Decision:** Student merit (CGPA/4.0 × 100) vs course merit: ≥ course = High, within 5% below = Fair, >5% below = Low.

**Alternatives considered:** (1) Tertile-based (top/mid/bottom third of merit range). (2) Fixed thresholds (≥90 High, ≥75 Fair, else Low). (3) No threshold — show raw percentage only.

**Rationale:** Comparing student merit directly against course merit gives personalised, actionable feedback. The 5% "fair" zone represents a realistic improvement margin. Fixed thresholds ignore per-course competitiveness.

**Trade-offs:** The 5% threshold is somewhat arbitrary. Very competitive courses (merit 100%) will show nearly everyone as "Low". But this is honest — students should know.

**Revisit if:** User testing reveals the 5% zone is too narrow or too wide, or if UPU publishes official competitiveness bands.

## Koko 0–10 scale with 4% CGPA weight — STPM Sprint 6, 2026-03-13

**Decision:** Koko score input accepts 0–10, formula: `(academicCgpa × 0.9) + (kokoScore × 0.04)`.

**Alternatives considered:** (1) Koko as 0–4 with 10% weight (previous implementation). (2) Koko as 0–100 percentage.

**Rationale:** The actual STPM system grades co-curriculum on a 0–10 scale. Previous implementation used 0–4 which was incorrect. 10 × 0.04 = 0.40 max, matching the known max CGPA of 4.00 (3.60 academic + 0.40 koko).

**Trade-offs:** None significant. This corrects a factual error.

**Revisit if:** The STPM grading system changes its koko weight or scale.

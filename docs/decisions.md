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

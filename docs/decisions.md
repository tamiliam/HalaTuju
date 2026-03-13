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

## Unified search endpoint for SPM + STPM — STPM Sprint 7, 2026-03-13

**Decision:** Extended the existing `CourseSearchView` to query both `Course` (SPM) and `StpmCourse` (STPM) tables with a `?qualification=SPM|STPM` filter, rather than maintaining separate endpoints.

**Alternatives considered:** (1) Keep `/api/v1/courses/search/` and `/api/v1/stpm/search/` as separate endpoints, with frontend merging results client-side. (2) Create a unified `UnifiedCourse` model/view that duplicates data.

**Rationale:** Single endpoint means one fetch, one set of filters, one pagination mechanism. STPM results are mapped to the same `CourseCard` shape at the view level, so the frontend doesn't need to handle two different response formats. Smart filter skipping (e.g. state filter skips STPM since STPM courses don't have state data) keeps results sensible.

**Trade-offs:** The view is more complex (~200 lines) with conditional query building. STPM courses lack some SPM fields (state, pathway_type), so some filters silently skip one qualification. If a third qualification is added (e.g. UEC), the view will need refactoring.

**Revisit if:** A third qualification pathway is added, or if the unified view becomes too complex to maintain.

## Map STPM → EligibleCourse client-side — STPM Sprint 8, 2026-03-13

**Decision:** Map `StpmRankedProgramme` to `EligibleCourse` type in the dashboard component, reusing the existing `CourseCard` component without modifications.

**Alternatives considered:** (1) Create a new `StpmCourseCard` component with STPM-specific fields. (2) Extend `CourseCard` to accept a union type of SPM and STPM data.

**Rationale:** The existing `CourseCard` already handles images (via field), badges (via source_type/level), merit bars (via merit_cutoff/student_merit), and bookmarks. STPM data maps cleanly to these fields. Zero changes to CourseCard means zero risk of breaking SPM rendering.

**Trade-offs:** Some STPM-specific data (university name, CGPA) is lost in the mapping or displayed as generic fields. The mapping logic lives in the dashboard component rather than a shared utility.

**Revisit if:** STPM cards need to show data that doesn't fit the EligibleCourse shape (e.g. CGPA requirements, MUET band).

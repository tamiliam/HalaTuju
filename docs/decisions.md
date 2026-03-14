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

## merit_type field for pre-U merit branching — Pre-U Sprint, 2026-03-13

**Decision:** Added `merit_type` CharField on `CourseRequirement` with three choices (`standard`, `matric`, `stpm_mata_gred`). Views.py branches merit calculation by this field, calling `pathways.py` formulas for matric/stpm.

**Alternatives considered:** (1) Modify `engine.py` to handle merit calculation internally. (2) Add a separate `PreUMeritCalculator` class. (3) Keep synthetic entries and add merit to them.

**Rationale:** `engine.py` is the golden master and must not be modified. `pathways.py` already has the correct formulas with 32 tests. A simple field + if/elif in views.py is the minimal change. Pre-U courses go through the same eligibility loop as all other courses — engine checks basic requirements, then views.py applies the track-specific formula as a second pass.

**Trade-offs:** Views.py gains ~50 lines of merit branching. The second-pass eligibility check (engine says eligible, then pathways says not eligible → skip) is slightly unintuitive. But it avoids touching the golden master.

**Revisit if:** A fourth merit formula is needed, or if engine.py is refactored to support pluggable merit calculators.

## Frontend JSON over DB for pre-U institution rendering — UI Polish Sprint, 2026-03-14

**Decision:** STPM and matric course detail pages use the frontend JSON data files (`stpm-schools.json`, `matric-colleges.ts`) to render institution cards, bypassing the DB Institution records.

**Alternatives considered:** (1) Enrich the DB Institution records with PPD, subjects, phone fields. (2) Have the API merge DB and frontend data. (3) Redirect pre-U course detail pages to the pathway pages.

**Rationale:** The frontend JSON has rich data (584 STPM schools with PPD, subjects, phone; 15 matric colleges with tracks, phone, website) that the DB records lack. Adding these fields to the DB would require schema changes, data migration, and ongoing sync with the source data. The frontend data is the authoritative source for this information.

**Trade-offs:** Two data paths for institution rendering: DB for regular courses, frontend JSON for pre-U. If pre-U institution data changes, both the JSON files and DB need updating. The course detail page has more code to handle the branching.

**Revisit if:** The Institution model gains PPD/subjects fields as part of a broader data enrichment effort, or if a unified institution data source is built.

## Real column rename over db_column workaround — Data Integrity Sprint, 2026-03-14

**Decision:** Renamed actual Supabase columns (`program_id` → `course_id`, `program_name` → `course_name`) and removed Django `db_column` parameters, rather than keeping the cosmetic ORM-level rename.

**Alternatives considered:** (1) Keep `db_column` workaround — zero Supabase changes needed. (2) Create a new table with the correct column names and migrate data.

**Rationale:** `db_column` creates a hidden mismatch between what Django code says and what the database actually stores. Anyone querying Supabase directly (RLS policies, dashboards, SQL scripts) would still see the old `program_*` names. A real rename eliminates this confusion layer entirely.

**Trade-offs:** Required coordinating a Supabase ALTER TABLE with a Django migration in the same deploy window. Brief risk of column-not-found errors if deploy order was wrong.

**Revisit if:** Never — this is a one-way improvement.

## TD-001: STPM SPM prerequisite fields — scope finding and user impact — Tech Debt Sprint 4, 2026-03-14

**Decision:** Fix applied (add `spm_pass_bi` and `spm_pass_math` to `SIMPLE_CHECKS` in `stpm_engine.py`). No user notification sent.

**Scope finding:** Queried Supabase production database. All 1,113 STPM requirement rows have `spm_pass_bi = false` and `spm_pass_math = false`. Zero programmes currently require a "pass" (as opposed to "credit") in BI or Math at SPM level. The 12 student profiles in the database have no STPM-specific data stored server-side (STPM eligibility uses client-side localStorage data).

**Alternatives considered:** (1) Fix the code and proactively alert users that results may have been incorrect. (2) Fix the code and do nothing. (3) Remove the unused model fields entirely.

**Rationale:** Since zero programmes set these flags to `true`, the missing check has never produced an incorrect result for any student. Alerting users about a bug that had no effect would cause unnecessary confusion. The fields exist in the model and CSV data for completeness — future programme data may set them. Removing them would lose that forward compatibility.

**Trade-offs:** If future CSV data sets these flags to `true`, the check will now correctly enforce them. Before this fix, such data would have been silently ignored.

**Revisit if:** New STPM programme data is loaded that sets `spm_pass_bi` or `spm_pass_math` to `true` — at that point, verify the STPM golden master baseline changes as expected.

## Backend-only calculations, delete frontend files — TD-002 Sprint, 2026-03-14

**Decision:** All eligibility formulas (merit, CGPA, pathway eligibility, fit scoring) live exclusively in the backend. Frontend deleted `merit.ts`, `stpm.ts`, and `pathways.ts` (596 lines) and now calls three new stateless API endpoints.

**Alternatives considered:** (1) Shared test vectors — keep both implementations, test against same fixtures. (2) Code generation — generate frontend functions from backend source. (3) Backend-only with API calls (chosen).

**Rationale:** User asked "If you were the developer, what would you wish your predecessors had done?" The answer is clear: one implementation, one place to change when requirements change. Shared test vectors still require maintaining two implementations. Code generation adds build complexity. API calls are simple, the app already requires network connectivity, and the ~200ms latency is acceptable for submit-time/page-load calculations.

**Trade-offs:** Grade pages now need network for merit/CGPA display (previously instant). Mitigated with 400ms debounce. Dashboard CGPA-to-percent was inlined as a trivial one-liner (no API call needed).

**Revisit if:** Offline support becomes a requirement, or if API latency degrades user experience on grade entry pages.

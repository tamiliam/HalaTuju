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

## Auth test mock fix over test infrastructure — TD-010 Sprint, 2026-03-14

**Decision:** Fixed 13 failing auth tests by adding a `jwt.get_unverified_header` mock alongside the existing `jwt.decode` mock in all test setUp methods. Did NOT build a reusable auth test infrastructure or JWT signing helper.

**Root cause:** The Supabase auth middleware calls `jwt.get_unverified_header(token)` before `jwt.decode()`. Tests were mocking only `jwt.decode`, but `get_unverified_header('fake-but-patched')` raised `InvalidTokenError` before `jwt.decode` was ever reached.

**Alternatives considered:** (1) Build a proper auth test infrastructure — a `TestAuthMixin` with real JWT signing using a test secret, role-based token generation (student, admin, anonymous), and shared helpers. (2) Simple mock fix (chosen).

**Rationale:** The proper infrastructure (option 1) is the right long-term answer, but it should be built when the admin layer is designed — not now. We don't yet know what roles, permissions, or auth flows the admin layer will need. Building test auth infrastructure now risks designing for requirements that don't exist yet (YAGNI). The mock fix is correct, minimal, and makes all 357 tests pass with 0 failures.

**What a future developer should do:** When building the admin/login tracking layer:
1. Design the role-based permission model first (student, counsellor, admin, etc.)
2. Build a `TestAuthMixin` or fixture that generates real signed JWTs with configurable roles
3. Replace the mock-based approach in `test_auth.py`, `test_saved_courses.py`, and `test_views.py` (reports) with the new mixin
4. Add tests for role-based access (e.g., admin can see all reports, student can only see own)
5. The middleware at `halatuju/middleware/supabase_auth.py` will also need updating for role extraction

**Trade-offs:** Three test files have near-identical mock boilerplate (header patcher + decode patcher). This is a code smell, but extracting a shared helper for 3 files would be premature — wait until the auth model is designed.

**Revisit if:** Admin layer work begins, or if a fourth test file needs the same auth mocking pattern.

## DB fixtures over CSV files for tests — Test Health Sprint, 2026-03-14

**Decision:** Created JSON fixtures (`courses.json`, `requirements.json`) dumped from production Supabase and use Django's `loaddata` in tests. Deleted all CSV-dependent test logic.

**Alternatives considered:** (1) Regenerate the old CSV files from Supabase. (2) Mock the DataFrame directly in each test. (3) DB fixtures via Django's `loaddata` (chosen).

**Rationale:** CSV files were deleted months ago and the data was subsequently modified across multiple sprints. Regenerating CSVs would create a second source of truth. Mocking DataFrames is fragile and wouldn't test the DB→DataFrame pipeline. Django fixtures are the standard approach, load into the test DB, and the shared `conftest.py` helper converts them to a DataFrame — replicating the production startup flow exactly.

**Trade-offs:** Fixture files are large (~33K lines combined). They must be regenerated when production data changes materially. But they're authoritative and testable.

**Revisit if:** Production data changes significantly (new courses, schema changes) — regenerate fixtures from Supabase.

## Golden master rebaseline: 8283 → 5319 — Test Health Sprint, 2026-03-14

**Decision:** Accepted 5319 as the correct SPM golden master baseline, replacing the stale 8283.

**Alternatives considered:** (1) Investigate and reverse the data changes that caused the drop. (2) Accept the new baseline after verification (chosen).

**Rationale:** The 8283 baseline was from CSV data that was migrated to Supabase and then modified across 3+ sprints (data integrity, MOHE audit, field corrections). The golden master test was silently skipping during all of these changes. Verified by comparing per-student eligibility counts between production DataFrame and fixture DataFrame — identical results. The data changes were intentional improvements, not regressions.

**Trade-offs:** None — this is a correction. The old baseline was never validated against the current data.

**Revisit if:** Never — forward baselines should be set against the current DB state.

## SupabaseAuthentication class for 401 responses — API Consistency Sprint, 2026-03-14

**Decision:** Added a lightweight `SupabaseAuthentication` DRF authentication class that returns `None` from `authenticate()` and `'Bearer'` from `authenticate_header()`. Registered as `DEFAULT_AUTHENTICATION_CLASSES`.

**Alternatives considered:** (1) Custom DRF exception handler to map `NotAuthenticated` → 401. (2) Override `APIView.permission_denied()` in a base view class. (3) DRF authentication class (chosen).

**Rationale:** DRF only returns 401 when at least one authenticator provides a `WWW-Authenticate` header. Our auth runs in Django middleware, not DRF's auth pipeline. Rather than fighting the framework (custom exception handlers, view overrides), the authentication class is the canonical mechanism. It's how DRF's own `TokenAuthentication` works.

**Trade-offs:** The class doesn't perform actual authentication (that's the middleware's job). This separation is slightly unintuitive — the "authenticator" is just a header provider. But it follows DRF conventions exactly.

**Revisit if:** The auth architecture changes to move JWT verification into DRF's authentication pipeline (e.g., replacing middleware with a proper DRF authenticator that also verifies tokens).

## Service module extraction for EligibilityCheckView — Refactoring Sprint, 2026-03-14

**Decision:** Extracted business logic from `EligibilityCheckView.post()` into a standalone `eligibility_service.py` module with 5 pure functions, reducing the view from ~310 lines to ~100 lines.

**Alternatives considered:** (1) Private methods on the view class (`_compute_merit()`, `_sort_results()`). (2) A service class with state (`EligibilityService(data, grades)`). (3) Pure module-level functions (chosen).

**Rationale:** Pure functions are the simplest option — no instantiation, no state, no DRF dependencies. Each function takes explicit parameters and returns plain dicts. This makes testing trivial (no request objects, no setUp) and the functions are reusable outside the view if needed. The view becomes a thin orchestrator that handles HTTP concerns only.

**Trade-offs:** The view must pass several parameters to each service function rather than relying on `self`. This is intentional — explicit parameters make data flow visible.

**Revisit if:** A second view needs the same eligibility logic (e.g., batch eligibility API), at which point the service module pays for itself immediately.

## Selenium-based URL validation for MOHE — External Links Sprint, 2026-03-14

**Decision:** Use Selenium with headless Chrome to validate MOHE ePanduan URLs by checking rendered page content, not HTTP status codes.

**Alternatives considered:** (1) httpx/requests HTTP status check. (2) Playwright MCP browser automation. (3) Selenium headless Chrome (chosen).

**Rationale:** MOHE's ePanduan portal always returns HTTP 302→200 regardless of whether the course exists. The rendered page shows "daripada 0 carian" for dead links and "1 daripada 1 carian" for valid links. HTTP clients cannot detect dead links. Playwright MCP failed because Chrome was already running. Selenium with headless Chrome works as a CLI tool without conflicts.

**Trade-offs:** Selenium is slower (~2-3 sec per URL with render wait) and requires Chrome + chromedriver installed locally. But it's a local admin tool, not deployed code.

**Revisit if:** MOHE changes their page structure (rendering detection would break), or if a public API becomes available.

## Course-level vs institution-level external links — External Links Sprint, 2026-03-14

**Decision:** Course detail pages have two distinct link types: (1) "More Info" pill in About section links to the external course portal (MOHE, MOE, polycc), (2) "More Info" button on institution cards links to the institution's own website.

**Alternatives considered:** (1) Single link per institution card combining both. (2) Link everything to MOHE. (3) Separate course-level and institution-level links (chosen).

**Rationale:** Course-level portals (MOHE ePanduan, MOE matric page, PISMP portal) describe the programme itself. Institution websites describe the institution — facilities, contact, admission. These serve different user needs. The separation also handles TVET correctly: TVET courses have per-institution hyperlinks (course-level), while the institution URL is the institution's general website.

**Trade-offs:** More complex frontend logic to determine which URL to show in the About pill (different logic per source_type). But the pattern is consistent once established.

**Revisit if:** A unified course information portal emerges that covers all institution types, or if polycc/MOE links become course-specific rather than portal-level.

## Engine keys as canonical subject format — Subject Key Unification Sprint, 2026-03-15

**Decision:** All SPM subject keys use lowercase engine format (`bm`, `eng`, `math`, `phy`) everywhere — frontend, backend, localStorage, API payloads. `subjects.ts` is the single source of truth with structured category metadata.

**Alternatives considered:** (1) Keep uppercase frontend keys with serializer mapping. (2) Use display names as keys. (3) Unify on engine keys (chosen).

**Rationale:** Engine keys were already used by 90% of the codebase (subjects.ts SUBJECT_NAMES, engine.py, pathways.py, eligibility_service.py, SPM prereqs). Only the grades page used uppercase. Aligning to the majority eliminates the serializer mapping layer entirely — one fewer place to maintain when subjects change.

**Trade-offs:** Beta testers must re-enter SPM grades (localStorage keys changed). Acceptable given small beta user base.

**Revisit if:** A new data source (e.g. MOE API) provides grades in a different key format — would need a mapping layer at the ingestion boundary, not the serializer.

## Default-deny permissions (SupabaseIsAuthenticated) — Security Sprint, 2026-03-14

**Decision:** Changed `REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES` from `AllowAny` to `SupabaseIsAuthenticated`. All 16 public endpoints explicitly marked with `permission_classes = [AllowAny]`.

**Alternatives considered:** (1) Keep AllowAny default and rely on developers remembering to add auth. (2) Use Django's built-in `IsAuthenticated` instead of custom class.

**Rationale:** Default-deny is a security best practice. A forgotten `permission_classes` line now results in 403 (safe) instead of public access (dangerous). Custom `SupabaseIsAuthenticated` is used because auth flows through Supabase JWT middleware, not Django's session auth.

**Trade-offs:** Every new public endpoint requires an explicit `permission_classes = [AllowAny]` line. This is intentional friction — forces the developer to consciously decide that an endpoint should be public.

**Revisit if:** Django's auth backend is changed from Supabase JWT to something else, or if a more granular RBAC system is introduced.

## i18n message files for course descriptions — Tech Debt Quick Wins 2, 2026-03-15

**Decision:** Pre-U course descriptions and headlines are stored in i18n message files (`en.json`, `ms.json`, `ta.json`) under a `courses.{course_id}` key, not in DB fields.

**Alternatives considered:** (1) Add `description_ta` and `headline_ta` fields to the Course model — requires migration, only solves Tamil. (2) Populate existing `description`/`description_en` DB fields — quick but excludes Tamil. (3) i18n message files (chosen).

**Rationale:** The project has a trilingual i18n system (EN/MS/TA) but the Course model only has 2 description fields (MS/EN). For a fixed set of 6 courses, i18n keys are the correct approach — all 3 languages, versioned with the codebase, no migration needed. The detail page checks i18n keys first, falls back to DB fields for the 390+ other courses.

**Trade-offs:** Two rendering paths for descriptions (i18n → DB → fallback template). But this is explicit and the fallback template itself is now an i18n key too.

**Revisit if:** All course descriptions need trilingual support — at that point, either add `description_ta`/`headline_ta` to the model, or build a course content CMS.

## IC gate replaces school input in auth flow — IC Gate Sprint, 2026-03-15

**Decision:** Replaced the optional school name input in AuthGateModal with a compulsory IC number (NRIC) step. IC is validated (DOB age 15–23, valid state code), stored in `StudentProfile.nric`, and displayed masked (`****-**-1234`) on the profile page. IC is immutable after initial entry.

**Alternatives considered:** (1) Keep school input and add IC as an additional field on profile page. (2) Collect IC later when needed (e.g., at application time). (3) Replace school with IC at auth time (chosen).

**Rationale:** User identified that school name was collected but unused, while IC provides verifiable student identity needed for tracking students through graduation. Making it compulsory at auth time ensures all authenticated users have an IC on record. Simple validation (DOB range + state code) catches typos without over-validating.

**Trade-offs:** Students must enter their IC to proceed — some may abandon. Mitigated by privacy reassurance message. IC is not editable after entry, preventing students from gaming eligibility. School field remains in the model but is not collected during auth.

**Revisit if:** User testing shows significant drop-off at the IC step, or if a less intrusive verification method becomes available.

## Profile view/edit per-section pattern — IC Gate Sprint, 2026-03-15

**Decision:** Profile page defaults to read-only view mode. Each section (Identity, Contact, Family) has an Edit button. Only one section can be in edit mode at a time, with Save/Cancel buttons.

**Alternatives considered:** (1) Keep all fields always editable with a single save button. (2) Inline edit on individual fields (click to edit each field). (3) Per-section view/edit (chosen).

**Rationale:** Always-editable forms invite accidental changes. Inline edit adds complexity for mobile. Per-section grouping matches the existing visual sections and gives users clear intent signals — "I want to change my contact info" vs accidental keystrokes.

**Trade-offs:** More state management (editingSection, snapshot for cancel). Slightly more code in the profile page. But UX is cleaner and prevents accidental data loss.

**Revisit if:** User testing reveals the Edit button is too many clicks, or if a more complex profile structure (e.g., education history, multiple addresses) requires a different pattern.

## Course content in BM database columns, not i18n — STPM Headlines Sprint, 2026-03-15

**Decision:** STPM headlines (and all course content: names, descriptions) are stored in BM in the database. The i18n system (`en.json`, `ms.json`, `ta.json`) is used only for static UI strings. If EN/TA course translations are needed later, they will be added as additional DB columns (`headline_en`, `headline_ta`), not i18n keys.

**Alternatives considered:** (1) Store headlines as i18n message keys (`courses.{course_id}.headline`) — trilingual from day one. (2) Store in DB with BM only (chosen). (3) Store in DB with BM + EN columns immediately.

**Rationale:** There are 1341 visible courses (390 SPM + 951 STPM). Maintaining i18n keys for this many courses creates a massive, hard-to-manage JSON file. Course content is dynamic (changes with annual data refreshes) while i18n files are static and versioned with code. DB columns allow content updates via management commands or admin tools without code deploys. BM is sufficient for now — 90%+ of users are BM-literate.

**Trade-offs:** No English or Tamil headlines until DB columns are added. The earlier decision (Tech Debt Quick Wins 2) to use i18n for pre-U descriptions is now inconsistent — those 6 descriptions should eventually migrate to DB columns too.

**Revisit if:** Multi-language course content becomes a priority, or if a course content CMS is built.

## Dual nullable FKs for SavedCourse — Saved Courses Sprint 1, 2026-03-15

**Decision:** SavedCourse has two nullable FKs (`course` → Course, `stpm_course` → StpmCourse) with a DB check constraint ensuring exactly one is set. Partial unique indexes enforce uniqueness per type.

**Alternatives considered:** (1) Generic string field (`course_id` + `course_type` varchar) — simpler model but no referential integrity. (2) Single polymorphic FK with content type — Django's ContentType framework adds complexity. (3) Dual nullable FKs (chosen).

**Rationale:** Referential integrity is non-negotiable for analytics (which courses are popular, applied, offered). Cascading deletes prevent orphan rows. Direct JOINs work without intermediary tables. The tabbed saved page (SPM/STPM) maps naturally to `WHERE course IS NOT NULL` / `WHERE stpm_course IS NOT NULL`. Pattern extends cleanly for a third qualification type (add another nullable FK + update check constraint).

**Trade-offs:** Check constraint makes bulk inserts slightly more complex (must ensure exactly one FK). Two partial unique indexes instead of one simple unique_together. But both are handled transparently by Django ORM.

**Revisit if:** A third qualification pathway (e.g. UEC) is added — at that point, consider whether the pattern still scales or if a polymorphic approach is warranted.

## Deterministic STPM classifier over Gemini AI — Field Taxonomy Sprint 2, 2026-03-16

**Decision:** Used deterministic keyword matching (`classify_stpm_course()`) instead of Gemini AI to classify 1,113 STPM courses into taxonomy keys.

**Alternatives considered:** (1) Gemini classification with structured output (original plan). (2) Manual classification spreadsheet. (3) Deterministic keyword matching on `category` column (chosen).

**Rationale:** STPM `category` values are consistent BM labels (~170 unique values) unlike the messy Gemini-generated `field` values (207 mixed-language). The category data is clean enough for deterministic matching. Benefits: $0 cost, reproducible, testable without API mocking, no rate limits, instant execution.

**Trade-offs:** New STPM categories added in future data refreshes require manual additions to the classifier. But this is a small maintenance cost vs. ongoing API costs and non-determinism.

**Revisit if:** A new data source with thousands of unpredictable category values is added, where keyword matching becomes impractical.

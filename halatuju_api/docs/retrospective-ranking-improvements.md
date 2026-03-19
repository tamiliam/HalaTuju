# Retrospective — Ranking Improvements Sprint (2026-03-19)

## What Was Built

1. **Comprehensive ranking audit** — documented all 4 ranking modes (SPM pre/post quiz, STPM pre/post quiz) with exact scoring rules, point adjustments, sort hierarchies. Identified 7 weaknesses (W4, W7, W8, W11, W14, W16, W21). Saved to `docs/2026-03-18-ranking-audit.md`.

2. **W4: PISMP course tag backfill** — Created `backfill_pismp_tags` management command. 12 specialisation mappings via keyword matching. PISMP base tags cover all 12 CourseTag dimensions. 73 courses backfilled in production Supabase. 33 tests.

3. **W11: STPM pre-quiz RIASEC signal** — Backend `StpmRankingView` derives RIASEC seed from student's STPM subjects when no quiz signals present. Frontend sends subject keys. Science students now see I-type programmes ranked higher pre-quiz; arts students see A-type higher. Post-quiz signals take precedence. 7 tests.

4. **W16 investigation** — Confirmed production has 100% STPM enrichment coverage (1,112/1,112). Test fixtures lack enrichment but production is fine. Closed as resolved.

## What Went Well

- **Audit-first approach** — doing a comprehensive audit before fixing anything prevented wasted effort. W16 was resolved without code changes (just a data investigation). W4 scope was clarified (73 PISMP only, not 75 including Asasi).
- **Reuse of existing infrastructure** — W11 reused `calculate_riasec_seed()` from the quiz engine and `_get_riasec_alignment()` from the ranking engine. Zero new scoring logic needed.
- **Production data queries** — querying Supabase directly revealed the real picture (vs test fixtures which showed 0 coverage across everything).

## What Went Wrong

1. **Test fixtures vs production data confusion**
   - *What happened*: Initial investigation reported 0 CourseTag rows across ALL course types, contradicting CLAUDE.md.
   - *Why*: Explore agent queried test fixtures (empty) instead of production Supabase. The test database doesn't load CourseTag fixture data.
   - *Fix*: When investigating data coverage, always query production Supabase directly. Test fixtures are for logic testing, not data completeness auditing.

2. **STPM enrichment false alarm**
   - *What happened*: Explore agent reported 99.9% null enrichment fields, triggering W16 as a priority item.
   - *Why*: Same root cause — test fixtures don't include StpmCourse enrichment data.
   - *Fix*: Same as above. Production queries are authoritative for data coverage questions.

## Design Decisions

- **W11 injected at view layer, not ranking engine** — the RIASEC seed derivation happens in `StpmRankingView.post()` before calling `get_stpm_ranked_results()`. This keeps the ranking engine pure (it just consumes signals) and makes the injection easy to test via API.
- **Post-quiz signals take precedence** — if `riasec_seed` already exists in signals (from quiz), `stpm_subjects` is ignored. This ensures the quiz (which is more nuanced) always wins.
- **PISMP base tags are conservative** — all PISMP courses get `high_people`, `regulated_profession`, `stable` career. Specialisation overrides only change dimensions that genuinely differ (environment, cognitive_type, etc.).

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 892 | 932 (+40) |
| PISMP courses with tags | 0 | 73 |
| STPM pre-quiz score range | 30-70 (CGPA only) | 30-98 (CGPA + RIASEC) |
| Ranking weaknesses open | 7 | 4 (W7, W8, W14, W21) |

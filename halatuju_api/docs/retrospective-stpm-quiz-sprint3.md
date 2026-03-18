# Retrospective — STPM Quiz Engine Sprint 3 (2026-03-18)

## What Was Built

Quiz-informed STPM ranking engine. Replaced the simple 3-factor formula (CGPA + field match + interview) with a 7-component formula that uses all quiz signal categories. Added result framing logic (3 modes from Q1 crystallisation signal). Wired enrichment fields into the eligibility output so they flow to ranking.

**Files modified:** 3 (stpm_ranking.py, stpm_engine.py, views.py)
**Files rewritten:** 1 (test_stpm_ranking.py — from 11 to 58 tests)

## What Went Well

- **Design doc precision:** Section 11 specified exact point values for every scoring component. Translation to code was mechanical — no design decisions needed during implementation.
- **Clean separation:** The ranking engine is pure functions with no database access. All course enrichment data (riasec_type, difficulty_level) flows through the eligible course dicts. This made testing trivial — just build dicts and call functions.
- **Backwards compatibility:** The new formula gracefully handles missing signals (empty dicts → 0 bonus). A student who skips the quiz gets CGPA + base only, same as v1.
- **No regressions:** 881 total backend tests pass. Both golden masters unchanged.

## What Went Wrong

Nothing. The sprint was clean because:
1. The scoring formula was fully specified in the design doc
2. No model changes were needed (Sprint 2 already added the fields)
3. The existing ranking test structure provided clear patterns

## Design Decisions

1. **Import FIELD_KEY_TO_RIASEC from enrich command:** The `_get_field_match_score` function imports `FIELD_KEY_TO_RIASEC` from the enrichment command to map cross-domain signals to course field_keys. This creates a dependency on the management command module, but avoids duplicating the mapping. The mapping is authoritative in one place.

2. **_FK_TO_INTEREST reverse mapping:** Created a manual mapping from field_key signals (e.g. `field_key_mekanikal`) back to their parent field_interest (e.g. `field_engineering`). This is needed for secondary field matching — when a student picks "Engineering" in Q2 but a course's field_key is `elektrik` (not in the Q3 sub-field they chose). The mapping is in `stpm_ranking.py`, not `stpm_quiz_data.py`, because it's a ranking concern.

3. **Goal alignment tiers:** Rather than a flat bonus, goal alignment uses high/low tiers. `goal_professional` only gives +4 if the course is in a regulated profession (medicine, law, engineering). `goal_employment` gives +3 universally. This prevents gaming where any goal gives a flat bonus regardless of course type.

4. **Framing in ranking response:** Result framing (heading + subtitle + mode) is returned in the ranking API response rather than a separate endpoint. The frontend needs it alongside ranked courses, so bundling avoids an extra API call.

## Numbers

| Metric | Value |
|--------|-------|
| Files modified | 3 |
| Files rewritten | 1 |
| New tests | 58 (was 11) |
| Total backend tests | 881 |
| Test failures | 0 |
| Golden master SPM | 5319 (unchanged) |
| Golden master STPM | 2026 (unchanged) |
| Scoring components | 7 |
| Max possible score | 98 |
| Min possible score | 42 |
| Framing modes | 3 |

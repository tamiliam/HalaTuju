# Retrospective — API Consistency Sprint (2026-03-15)

## What Was Built

Standardised API response formats and extracted hardcoded constants:
- **TD-005**: Audited error responses — already consistent (`{'error': 'message'}` everywhere)
- **TD-006**: Standardised `count` → `total_count` across CourseListView, InstitutionListView, OutcomeListView
- **TD-022**: Extracted `SOURCE_TYPE_ORDER` from inline method variable to module-level constant
- **TD-026**: Added `course_name` alias to `CourseSerializer` via `CharField(source='course')` — backwards compatible
- **TD-052**: Extracted merit gap thresholds to named constants in `engine.py` (`MERIT_GAP_HIGH`, `MERIT_GAP_FAIR`, `MERIT_COLORS`). `eligibility_service.py` now derives its colour tuples from `engine.MERIT_COLORS`.

## What Went Well

- All changes were backwards compatible — no frontend code changes required
- CourseSerializer alias approach (`course_name = CharField(source='course')`) means both `course` and `course_name` exist in responses, so existing frontend code keeps working
- Only 4 test assertions needed updating (all `count` → `total_count`)
- Golden masters unaffected (SPM 5319, STPM 1811)

## What Went Wrong

Nothing significant. Initially considered changing all count keys to exactly `total_count` across every endpoint, but realised contextual keys like `total_eligible` and `total_ranked` already match their frontend TypeScript types and have specific semantics — changing them would break things for no benefit.

## Design Decisions

- **Kept contextual count keys**: `total_eligible` (STPM eligibility), `total_ranked` (ranking), `total` (quiz, STPM ranking) left as-is. These match frontend TypeScript interfaces and have endpoint-specific meanings.
- **Added alias, didn't rename**: `CourseSerializer` now returns both `course` and `course_name`. Frontend can migrate to `course_name` gradually.
- **Frontend thresholds not touched**: Matric page (94/89) and STPM detail page (80/60) thresholds left in frontend — the matric page uses API-provided labels anyway, and the STPM page thresholds are for average merit display (different context from eligibility thresholds).

## Numbers

| Metric | Value |
|--------|-------|
| Backend tests | 424 pass, 0 fail |
| Golden masters | SPM 5319, STPM 1811 |
| Frontend build | Clean |
| Files changed | 6 (views.py, engine.py, eligibility_service.py, serializers.py, test_api.py, test_outcomes.py) |
| Tech debt resolved | 5 items (TD-005, TD-006, TD-022, TD-026, TD-052) |
| Total resolved | 35/52 |

# Sprint 4 Retrospective — Ranking Engine Backend

**Date**: 2026-02-17
**Duration**: Single session
**Deliverable**: Ported ranking engine from Streamlit to Django API

## What Was Built

- `apps/courses/ranking_engine.py` — 290-line port of the 551-line Streamlit ranking engine
- `RankingRequestSerializer` — validates eligible_courses + student_signals
- `RankingView.post()` — wired endpoint at `POST /api/v1/ranking/`
- AppConfig extended to load course_tags_map, inst_subcategories, inst_modifiers_map at startup
- 34 new tests across 7 test classes

## What Went Well

- **Dependency injection** made the port clean. By passing course tags and institution data as parameters instead of using module-level globals, the ranking engine is fully testable without a database.
- **No golden master breakage**. The eligibility engine was untouched — 8280 baseline held throughout.
- **No migrations needed**. All data structures already existed in the models; only the loading logic in AppConfig needed extension.
- **Clean test isolation**. Tests use explicit tag/signal dicts, no DB fixtures needed for the ranking logic tests.

## What Went Wrong

- **Default tag values caused test failures**. Two institution modifier tests failed initially because `income_risk_tolerant` also triggers course tag scoring via the default `career_structure='volatile'`. Fix: provide explicit neutral tags in test setup to isolate the behaviour being tested.
  - **Lesson**: When testing one subsystem in a scoring engine with many interacting rules, always provide explicit inputs for ALL subsystems — don't rely on "empty" meaning "neutral".

## Design Decisions

1. **Pure functions over globals**: The Streamlit version cached `COURSE_TAGS`, `INST_MODIFIERS`, and `INST_SUBCATEGORIES` as module-level globals loaded from JSON files. The Django version loads these in AppConfig.ready() and passes them as parameters to ranking functions. This eliminates hidden state and makes testing trivial.

2. **Institution modifiers stay in JSON for now**: The `urban` and `cultural_safety_net` fields aren't in the Institution model yet. Rather than adding a migration + data load in this sprint, we load from `data/institutions.json` at startup. A future sprint can migrate these to model fields.

3. **No code deduplication with Streamlit version**: The Django ranking engine is a standalone port, not a wrapper around the Streamlit code. This is intentional — the Streamlit version will be retired after migration is complete.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests | 70 | 104 |
| New tests | — | +34 |
| Golden master | 8280 | 8280 |
| Files created | — | 2 (ranking_engine.py, test_ranking.py) |
| Files modified | — | 4 (views.py, serializers.py, apps.py, CLAUDE.md) |
| Migrations | 0 | 0 |
| Deploys | 0 | 0 |

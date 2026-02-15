# Sprint 3 Retrospective — Quiz API Backend

**Date**: 2026-02-16
**Branch**: `feature/v1.1-stream-logic`

## What Was Built

1. **Quiz data module** (`apps/courses/quiz_data.py`): 6 psychometric questions × 3 languages (EN, BM, TA), ported from `src/quiz_data.py`. Pure data — no logic, no state.
2. **Quiz engine** (`apps/courses/quiz_engine.py`): Stateless signal accumulator. Takes a list of answers, returns categorised `student_signals` in the 5-bucket taxonomy + signal strength map.
3. **Quiz questions endpoint** (`GET /api/v1/quiz/questions/?lang=en`): Returns questions in the requested language. Falls back to English for unknown languages. Public (no auth).
4. **Quiz submit endpoint** (`POST /api/v1/quiz/submit/`): Accepts 6 answers, validates question IDs and option indices, runs the engine, returns signals. Public (no auth).
5. **14 tests**: 4 endpoint tests (questions), 6 endpoint tests (submit + validation), 4 engine unit tests (accumulation, strength, empty signals, language parity).

## What Went Well

- **Clean port**: The Streamlit-era code had clear separation between data (`quiz_data.py`) and logic (`quiz_manager.py`). Stripping `st.session_state` was straightforward — the core algorithm was already sound.
- **Exceeded test target**: Roadmap said 8-10 tests, delivered 14. The extra tests cover all validation paths and language parity.
- **No backend changes needed elsewhere**: `ProfileView.put()` already accepted `student_signals` in its allowed fields list. Zero modifications to existing code beyond imports and URL registration.
- **No migrations**: Pure Python — no DB schema changes. No Supabase security checks needed.
- **Fast sprint**: Data + engine + views + tests + URLs completed in a single pass with no errors.

## What Went Wrong

Nothing went wrong this sprint. The scope was well-defined, the source code was clean, and no unexpected issues emerged.

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Stateless engine (no DB, no session) | Quiz results are ephemeral — frontend stores them in state and optionally saves to profile via `PUT /api/v1/profile/`. No reason to persist quiz answers server-side. |
| Public endpoints (no auth) | The quiz is a lead-generation tool — unauthenticated users should be able to take it. Signals are only persisted if the user logs in and saves their profile. |
| Dict-based data (not DB model) | 6 questions × 3 languages = 18 records. Too small for a DB table. A Python dict is simpler, faster, and version-controlled. |
| 5-category taxonomy with reverse lookup | The engine categorises signals into 5 buckets matching the ranking engine's expected input. A reverse lookup dict (`_SIGNAL_TO_CATEGORY`) avoids nested loops. |
| `option_index` not `option_text` | Index is unambiguous across languages. If a user answers in BM, the signal mapping is identical to answering in EN — only the display text differs. |

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests | 56 | 70 |
| Golden master | 8280 | 8280 |
| Backend files | 6 key files | 8 key files (+quiz_data, +quiz_engine) |
| API endpoints | 9 | 11 (+quiz/questions, +quiz/submit) |

## Next Steps

Sprint 4: Ranking Engine Backend
- Port `src/ranking_engine.py` → `apps/courses/ranking_engine.py` (551 lines — most complex migration task)
- Load course tags from `CourseTag` model (not JSON file)
- Load institution modifiers from `Institution` model (not JSON file)
- Implement `RankingView.post()` (currently a stub)
- 10-15 tests (score calculation, cap enforcement, merit penalty, tie-breaking, sort stability)

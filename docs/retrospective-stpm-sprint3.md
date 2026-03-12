# STPM Sprint 3 Retrospective — Ranking Engine + Supabase Migration

**Date:** 2026-03-13
**Branch:** `feature/stpm-entrance`

## What Was Built

1. **Supabase migration** — Created `stpm_courses` and `stpm_requirements` tables with RLS policies (public read). Loaded all 1,113 courses and 1,113 requirements via batch SQL inserts.

2. **STPM ranking engine** (`stpm_ranking.py`) — Pure-function scoring: BASE=50, CGPA margin bonus (+20 max, capped at 1.0), field interest match (+10 via keyword→signal mapping), interview penalty (-3). Sorts descending by fit_score, ties broken by programme name.

3. **Ranking API endpoint** (`POST /api/v1/stpm/ranking/`) — Accepts eligible programmes + student CGPA + quiz signals, returns ranked list with fit_score and fit_reasons per programme.

4. **Frontend integration** — `rankStpmProgrammes()` API client chains ranking after eligibility check. Dashboard displays colour-coded fit score badges (green ≥70, amber ≥55, grey <55) and fit reasons on each programme card.

## What Went Well

- **Batch loading strategy**: Breaking 1,113 requirements into 23 batches of 50 rows (~17KB each) kept every SQL call under the Supabase MCP tool's limits. All 23 batches succeeded first try.
- **Pattern reuse**: The STPM ranking engine mirrors `ranking_engine.py` patterns (pure functions, dict-in/dict-out, type hints) making review straightforward.
- **Clean test progression**: 8 ranking tests + 5 API tests all passed on first run. No debugging needed.
- **Frontend build clean**: TypeScript types for the new ranking response passed the build without type errors.

## What Went Wrong

1. **Context exhaustion during Supabase loading**
   - Symptom: Previous session ran out of context mid-way through loading requirements batches.
   - Root cause: Each SQL batch insert consumed significant context (full SQL + MCP response), and 23 batches exceeded the window.
   - Fix: In the continuation session, delegated batches 8-22 to a subagent, keeping the main context lean. Future bulk data operations should always use subagents for batch work.

## Design Decisions

- **Separate ranking module** (`stpm_ranking.py`) rather than extending `ranking_engine.py`: The SPM ranking engine is tightly coupled to SPM-specific concepts (merit tiers, credential priority, pathway scoring). A separate module keeps both clean and independently testable.
- **Client-side ranking chain** (eligibility → ranking as two API calls): Keeps the eligibility endpoint pure (no quiz signal dependency) and lets the ranking be optional or cached independently.

## Numbers

| Metric | Value |
|--------|-------|
| Tests collected | 307 |
| Tests passing | 274 |
| Tests added | 13 (8 ranking + 5 API) |
| SPM golden master | 8283 (unchanged) |
| STPM golden master | 1811 (unchanged) |
| Supabase rows loaded | 2,226 (1,113 courses + 1,113 requirements) |
| Commits | 4 (ranking engine, API endpoint, frontend, docs) |

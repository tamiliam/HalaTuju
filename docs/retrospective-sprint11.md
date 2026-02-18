# Sprint 11 Retrospective — AI Report Backend

**Date**: 2026-02-18
**Duration**: Single session
**Deliverable**: Gemini-powered narrative counselor report generation

## What Was Built

- **`apps/reports/prompts.py`**: BM and EN counselor report templates ported from legacy `src/prompts.py`. Added `insights_summary` placeholder for deterministic insights. Counselor personas mapped by model family (Cikgu Venu for gemini-3, Cikgu Gopal for gemini-2.5, Cikgu Guna for gemini-2.0).
- **`apps/reports/report_engine.py`**: Core `generate_report()` function — formats student data (grades, signals, eligible courses, insights) into a prompt, calls Gemini with model cascade fallback (gemini-2.5-flash → gemini-2.5-flash-lite → gemini-2.0-flash), returns markdown + metadata.
- **`apps/reports/views.py`**: Three endpoints wired up — `POST /api/v1/reports/generate/` (generate and save), `GET /api/v1/reports/` (list student's reports), `GET /api/v1/reports/<id>/` (report detail). All auth-protected.
- **12 new tests**: Format helpers (6), prompt templates (2), persona mapping (1), Gemini mock tests (3 — success, cascade fallback, missing API key).

## What Went Well

- **Clean reuse of existing infrastructure**: `GeneratedReport` model, migration, URL routing, and `GEMINI_API_KEY` in settings were all already in place from earlier sprints. Only needed to fill in the engine and views.
- **All 144 tests passed** (132 existing + 12 new) — no regressions.
- **Golden master 8280 unchanged** — no eligibility logic touched.
- **Design simplification**: Report view accepts `eligible_courses` and `insights` from the frontend (already available from eligibility check) instead of re-running the expensive eligibility engine internally. Avoids code duplication.
- **Legacy port was straightforward**: The Streamlit `ai_wrapper.py` had a solid model cascade pattern. Adapted cleanly to Django without the Streamlit/OpenAI baggage.

## What Went Wrong

- **Mock patching issue**: Initial tests tried to patch `apps.reports.report_engine.genai` but `genai` is imported lazily inside the function (not at module level). Fixed by patching `google.generativeai.GenerativeModel` directly. Lesson: when mocking lazy imports, patch the actual module path, not the local reference.

## Design Decisions

1. **Frontend sends eligible_courses + insights**: The report endpoint doesn't re-run the eligibility check. The frontend already has these from the `/eligibility/check/` call. This avoids duplicating the heavy eligibility loop and keeps the report endpoint focused on prompt formatting + Gemini.
2. **Model cascade without OpenAI fallback**: The legacy wrapper had OpenAI as a fallback. Removed for simplicity — three Gemini models provide sufficient redundancy. Can add back if needed.
3. **Lazy genai import**: `google.generativeai` is imported inside `generate_report()` rather than at module level. This prevents import errors if the package isn't installed in a test/dev environment.
4. **Report saved to DB**: Every generation creates a `GeneratedReport` row with profile + courses snapshots. Students can retrieve past reports without re-generating.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 132 | 144 |
| Golden master | 8280 | 8280 |
| Files created | — | 4 (report_engine.py, prompts.py, test_report_engine.py, retrospective) |
| Files modified | — | 4 (views.py, urls.py, CHANGELOG, CLAUDE.md) |

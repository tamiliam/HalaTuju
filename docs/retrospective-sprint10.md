# Sprint 10 Retrospective — Deterministic Insights

**Date**: 2026-02-18
**Duration**: Single session
**Deliverable**: Insights engine + frontend panel, KKOM source_type separation

## What Was Built

- **`insights_engine.py`**: Pure function `generate_insights(eligible_courses)` that produces structured summaries — stream breakdown with Malay labels, top 5 fields by count, level distribution, merit summary (high/fair/low/no_data), and a one-line Malay summary text.
- **Eligibility response enhancement**: `POST /api/v1/eligibility/check/` now returns an `insights` key embedded in the response. No new endpoint needed — simpler than originally planned.
- **InsightsPanel component**: Three-column dashboard section showing Bidang Teratas (top fields), Tahap Pengajian (level distribution), and Peluang Kemasukan (merit bar chart with colour-coded bars).
- **KKOM separation** (user change): Kolej Komuniti requirements extracted from `requirements.csv` into `kkom_requirements.csv` with `source_type: 'kkom'`.
- **8 new tests**: Empty input, stream breakdown counts, Malay labels, top fields ranking, merit aggregation, level distribution, summary text.

## What Went Well

- **Design simplification**: Originally planned a separate `POST /api/v1/insights/` endpoint. Embedding insights in the eligibility response is simpler (one API call, no extra frontend fetch).
- **All 132 tests passed first run** — no bugs.
- **Golden master 8280 unchanged** — no eligibility logic touched.
- **Frontend build succeeded first try** — clean TypeScript, no type errors.
- **Pure function approach**: `generate_insights()` takes a list and returns a dict. No DB queries, no side effects, trivially testable.

## What Went Wrong

- Nothing. Clean sprint.

## Design Decisions

1. **Embed in eligibility response vs separate endpoint**: Embedding avoids an extra API call and keeps the frontend simple. Sprint 11's AI report backend can call `generate_insights()` internally.
2. **Malay labels and text**: All insight labels in Malay (Bidang Teratas, Tahap Pengajian, Peluang Kemasukan) to match the app's bilingual audience. Summary text is fully Malay.
3. **Merit bar chart**: Only shows courses that have merit data (excludes TVET with no_data). Uses percentage-width bars with green/yellow/red colours matching the existing traffic light system.
4. **Top 5 fields limit**: Capped at 5 to avoid clutter. Most students have 4-5 distinct fields anyway.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 124 | 132 |
| Golden master | 8280 | 8280 |
| Files created | — | 3 (insights_engine.py, test_insights.py, retrospective) |
| Files modified | — | 6 (views.py, api.ts, page.tsx, CHANGELOG, CLAUDE.md, roadmap) |
| User changes included | — | 3 (requirements.csv, kkom_requirements.csv, load_csv_data.py, test_golden_master.py) |

# Sprint 8 Retrospective — Course Detail Enhancement

**Date**: 2026-02-18
**Duration**: Single session
**Deliverable**: Course detail page enriched with fees, allowances, "Apply" links, and benefit badges

## What Was Built

- **`load_course_details`** method in `load_csv_data.py`: Reads `details.csv` (407 rows) and enriches existing CourseInstitution rows with fees, allowances, hyperlinks, and free hostel/meals flags. TVET rows match by course+institution; Poly/Univ rows apply to all institutions for that course.
- **Enhanced API response**: `GET /courses/<id>/` now returns per-institution offering details (tuition, hostel, registration fees, monthly/practical allowances, free_hostel, free_meals, hyperlink) alongside basic institution data.
- **Frontend enhancements**: InstitutionCard now shows fee grid, "Apply" button linking to official portal, and coloured badges for allowances and free benefits.
- **5 new tests**: Offering fees, hyperlink, allowances, free badges, empty field handling.

## What Went Well

- **No schema migration needed**: CourseInstitution model already had all the fee fields from initial setup — just needed to populate them.
- **Clean data loading strategy**: TVET rows have institution_id (per-institution fees), Poly/Univ rows don't (shared fees) — handled with a simple `if inst_id` branch.
- **All 119 tests passed on first run** — no bugs encountered.
- **Zero engine changes** — this sprint was purely presentation layer, so golden master was never at risk.

## What Went Wrong

- Nothing. Clean sprint with no failures or rework.

## Design Decisions

1. **Inline offering data in institution response**: Rather than creating a separate `offerings` array, the fee/hyperlink fields are merged directly into each institution object. Simpler for the frontend and avoids breaking the existing `institutions` response shape.
2. **Allowance parsing strips "RM" prefix**: `details.csv` stores allowances as `RM100`, `RM300` etc. The loader strips the prefix and stores as Decimal. Frontend re-adds "RM" in display.
3. **No separate serializer**: Offering fields are added inline in the view rather than creating a CourseInstitutionSerializer. Keeps it simple — only 8 fields added.

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 114 | 119 |
| Golden master | 8280 | 8280 |
| Files modified | — | 5 (load_csv_data.py, views.py, api.ts, page.tsx, test_api.py) |
| Files created | — | 0 |
| Frontend routes | 16 | 16 |
| Offerings with hyperlinks | 0 | 407 |
| Offerings with fee data | 0 | 320+ |

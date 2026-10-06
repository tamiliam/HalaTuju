# Sprint 6 Retrospective — Dashboard Redesign (Card Grid)

**Date**: 2026-02-17
**Duration**: Single session
**Deliverable**: Responsive card grid with merit traffic lights

## What Was Built

- **Merit calculation in eligibility endpoint**: `prepare_merit_inputs` + `calculate_merit_score` compute student merit once per request; `check_merit_probability` adds `merit_label`/`merit_color` per eligible course
- **CourseCard component** (`components/CourseCard.tsx`): Reusable vertical card with field image header, type/level badges, merit traffic light, rank badge, fit reasons, and save button
- **Responsive card grid**: `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` replaces single-column list for both flat and ranked views
- **Merit traffic lights**: Green dot (High Chance), amber (Fair Chance), red (Low Chance) based on student merit vs course cutoff. TVET courses show no indicator.
- **Low merit dimming**: Cards with `merit_label === 'Low'` rendered at 60% opacity

## What Went Well

- **Backend merit functions already existed**. `prepare_merit_inputs`, `calculate_merit_score`, and `check_merit_probability` were all in `engine.py` from the Streamlit app. Just needed to call them from the Django view.
- **Clean build on first try**. No TypeScript errors, no build failures after the full rewrite.
- **Significant code reduction**. Dashboard went from ~764 lines to ~370 lines by extracting CourseCard and FilterDropdown.
- **Bug fix for free**. The ranking engine's merit penalty was silently broken (defaulting `student_merit` to 0). Adding `student_merit` to the eligibility response fixed this without changing ranking code.

## What Went Wrong

- **Grade key mismatch**: `prepare_merit_inputs` uses `'history'` but the Django serializer maps SEJ to `'hist'`. Caught during planning, fixed with a simple key rename before calling the function. This is a latent inconsistency between the Streamlit-era engine code and the Django serializer conventions.
- **Plan file deletion**: The detailed sprint plan file was deleted at Sprint 4 close per workflow, but it contained file-level breakdowns for all 15 sprints. Had to rebuild Sprint 6 scope from the roadmap summary and memory file. Going forward, the plan file should either not be deleted or the file-level detail should be captured in the roadmap itself.

## Design Decisions

1. **Vertical card layout**: Cards use image-on-top instead of image-on-left. Better for grid columns — each card is self-contained and works at any width.

2. **Merit in eligibility response, not ranking**: Merit traffic lights should show regardless of quiz completion. Adding it to the eligibility endpoint (not ranking) means all users see it, not just quiz-takers.

3. **CoQ defaults to 5.0**: The merit formula includes co-curricular quality (0-10). We default to 5.0 (neutral) since there's no UI to capture it yet. This means merit scores are slightly conservative.

4. **Low merit dimmed, not filtered**: The original decision said "below min = filtered out". We chose to dim (opacity-60) instead, keeping the course visible. This avoids changing the eligibility count and gives students full information.

5. **Fit reasons capped at 2**: In the card grid, space is tighter than the old horizontal layout. Fit reason tags limited to 2 per card (was 3).

## Numbers

| Metric | Before | After |
|--------|--------|-------|
| Backend tests | 104 | 106 |
| Golden master | 8280 | 8280 |
| Files created | — | 1 (CourseCard.tsx) |
| Files modified | — | 4 (views.py, test_api.py, api.ts, dashboard/page.tsx) |
| Dashboard lines | ~764 | ~370 |
| Frontend routes | 16 | 16 |
| Migrations | 0 | 0 |

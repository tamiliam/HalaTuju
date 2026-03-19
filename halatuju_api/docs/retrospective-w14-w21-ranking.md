# Retrospective — W14+W21 Ranking Tiebreak & Science Tracks Sprint

**Date:** 2026-03-20

## What Was Built

- **W14**: 5-level STPM sort tiebreaking hierarchy replacing 2-level sort (score+name). New levels: university tier (research/comprehensive/focused), min_cgpa competitiveness, difficulty_level. UNIVERSITY_TIER map for 9 universities.
- **W21**: TRACK_FIELD_MAP expansion — added `matric:sains` and `stpm:sains` tracks mapping to `field_health` + `field_agriculture` for +3 field preference bonus.

## What Went Well

- Both changes were small, focused, and quick to implement.
- Combined into a single sprint since they were independent ranking improvements.
- Test-first approach caught a scoring conflict in the competitiveness tiebreak test.

## What Went Wrong

1. **Competitiveness tiebreak test used min_cgpa values that affected the base score differently.**
   - Symptom: `test_competitiveness_breaks_tie` failed because courses A and B had different fit scores despite intending to test only the tiebreaker.
   - Root cause: `min_cgpa` feeds into both CGPA margin (which affects score) and the competitiveness tiebreaker. Setting min_cgpa=2.5 vs 3.5 with student_cgpa=3.5 gives margins of 1.0 vs 0.0 — different scores, not a tie.
   - Fix: Changed test values so both courses exceed the CGPA_MARGIN_CAP (1.0), ensuring equal scores. Lesson: when testing tiebreakers, ensure all prior sort keys produce equal values.

## Design Decisions

- **UNIVERSITY_TIER grouping**: Research (5 unis, tier 3) > Comprehensive (4 unis, tier 2) > Focused (all others, tier 1). Based on Malaysian university classification. Defaulting unlisted to tier 1 avoids maintenance overhead.
- **Science track mapping**: `matric:sains` and `stpm:sains` both map to health + agriculture — the two fields most aligned with pure science pathways.

## Numbers

- Tests: 958 → 966 (+8)
- Files changed: 6
- Golden masters: unchanged (SPM=5319, STPM=2026)

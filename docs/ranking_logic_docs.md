# Ranking Engine Logic Documentation

## Overview
The Ranking Engine (`src/ranking_engine.py`) matches a Student's Profile (signals) to Course Metadata (tags). It calculates a **Fit Score** (Base 100) for every course offering.

## Scoring Methodology
**Base Score:** 100
**Global Cap:** ±20 (Score range 80-120)
**Category Cap:** ±6 per category

### 1. Work Preference Signals
Matches the nature of the work.
- **Hands-On**:
  - `+5` if Student `hands_on > 0` AND Course `work_modality = 'hands_on'`.
  - `-3` if Student `hands_on = 0` AND Course `work_modality = 'hands_on'`.
- **Problem Solving**: `+3` if Student `problem_solving > 0` AND Course `mixed`.
- **Helping People**: `+4` if Student `people_helping > 0` AND Course `high_people`.
- **Creative** (Weighted Split):
  - `+4` if Student `creative > 0` AND Course `project_based`. (Active Creation)
  - `+2` if Student `creative > 0` AND Course `abstract`. (Conceptual Creation)

### 2. Environment Fit
Matches the physical location of work.
- **Workshop**: `+4` if `workshop` match.
- **Office**: `+4` if `office` match.
- **Field**: `+4` if `field` match.
- **Social**: `+3` if Student `high_people_environment` AND Course `high_people` or `office`.

### 3. Learning Tolerance
Matches how the student prefers to learn.
- **Learning by Doing**: `+3` if `hands_on` or `project_based`.
- **Theory Oriented**: `+3` if `theory` or `mixed`.
- **Concept First**: `+3` if `theoretical` or `abstract`.
- **Project Based**: `+3` if `project_based`.

### 4. Energy Sensitivity (Safety Rails)
Penalizes courses that might cause burnout based on sensitivity.
- **Introversion**: `-6` if Student `low_people_tolerance` AND Course `high_people`.
- **Physical Fatigue**: `-6` if Student `physical_fatigue_sensitive` AND Course `physically_demanding`.

### 5. Value Trade-off
Matches alignment with student goals.
- **Entrepreneurial**: `+3` if `income_risk_tolerant`.
- **Stability**: `+4` if `regulated_profession` or `employment_first`.
- **Pathway**: `+4` if `pathway_friendly`.
- **Meaning**: `+3` if `people_helping` or `regulated`.

---

## Institution Modifiers
Adjusts score based on the specific campus location.
**Cap:** ±5

1. **Urban Preference**:
   - `+2` if Student `income_risk_tolerant` (Proxy for Income) AND Institution is `Urban`.

2. **Cultural Safety Net (Community Support)**:
   - Trigger: Student `proximity_priority > 0`.
   - `+4` if Institution Cultural Safety Net = `High`.
   - `-2` if Institution Cultural Safety Net = `Low`.

---

## Dashboard Grouping (Requirement B)
Course offerings are grouped by **Course ID**.
- **Displayed Score**: The MAXIMUM score among all available locations.
- **Fit Reasons**: Aggregated from the best fit.
- **Location Ordering**: Locations within the course card are sorted by their specific score descending.

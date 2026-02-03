# Merit Point Integration Plan

> **Status**: ✅ **IMPLEMENTED** (2026-02-03)
>
> All core functionality is complete. Merit badges now display on course cards.

## Objective
To implement a "Merit Point" system that estimates a student's probability of admission into Public Universities (UA) and Polytechnic/KK by comparing their calculated merit score against historical admission statistics.

## Data Source

| Source | Status | Location |
|--------|--------|----------|
| **Public Universities (UA)** | ✅ Complete | `data/university_requirements.csv` (205 programs with cutoffs) |
| **Polytechnic (POLY)** | ✅ Complete | `data/requirements.csv` (85 programs with cutoffs) |
| **Kolej Komuniti (KK)** | ✅ Complete | `data/requirements.csv` (48 programs with cutoffs) |
| **TVET (ILJTM/ILKBS)** | ❌ Excluded | No merit system |
| **PISMP** | ❌ Excluded | No merit data available |
| **STPM** | ❌ Excluded | Different admission system |

### Data Files
- `data/requirements.csv` - Contains `merit_cutoff` column for Poly/KK (133 courses)
- `data/university_requirements.csv` - Contains `merit_cutoff` column for UA (205 courses)
- `data/merit_cutoffs.csv` - Archive/backup of Poly/KK merit data (no longer loaded separately)

## Implementation Summary

### 1. Student Merit Calculation ✅
**Location**: `src/engine.py:201` - `calculate_merit_score()`

**Formula**: `(AcademicScore * 0.90) + (CoCurriculumScore * 0.10)`
- **AcademicScore**: Calculated from best subject grades (standardized 18-point scale)
- **CoCurriculumScore**: User input (0-10)

**Helper**: `src/engine.py:619` - `prepare_merit_inputs()` - Auto-splits grades into UPU sections.

### 2. Probability Classification ✅
**Location**: `src/engine.py:595` - `check_merit_probability()`

| Condition | Label | Color |
|-----------|-------|-------|
| `StudentMerit >= CourseCutoff` | **High Chance** | 🟢 Green (#2ecc71) |
| `StudentMerit >= CourseCutoff - 5` | **Medium Chance** | 🟡 Yellow (#f1c40f) |
| `StudentMerit < CourseCutoff - 5` | **Low Chance** | 🔴 Red (#e74c3c) |

*Buffer of ±5 points accounts for year-to-year fluctuations.*

### 3. Dashboard Integration ✅
**Location**: `src/dashboard.py:390-412`

- Merit calculated once per student in `generate_dashboard_data()` (line 154)
- Badge rendered in `render_course_card()` when `merit_cutoff > 0`
- Displays: `📊 {Chance Label}` with tooltip showing exact scores
- Translations available for EN, BM, TA

### 4. Data Loading ✅
**Location**: `src/data_manager.py`

- Merit cutoffs loaded directly from `requirements.csv` (Poly/KK)
- Merit cutoffs loaded from `university_requirements.csv` (UA)
- **Note**: Removed redundant merge with `merit_cutoffs.csv` to fix column collision bug (2026-02-03)

## Changelog

### 2026-02-03
- Fixed column collision bug (`merit_cutoff_x`, `merit_cutoff_y`) in `data_manager.py`
- Removed redundant load of `merit_cutoffs.csv` (data already in `requirements.csv`)
- Updated this plan document to reflect completed status

### Previous
- Initial implementation of merit calculation engine
- Added probability classification with color-coded badges
- Integrated merit badges into course cards
- Added translations for probability labels

## Future Enhancements (Optional)

- [ ] Add co-curriculum score input field in UI (currently uses default)
- [ ] Show merit score breakdown in detailed view
- [ ] Historical trend data (multi-year cutoffs)
- [ ] Merit comparison chart across similar courses

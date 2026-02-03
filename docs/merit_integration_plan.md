# Merit Point Integration Plan

## Objective
To implement a "Merit Point" system that estimates a student's probability of admission into Public Universities (UA) by comparing their calculated merit score against historical admission statistics.

## Data Source
1.  **Public Universities (UA)**: `Random/data/spm/mohe_programs_with_khas.csv` (Contains `merit`).
2.  **Polytechnic & Community Colleges (Poly/KK)**:
    - *Status*: Data currently missing in `Random/data`.
    - *Action*: We will create a placeholder `data/poly_merit.csv` or add a `merit_cutoff` column to `requirements.csv` to support this when data becomes available.
3.  **Excluded**: STPM, ILJTM, ILKBS, PISMP (No merit system or data unavailable).

## Scope
- **Included**: Public Universities (UA+Asasi), Polytechnics, Community Colleges.
- **Excluded**: STPM, TVET (ILJTM/ILKBS), PISMP.

## Logic Implementation

### 1. Student Merit Calculation
We will use the existing `calculate_merit_score` function in `src/engine.py`.
- **Formula**: `(AcademicScore * 0.90) + (CoCurriculumScore * 0.10)`
- **AcademicScore**: Calculated from best subject grades (standardized 18-point scale).
- **CoCurriculumScore**: User input (0-10), defaulting to a conservative estimate if not provided.

### 2. Merit Mapping Logic
 Since course names in `HalaTuju` (Detailed) may differ from `MOHE` (Generic), we will apply the following mapping rules:

1.  **Direct Match**: Normalized Name check (ignoring case/spacing).
2.  **Generic IT Mapping**:
    - **Source**: `FB4482001` (Diploma Teknologi Maklumat)
    - **Targets**:
        - `POLY-DIP-072` (Software & App Development)
        - `POLY-DIP-073` (Networking System)
        - `POLY-DIP-074` (Information Security)
        - `POLY-DIP-075` (Digital Game Programming)
        - `POLY-DIP-076` (Web Development)
        - `POLY-DIP-077` (Data Management & Visualization)
3.  **Fuzzy Matching**:
    - Ignore `#` suffix (e.g., `DIPLOMA REKA BENTUK INDUSTRI #` == `Diploma Rekabentuk Industri`).
    - Standardize `REKA BENTUK` vs `REKABENTUK`.
4.  **KK Certificate Manual Mapping**:
    - `KKOM-CET-002` (Certificate in F&B) -> `FC3811006` (CERTIFICATE IN FOOD AND BEVERAGE SERVICE)
    - `KKOM-CET-022` (Sijil Seni Visual) -> `FC3215001` (SIJIL TEKNOLOGI REKA BENTUK GRAFIK KREATIF)

### 3. Probability Classification
For each eligible course, we compare `StudentMerit` vs `CourseCutoff`:

| Condition | Probability Label | Color Indicator |
| :--- | :--- | :--- |
| `StudentMerit >= CourseCutoff` | **High Probability** | 🟢 Green |
| `StudentMerit >= CourseCutoff - 5` | **Fair Probability** | 🟡 Yellow |
| `StudentMerit < CourseCutoff - 5` | **Low Probability** | 🔴 Red |

*Note: A 5-point buffer is used to account for year-to-year fluctuations.*

## Implementation Steps

### Phase 1: Data Preparation
1.  **Update `process_university_data.py`** (Task #12 in `task.md`):
    - Extract `merit` column from `mohe_programs_with_khas.csv`.
    - Clean string values (remove `%`) and convert to float.
    - Save as `merit_cutoff` in `university_requirements.csv`.

### Phase 2: Engine Update
1.  **Verify `src/engine.py`**:
    - Ensure `calculate_merit_score` is exposed and working correctly.
    - Add a helper `check_merit_probability(student_merit, course_cutoff)` to return the status label.

### Phase 3: Dashboard Integration
1.  **Update `src/dashboard.py`**:
    - In `generate_dashboard_data`:
        - Calculate `student_merit` once relative to the user's results.
    - In `render_course_card`:
        - Check if `merit_cutoff` > 0.
        - If yes, display the "True Test" Merit Bar or Badge.
        - Show "Your Merit: XX.XX" vs "Avg Cutoff: YY.YY".

## User Review Required
- **Buffer Zone**: Is a 5-point buffer for "Fair" probability acceptable?
- **Co-Curriculum Default**: If a user doesn't enter Co-Q marks, what default should we use? (Proposed: 5.0/10.0 or 0.0).


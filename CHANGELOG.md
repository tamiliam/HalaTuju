# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-04

### 🎓 Major Feature: University Course Integration

Added comprehensive support for 87 Malaysian public university (IPTA) Asasi and Foundation programs across 20 institutions.

### ✨ New Features

#### Data Layer
-   **New Data Files**:
    -   `data/university_requirements.csv` - 87 university course eligibility rules
    -   `data/university_courses.csv` - Course metadata (department, field, frontend_label)
    -   `data/university_institutions.csv` - 20 IPTA universities with constituency data
-   **Course Catalog Expansion**: 727 → 814 courses (+12% growth)

#### Eligibility Engine (`src/engine.py`)
-   **Grade B Requirements**: New tier stricter than Credit C (Grade B or better)
    -   `credit_bm_b`, `credit_eng_b`, `credit_math_b`, `credit_addmath_b`
-   **Distinction Requirements**: Grade A- or better
    -   `distinction_bm`, `distinction_eng`, `distinction_math`, `distinction_addmath`
    -   `distinction_bio`, `distinction_phy`, `distinction_chem`, `distinction_sci`
-   **Complex OR-Group Logic**: JSON-based multi-subject requirements
    -   Example: "Need 2 subjects with Grade B from [Physics, Chemistry, Biology]"
    -   Supports AND logic between groups, OR logic within groups
-   **Pendidikan Islam/Moral Support**: `pass_islam`, `credit_islam`, `pass_moral`, `credit_moral`
-   **Additional Science Requirements**: `pass_sci`, `credit_sci`, `credit_addmath`

#### UI Updates (`main.py`, `src/dashboard.py`, `src/translations.py`)
-   **Institution Filter**: Added "Public University" (Universiti Awam) option
-   **Dashboard Metrics**: Expanded from 4 to 5 columns to include UA course count
-   **Translations**: Added `inst_ua` key in English/Bahasa Melayu/Tamil
-   **Grade Input**: Added "Pendidikan Islam" and "Pendidikan Moral" to Other Subjects dropdown

#### Data Manager (`src/data_manager.py`)
-   **University Data Merging**:
    -   Extracts course name and institution from `notes` column
    -   Merges with institution metadata for state/URL
    -   Maps to consistent type naming: "Universiti Awam"
-   **Type Standardization**: All institution types now use Bahasa Melayu for filter compatibility

### 🧪 Testing

-   **Golden Master Test Expansion** (`tests/test_golden_master.py`):
    -   Added 8 new student profiles (43-50) for UA requirement testing
    -   Grade B testing, Distinction testing, Complex OR-group testing
    -   Updated baseline: 5,318 → 8,280 eligible matches (+2,962)
    -   Test coverage: 50 students × 407 courses = 20,350 checks
-   **University Integration Tests** (`test_university_integration.py`):
    -   Data loading verification
    -   Eligibility engine testing with strong/weak students
    -   Complex requirements JSON parsing

### 🐛 Bug Fixes

-   **NaN Handling**: Fixed AttributeError in `check_complex_requirements()` when pandas passes NaN as float type
-   **Type Consistency**: Changed UA type from 'UA' to 'Universiti Awam' for UI compatibility
-   **Windows Console**: Removed Unicode emojis from test output for cp1252 encoding compatibility

### 📝 Documentation

-   **README.md**: Updated course catalog numbers and feature descriptions
-   **DATA_DICTIONARY.md**: Documented all 20+ new UA requirement columns and complex_requirements JSON format
-   **docs/university_integration_complete.md**: Comprehensive implementation summary

### ⚙️ Technical

-   **Engine Functions**:
    -   `is_credit_b(grade)` - Checks if grade is B or better
    -   `is_distinction(grade)` - Checks if grade is A- or better
    -   `check_complex_requirements(grades, json_str)` - Evaluates OR-group logic
    -   `map_subject_code(code)` - Maps 60+ SPM subjects to internal keys
-   **Performance**: No noticeable impact despite 12% course increase (~140KB additional data)

### 🔄 Backward Compatibility

-   All changes fully backward compatible with existing Poly/KK/TVET courses
-   New requirement columns default to 0 (not required)
-   Existing eligibility logic unchanged

## [1.0.0] - 2026-01-24

### 🚀 Initial Release
First official stable release of **HalaTuju**, the SPM Leaver Course Recommender.

### ✨ Key Features
-   **Eligibility Engine**: 
    -   Exact matching against General and Specific requirements for Polytechnics, Community Colleges, ILKBS, and ILJTM.
    -   Support for gender-specific, physically demanding, and interview-based course rules.
-   **Ranking System**: 
    -   Weighted scoring based on Student Interest (RIASEC), Work Preferences (Hands-on vs Theory), and Learning Styles.
    -   Tie-breaking logic using Credential Priority (Diploma > Certificate) and Institution Tier functionality.
-   **Dashboard**:
    -   Interactive filtering and "Tiered" display (Top 5 Matches vs Rest).
    -   Visual indicators for specific requirements (Medical checks, Interviews).
-   **Reports**:
    -   AI-generated personalized career pathway reports (Gemini Pro + OpenAI Fallback).
    -   PDF export functionality.
-   **Localization**: Full English, Malay, and Tamil language support.

### 🐛 Key Fixes & Stability
-   **Gender Logic**: Fixed regression where engine hardcoded Malay gender terms, causing rejection of eligible students using English/Tamil UI.
-   **Data Integerity**: Implemented a "Golden Master" regression test suite (`tests/test_golden_master.py`) achieving 100% integrity on 13,000+ test cases.
-   **Cleanup**: Removed unused dependency `match_jobs_rag` and unused `InsightGenerator`, consolidated imports, and verified no hardcoded secrets exist.

### ⚙️ Technical
-   **Stack**: Streamlit, Pandas, Supabase (Auth/DB), Google Gemini.
-   **Testing**: Automated Golden Master testing for the engine.

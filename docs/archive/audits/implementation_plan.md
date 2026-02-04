
# Integration of University (SPM) Programs

This plan outlines the steps to integrate additional programs from `Random/data/spm/mohe_programs_with_khas.csv` into the `HalaTuju` system.

> [!NOTE]
> **Status**: Planning Phase Completed. Implementation paused as per user request.

## User Review Required
> [!IMPORTANT]
> **Bumiputra Filtering**: Filtering out programs where `bumiputera` != "No".
> **Duplicate Handling**: Explicitly **excluding** programs matching "Politeknik", "Kolej Komuniti", or "ILKM" from the new source to prevent overlapping with existing `requirements.csv`.
> **New Category**: Adding **"Universiti Awam" (Public University)**, **"Ijazah Perguruan" (Teacher Degree)**, and **"Kolej Tingkatan 6" (Form 6 College)** as new categories on the Dashboard.

## 1. Missing Information Analysis

The new data source (`mohe_programs_with_khas.csv`) lacks several fields required by the `HalaTuju` UI cards.

| Field | Status | Mitigation Strategy |
| :--- | :--- | :--- |
| **Fees** | ❌ Missing | Default to **"Check University Website"**. |
| **Hostel Fee** | ❌ Missing | Default to **"N/A"**. |
| **Institution URL** | ❌ Missing | Use the **Course URL** (`link` column) as the destination for all buttons. |
| **Jobs / Careers** | ❌ Missing | Leave empty (hide career pills). *Future*: Map to MASCO via keyword matching. |
| **Synopsis** | ❌ Missing | Auto-generate: `"{Program Name}" at {University}`. |
| **State** | ⚠️ Partial | Extract from `kampus` column (e.g., "Sabah" from "Kampus Kota Kinabalu, Sabah"). |
| **Duration** | ✅ Present | Use `duration` column (e.g., "02 Semester"). |

## 2. Proposed Changes

### Data Processing
#### [NEW] `scripts/process_university_data.py`
- Reads `Random/data/spm/mohe_programs_with_khas.csv`.
- **Filtering Logic**:
    - Keep if `bumiputera` == "No" OR `bumiputera` is empty/null.
    - **Exclude** if `program_name` or `university` contains "Politeknik", "Kolej Komuniti", "ILJTM", "ILKBS", "MARA".
- **Parsing Logic**:
    - REGEX to extract specific grades (e.g., "Gred C ...").
    - JSON builder for "Subject Groups" (e.g., "Credit in 2 of Physics, Chem, Bio").
    - State extraction from `kampus`.
- **Output**: `HalaTuju/data/university_requirements.csv`.

### Engine Extension
#### [MODIFY] `HalaTuju/src/engine.py`
- Add `subject_group_req` to `ALL_REQ_COLUMNS`.
- Update `check_eligibility()` to parse `subject_group_req` (JSON):
    - specific logic: `count(credits in subjects) >= min_count`.

### Dashboard Update
#### [MODIFY] `HalaTuju/src/data_manager.py`
- Load `university_requirements.csv`, `form6_schools.csv`, `pismp_requirements.csv`.
- Tag rows with appropriate categories: `inst_ua`, `inst_form6`, `inst_pismp`.
- Merge Form 6 schools with Form 6 requirements (many schools, single logic).
- Merge PISMP requirements (likely single broad logic or per-major).

#### [MODIFY] `HalaTuju/src/dashboard.py`
- Update `get_institution_type` to recognize new categories.
- Add `inst_ua`, `inst_form6`, `inst_pismp` to `stats` and filters.

#### [MODIFY] `HalaTuju/src/translations.py`
- Add labels:
    - "Public University" (Universiti Awam)
    - "Teacher Degree" (Ijazah Perguruan)
    - "Form 6 College" (Kolej Tingkatan 6)

### New Data Processing for Form 6 & PISMP
#### [NEW] `scripts/process_form6_pismp.py`
- **Form 6**:
    - Input: `SchoolScraper/output/schools_list.csv` (Schools) + `SYARAT KEMASUKAN TINGKATAN ENAM.pdf` (Logic).
    - Logic: Hardcode general entry requirements (e.g. Credit BM, Pass History, etc.).
    - Output: `data/form6_schools.csv` (Locations) + Entry in `requirements.csv` or handled in Engine.
- **PISMP**:
    - Input: `01_PISMP 2025...pdf` (Logic).
    - Logic: Extract minimum eligibility (5 Credits, Age limit, etc.).
    - Output: `data/pismp_requirements.csv` (Single entry or per major if details available).

## 3. Verification Plan

### Automated Tests
- **Exclusion Test**: Ensure `POLY-DIP-001` (from Poly list) does NOT appear in the new CSV.
- **Inclusion Test**: Ensure `ASASI KEJURUTERAAN DAN TEKNOLOGI` (UPNM) appears.
- **Logic Test**: Test a student with only 1 credit in Science group against a requirement of "2 credits in Science group".

### Manual UI Check
- Verify "Universiti Awam" appears in the Filter dropdown.
- Verify fees show "Check University Website" instead of crashing.

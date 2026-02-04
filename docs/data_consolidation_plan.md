# Data File Consolidation Plan

**Status**: Proposed (2026-02-04)
**Principle**: Avoid file proliferation - merge into existing structures where possible

## Problem Statement

UA integration created 3 new data files:
- `data/university_institutions.csv` (5KB)
- `data/university_courses.csv` (9.3KB)
- `data/university_courses_update.csv` (10KB) - appears to be duplicate

This violates the "minimal files" principle and creates parallel structures to existing files.

## Consolidation Strategy

### 1. ✅ Keep Separate (Follows Established Pattern)
- `university_requirements.csv` (68KB)
  - **Justification**: Parallel to `requirements.csv` and `tvet_requirements.csv`
  - **Pattern**: One requirements file per institution type

### 2. 🔄 Merge Into Existing Files

#### A. `university_institutions.csv` → `institutions.json`
**Action**: Add 20 UA institutions to existing `institutions.json`

**Current State:**
- `institutions.json`: 74KB, ~80 institutions (Poly/KK/TVET)
- `university_institutions.csv`: 5KB, 20 institutions

**After Merge**: ~79KB (within reasonable size)

**Migration Task**:
1. Read `university_institutions.csv`
2. Transform to JSON structure matching existing pattern
3. Add `modifiers` field:
   - `urban`: Based on location (KL/Penang/Johor Bahru = true)
   - `cultural_safety_net`: Map from `indians_%` column
     - ≥10% → "high"
     - 5-10% → "moderate"
     - <5% → "low"
4. Append to `institutions.json`
5. Archive `university_institutions.csv` to `data/archive/`

#### B. `university_courses.csv` → Review for Redundancy
**Action**: Check if data duplicates `university_requirements.csv`

If redundant:
- Delete `university_courses.csv`
- Delete `university_courses_update.csv`

If contains unique metadata:
- Keep minimal metadata in `university_requirements.csv` `notes` column
- Or merge into a single `courses.csv` master file

### 3. 📋 Pending: Course Tags
**Action**: Add 87 UA course tags to existing `course_tags.json`

**Current State:**
- `course_tags.json`: 136KB, ~727 courses

**After Addition**: ~152KB (within reasonable size)

**Migration Task**:
1. Manual tagging required for 87 UA courses
2. Add 12 taxonomy dimensions per course (work_modality, people_interaction, etc.)
3. Append to `course_tags.json` array

## Implementation Priority

1. **Phase 1 (High Priority)**: Merge `university_institutions.csv` → `institutions.json`
   - Required for ranking system to work
   - Adds `cultural_safety_net` based on Indian population data

2. **Phase 2 (High Priority)**: Add UA tags to `course_tags.json`
   - Required for ranking system to work
   - Most time-consuming (manual tagging)

3. **Phase 3 (Low Priority)**: Clean up redundant course files
   - Review `university_courses.csv` necessity
   - Archive or delete duplicates

## Cultural Safety Net Mapping

Based on `university_institutions.csv` data:

| Institution | Indians % | Proposed cultural_safety_net |
|:---|---:|:---|
| USIM (Nilai) | 18.0% | **high** |
| UM (KL) | 13.8% | **high** |
| USM (Penang) | 10.3% | **high** |
| UPM (Serdang) | 9.4% | **moderate** |
| UPSI (Tanjung Malim) | 9.0% | **moderate** |
| UPNM (KL) | 8.3% | **moderate** |
| UiTM (Shah Alam) | 7.7% | **moderate** |
| UTeM (Melaka) | 7.4% | **moderate** |
| UIAM (Gombak) | 7.3% | **moderate** |
| UKM (Bangi) | 6.6% | **moderate** |
| UniMAP (Perlis) | 4.7% | **low** |
| UUM (Kedah) | 2.6% | **low** |
| UTHM (Batu Pahat) | 2.5% | **low** |
| UMPSA (Kuantan) | 2.2% | **low** |
| UMT (Terengganu) | 0.7% | **low** |
| UNIMAS (Sarawak) | 0.6% | **low** |
| UMS (Sabah) | 0.5% | **low** |
| UniSZA (Terengganu) | 0.4% | **low** |
| UMK (Kelantan) | 0.2% | **low** |

## Success Criteria

- ✅ No new JSON files created
- ✅ Institution modifiers work for UA courses
- ✅ Ranking system properly scores UA courses
- ✅ No duplicate data across files
- ✅ All archived files documented in `data/archive/README.md`

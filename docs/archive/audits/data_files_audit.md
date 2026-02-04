# Data Files Audit & Consolidation Plan

**Date**: 2026-02-04
**Status**: Proposed
**Principle**: Minimize file count - merge redundant data into core files

## Executive Summary

**Current State**: 22 files (21 data files + 1 backup folder)
**Proposed State**: 11 files (50% reduction)
**Files to DELETE**: 6
**Files to MERGE**: 5
**Files to KEEP**: 11

---

## Detailed Analysis

### ✅ KEEP AS-IS (Core Files)

#### 1. Requirements Files (3 files)
| File | Size | Rows | Purpose | Keep? |
|:---|---:|---:|:---|:---:|
| `requirements.csv` | 7.8K | 140 | Poly/KK eligibility rules | ✅ |
| `tvet_requirements.csv` | 9.3K | 182 | TVET eligibility rules | ✅ |
| `university_requirements.csv` | 68K | 87 | UA eligibility rules | ✅ |

**Justification**: Established pattern - one requirements file per institution type.

#### 2. Metadata Files (2 files)
| File | Size | Purpose | Keep? |
|:---|---:|:---|:---:|
| `course_tags.json` | 136K | Ranking taxonomy (12 dimensions) | ✅ |
| `institutions.json` | 74K | Institution modifiers for ranking | ✅ |

**Justification**: JSON format required by ranking engine. Will be extended (not replaced).

#### 3. Mapping Files (1 file)
| File | Size | Purpose | Keep? |
|:---|---:|:---|:---:|
| `subject_name_mapping.json` | 2.2K | SPM subject code mappings | ✅ |

**Justification**: Critical for engine to map 60+ SPM subject variations.

---

### 🔄 MERGE INTO EXISTING FILES (5 files → eliminate)

#### 4. Merit Data (REDUNDANT)
| File | Size | Rows | Status |
|:---|---:|---:|:---|
| `merit_cutoffs.csv` | 3.7K | 133 | ❌ **DELETE** |

**Reason**:
- `requirements.csv` already has `merit_cutoff` column (see line 20)
- Code comments confirm: "merit_cutoffs.csv is no longer loaded" ([data_manager.py:48-49](c:\Users\tamil\Python\HalaTuju\src\data_manager.py#L48-L49))
- File contains 133 rows, requirements.csv has 140 rows
- **All data is duplicated**

**Action**: Delete immediately (no migration needed).

#### 5. Course Details (SHOULD MERGE)
| File | Size | Columns | Status |
|:---|---:|:---|:---|
| `details.csv` | 71K | 15 columns | 🔄 **MERGE into courses.csv** |

**Columns in details.csv**:
```
course_id, req_interview, source_type, institution_id, hyperlink,
single, monthly_allowance, practical_allowance, free_hostel, free_meals,
tuition_fee_semester, hostel_fee_semester, registration_fee,
req_academic, medical_restrictions
```

**Reason**:
- Details are course-specific, should be in `courses.csv`
- Currently requires merge operation in data_manager.py (lines 46, 61-79)
- Merging eliminates runtime overhead

**Action**:
1. Add 14 new columns to `courses.csv` (exclude course_id)
2. Left join details.csv into courses.csv
3. Delete details.csv
4. Update data_manager.py to remove merge logic

#### 6. MASCO Job Links (SHOULD MERGE)
| File | Size | Purpose | Status |
|:---|---:|:---|:---|
| `course_masco_link.csv` | 12K | Links courses to MASCO job codes | 🔄 **MERGE into courses.csv** |
| `masco_details.csv` | 21K | MASCO job titles and URLs | 🔄 **MERGE into courses.csv** |

**Reason**:
- Career data is course metadata
- Currently separate lookups required
- `courses.csv` already has `career` column (can be extended to JSON)

**Action**:
1. Join `course_masco_link.csv` + `masco_details.csv` on `masco_code`
2. Add `masco_code`, `job_title`, `job_url` columns to `courses.csv`
3. Delete both MASCO files
4. Update career display logic to use new columns

#### 7. Institution Links (REDUNDANT)
| File | Size | Purpose | Status |
|:---|---:|:---|:---|
| `links.csv` | 13K | Links institution_id to course_id | ❓ **CHECK IF USED** |

**Reason**:
- `details.csv` already has `institution_id` per course
- If details.csv is merged into courses.csv, links.csv becomes redundant

**Action**:
1. Verify links.csv is not used in code (grep for "links.csv")
2. If unused or redundant with details.csv → DELETE
3. If used → keep temporarily until details.csv merge is complete

#### 8. University Metadata (SHOULD MERGE)
| File | Size | Rows | Status |
|:---|---:|:---|:---|
| `university_courses.csv` | 9.3K | 87 | 🔄 **MERGE into university_requirements.csv** |
| `university_courses_update.csv` | 10K | ? | ❌ **DELETE (appears duplicate)** |
| `university_institutions.csv` | 5.0K | 20 | 🔄 **MERGE into institutions.json** |

**Reason**:
- `university_courses.csv` has course metadata that should be in `university_requirements.csv` (or merged into main `courses.csv`)
- `university_courses_update.csv` appears to be a duplicate/working file
- `university_institutions.csv` should be in `institutions.json` (as per consolidation plan)

**Action**:
1. **Phase 1**: Merge `university_institutions.csv` → `institutions.json`
   - Add `cultural_safety_net` based on `indians_%` column
   - Add `urban`, `subsistence_support`, `strong_hostel` modifiers

2. **Phase 2**: Merge `university_courses.csv` into `courses.csv` OR `university_requirements.csv`
   - Check for unique columns in university_courses.csv
   - If minimal unique data → merge into university_requirements.csv notes column
   - If substantial metadata → add rows to courses.csv with type='Universiti Awam'

3. **Phase 3**: Delete `university_courses_update.csv` after verifying it's a duplicate

---

### ❌ DELETE IMMEDIATELY (Redundant/Backup)

#### 9. Backup Files
| File | Size | Status |
|:---|---:|:---|
| `courses.csv.bak` | 271K | ❌ **DELETE** |

**Reason**:
- Git provides version control
- .bak files are anti-pattern in version-controlled repos
- If needed for safety, move to `data/archive/` folder

**Action**: Delete or move to archive.

#### 10. Draft/WIP Files
| File | Size | Status |
|:---|---:|:---|
| `new_pathways_requirements.csv` | 30K | ❓ **VERIFY THEN DELETE** |
| `pismp_requirements_draft.csv` | 27K | ❓ **VERIFY THEN DELETE** |
| `form6_schools_final.csv` | 105K | ❓ **VERIFY THEN DELETE** |

**Reason**:
- "draft" in filename suggests work-in-progress
- "new_pathways" suggests planned feature not yet implemented
- These may be source data for future integration (see `implementation_plan.md`)

**Action**:
1. Check if data is used in production code
2. If NOT used → move to `data/archive/` or `Random/data/` (source data location)
3. If used → keep but rename to remove "draft" suffix

---

### 📊 Institutional Files (Keep Separate)

| File | Size | Purpose | Keep? |
|:---|---:|:---|:---:|
| `institutions.csv` | 37K | Poly/KK institution metadata | ✅ |
| `tvet_institutions.csv` | 13K | TVET institution metadata | ✅ |

**Justification**:
- Parallel to institution type pattern (like requirements files)
- Used for data loading and merging operations
- Different schemas from institutions.json

**Note**: These are **source data** files. `institutions.json` is the **processed** version used by the ranking engine.

---

## Consolidation Priority

### Phase 1: Immediate Deletions (No Risk)
1. ❌ Delete `merit_cutoffs.csv` - confirmed redundant
2. ❌ Delete `courses.csv.bak` - version control exists
3. ❌ Delete `university_courses_update.csv` - appears duplicate

**Time**: 5 minutes
**Risk**: None

### Phase 2: Merge University Data (Addresses Ranking Gap)
1. 🔄 Merge `university_institutions.csv` → `institutions.json`
   - Add 20 UA institutions with modifiers
   - Map `indians_%` to `cultural_safety_net`
2. 🔄 Verify and clean up `university_courses.csv`

**Time**: 2-3 hours
**Risk**: Low (affects only UA courses, which aren't ranked yet anyway)

### Phase 3: Merge Course Details (Simplifies Architecture)
1. 🔄 Merge `details.csv` → `courses.csv`
2. 🔄 Merge MASCO files → `courses.csv`
3. 🔄 Verify and delete `links.csv` if redundant
4. Update `data_manager.py` to remove merge logic

**Time**: 3-4 hours
**Risk**: Medium (requires careful testing of course display)

### Phase 4: Archive Unused Files
1. Move `new_pathways_requirements.csv` to archive (if unused)
2. Move `pismp_requirements_draft.csv` to archive (if unused)
3. Move `form6_schools_final.csv` to archive (if unused)

**Time**: 30 minutes
**Risk**: None (archiving, not deleting)

---

## Expected File Count After Consolidation

### Current: 21 data files
### After Phase 1: 18 files (-3)
### After Phase 2: 16 files (-2)
### After Phase 3: 13 files (-3)
### After Phase 4: 10-13 files (depending on archive decisions)

---

## Proposed Final Structure

```
data/
├── requirements.csv              # Poly/KK eligibility (with merit_cutoff)
├── tvet_requirements.csv         # TVET eligibility
├── university_requirements.csv   # UA eligibility
├── courses.csv                   # ALL course metadata (Poly/KK/TVET/UA)
├── tvet_courses.csv             # TVET-specific metadata (if needed)
├── institutions.csv              # Poly/KK institution source data
├── tvet_institutions.csv         # TVET institution source data
├── institutions.json             # ALL institution modifiers (Poly/KK/TVET/UA)
├── course_tags.json              # ALL course tags for ranking (Poly/KK/TVET/UA)
├── subject_name_mapping.json    # SPM subject mappings
└── archive/
    ├── merit_cutoffs.csv         # Deprecated (merged into requirements.csv)
    ├── details.csv               # Deprecated (merged into courses.csv)
    ├── course_masco_link.csv     # Deprecated (merged into courses.csv)
    ├── masco_details.csv         # Deprecated (merged into courses.csv)
    ├── links.csv                 # Deprecated (redundant)
    ├── university_courses.csv    # Deprecated (merged)
    ├── university_institutions.csv # Deprecated (merged into institutions.json)
    └── new_pathways_requirements.csv # Future feature source data
```

**Final Count**: 10 active data files

---

## Success Criteria

- ✅ No backup files (.bak) in data/ directory
- ✅ No "draft" or "update" files in production
- ✅ All course metadata in single `courses.csv` (or type-specific files)
- ✅ All institution modifiers in single `institutions.json`
- ✅ Merit cutoffs integrated into requirements files
- ✅ MASCO job data accessible without separate lookups
- ✅ All deprecated files moved to `data/archive/` with README explaining history
- ✅ data_manager.py simplified (fewer merge operations)
- ✅ Golden master tests still passing

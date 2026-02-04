# Data Consolidation - Completion Summary

**Date**: 2026-02-04
**Status**: ✅ COMPLETE
**Files Reduced**: 22 → 14 (36% reduction)

---

## Phase 1: Institution Merge ✅

**Action**: Merged 3 institution files into 1

**Files Consolidated**:
- `institutions.csv` (137 Poly/KK)
- `tvet_institutions.csv` (55 TVET)
- `university_institutions.csv` (20 UA)
- **→ institutions.csv (212 total)**

**Changes Made**:
1. Created [scripts/merge_institutions.py](../scripts/merge_institutions.py)
2. Standardized column names (Title Case, spaces not underscores)
3. Updated [src/data_manager.py](../src/data_manager.py:38-43) to use unified file
4. Archived old files to [data/archive/](../data/archive/)

**Test Result**: ✅ Golden master tests passed (8280 matches)

---

## Phase 2: Course Merge ✅

**Action**: Merged Poly/KK/UA courses into 1 file (per user rule: "Poly/KK/UA should always be in one file")

**Files Consolidated**:
- `courses.csv` (139 Poly/KK)
- `university_courses.csv` (87 UA)
- **→ courses.csv (226 total)**

**Schema** (10 columns):
```
course_id, course, wbl, level, department, field,
frontend_label, semesters, description, career
```

**Changes Made**:
1. Created [scripts/merge_courses.py](../scripts/merge_courses.py)
2. Handled encoding issues (latin1 for courses.csv)
3. Updated [src/data_manager.py](../src/data_manager.py:205-237) to use unified courses.csv for UA merge
4. Archived university_courses.csv to [data/archive/](../data/archive/)

**Test Result**: ✅ Golden master tests passed (8280 matches, 100% integrity)

**Note**: `tvet_courses.csv` kept separate due to schema conflict (no "field" column, "months" vs "semesters")

---

## Phase 3: Redundant File Deletion ✅

**Files Deleted**:

### Confirmed Redundant:
1. ✅ `merit_cutoffs.csv` - Data already in requirements.csv (merit_cutoff column)
2. ✅ `courses.csv.bak` - Git provides version control
3. ✅ `university_courses_update.csv` - Duplicate of university_courses.csv

### Old Backups (data/backup/):
4. ✅ `jobs_mapped.csv` (Jan 23, 12 days old)
5. ✅ `requirements.csv` (Jan 18, 17 days old)
6. ✅ `requirements_old.csv` (Jan 16, 19 days old)
7. ✅ `tvet_requirements.csv` (Jan 17, 18 days old)

**Retained**:
- ✅ `institutions.csv.pre-merge` (Feb 4 backup - kept)
- ✅ `courses.csv.pre-merge` (Feb 4 backup - kept)

---

## Phase 4: WIP Files Archived ✅

**Files Moved to archive/** (not production ready):
1. ✅ `form6_schools_final.csv` (105K) - Form 6 schools (planned feature)
2. ✅ `new_pathways_requirements.csv` (30K) - Form 6/PISMP requirements (planned)
3. ✅ `pismp_requirements_draft.csv` (27K) - PISMP draft requirements

---

## File Redundancy Analysis

### ✅ Links.csv - NOT Redundant (KEEP)
**Purpose**: Maps institution_id to course_id (547 rows)
**Why Keep**:
- Poly courses are 1:many (one course offered at multiple institutions)
- details.csv is institution-specific logistics (fees, hostel)
- links.csv provides the base relationship mapping

**Used in**: [data_manager.py:83-85](../src/data_manager.py#L83-L85)

### ✅ Details.csv - NOT Redundant (KEEP)
**Purpose**: Institution-specific course logistics (fees, hostel, hyperlinks)
**Why Keep**:
- Contains 15 columns of institution-course-specific data
- Different from course metadata (which is course-level, not institution-level)
- Used extensively in data_manager.py merge operations

**Columns**:
```
course_id, req_interview, source_type, institution_id, hyperlink,
single, monthly_allowance, practical_allowance, free_hostel, free_meals,
tuition_fee_semester, hostel_fee_semester, registration_fee,
req_academic, medical_restrictions
```

---

## Final Data Structure (14 Active Files)

```
data/
├── requirements.csv              # Poly/KK eligibility rules (140 rows)
├── tvet_requirements.csv         # TVET eligibility rules (182 rows)
├── university_requirements.csv   # UA eligibility rules (88 rows)
├── courses.csv                   # Poly/KK/UA course metadata (226 rows)
├── tvet_courses.csv             # TVET course metadata (~800 rows)
├── institutions.csv              # ALL institutions: Poly/KK/TVET/UA (212 rows)
├── details.csv                   # Institution-course logistics (71K)
├── links.csv                     # Institution-course relationships (547 rows)
├── course_tags.json              # Course ranking taxonomy (136K, 12 dimensions)
├── institutions.json             # Institution modifiers for ranking (74K)
├── course_masco_link.csv         # Course-to-job mappings (12K)
├── masco_details.csv             # Job titles and URLs (21K)
├── subject_name_mapping.json    # SPM subject code mappings (2.2K)
├── backup/
│   ├── institutions.csv.pre-merge  # Feb 4 backup
│   └── courses.csv.pre-merge       # Feb 4 backup
└── archive/
    ├── tvet_institutions.csv
    ├── university_institutions.csv
    ├── university_courses.csv
    ├── form6_schools_final.csv
    ├── new_pathways_requirements.csv
    └── pismp_requirements_draft.csv
```

---

## Code Changes Summary

### [src/data_manager.py](../src/data_manager.py)

**Lines 38-43**: Removed tvet_institutions.csv and university_institutions.csv loading
```python
# OLD:
df_tvet_inst = load('tvet_institutions.csv')
df_ua_inst = load('university_institutions.csv')

# NEW:
df_inst = load('institutions.csv')  # Now includes Poly/KK/TVET/UA
```

**Line 148**: Updated TVET merge to use unified df_inst
```python
tvet_merged = pd.merge(tvet_merged, df_inst, on='institution_id', how='left')
```

**Lines 205-237**: Updated UA merge to use unified courses.csv
```python
# OLD:
df_ua_courses = load('university_courses.csv')
ua_merged = pd.merge(ua_merged, df_ua_courses, on='course_id', how='left')

# NEW:
# df_ua_courses removed - now merged into unified courses.csv
ua_merged = pd.merge(ua_merged, df_courses, on='course_id', how='left')
```

**Lines 241-253**: Updated UA institution merge to use filtered df_inst
```python
df_ua_inst_filtered = df_inst[df_inst['type'] == 'IPTA'].copy()
```

---

## Test Verification

**Golden Master Tests**: ✅ PASSED
- Total Checks: 20,350 (50 students × 407 courses)
- Valid Applications: 8,280
- System Integrity: 100%

**Command**:
```bash
python -m unittest tests/test_golden_master.py
```

---

## Remaining Opportunities (Future Work)

### Phase 5: MASCO File Merge (Optional)
**Current**:
- `course_masco_link.csv` (course_id → masco_code)
- `masco_details.csv` (masco_code → job_title, url)

**Proposed**: Merge into `masco_jobs.csv` (single lookup)
**Impact**: -33K, 2 files → 1 file
**Priority**: Low (current two-file approach works fine)

### Phase 6: Column Cleanup (Requires Investigation)
**Potentially Unused Columns**:

**courses.csv**:
- `wbl` (Work-Based Learning) - verify usage
- `department` - may be redundant with field/frontend_label

**details.csv**:
- `source_type` - appears always "poly" or empty
- `req_academic` - always empty in samples
- `registration_fee` - always empty in samples
- `monthly_allowance`, `practical_allowance` - always 0 in samples

**Action Needed**: Grep codebase to verify if these columns are referenced

---

## Success Metrics

### Achieved ✅
- ✅ No backup files (.bak) in data/ directory
- ✅ No "draft" or "update" files in production
- ✅ All Poly/KK/UA courses in single courses.csv
- ✅ All institutions in single institutions.csv
- ✅ Merit cutoffs integrated into requirements.csv (merit_cutoff column)
- ✅ 36% file reduction (22 → 14 files)
- ✅ Golden master tests passing
- ✅ data_manager.py simplified (fewer file loads)

### Pending (Future Phases)
- ⏳ All institution modifiers in single institutions.json (UA not yet added)
- ⏳ All course tags in single course_tags.json (UA not yet tagged)
- ⏳ MASCO files merged (optional)
- ⏳ Unused column cleanup

---

## Architectural Principle Established

**File Management Philosophy** (documented in [CLAUDE.md](../CLAUDE.md)):

> **CRITICAL: Avoid creating new files whenever possible.**
>
> - Prefer Extension Over Creation: Extend existing files rather than creating parallel structures
> - Threshold: Only create new files when exceeding 10,000 lines or 5MB
> - User Rule: "Poly/KK/UA should always be in one file. If there is no conflict, TVET too can be part of the file. Otherwise, TVET gets maintained separately."

---

## References

- Original audit: [data_files_comprehensive_audit.md](data_files_comprehensive_audit.md)
- Consolidation plan: [data_consolidation_plan.md](data_consolidation_plan.md)
- Merge scripts: [scripts/merge_institutions.py](../scripts/merge_institutions.py), [scripts/merge_courses.py](../scripts/merge_courses.py)

# Data Consolidation Summary - February 4, 2026

**Status**: ✅ COMPLETE
**Duration**: Full day session
**Impact**: 41% file reduction, established data governance policies

---

## Overview

Completed comprehensive data folder consolidation following principle: **TIGHT, ALWAYS TRUE**
- Eliminated redundant files
- Established single sources of truth
- Removed "fluff" from machine-readable files
- Created governance policies to prevent future mistakes

---

## Files Reduced: 22 → 13 (41% reduction)

### Starting Point (Morning)
- 22 active data files
- Multiple sources of truth
- Redundant backups in main folder
- Mixed machine-readable and human-readable data
- Inconsistent patterns across institution types

### End Point (Evening)
- 13 active data files
- Single source of truth for each data type
- Clean backup structure
- Strict separation: machine-readable vs human-readable
- Consistent patterns: all types use same mechanisms

---

## Major Changes Completed

### 1. Institution Merge ✅
**Merged**: 3 files → 1
- `institutions.csv` (137 Poly/KK) + `tvet_institutions.csv` (55) + `university_institutions.csv` (20)
- **Result**: `institutions.csv` (212 total)
- **Synced with**: `institutions.json` (212 entries, modifiers only, NO redundant data)

**Script**: `scripts/merge_institutions.py`
**Backup**: `data/backup/institutions.csv.pre-merge`
**Archived**: `tvet_institutions.csv`, `university_institutions.csv`

### 2. Course Merge ✅
**Merged**: 2 files → 1 (following rule: "Poly/KK/UA together")
- `courses.csv` (139 Poly/KK) + `university_courses.csv` (87 UA)
- **Result**: `courses.csv` (226 total)
- **Kept separate**: `tvet_courses.csv` (schema conflict: "months" vs "semesters", no "field" column)

**Script**: `scripts/merge_courses.py`
**Backup**: `data/backup/courses.csv.pre-merge`
**Archived**: `university_courses.csv`

### 3. UA Course-Institution Linking ✅
**Added**: 87 UA course-institution mappings to `links.csv`
- **Pattern**: ALL institution types now use `links.csv` (consistent!)
- **Before**: UA parsed institution names from `notes` column (unreliable)
- **After**: UA uses `institution_id` via `links.csv` (reliable)

**Script**: `scripts/populate_ua_links.py`
**Result**: `links.csv` (546 → 633 rows)
**Backup**: `data/backup/links.csv.pre-ua`

### 4. Institution Sync ✅
**Synchronized**: `institutions.csv` ↔ `institutions.json`
- **Added**: 20 missing UA institutions to `institutions.json`
- **Removed**: Redundant data (name, address) from JSON - only `inst_id` + `modifiers` now
- **Auto-mapped**: Indians % → cultural_safety_net (≥10%=high, 5-10%=moderate, <5%=low)

**Script**: `scripts/sync_institutions_json.py`
**Result**: Both files have 212 institutions (in sync)
**Backup**: `data/backup/institutions.json.pre-sync`

### 5. Requirements Cleanup ✅
**Cleaned**: `university_requirements.csv` (35 → 33 columns)
- **Deleted**: `notes` column (redundant - data in `courses.csv` + `links.csv`)
- **Moved**: `syarat_khas_raw` → `details.csv` (human-readable text)
- **Kept**: All 33 machine-readable eligibility columns + `complex_requirements` JSON

**Script**: `scripts/cleanup_ua_requirements.py`
**Result**: Requirements files now machine-readable ONLY
**Backup**: `data/backup/university_requirements.csv.pre-cleanup`

### 6. Deleted Redundant Files ✅
- ❌ `merit_cutoffs.csv` (data in `requirements.csv`)
- ❌ `courses.csv.old` (duplicate of backup)
- ❌ `university_courses_update.csv` (duplicate)
- ❌ 4 old backup files from January

**Total space freed**: ~200KB

### 7. Archived WIP Files ✅
Moved to `data/archive/`:
- `form6_schools_final.csv` (Form 6 schools - planned feature)
- `new_pathways_requirements.csv` (Form 6/PISMP - planned)
- `pismp_requirements_draft.csv` (PISMP draft)

### 8. Parser Script Archived ✅
- Moved `scripts/parse_university_requirements.py` → `scripts/archive/`
- **Reason**: Initial data import complete, running again would overwrite curated data

---

## Code Changes

### data_manager.py Updates

**Lines 38-43**: Removed separate institution file loading
```python
# OLD: df_tvet_inst = load('tvet_institutions.csv')
# NEW: df_inst = load('institutions.csv')  # Unified
```

**Lines 148, 241-253**: Updated merges to use unified institutions.csv

**Lines 205-237**: Updated UA merge logic
```python
# OLD: Parse institution from notes column
# NEW: Use links.csv → institutions.csv → courses.csv (consistent with Poly/KK)
```

**Lines 218-228**: Removed notes column parsing
```python
# DELETED: 15 lines of notes parsing code
# NEW: Direct course name from courses.csv merge
```

---

## Documentation Created

### 1. DATA_FOLDER_POLICY.md ✅ **CRITICAL**
**Path**: `docs/DATA_FOLDER_POLICY.md`

**Contents**:
- 10 Golden Rules (TIGHT, ALWAYS TRUE principle)
- Forbidden patterns (what NOT to do)
- File creation checklist
- Column addition checklist
- Single source of truth mapping
- Sync requirements
- Common mistakes & how to avoid
- Emergency rollback procedure

**Purpose**: Prevent future agents from making data management mistakes

### 2. data_consolidation_complete.md
**Path**: `docs/data_consolidation_complete.md`
- Complete record of file merges
- Before/after statistics
- Benefits achieved

### 3. institution_sync_complete.md
**Path**: `docs/institution_sync_complete.md`
- Institution sync process
- Modifier mappings
- Maintenance workflows

### 4. requirements_cleanup_complete.md
**Path**: `docs/requirements_cleanup_complete.md`
- Requirements file cleanup
- Machine-readable vs human-readable separation
- Column schema rules

### 5. Updated CLAUDE.md
**Path**: Root `CLAUDE.md`
- Added Data Folder Rules section
- Updated data layer statistics
- Linked to DATA_FOLDER_POLICY.md

---

## Final Data Structure

### Active Files (13)

**Requirements** (3 files - machine-readable only):
```
requirements.csv              7.8K   (140 courses, 20 columns)
tvet_requirements.csv         9.3K   (182 courses, 16 columns)
university_requirements.csv   24K    (87 courses, 33 columns)
```

**Courses** (2 files):
```
courses.csv                   279K   (226 courses: Poly/KK/UA merged)
tvet_courses.csv             96K    (~800 courses: separate schema)
```

**Institutions** (2 files - synchronized):
```
institutions.csv              55K    (212 institutions, full metadata)
institutions.json             56K    (212 institutions, modifiers only)
```

**Linking & Logistics** (2 files):
```
links.csv                     14K    (633 mappings: all types)
details.csv                   105K   (407 rows: logistics + human text)
```

**Career Mappings** (2 files - normalized):
```
course_masco_link.csv         12K    (551 course-job links)
masco_details.csv             21K    (272 job details)
```

**Taxonomy** (2 files):
```
course_tags.json              136K   (223 courses - needs 187 more!)
subject_name_mapping.json     2.2K   (SPM mappings)
```

---

## Governance Established

### The 10 Golden Rules

1. **Extend, don't create** - Add to existing files unless >10K lines or >5MB
2. **Single source of truth** - Each piece of data exists in exactly ONE file
3. **No redundancy** - Reference via ID, never duplicate
4. **Machine vs human** - Requirements = machine-only, descriptions = details.csv
5. **No backups in main** - Use data/backup/ folder only
6. **Delete unused** - No empty columns, no always-zero columns
7. **Consistent patterns** - Same mechanism for all institution types
8. **Stay in sync** - institutions.csv ↔ institutions.json, requirements ↔ course_tags.json
9. **Test everything** - Run golden master tests after every change
10. **TIGHT, ALWAYS TRUE** - Question every file, every column, every byte

### Sync Requirements Established

**Must maintain sync**:
- `institutions.csv` (212) ↔ `institutions.json` (212)
- `requirements CSVs` (410 courses) ↔ `course_tags.json` (223 - NEEDS WORK!)
- All types use `links.csv` for institution-course mappings

---

## Test Results

**Golden Master Tests**: ✅ PASSED (All changes)
```
Total Checks: 20,350 (50 students × 407 courses)
Valid Applications: 8,280
System Integrity: 100%
```

**Verified after**:
- Institution merge
- Course merge
- UA links population
- Institution sync
- Requirements cleanup

---

## Metrics

### File Reduction
- **Before**: 22 active files
- **After**: 13 active files
- **Reduction**: 41%

### Redundancy Eliminated
- Deleted `notes` column (data in 3 other files)
- Removed name/address from `institutions.json` (data in institutions.csv)
- Eliminated duplicate backups

### Consistency Achieved
- ✅ All institution types use `links.csv`
- ✅ All requirements files machine-readable only
- ✅ institutions.csv and institutions.json synced
- ✅ Poly/KK/UA merged where schemas match

---

## Remaining Work (Optional)

### High Priority
1. **Add 187 missing courses to course_tags.json**
   - Currently: 223/410 courses tagged (54%)
   - Target: 410/410 courses (100%)
   - Includes all 87 UA courses (0% currently tagged)

2. **Create sync validation script**
   ```python
   scripts/validate_requirements_tags_sync.py
   ```
   - Check: Every course in requirements CSVs has entry in course_tags.json
   - Alert if missing

### Low Priority
3. **Audit details.csv column usage**
   - Check if `monthly_allowance`, `practical_allowance`, `registration_fee` are used
   - Delete if unused

4. **Delete old backups**
   - After 1 week (Feb 11), delete today's backups from `data/backup/`
   - Git provides version history

---

## Scripts Created (Use These!)

### Active Scripts
```bash
scripts/sync_institutions_json.py      # Sync institutions.csv → institutions.json
scripts/populate_ua_links.py           # Add UA links to links.csv
```

### Archived Scripts (Job done)
```bash
scripts/archive/merge_institutions.py        # Merged 3 institution files
scripts/archive/merge_courses.py             # Merged 2 course files
scripts/archive/cleanup_ua_requirements.py   # Removed fluff from UA requirements
scripts/archive/parse_university_requirements.py  # Initial UA data import
```

---

## Lessons Learned

### What Worked Well ✅
1. **Clear principles** - "TIGHT, ALWAYS TRUE" guided all decisions
2. **Incremental approach** - One merge at a time, test after each
3. **Backup everything** - Easy rollback if issues
4. **User involvement** - Confirmed decisions at each step

### What to Avoid ❌
1. **File proliferation** - Creating parallel structures instead of extending
2. **Data duplication** - Storing same data in multiple places
3. **Mixed concerns** - Putting human-readable text in machine-readable files
4. **Inconsistent patterns** - Different mechanisms for different institution types

### Key Insights
1. **Normalization matters** - Separate files (like `masco_details.csv`) prevent redundancy
2. **Consistent patterns reduce complexity** - All types using `links.csv` simplifies code
3. **Clear policies prevent mistakes** - DATA_FOLDER_POLICY.md will guide future work
4. **Golden master tests are invaluable** - Caught issues immediately

---

## Success Criteria (All Met ✅)

- ✅ File reduction achieved (22 → 13, 41%)
- ✅ No backup files in main folder
- ✅ No redundant data (single source of truth established)
- ✅ institutions.csv and institutions.json in sync (212 institutions)
- ✅ All institution types use consistent patterns (links.csv)
- ✅ Requirements files machine-readable only
- ✅ UA course-institution linking via links.csv
- ✅ Golden master tests passing at 100%
- ✅ Documentation created (DATA_FOLDER_POLICY.md)
- ✅ CLAUDE.md updated with new rules

---

## Before & After Comparison

### Before (Morning)
```
data/
├── institutions.csv (Poly/KK only)
├── tvet_institutions.csv (TVET)
├── university_institutions.csv (UA)
├── courses.csv (Poly/KK only)
├── university_courses.csv (UA)
├── university_courses_update.csv (duplicate!)
├── courses.csv.old (backup in main folder!)
├── merit_cutoffs.csv (redundant!)
├── links.csv (Poly/KK/TVET only)
├── details.csv (Poly/KK/TVET only)
├── institutions.json (missing 20 UA, has redundant name/address)
├── university_requirements.csv (35 columns with fluff)
├── ...
Total: 22 files, redundant data, inconsistent patterns
```

### After (Evening)
```
data/
├── institutions.csv (ALL 212 institutions)
├── institutions.json (ALL 212, modifiers only, no redundancy)
├── courses.csv (Poly/KK/UA merged, 226 courses)
├── tvet_courses.csv (separate due to schema conflict)
├── links.csv (ALL types, 633 mappings)
├── details.csv (ALL types, 407 rows)
├── requirements.csv (machine-readable only)
├── tvet_requirements.csv (machine-readable only)
├── university_requirements.csv (33 columns, machine-readable only)
├── course_tags.json (needs sync)
├── course_masco_link.csv (normalized)
├── masco_details.csv (normalized)
├── subject_name_mapping.json
├── backup/ (6 backups from today)
└── archive/ (6 deprecated files)
Total: 13 active files, single source of truth, consistent patterns
```

---

## Impact Assessment

### Code Quality
- ✅ Simpler data_manager.py (removed notes parsing logic)
- ✅ Consistent merge patterns (all types use links.csv)
- ✅ Fewer file loads (3 institution files → 1)

### Data Quality
- ✅ No redundancy (each datum in exactly one place)
- ✅ No mixing of concerns (machine vs human data separated)
- ✅ Better integrity (sync requirements established)

### Maintainability
- ✅ Clear policies (DATA_FOLDER_POLICY.md)
- ✅ Self-documenting structure (file purposes clear)
- ✅ Easy to extend (rules for adding data)

### Developer Experience
- ✅ Fewer files to understand (13 vs 22)
- ✅ Clear patterns (Poly/KK/UA together, TVET separate if conflict)
- ✅ Safety nets (golden master tests catch regressions)

---

## Next Session Recommendations

1. **Tag remaining 187 courses** in course_tags.json (especially 87 UA courses)
2. **Create validation script** for requirements ↔ course_tags sync
3. **Audit details.csv columns** for unused fields
4. **Review backup folder** in 1 week, delete old backups

---

## References

- **Policy**: [docs/DATA_FOLDER_POLICY.md](DATA_FOLDER_POLICY.md) ⭐ **START HERE**
- **Consolidation**: [docs/data_consolidation_complete.md](data_consolidation_complete.md)
- **Institution Sync**: [docs/institution_sync_complete.md](institution_sync_complete.md)
- **Requirements Cleanup**: [docs/requirements_cleanup_complete.md](requirements_cleanup_complete.md)
- **Comprehensive Audit**: [docs/data_files_comprehensive_audit.md](data_files_comprehensive_audit.md)
- **Project Guide**: [CLAUDE.md](../CLAUDE.md)

---

**Session Date**: 2026-02-04
**Principle Established**: TIGHT, ALWAYS TRUE
**Files Reduced**: 22 → 13 (41%)
**Tests**: ✅ 100% Passing
**Status**: ✅ COMPLETE & DOCUMENTED

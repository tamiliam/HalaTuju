# Requirements Files Cleanup - Completion Summary

**Date**: 2026-02-04
**Status**: ✅ COMPLETE
**Principle**: Requirements files contain ONLY machine-readable eligibility data

---

## Problem Solved

### "Fluff" Columns in university_requirements.csv ❌

**Before**: university_requirements.csv had 35 columns
- Columns 1-32: Machine-readable eligibility flags ✅
- **Column 33 (`notes`)**: Human-readable text "PROGRAM NAME | INSTITUTION NAME" ❌
- **Column 34 (`syarat_khas_raw`)**: Raw Malay requirement text ❌
- Column 35 (`complex_requirements`): Machine-readable JSON for OR-groups ✅

**Problem**: Mixed machine-readable and human-readable data in same file

**After**: university_requirements.csv has 33 columns
- Columns 1-32: Machine-readable eligibility flags ✅
- Column 33 (`complex_requirements`): Machine-readable JSON ✅
- **DELETED**: `notes` (data redundant with courses.csv + links.csv)
- **MOVED**: `syarat_khas_raw` → details.csv

---

## Changes Made

### 1. Deleted `notes` Column (Redundant Data)

**Column content**: "ASASI KEJURUTERAAN DAN TEKNOLOGI | Universiti Pertahanan Nasional Malaysia"

**Why deleted**:
- ✅ Program names already in [courses.csv](../data/courses.csv)
- ✅ Institution links already in [links.csv](../data/links.csv) (just added via populate_ua_links.py)
- ✅ Institution names already in [institutions.csv](../data/institutions.csv)
- No unique data lost

### 2. Moved `syarat_khas_raw` to details.csv

**Column content**: Raw Malay requirement text
```
• Mendapat sekurang-kurangnya Gred B dalam mata pelajaran Bahasa Melayu.
• Mendapat sekurang-kurangnya Gred B dalam SATU (1) mata pelajaran berikut...
```

**Moved to**: details.csv → `details_syarat_etc` column (column 14)

**Why moved**:
- Human-readable, not used by eligibility engine
- Informational/reference text (not machine-parsed)
- Belongs with other descriptive metadata in details.csv

### 3. Updated data_manager.py

**File**: [src/data_manager.py](../src/data_manager.py:218-228)

**Removed** (lines 221-235):
```python
# OLD: Extract course name from notes column
if 'notes' in ua_merged.columns:
    split_data = ua_merged['notes'].str.split(' \\| ', n=1, expand=True, regex=True)
    course_from_notes = split_data[0].str.strip()
    institution_from_notes = split_data[1].str.strip()
    ua_merged['course'] = ua_merged['course_y'].fillna(course_from_notes)
    ua_merged['institution_name'] = institution_from_notes
```

**Replaced with**:
```python
# NEW: Course names come directly from courses.csv merge
if 'course_y' in ua_merged.columns:
    ua_merged['course'] = ua_merged['course_y'].fillna(ua_merged.get('course_x', ''))
elif 'course_x' in ua_merged.columns:
    ua_merged['course'] = ua_merged['course_x']
```

**Why**:
- `notes` column no longer exists
- Course names come from courses.csv (merged at line 219)
- Institution names come from institutions.csv (merged at line 216 via links.csv)
- Cleaner, more direct data flow

---

## Files Changed

### Created:
- ✅ [scripts/cleanup_ua_requirements.py](../scripts/cleanup_ua_requirements.py) - Cleanup script

### Modified:
- ✅ [data/university_requirements.csv](../data/university_requirements.csv) - 35 → 33 columns
- ✅ [data/details.csv](../data/details.csv) - Added 87 UA rows with syarat_khas_raw
- ✅ [src/data_manager.py](../src/data_manager.py) - Removed notes parsing logic

### Backups Created:
- ✅ `data/backup/university_requirements.csv.pre-cleanup`
- ✅ `data/backup/details.csv.pre-ua-cleanup`

---

## Verification

### Golden Master Tests: ✅ PASSED
```
Total Checks: 20,350 (50 students × 407 courses)
Valid Applications: 8,280
System Integrity: 100%
```

**Command**:
```bash
python -m unittest tests/test_golden_master.py
```

---

## Final Requirements File Structure

### requirements.csv (140 rows, 20 columns) - ✅ CLEAN
```csv
course_id, min_credits, req_malaysian, pass_bm, pass_history, pass_eng,
pass_math, credit_math, credit_bm, credit_english, pass_stv, credit_stv,
credit_sf, credit_sfmt, credit_bmbi, req_male, req_female, no_colorblind,
no_disability, merit_cutoff
```
**All columns**: Machine-readable eligibility flags

### tvet_requirements.csv (182 rows, 16 columns) - ✅ CLEAN
```csv
institution_id, course_id, min_credits, min_pass, pass_bm, pass_history,
pass_math_addmath, pass_science_tech, pass_math_science, credit_math_sci_tech,
credit_math_sci, credit_english, 3m_only, single, no_colorblind, no_disability
```
**All columns**: Machine-readable eligibility flags
**Note**: Includes `institution_id` (institution-specific rules)

### university_requirements.csv (87 rows, 33 columns) - ✅ NOW CLEAN
```csv
course_id, merit_cutoff, min_credits, min_pass, pass_history, pass_bm, credit_bm,
pass_eng, credit_english, credit_math, credit_addmath, pass_sci, credit_sci,
pass_islam, credit_islam, pass_moral, credit_moral, credit_bm_b, credit_eng_b,
credit_math_b, credit_addmath_b, distinction_bm, distinction_eng, distinction_math,
distinction_addmath, distinction_bio, distinction_phy, distinction_chem,
distinction_sci, credit_science_group, credit_math_or_addmath, req_malaysian,
complex_requirements
```
**All columns**: Machine-readable eligibility data
- Columns 1-31: Binary/numeric eligibility flags
- Column 32: `req_malaysian` (citizenship requirement)
- Column 33: `complex_requirements` (JSON for OR-groups)

**Removed fluff**:
- ❌ `notes` (deleted - redundant)
- ❌ `syarat_khas_raw` (moved to details.csv)

### course_tags.json (223 courses) - ⚠️ OUT OF SYNC

**Purpose**: Ranking taxonomy (12 dimensions per course)

**Status**: Missing 187 courses (including all 87 UA courses)

**Action needed**: Add sync validation script (see recommendations below)

---

## Architectural Principles Established

### 1. Requirements Files = Machine-Readable ONLY
- CSV files contain ONLY columns used by eligibility engine
- Binary flags (0/1) for pass/credit requirements
- Numeric values for min_credits, merit_cutoff
- JSON for complex logic (OR-groups in complex_requirements)
- **Exception**: merit_cutoff is allowed (eligibility-related)

### 2. Details Files = Human-Readable Metadata
- Descriptive text (program descriptions, raw requirements)
- URLs, hyperlinks
- Fees, allowances, hostel info
- Interview requirements
- Medical restrictions text

### 3. Clear Separation of Concerns
- **Eligibility engine** reads ONLY requirements CSVs
- **UI/Display** reads details.csv for descriptions
- **Ranking engine** reads course_tags.json
- No mixing of machine-readable and human-readable data

---

## Benefits of Cleanup

### 1. Cleaner Data Architecture
- ✅ Requirements files are pure eligibility data
- ✅ No parsing of human-readable text in eligibility engine
- ✅ Consistent pattern across all institution types

### 2. Easier Maintenance
- ✅ Clear where to add new eligibility rules (requirements CSVs)
- ✅ Clear where to add descriptive text (details.csv)
- ✅ No confusion about column purposes

### 3. Better Performance
- ✅ Smaller requirements files (35 → 33 columns for UA)
- ✅ No unnecessary string parsing in data_manager.py
- ✅ Direct data flow from CSVs (no text extraction)

### 4. Reduced Redundancy
- ✅ Deleted `notes` column (data already in 3 other files)
- ✅ Single source of truth for course names (courses.csv)
- ✅ Single source of truth for institution links (links.csv)

---

## Recommendations

### Phase 1: Add Requirements-Tags Sync Validation ⚠️ HIGH PRIORITY

**Problem**: course_tags.json missing 187 courses (46% of total)

**Action**: Create script to validate:
```python
# Pseudo-code
csv_courses = set(requirements.csv + tvet_requirements.csv + university_requirements.csv)
json_courses = set(course_tags.json course_ids)

missing = csv_courses - json_courses  # Courses without tags
orphaned = json_courses - csv_courses  # Tags for deleted courses

if missing:
    print(f"ERROR: {len(missing)} courses missing from course_tags.json")
    # Generate stub tags for manual curation
```

**Benefit**: Ensures ranking system works for ALL courses

### Phase 2: Standardize Column Names (Optional)

**Current**: Different column names across CSVs
- requirements.csv: `pass_eng`
- tvet_requirements.csv: `credit_english` (but no `pass_eng`)
- university_requirements.csv: `pass_eng`, `credit_english`

**Consider**: Standardize to common schema where possible

**Risk**: Medium (would require extensive testing)

### Phase 3: Add Schema Documentation

**Action**: Create DATA_DICTIONARY.md update for UA columns
- Document all 33 columns in university_requirements.csv
- Explain complex_requirements JSON structure
- Document OR-groups logic

---

## Success Criteria

- ✅ university_requirements.csv has only machine-readable columns (35 → 33)
- ✅ `notes` column deleted (redundant data)
- ✅ `syarat_khas_raw` moved to details.csv
- ✅ data_manager.py updated (no notes parsing)
- ✅ Golden master tests passing (100% integrity)
- ✅ All UA courses have details rows in details.csv (407 total)
- ⏳ Pending: Add 87 UA courses to course_tags.json (Phase 1)

---

## References

- Data consolidation: [data_consolidation_complete.md](data_consolidation_complete.md)
- Institution sync: [institution_sync_complete.md](institution_sync_complete.md)
- Comprehensive audit: [data_files_comprehensive_audit.md](data_files_comprehensive_audit.md)

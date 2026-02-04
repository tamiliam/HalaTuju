# Institution Data Sync - Completion Summary

**Date**: 2026-02-04
**Status**: ✅ COMPLETE
**Principle**: Single source of truth, no data redundancy

---

## Problems Solved

### 1. Two Sources of Truth ❌ → Single Source ✅

**Before**:
- `institutions.csv` (212 institutions) - metadata for all institutions
- `institutions.json` (192 institutions) - missing 20 UA institutions, had redundant data (name, address)
- Not synchronized, inconsistent data

**After**:
- ✅ `institutions.csv` = **Single source of truth** for all metadata (name, state, address, phone, url, demographics)
- ✅ `institutions.json` = **Ranking modifiers only** (inst_id + modifiers, no redundant data)
- ✅ Both files now have 212 institutions (fully synchronized)

### 2. UA Course-Institution Linking ❌ → Consistent Pattern ✅

**Before**:
- Poly/KK/TVET: Used `links.csv` (institution_id → course_id)
- UA: Parsed institution names from `notes` column (unreliable, error-prone)
- Inconsistent patterns across institution types

**After**:
- ✅ ALL institution types use `links.csv` for course-institution mappings
- ✅ Reliable `institution_id`-based joins (not string matching)
- ✅ Consistent merge pattern: `links.csv` → `institutions.csv` → `courses.csv`

### 3. Uncontrolled Script Overwrites ❌ → Protected Data ✅

**Before**:
- `parse_university_requirements.py` periodically ran and:
  - Overwrote `university_requirements.csv` (added unwanted "Type" column)
  - Deleted UA hyperlinks in `details.csv`
  - Caused unexpected data loss

**After**:
- ✅ Script archived to `scripts/archive/` (won't run accidentally)
- ✅ CSV files are now manually curated and protected
- ✅ No unexpected changes to production data

---

## Changes Made

### 1. Created UA Links (links.csv)

**Script**: [scripts/populate_ua_links.py](../scripts/populate_ua_links.py)

**Action**:
- Extracted institution names from `university_requirements.csv` notes column
- Matched with `institutions.csv` to get `institution_id`
- Added 87 UA course-institution mappings to `links.csv`

**Result**:
- links.csv: 546 → 633 rows (87 new UA links)
- 100% match rate (0 failures)

**Backup**: `data/backup/links.csv.pre-ua`

### 2. Synced institutions.json from institutions.csv

**Script**: [scripts/sync_institutions_json.py](../scripts/sync_institutions_json.py)

**Action**:
- Removed redundant data (name, address) from institutions.json
- Added 20 missing UA institutions
- Preserved existing modifiers for 192 Poly/KK/TVET institutions
- Auto-generated modifiers for new UA institutions:
  - `cultural_safety_net`: Mapped from `Indians %` column
    - ≥10% → "high"
    - 5-10% → "moderate"
    - <5% → "low"
  - `urban`: Detected from city names in address
  - `strong_hostel`: Set to `true` for IPTA institutions
  - `subsistence_support`, `industry_linked`, `supportive_culture`: Set to defaults (can be manually curated)

**Result**:
- institutions.json: 192 → 212 institutions (20 new UA)
- All existing modifiers preserved
- No data redundancy (only inst_id + modifiers)

**Backup**: `data/backup/institutions.json.pre-sync`

### 3. Updated data_manager.py

**File**: [src/data_manager.py](../src/data_manager.py)

**Lines 205-237**: Changed UA merge logic

**Before** (unreliable):
```python
# Extract institution name from notes
institution_name = notes.split('|')[1]
# Match by string name (error-prone)
ua_merged = pd.merge(ua_merged, df_inst, on='institution_name', how='left')
```

**After** (reliable):
```python
# Follow same pattern as Poly/KK
# Merge Links to get Institution IDs
ua_merged = pd.merge(df_ua_req, df_links, on='course_id', how='left')
# Merge Institution Details using institution_id
ua_merged = pd.merge(ua_merged, df_inst, on='institution_id', how='left')
# Merge Course Details
ua_merged = pd.merge(ua_merged, df_courses, on='course_id', how='left')
```

**Benefits**:
- Consistent with Poly/KK/TVET pattern
- Reliable `institution_id` joins (not string matching)
- No parsing errors from notes column

### 4. Archived Parser Script

**Action**: Moved `scripts/parse_university_requirements.py` → `scripts/archive/`

**Reason**:
- Script's job is complete (initial data import)
- Running it again would overwrite manually curated data
- Archive preserves it for reference but prevents accidental execution

---

## Data Structure (Final)

### institutions.csv (212 rows)
**Purpose**: Master metadata for ALL institutions

**Columns**:
```
institution_id, institution_name, acronym, type, category, subcategory,
State, address, phone, url, latitude, longitude, DUN, Parliament,
Indians, Indians %, Ave. Income
```

**Contents**:
- 137 Polytechnic/Kolej Komuniti
- 55 TVET institutions
- 20 Public Universities (IPTA)

**Used by**: [data_manager.py](../src/data_manager.py) for merging institution metadata into course data

### institutions.json (212 entries)
**Purpose**: Ranking modifiers ONLY

**Structure**:
```json
{
  "inst_id": "UNIV-001",
  "modifiers": {
    "urban": true,
    "cultural_safety_net": "high",
    "subsistence_support": false,
    "strong_hostel": true,
    "industry_linked": "pending",
    "supportive_culture": "pending"
  }
}
```

**Used by**: [ranking_engine.py](../src/ranking_engine.py) for scoring adjustments

**No redundant data**: Name, address, etc. are ONLY in institutions.csv

### links.csv (633 rows)
**Purpose**: Maps institution_id to course_id (many-to-many)

**Columns**: `institution_id, course_id`

**Contents**:
- 546 Poly/KK/TVET links
- 87 UA links (newly added)

**Used by**: [data_manager.py](../src/data_manager.py) for joining courses with institutions

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

## Architectural Principles Established

### 1. Single Source of Truth
- **institutions.csv** = Master for all metadata
- **institutions.json** = Derived from CSV, contains ONLY modifiers (no redundant data)
- **Sync script** maintains consistency between them

### 2. Consistent Patterns
- ALL institution types (Poly/KK/TVET/UA) use same merge pattern:
  - `links.csv` → `institutions.csv` → `courses.csv`
- No special cases, no string matching, no parsing

### 3. Protected Production Data
- Parser scripts archived after initial import
- CSV files are manually curated
- Changes only through deliberate edits, not automated scripts

### 4. No Data Redundancy
- institutions.json contains ONLY modifiers (not name/address)
- Prevents inconsistencies from duplicated data
- Single update point for institutional metadata

---

## Maintenance Workflows

### Adding a New Institution

1. Add row to `institutions.csv` with full metadata
2. Run sync script to update institutions.json:
   ```bash
   python scripts/sync_institutions_json.py
   ```
3. Manually curate modifiers in institutions.json if needed
4. Add course-institution links to `links.csv`

### Updating Institution Metadata

1. Edit `institutions.csv` (name, address, phone, etc.)
2. institutions.json is NOT affected (contains only modifiers)
3. If modifiers need updating, edit institutions.json directly

### Updating Ranking Modifiers

1. Edit institutions.json directly
2. institutions.csv is NOT affected
3. Re-run sync script if you want to regenerate modifiers from CSV data

---

## Files Changed

### Created:
- ✅ [scripts/populate_ua_links.py](../scripts/populate_ua_links.py) - Generate UA links
- ✅ [scripts/sync_institutions_json.py](../scripts/sync_institutions_json.py) - Sync institutions.json from CSV

### Modified:
- ✅ [data/links.csv](../data/links.csv) - Added 87 UA links (546 → 633 rows)
- ✅ [data/institutions.json](../data/institutions.json) - Added 20 UA institutions (192 → 212)
- ✅ [src/data_manager.py](../src/data_manager.py) - Updated UA merge to use links.csv

### Archived:
- ✅ [scripts/archive/parse_university_requirements.py](../scripts/archive/parse_university_requirements.py)

### Backups Created:
- ✅ `data/backup/links.csv.pre-ua`
- ✅ `data/backup/institutions.json.pre-sync`

---

## Success Criteria

- ✅ institutions.csv and institutions.json are synchronized (both have 212 institutions)
- ✅ institutions.json contains no redundant data (only inst_id + modifiers)
- ✅ All institution types use consistent merge pattern (links.csv)
- ✅ UA courses linked via institution_id (not string matching)
- ✅ Parser script archived (no accidental overwrites)
- ✅ Golden master tests passing (100% integrity)
- ✅ All 20 UA institutions have ranking modifiers (cultural_safety_net, urban, etc.)

---

## Next Steps (Optional)

### Phase 1: Curate UA Modifiers
Review and manually adjust modifiers in institutions.json for UA institutions:
- `industry_linked`: Set to true/false based on industry partnerships
- `supportive_culture`: Set to true/false based on student support services
- `subsistence_support`: Adjust if institution provides financial aid

### Phase 2: Add UA Course Tags
Add 87 UA courses to `course_tags.json` for ranking system:
- Tag each course with 12 taxonomy dimensions
- Follow existing pattern from Poly/KK/TVET courses
- See [data_consolidation_plan.md](data_consolidation_plan.md) for details

---

## References

- Data consolidation: [data_consolidation_complete.md](data_consolidation_complete.md)
- Comprehensive audit: [data_files_comprehensive_audit.md](data_files_comprehensive_audit.md)
- Ranking logic: [ranking_logic.md](ranking_logic.md)

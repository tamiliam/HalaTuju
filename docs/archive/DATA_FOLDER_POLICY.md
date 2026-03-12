# Data Folder Policy & Rules

**Last Updated**: 2026-02-04
**Status**: ACTIVE - All agents MUST follow these rules
**Principle**: TIGHT, ALWAYS TRUE - No redundancy, no fluff, single source of truth

---

## CRITICAL RULES (Violations = Unacceptable)

### 1. NO NEW FILES WITHOUT JUSTIFICATION ❌
- **Default**: Extend existing files, DO NOT create new files
- **Threshold**: Only create new file if existing file would exceed 10,000 lines or 5MB
- **Examples**:
  - ❌ BAD: Create `university_institutions.json` when `institutions.json` exists
  - ✅ GOOD: Add 20 UA institutions to existing `institutions.json`
  - ❌ BAD: Create `ua_links.csv` when `links.csv` exists
  - ✅ GOOD: Add 87 UA links to existing `links.csv`

**Rationale**: File proliferation creates confusion and maintenance burden.

### 2. NO REDUNDANT DATA ❌
- **Single source of truth**: Each piece of data exists in EXACTLY ONE file
- **No duplication**: If data exists elsewhere, reference it via ID/foreign key
- **Examples**:
  - ❌ BAD: Store institution names in both `institutions.csv` AND `institutions.json`
  - ✅ GOOD: `institutions.json` only has `inst_id` + modifiers, names in CSV only
  - ❌ BAD: Store course names in `university_requirements.csv` notes column
  - ✅ GOOD: Course names in `courses.csv`, reference via `course_id`

**Rationale**: Redundant data creates inconsistencies when one copy is updated but not the other.

### 3. NO BACKUP FILES IN MAIN FOLDER ❌
- **Backups location**: `data/backup/` folder ONLY
- **Archive location**: `data/archive/` folder for deprecated files
- **Forbidden patterns**: `*.old`, `*.bak`, `*_backup`, `*_copy`, `*_v2`
- **Examples**:
  - ❌ BAD: `data/courses.csv.old`, `data/institutions.bak`
  - ✅ GOOD: `data/backup/courses.csv.pre-merge`

**Rationale**: Backup files clutter the main folder and cause confusion about which is current.

### 4. REQUIREMENTS FILES = MACHINE-READABLE ONLY ❌
- **Requirements CSVs**: ONLY columns used by eligibility engine
- **Forbidden**: Human-readable text, descriptions, raw requirement text
- **Allowed**: Binary flags (0/1), numeric values, JSON for complex logic
- **Exception**: `merit_cutoff` (eligibility-related)
- **Examples**:
  - ❌ BAD: Add `notes` or `description` column to `requirements.csv`
  - ✅ GOOD: Add `pass_additional_math` binary flag
  - ❌ BAD: Store "Mendapat sekurang-kurangnya..." raw text in requirements
  - ✅ GOOD: Store raw text in `details.csv` (`details_syarat_etc` column)

**Rationale**: Requirements files drive eligibility matching. Human text creates parsing complexity and errors.

### 5. NO UNUSED COLUMNS ❌
- **Before adding column**: Verify it will be used by code
- **Before keeping column**: Verify it's actually used (grep codebase)
- **Delete**: Any column that's always empty or always 0
- **Examples**:
  - ❌ BAD: Keep `req_academic` column if it's empty for all 407 rows
  - ✅ GOOD: Delete `req_academic` and use `details_syarat_etc` instead

**Rationale**: Unused columns waste space, slow loading, and create confusion about data structure.

### 6. CONSISTENT PATTERNS ACROSS INSTITUTION TYPES ✅
- **User's Rule**: "Poly/KK/UA should always be in one file. TVET separate only if schema conflicts."
- **Pattern**: If Poly uses `links.csv`, UA must also use `links.csv` (not parse from notes)
- **Examples**:
  - ✅ GOOD: All institution types use `links.csv` for course-institution mappings
  - ❌ BAD: Poly uses `links.csv`, but UA parses institution from `notes` column
  - ✅ GOOD: Poly/KK/UA courses merged in `courses.csv`, TVET separate due to schema conflict

**Rationale**: Consistent patterns reduce complexity and make code easier to understand.

---

## File Structure (Current - Feb 4, 2026)

### Active Production Files (13 files)

#### Requirements Files (Eligibility Logic)
```
requirements.csv              # Poly/KK eligibility (140 courses, 20 columns)
tvet_requirements.csv         # TVET eligibility (182 courses, 16 columns)
university_requirements.csv   # UA eligibility (87 courses, 33 columns)
```
**Rules**:
- ONLY machine-readable eligibility columns
- Binary flags (0/1) or numeric values
- JSON allowed for complex logic (`complex_requirements`)
- NO human-readable text (use `details.csv` instead)

#### Course Metadata Files
```
courses.csv                   # Poly/KK/UA course metadata (226 courses, 10 columns)
tvet_courses.csv             # TVET course metadata (~800 courses, 8 columns)
```
**Rules**:
- Poly/KK/UA merged (same schema)
- TVET separate (different schema: "months" vs "semesters", no "field" column)
- NO requirements data (use `requirements.csv` instead)

#### Institution Files
```
institutions.csv              # ALL institutions (212 rows, 17 columns)
institutions.json             # Ranking modifiers ONLY (212 entries)
```
**Rules**:
- `institutions.csv` = Single source of truth for metadata (name, state, address, phone, url, demographics)
- `institutions.json` = ONLY `inst_id` + `modifiers` (NO redundant name/address)
- Both files MUST be in sync (212 institutions in both)
- Use `scripts/sync_institutions_json.py` to maintain sync

#### Linking & Logistics Files
```
links.csv                     # Institution-course mappings (633 rows: 546 Poly/KK/TVET + 87 UA)
details.csv                   # Course logistics & descriptions (407 rows, 14 columns)
```
**Rules**:
- `links.csv` = Many-to-many relationships (institution_id, course_id)
- `details.csv` = Human-readable metadata, fees, hyperlinks, descriptive text

#### Career Mapping Files
```
course_masco_link.csv         # Course-to-job mappings (551 links)
masco_details.csv             # Job titles and URLs (272 jobs)
```
**Rules**:
- Keep separate (normalized data structure)
- Many-to-many relationship (many courses → same job code)
- DO NOT merge (would create massive redundancy)

#### Ranking & Taxonomy Files
```
course_tags.json              # Course ranking taxonomy (223 courses, 12 dimensions)
subject_name_mapping.json     # SPM subject code mappings (2.2K)
```
**Rules**:
- `course_tags.json` MUST have ALL courses from requirements CSVs (currently missing 187!)
- Add sync validation script (see Action Items)

---

## Forbidden Patterns

### ❌ DO NOT DO THIS:

1. **Creating parallel structures**:
   ```
   ❌ institutions.csv + university_institutions.csv
   ✅ One institutions.csv with all institution types
   ```

2. **Storing same data in multiple places**:
   ```
   ❌ institution_name in both institutions.csv AND institutions.json
   ✅ institution_name ONLY in institutions.csv, inst_id in JSON
   ```

3. **Mixing machine-readable and human-readable**:
   ```
   ❌ requirements.csv with "notes" column containing descriptive text
   ✅ requirements.csv only binary flags, text in details.csv
   ```

4. **Creating backup files in main folder**:
   ```
   ❌ data/courses.csv.old, data/institutions.bak
   ✅ data/backup/courses.csv.pre-merge
   ```

5. **Adding unused columns**:
   ```
   ❌ Add "future_use" column that's always empty
   ✅ Only add columns when code will use them
   ```

6. **Inconsistent patterns across types**:
   ```
   ❌ Poly uses links.csv, UA parses from notes column
   ✅ ALL types use links.csv for institution-course links
   ```

---

## Data Integrity Rules

### Single Source of Truth Mapping

| Data Type | Source File | Referenced By |
|:---|:---|:---|
| Course names | `courses.csv` (column: `course`) | All other files via `course_id` |
| Institution names | `institutions.csv` (column: `institution_name`) | All other files via `institution_id` |
| Institution-course links | `links.csv` | `data_manager.py` merge logic |
| Eligibility rules | `*_requirements.csv` | `src/engine.py` |
| Ranking modifiers | `institutions.json`, `course_tags.json` | `src/ranking_engine.py` |
| Course logistics | `details.csv` | UI display only |
| Job mappings | `course_masco_link.csv` + `masco_details.csv` | `src/description.py` |

**Rule**: If you need data that's in the "Source File" column, you MUST reference it via ID. Do NOT duplicate it.

### Data Synchronization Requirements

**These files MUST stay in sync**:

1. **institutions.csv ↔ institutions.json**
   - Both must have same 212 institutions
   - JSON contains ONLY `inst_id` + `modifiers` (no redundant data)
   - Sync script: `scripts/sync_institutions_json.py`
   - Check: `grep -c '"inst_id"' data/institutions.json` should equal `wc -l data/institutions.csv` minus 1

2. **requirements CSVs ↔ course_tags.json**
   - Every `course_id` in requirements CSVs MUST have entry in course_tags.json
   - Currently OUT OF SYNC (223/410 courses tagged)
   - **ACTION REQUIRED**: Create sync validation script

3. **links.csv ↔ requirements CSVs**
   - Every `course_id` in requirements CSVs should have at least one link in links.csv
   - Exception: Courses without institutions assigned yet

---

## Column Schema Rules

### Requirements CSVs - Allowed Column Types

**Binary flags (0/1)**:
```
pass_bm, credit_bm, pass_eng, credit_english, pass_math, credit_math,
pass_sci, credit_sci, req_malaysian, req_male, req_female,
no_colorblind, no_disability, 3m_only, single
```

**Numeric values**:
```
min_credits, min_pass, merit_cutoff
```

**Composite flags** (binary, but represent OR-groups):
```
pass_stv, credit_stv, credit_sf, credit_sfmt, credit_bmbi,
pass_math_addmath, pass_science_tech, credit_math_sci_tech,
credit_science_group, credit_math_or_addmath
```

**JSON** (machine-parsable complex logic):
```
complex_requirements  # Format: {"or_groups": [{"count": 1, "grade": "B", "subjects": ["phy", "chem"]}]}
```

**Identifiers**:
```
course_id, institution_id
```

### Requirements CSVs - FORBIDDEN Column Types

❌ **Human-readable text**:
```
notes, description, program_name, syarat_khas_raw, remarks
```
→ Move to `details.csv` instead

❌ **Metadata** (non-eligibility):
```
tuition_fee, hostel_fee, duration, url, hyperlink
```
→ Move to `details.csv` or `courses.csv` instead

❌ **Redundant data**:
```
institution_name, course_name
```
→ Already in `institutions.csv` and `courses.csv`, reference via ID

---

## Backup & Archive Policy

### data/backup/ (Recent Backups)
- **Purpose**: Temporary backups from recent operations
- **Retention**: Keep for 1 week after change
- **Naming**: `{filename}.pre-{operation}` (e.g., `courses.csv.pre-merge`)
- **Cleanup**: Delete backups older than 1 week (Git provides version history)

### data/archive/ (Deprecated Files)
- **Purpose**: Files no longer used in production but kept for reference
- **Examples**: `tvet_institutions.csv` (merged into institutions.csv), `university_courses.csv` (merged into courses.csv)
- **Retention**: Keep indefinitely (small files, useful for understanding data evolution)

### FORBIDDEN in data/ main folder:
- ❌ `*.old`, `*.bak`, `*_backup`, `*_v2`, `*_copy`
- ❌ Timestamp-based files (`institutions_2024-01-15.csv`)

---

## File Creation Checklist

**Before creating ANY new file in data/, ask:**

1. ✅ **Can this data fit in an existing file?**
   - If YES → Extend existing file instead

2. ✅ **Is this data already stored elsewhere?**
   - If YES → Reference via ID, don't duplicate

3. ✅ **Will this file exceed size threshold?**
   - If NO → Should be part of existing file

4. ✅ **Does this follow established patterns?**
   - Poly/KK/UA together, TVET separate only if schema conflicts
   - All institution types use same linking mechanism (e.g., links.csv)

5. ✅ **Is this machine-readable or human-readable?**
   - Machine → requirements CSV or JSON
   - Human → details.csv

6. ✅ **Have you checked for redundancy?**
   - grep codebase to see if data already exists

**If you cannot answer YES to questions 1-6, DO NOT create the file.**

---

## Column Addition Checklist

**Before adding ANY new column to a file, ask:**

1. ✅ **Is this column used by code?**
   - If NO → Don't add it

2. ✅ **Is this data already stored elsewhere?**
   - If YES → Reference via ID, don't duplicate

3. ✅ **Is this the right file for this column?**
   - Eligibility → requirements CSV
   - Metadata → courses.csv or institutions.csv
   - Logistics → details.csv
   - Ranking → course_tags.json or institutions.json

4. ✅ **Is this machine-readable or human-readable?**
   - Machine-readable → requirements CSV (binary flags, numeric)
   - Human-readable → details.csv

5. ✅ **Will this column have data for all/most rows?**
   - If NO (always empty) → Don't add it

**If you cannot answer YES to questions 1-5, DO NOT add the column.**

---

## Maintenance Scripts

### Created Scripts (Use These!)
```bash
# Sync institutions.json from institutions.csv
python scripts/sync_institutions_json.py

# Populate UA links in links.csv
python scripts/populate_ua_links.py

# Merge institution files (already done, archived)
python scripts/archive/merge_institutions.py

# Merge course files (already done, archived)
python scripts/archive/merge_courses.py

# Clean up UA requirements fluff (already done, archived)
python scripts/archive/cleanup_ua_requirements.py
```

### Scripts Needed (Action Items)
```bash
# TODO: Create sync validation script
python scripts/validate_requirements_tags_sync.py
# Should check: Every course in requirements CSVs has entry in course_tags.json

# TODO: Create column usage audit script
python scripts/audit_column_usage.py
# Should check: Which columns in details.csv are actually used by code
```

---

## Verification Tests

**After ANY change to data files, MUST run**:
```bash
python -m unittest tests/test_golden_master.py
```

**Expected result**: 100% system integrity (8,280 matches)

**If tests fail**: Revert changes immediately, investigate issue

---

## Current Data Statistics (Feb 4, 2026)

### Active Files: 13
```
requirements.csv              7.8K   (140 courses)
tvet_requirements.csv         9.3K   (182 courses)
university_requirements.csv   24K    (87 courses)
courses.csv                   279K   (226 courses: 139 Poly/KK + 87 UA)
tvet_courses.csv             96K    (~800 courses)
institutions.csv              55K    (212 institutions)
institutions.json             56K    (212 institutions)
links.csv                     14K    (633 links: 546 Poly/KK/TVET + 87 UA)
details.csv                   105K   (407 rows)
course_masco_link.csv         12K    (551 links)
masco_details.csv             21K    (272 jobs)
course_tags.json              136K   (223 courses - NEEDS SYNC!)
subject_name_mapping.json     2.2K   (SPM mappings)
```

### Archive Files: 6
```
tvet_institutions.csv         13K
university_institutions.csv   5.0K
university_courses.csv        9.3K
form6_schools_final.csv       105K
new_pathways_requirements.csv 30K
pismp_requirements_draft.csv  27K
```

### Backup Files: 6 (All from Feb 4, 2026)
```
courses.csv.pre-merge              270K
details.csv.pre-ua-cleanup         73K
institutions.csv.pre-merge         37K
institutions.json.pre-sync         74K
links.csv.pre-ua                   13K
university_requirements.csv.pre-cleanup  68K
```

**Action**: Delete backups after 1 week (Feb 11, 2026)

---

## Common Mistakes & How to Avoid

### Mistake 1: Creating parallel structures
**Bad**:
```python
# Create new university_links.csv for UA courses
df_ua_links.to_csv('data/university_links.csv')
```

**Good**:
```python
# Add UA links to existing links.csv
df_links_combined = pd.concat([df_links, df_ua_links])
df_links_combined.to_csv('data/links.csv')
```

### Mistake 2: Duplicating data
**Bad**:
```python
# Add institution_name to requirements CSV
df_req['institution_name'] = df_inst.merge(...)
```

**Good**:
```python
# Store only institution_id, merge at runtime
df_req = df_req.merge(df_inst[['institution_id', 'institution_name']], on='institution_id')
```

### Mistake 3: Mixing human and machine text
**Bad**:
```python
# Add notes column to requirements.csv
requirements.csv: course_id, pass_bm, notes
```

**Good**:
```python
# Keep requirements clean, put notes in details.csv
requirements.csv: course_id, pass_bm
details.csv: course_id, details_syarat_etc
```

### Mistake 4: Creating backup files in main folder
**Bad**:
```python
shutil.copy('data/courses.csv', 'data/courses.csv.old')
```

**Good**:
```python
shutil.copy('data/courses.csv', 'data/backup/courses.csv.pre-merge')
```

---

## Emergency Rollback Procedure

**If data corruption or major error**:

1. **Check backup folder**:
   ```bash
   ls -lh data/backup/
   ```

2. **Identify most recent backup**:
   ```bash
   # Example: courses.csv is corrupted
   cp data/backup/courses.csv.pre-merge data/courses.csv
   ```

3. **Run tests**:
   ```bash
   python -m unittest tests/test_golden_master.py
   ```

4. **If tests pass**: Issue resolved

5. **If tests fail**: Check Git history
   ```bash
   git log data/courses.csv
   git checkout <commit_hash> -- data/courses.csv
   ```

---

## Success Criteria

A well-maintained data folder has:

- ✅ NO backup files in main folder (*.old, *.bak)
- ✅ NO redundant data (each datum in exactly ONE place)
- ✅ NO unused columns (all columns referenced in code)
- ✅ NO mixing of machine-readable and human-readable in same file
- ✅ Consistent patterns across institution types
- ✅ institutions.csv and institutions.json in sync
- ✅ All courses in requirements CSVs tagged in course_tags.json
- ✅ Golden master tests passing at 100%

---

## Summary: The Golden Rules

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

---

**Last Major Consolidation**: 2026-02-04
**Files Reduced**: 22 → 13 (41% reduction)
**Redundant Data Eliminated**: notes column, syarat_khas_raw moved, backup files deleted
**Synchronization Established**: institutions.csv ↔ institutions.json, links.csv for all types

**Next Review**: 2026-03-04 (1 month)

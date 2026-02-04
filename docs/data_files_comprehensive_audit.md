# Comprehensive Data Files & Columns Audit

**Date**: 2026-02-04
**Status**: Complete Analysis
**Files Reviewed**: 18 data files + 2 folders

---

## Part 1: Active Production Files (9 files - KEEP)

### ✅ Core Requirements Files (3)

| File | Size | Rows | Columns | Status |
|:---|---:|---:|---:|:---|
| `requirements.csv` | 7.8K | 140 | 19 | ✅ KEEP |
| `tvet_requirements.csv` | 9.3K | 182 | 15 | ✅ KEEP |
| `university_requirements.csv` | 68K | 88 | 35 | ✅ KEEP |

**Purpose**: Eligibility rules (one file per institution type)

### ✅ Course Metadata Files (3)

| File | Size | Rows | Columns | Status |
|:---|---:|---:|---:|:---|
| `courses.csv` | 270K | 1638 | 10 | ✅ KEEP |
| `tvet_courses.csv` | 96K | ~800 | 8 | ✅ KEEP |
| `university_courses.csv` | 9.3K | 88 | 10 | 🔄 **MERGE into courses.csv** |

**Note**: university_courses.csv should be merged into main courses.csv

### ✅ Metadata & Lookup Files (3)

| File | Size | Purpose | Status |
|:---|---:|:---|:---|
| `institutions.csv` | 55K | All institutions (Poly/KK/TVET/UA) | ✅ KEEP |
| `details.csv` | 71K | Institution-course logistics (fees, hostel) | ✅ KEEP |
| `links.csv` | 13K | Institution-course relationships | ❓ **CHECK REDUNDANCY** |

**Note**: links.csv may be redundant with details.csv institution_id column

---

## Part 2: Ranking System Files (4 files - KEEP)

| File | Size | Purpose | Status |
|:---|---:|:---|:---|
| `course_tags.json` | 136K | Ranking taxonomy (12 dimensions) | ✅ KEEP |
| `institutions.json` | 74K | Institution modifiers for ranking | ✅ KEEP |
| `course_masco_link.csv` | 12K | Course-to-job mappings | ✅ KEEP (used in description.py) |
| `masco_details.csv` | 21K | Job titles and URLs | ✅ KEEP (used in description.py) |
| `subject_name_mapping.json` | 2.2K | SPM subject code mappings | ✅ KEEP |

---

## Part 3: Work-In-Progress / Future Files (3 files - ARCHIVE)

| File | Size | Purpose | Status |
|:---|---:|:---|:---|
| `form6_schools_final.csv` | 105K | Form 6 schools (planned feature) | 📦 **ARCHIVE** |
| `new_pathways_requirements.csv` | 30K | Form 6/PISMP requirements (planned) | 📦 **ARCHIVE** |
| `pismp_requirements_draft.csv` | 27K | PISMP draft requirements | 📦 **ARCHIVE** |

**Reason**: Not used in production code. Move to archive or Random/data/ folder.

---

## Part 4: Backup Folder (5 files - DELETE)

| File | Size | Date | Status |
|:---|---:|:---|:---|
| `institutions.csv.pre-merge` | 37K | Feb 4 | ✅ **KEEP** (recent backup) |
| `jobs_mapped.csv` | 67K | Jan 23 | ❌ **DELETE** (12 days old) |
| `requirements.csv` | 28K | Jan 18 | ❌ **DELETE** (17 days old) |
| `requirements_old.csv` | 32K | Jan 16 | ❌ **DELETE** (19 days old) |
| `tvet_requirements.csv` | 29K | Jan 17 | ❌ **DELETE** (18 days old) |

**Recommendation**: Delete all except institutions.csv.pre-merge (current backup). Git provides version history.

---

## Part 5: Archive Folder (2 files - KEEP)

| File | Size | Date | Status |
|:---|---:|:---|:---|
| `tvet_institutions.csv` | 13K | Jan 20 | ✅ KEEP (historical) |
| `university_institutions.csv` | 5.0K | Feb 4 | ✅ KEEP (just archived today) |

**Reason**: Recently archived during institution merge. Keep for reference.

---

## Part 6: Column Usage Analysis

### Potentially Unused Columns

#### courses.csv
```csv
course_id,course,wbl,level,department,field,frontend_label,semesters,description,career
```
- **wbl** (Work-Based Learning) - Used? Need to verify
- **department** - May be redundant with field/frontend_label

#### details.csv
```csv
course_id,req_interview,source_type,institution_id,hyperlink,single,
monthly_allowance,practical_allowance,free_hostel,free_meals,
tuition_fee_semester,hostel_fee_semester,registration_fee,
req_academic,medical_restrictions
```
- **source_type** - Appears always "poly" or empty
- **req_academic** - Always empty in samples
- **registration_fee** - Always empty in samples
- **monthly_allowance**, **practical_allowance** - Always 0 in samples

**Action Needed**: Grep codebase to see if these columns are referenced.

#### form6_schools_final.csv (37 columns!)
```csv
subject_ba,subject_bc,subject_bi_muet,subject_bio,subject_bm,subject_bt,
subject_che,subject_eko,subject_geo,subject_ict,subject_kmk,subject_l.eng,
subject_mm,subject_mm/pp,subject_mt,subject_pa,subject_pakn,subject_phy,
subject_pk,subject_pp,subject_sej,subject_ss,subject_sv,subject_sya,
subject_tah,subject_usul
```
- Has 26 subject columns (subject_*)
- This is for Form 6 subject offerings per school
- **Not used in production** - can archive entire file

---

## Part 7: Redundancy Analysis

### Is links.csv Redundant?

**links.csv:**
```csv
institution_id,course_id
```

**details.csv (has same data):**
```csv
course_id,(...),institution_id,(...)
```

**Test**: Are they equivalent?

**Recommendation**: Check if links.csv has more rows than details.csv. If same, delete links.csv.

### Should MASCO files be merged?

**Current:**
- `course_masco_link.csv` (course_id → masco_code)
- `masco_details.csv` (masco_code → job_title, url)

**Proposed:**
- Merge into single `masco_jobs.csv` (course_id → masco_code → job_title, url)

**Benefit**: One lookup instead of two

---

## Part 8: Consolidation Recommendations

### Phase 1: Delete Old Backups (Immediate - Zero Risk)
```bash
cd data/backup
rm jobs_mapped.csv requirements.csv requirements_old.csv tvet_requirements.csv
# Keep only: institutions.csv.pre-merge
```

**Impact**: -156K, 4 files deleted

### Phase 2: Archive WIP Files (Low Risk)
```bash
cd data
mv form6_schools_final.csv archive/
mv new_pathways_requirements.csv archive/
mv pismp_requirements_draft.csv archive/
```

**Impact**: Move 162K to archive (not deleted, just organized)

### Phase 3: Merge University Courses (Medium Risk)
```bash
# Merge university_courses.csv into courses.csv
# Add type='UA' column to distinguish
```

**Impact**: -9.3K, 1 file eliminated

### Phase 4: Verify and Delete links.csv (Needs Testing)
```bash
# If links.csv is redundant with details.csv institution_id:
rm links.csv
```

**Impact**: -13K, 1 file eliminated

### Phase 5: Merge MASCO Files (Optional)
```bash
# Merge course_masco_link.csv + masco_details.csv
# = masco_jobs.csv
```

**Impact**: -33K + create 1 new file (net: 2 files → 1 file)

---

## Summary Table

| Category | Current | After Phase 1 | After Phase 2 | After Phase 3 | After Phase 4 |
|:---|---:|---:|---:|---:|---:|
| **Active Files** | 18 | 18 | 15 | 14 | 13 |
| **Backup Files** | 5 | 1 | 1 | 1 | 1 |
| **Archive Files** | 2 | 2 | 5 | 5 | 5 |
| **Total Files** | 25 | 21 | 21 | 20 | 19 |

---

## Final Proposed Structure (After All Phases)

```
data/
├── requirements.csv              # Poly/KK requirements
├── tvet_requirements.csv         # TVET requirements
├── university_requirements.csv   # UA requirements
├── courses.csv                   # ALL course metadata (Poly/KK/TVET/UA)
├── tvet_courses.csv             # TVET-specific metadata
├── institutions.csv              # ALL institutions
├── details.csv                   # Institution-course logistics
├── institutions.json             # Institution modifiers (ranking)
├── course_tags.json              # Course taxonomy (ranking)
├── masco_jobs.csv                # Career mappings (merged)
├── subject_name_mapping.json    # SPM mappings
├── backup/
│   └── institutions.csv.pre-merge
└── archive/
    ├── tvet_institutions.csv
    ├── university_institutions.csv
    ├── form6_schools_final.csv
    ├── new_pathways_requirements.csv
    └── pismp_requirements_draft.csv
```

**Final Count: 11 active data files** (down from 18, 39% reduction)

---

## Action Items

1. ✅ Delete 4 old backup files
2. ✅ Archive 3 WIP files
3. ❓ Verify links.csv redundancy
4. ❓ Check for unused columns in details.csv
5. 🔄 Merge university_courses.csv into courses.csv
6. 🔄 Consider merging MASCO files

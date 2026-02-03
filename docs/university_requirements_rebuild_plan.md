# University Requirements Rebuild Plan

> **Status**: PLANNING
> **Created**: 2026-02-03
> **Source**: `Random/data/spm/mohe_programs_with_khas.csv` (364 programs)
> **Target**: `data/university_requirements.csv`

---

## 1. Problem Statement

The current `data/univ_requirements.csv` captures only basic requirements:
```csv
UA,UZ0520001,83.19,5,1,1,1,0,0,0,0,1,100,[],ASASI KEJURUTERAAN...
```

This misses the rich `syarat_khas` (special requirements) from the MOHE source:
```
• Gred B dalam mata pelajaran Bahasa Melayu
• Gred B dalam SATU (1): Matematik Tambahan / Matematik
• Gred B dalam SATU (1): Sains / Sains Komputer / Fizik
• Gred C dalam mata pelajaran Bahasa Inggeris
• Gred B dalam mana-mana SATU (1) mata pelajaran yang belum diambil kira
• Taraf Perkahwinan: Bujang
```

**Impact**: Students may see courses they're NOT actually eligible for, or miss courses they ARE eligible for.

---

## 2. Source Data Analysis

### 2.1 Available Columns in `mohe_programs_with_khas.csv`
| Column | Description | Example |
|--------|-------------|---------|
| `program_name` | Course name | ASASI KEJURUTERAAN |
| `code` | Course ID | UZ0520001 |
| `university` | Institution | Universiti Pertahanan Nasional Malaysia |
| `merit` | Merit cutoff | 83.19% |
| `duration` | Program length | 02 Semester |
| `level` | Education level | Asasi/ Matrikulasi/ Foundation |
| `interview` | Interview required | Tidak / Ya |
| `kampus` | Campus location | Kampus Kem Sungai Besi |
| `bumiputera` | Bumiputera restriction | No / Yes / "Berketurunan Melayu..." |
| `syarat_am` | General requirements (text) | Gred C: BM, Gred E: Sejarah... |
| `requirements` | Parsed general req | "Gred C: BAHASA MELAYU; Gred E: SEJARAH" |
| `syarat_khas` | Special requirements (text) | Detailed bullet points |

### 2.2 Requirement Patterns in `syarat_khas`

From analyzing the data, these patterns appear:

**A. Single Subject Requirements**
```
Mendapat sekurang-kurangnya Gred [X] dalam mata pelajaran [SUBJECT]
```
→ Map to: `credit_[subject]` or `pass_[subject]`

**B. OR-Group Requirements**
```
Mendapat sekurang-kurangnya Gred [X] dalam SATU (1) mata pelajaran berikut:
• Subject1 / Subject2 / Subject3
```
→ Map to: composite columns like `credit_sfmt`, `pass_stv`, or new columns

**C. Any-Subject Requirements**
```
Mendapat sekurang-kurangnya Gred [X] dalam mana-mana SATU/DUA (N) mata pelajaran yang belum diambil kira
```
→ Map to: `min_credits` / `min_pass` adjustment

**D. Non-Academic Requirements**
```
Taraf Perkahwinan: Bujang
```
→ Map to: `single` column

**E. Bumiputera Restrictions**
```
Berketurunan Melayu, Anak Negeri Sabah, Anak Negeri Sarawak dan Orang Asli sahaja
```
→ Map to: `bumiputera_only` column (new)

---

## 3. Target Schema

### 3.1 Columns to Keep (from current)
| Column | Keep | Notes |
|--------|------|-------|
| `type` | ✅ | UA for university |
| `course_id` | ✅ | Primary key |
| `merit_cutoff` | ✅ | From `merit` field |
| `min_credits` | ✅ | Derive from syarat_am |
| `pass_history` | ✅ | Usually Gred E |
| `pass_bm` | ✅ | Usually Gred C |
| `credit_bm` | ✅ | From syarat_khas if Gred B |
| `pass_eng` | ✅ | From syarat_khas |
| `credit_english` | ✅ | From syarat_khas if Gred B |
| `credit_math` | ✅ | From syarat_khas |
| `req_malaysian` | ✅ | Always 1 |
| `notes` | ✅ | Course name + university |

### 3.2 New Columns Needed
| Column | Type | Description |
|--------|------|-------------|
| `distinction_bm` | int | A- or better in BM |
| `distinction_eng` | int | A- or better in English |
| `distinction_addmath` | int | A- or better in Add Maths |
| `credit_bm_b` | int | B or better in BM |
| `credit_eng_b` | int | B or better in English |
| `credit_addmath_b` | int | B or better in Add Maths |
| `credit_math_addmath` | int | Credit in Math OR Add Math |
| `credit_science_group` | int | Credit in Science/Physics/Chemistry/etc |
| `credit_any_n` | int | N credits in any uncounted subjects |
| `pass_pi` | int | Pass in Pendidikan Islam (for Muslim students) |
| `credit_pi` | int | Credit in Pendidikan Islam |
| `pass_pm` | int | Pass in Pendidikan Moral (for non-Muslim students) |
| `credit_pm` | int | Credit in Pendidikan Moral |
| `single` | int | Must be unmarried |
| `bumiputera_only` | int | Bumiputera restriction |
| `req_interview` | int | Interview required |
| `syarat_khas_raw` | text | Original text for debugging |

### 3.3 Grade Mapping
| Malay Term | Grade | Min Grade | Column Prefix |
|------------|-------|-----------|---------------|
| Gred A-/A/A+ | A | A- | `distinction_` |
| Gred B-/B/B+ | B | B- | `credit_X_b` |
| Gred C/C+ | C | C | `credit_` (existing) |
| Gred D/E | Pass | E | `pass_` (existing) |

---

## 4. Implementation Steps

### Phase 1: Data Extraction Script
**File**: `scripts/parse_university_requirements.py`

```python
# Pseudocode
1. Load mohe_programs_with_khas.csv
2. For each row:
   a. Parse syarat_am → extract general requirements
   b. Parse syarat_khas → extract special requirements
   c. Map to structured columns
   d. Handle OR-groups with composite columns
3. Output to university_requirements.csv
```

### Phase 2: Parser Implementation

**Key parsing functions needed:**
1. `parse_single_subject(text)` → Extract "Gred X dalam SUBJECT"
2. `parse_or_group(text)` → Extract "Gred X dalam SATU mata pelajaran: A/B/C"
3. `parse_any_subjects(text)` → Extract "Gred X dalam mana-mana N mata pelajaran"
4. `parse_non_academic(text)` → Extract marital status, bumiputera, etc.

**Subject Name Mapping:**
```python
SUBJECT_MAP = {
    # Compulsory subjects
    "Bahasa Melayu": "bm",
    "Bahasa Inggeris": "eng",
    "Matematik": "math",
    "Sejarah": "hist",
    "Pendidikan Islam": "pi",      # Compulsory for Muslim students
    "Pendidikan Moral": "pm",      # Compulsory for non-Muslim students
    # STEM electives
    "Matematik Tambahan": "addmath",
    "Fizik": "phy",
    "Kimia": "chem",
    "Biologi": "bio",
    "Sains": "sci",
    "Sains Komputer": "comp_sci",
    # ... etc
}
```

### Phase 3: Engine Updates
**File**: `src/engine.py`

1. Add new requirement checks for new columns
2. Handle grade B requirements (stricter than C)
3. Add composite check functions for OR-groups

### Phase 4: Testing
1. Golden master test update for UA courses
2. Manual verification of 10-20 sample courses
3. Compare eligibility results before/after

---

## 5. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Parsing errors | Wrong eligibility | Manual review of edge cases |
| Missing subject mappings | Silent failures | Log unmapped subjects |
| Bumiputera filtering | Legal/ethical | Document clearly, user option |
| Data staleness | Wrong info | Version control, update process |

---

## 6. Success Criteria

1. ✅ All 364 programs parsed without errors
2. ✅ `syarat_khas` requirements reflected in columns
3. ✅ Engine correctly evaluates new requirements
4. ✅ Sample verification: 95%+ accuracy
5. ✅ No regression in Poly/KK/TVET eligibility

---

## 7. Estimated Effort

| Phase | Effort |
|-------|--------|
| Phase 1: Parser script | 2-3 hours |
| Phase 2: Subject mapping | 1-2 hours |
| Phase 3: Engine updates | 2-3 hours |
| Phase 4: Testing | 1-2 hours |
| **Total** | **6-10 hours** |

---

## 8. Files to Create/Modify

### New Files
- `scripts/parse_university_requirements.py` - Parser script
- `data/university_requirements.csv` - New requirements file
- `data/subject_name_mapping.json` - Subject name translations

### Modified Files
- `src/engine.py` - Add new requirement checks
- `src/data_manager.py` - Load new file
- `DATA_DICTIONARY.md` - Document new columns
- `tests/test_golden_master.py` - Update for UA courses
- `main.py` - Add Pendidikan Islam / Pendidikan Moral to "Other subjects" dropdown options

---

## 9. Decisions Made

1. **Bumiputera handling**: ✅ Filter out entirely - courses with bumiputera restrictions will be excluded
2. **Pendidikan Islam / Pendidikan Moral**: ✅ Add to "Other subjects" dropdown - these are compulsory SPM subjects (PI for Muslim students, PM for non-Muslim students). Students can select and enter grades. Courses requiring these grades will be supported.
3. **Grade B requirements**: ✅ Add new columns like `credit_bm_b` for Grade B (stricter than Grade C)

---

## 10. Next Steps

1. [ ] Review this plan with stakeholder
2. [ ] Decide on bumiputera policy
3. [ ] Create subject name mapping file
4. [ ] Implement parser script
5. [ ] Run parser and validate output
6. [ ] Update engine with new checks
7. [ ] Run full test suite

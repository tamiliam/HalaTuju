# SPM Subject Expansion Implementation Plan

**Version:** 1.1
**Date:** 2026-02-04
**Status:** CLOSED (Policy Decision)
**Author:** Claude Code

---

> **Resolution (2026-02-04):**
> - All mainstream, technical, and vocational SPM subjects are now covered
> - Islamic school subjects explicitly excluded by policy
> - SKM qualifications out of scope
> - Bumiputra-only courses out of scope
> - No further expansion needed for v1.x

---

## 1. Executive Summary

### Current State
HalaTuju currently supports **24 SPM subjects** across 3 categories. However, the eligibility engine uses composite checks (`pass_stv`, `credit_stv`) that reference **Technical (`tech`)** and **Vocational (`voc`)** subject keys that **are not available in the UI**.

This means students from:
- Vocational schools
- Technical schools
- Mainstream schools offering technical/vocational electives

**Cannot accurately input their results**, leading to incorrect eligibility determinations.

### Target State
Expand subject list to **~45 subjects** covering:
- Current Science & Arts subjects
- Technical/Engineering subjects (Pengajian Kejuruteraan)
- IT/Computing subjects
- Vocational subjects (MPV - Mata Pelajaran Vokasional)
- Other electives (Sports Science, Music, etc.)

### Out of Scope
The following are explicitly **NOT included** (as per user specification):
- Islamic school subjects (Tasawwur Islam, Syariah Islamiah, Al-Quran studies)
- Bumiputera-specific programs
- Arabic language variants (Bahasa Arab Tinggi, Al-Lughah, etc.)

---

## 2. Gap Analysis

### 2.1 Current Subject Lists (engine.py)

```python
# Current - 24 subjects total
SUBJ_LIST_SCIENCE = ["chem", "phy", "bio", "addmath"]  # 4
SUBJ_LIST_ARTS = [
    "b_arab", "b_cina", "b_tamil",
    "ekonomi", "geo",
    "lit_bm", "lit_eng", "lit_cina", "lit_tamil",
    "lukisan", "psv", "business", "poa", "keusahawanan"
]  # 14
SUBJ_LIST_EXTRA = [
    "moral", "islam", "pertanian", "sci", "srt", "addsci"
]  # 6
```

### 2.2 Engine Composite Checks Reference (engine.py:494-500)

```python
# Engine expects 'tech' and 'voc' keys but UI doesn't provide them!
if to_int(req.get('credit_stv')) == 1:
    cond = has_credit(all_sci) or is_credit(g.get('tech')) or is_credit(g.get('voc'))

if to_int(req.get('pass_stv')) == 1:
    cond = has_pass(all_sci) or is_pass(g.get('tech')) or is_pass(g.get('voc'))
```

### 2.3 Missing Subjects (from requirement analysis)

**Technical/Engineering (7 subjects):**
| Internal Key | Display Name (BM) | Display Name (EN) |
|--------------|-------------------|-------------------|
| `eng_civil` | Pengajian Kejuruteraan Awam | Civil Engineering Studies |
| `eng_mech` | Pengajian Kejuruteraan Mekanikal | Mechanical Engineering Studies |
| `eng_elec` | Pengajian Kejuruteraan Elektrik & Elektronik | Electrical & Electronic Engineering |
| `eng_draw` | Lukisan Kejuruteraan | Engineering Drawing |
| `gkt` | Grafik Komunikasi Teknikal | Technical Communication Graphics |
| `kelestarian` | Asas Kelestarian | Sustainability Basics |
| `reka_cipta` | Reka Cipta | Design & Innovation |

**IT/Computing (3 subjects):**
| Internal Key | Display Name (BM) | Display Name (EN) |
|--------------|-------------------|-------------------|
| `comp_sci` | Sains Komputer | Computer Science |
| `multimedia` | Produksi Multimedia | Multimedia Production |
| `digital_gfx` | Reka Bentuk Grafik Digital | Digital Graphics Design |

**Vocational - MPV (10 subjects):**
| Internal Key | Display Name (BM) | Display Name (EN) |
|--------------|-------------------|-------------------|
| `voc_construct` | Pembinaan Domestik | Domestic Construction |
| `voc_plumb` | Kerja Paip Domestik | Domestic Plumbing |
| `voc_wiring` | Pendawaian Domestik | Domestic Wiring |
| `voc_weld` | Kimpalan Arka | Arc Welding |
| `voc_auto` | Menservis Automobil | Automobile Servicing |
| `voc_elec_serv` | Menservis Peralatan Elektrik Domestik | Domestic Electrical Servicing |
| `voc_food` | Tanaman Makanan | Food Crops |
| `voc_landscape` | Landskap dan Nurseri | Landscape & Nursery |
| `voc_catering` | Katering dan Penyajian | Catering & Serving |
| `voc_tailoring` | Jahitan dan Rekaan Pakaian | Tailoring & Fashion Design |

**Other Electives (3 subjects):**
| Internal Key | Display Name (BM) | Display Name (EN) |
|--------------|-------------------|-------------------|
| `sports_sci` | Sains Sukan | Sports Science |
| `music` | Pendidikan Muzik | Music Education |
| `sinografi` | Sinografi | Scenography |

---

## 3. Implementation Architecture

### 3.1 Subject Category Restructure

**NEW Structure (Proposed):**

```python
# ============================================
# SUBJECT LISTS - Single Source of Truth
# ============================================

# Compulsory (always shown, not in dropdown)
SUBJ_COMPULSORY = ["bm", "eng", "math", "hist"]

# Science Stream Electives
SUBJ_LIST_SCIENCE = [
    "chem", "phy", "bio", "addmath"
]

# Arts Stream Electives
SUBJ_LIST_ARTS = [
    "b_cina", "b_tamil",  # Languages (b_arab removed - Islamic schools)
    "ekonomi", "geo",
    "lit_bm", "lit_eng", "lit_cina", "lit_tamil",
    "lukisan", "psv", "business", "poa", "keusahawanan"
]

# Technical/Engineering (NEW)
SUBJ_LIST_TECHNICAL = [
    "eng_civil", "eng_mech", "eng_elec",
    "eng_draw", "gkt", "kelestarian", "reka_cipta"
]

# IT/Computing (NEW)
SUBJ_LIST_IT = [
    "comp_sci", "multimedia", "digital_gfx"
]

# Vocational - MPV (NEW)
SUBJ_LIST_VOCATIONAL = [
    "voc_construct", "voc_plumb", "voc_wiring", "voc_weld",
    "voc_auto", "voc_elec_serv", "voc_food", "voc_landscape",
    "voc_catering", "voc_tailoring"
]

# General Electives (mixed pool)
SUBJ_LIST_EXTRA = [
    "moral", "pertanian", "sci", "srt", "addsci",
    "sports_sci", "music"
]

# Composite Groups for Engine Logic
SUBJ_GROUP_SCIENCE = ["chem", "phy", "bio", "sci", "addsci"]
SUBJ_GROUP_TECHNICAL = SUBJ_LIST_TECHNICAL + SUBJ_LIST_IT
SUBJ_GROUP_VOCATIONAL = SUBJ_LIST_VOCATIONAL
SUBJ_GROUP_STV = SUBJ_GROUP_SCIENCE + SUBJ_GROUP_TECHNICAL + SUBJ_GROUP_VOCATIONAL
```

### 3.2 Engine Update Strategy

**Current Problem:** Engine checks `g.get('tech')` and `g.get('voc')` - single keys for all technical/vocational.

**Solution:** Check against subject groups instead of single keys.

```python
# BEFORE (broken)
if to_int(req.get('credit_stv')) == 1:
    cond = has_credit(all_sci) or is_credit(g.get('tech')) or is_credit(g.get('voc'))

# AFTER (correct)
if to_int(req.get('credit_stv')) == 1:
    has_tech = any(is_credit(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
    has_voc = any(is_credit(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
    cond = has_credit(all_sci) or has_tech or has_voc
```

---

## 4. Detailed Implementation Steps

### Phase 1: Data Layer Updates (engine.py)

**File:** `src/engine.py`

#### Step 1.1: Add New Subject Lists
Location: After line 155 (after existing `SUBJ_LIST_EXTRA`)

```python
# Technical/Engineering Subjects
SUBJ_LIST_TECHNICAL = [
    "eng_civil", "eng_mech", "eng_elec",
    "eng_draw", "gkt", "kelestarian", "reka_cipta"
]

# IT/Computing Subjects
SUBJ_LIST_IT = [
    "comp_sci", "multimedia", "digital_gfx"
]

# Vocational Subjects (MPV)
SUBJ_LIST_VOCATIONAL = [
    "voc_construct", "voc_plumb", "voc_wiring", "voc_weld",
    "voc_auto", "voc_elec_serv", "voc_food", "voc_landscape",
    "voc_catering", "voc_tailoring"
]

# Other Electives
SUBJ_LIST_OTHER = ["sports_sci", "music"]

# Composite Groups for eligibility logic
SUBJ_GROUP_SCIENCE = ["chem", "phy", "bio", "sci", "addsci"]
SUBJ_GROUP_TECHNICAL = SUBJ_LIST_TECHNICAL + SUBJ_LIST_IT
SUBJ_GROUP_VOCATIONAL = SUBJ_LIST_VOCATIONAL
```

#### Step 1.2: Update EXTRA list
```python
# Remove 'islam' (Islamic schools), add new extras
SUBJ_LIST_EXTRA = [
    "moral", "pertanian", "sci", "srt", "addsci",
    "sports_sci", "music"
]
```

#### Step 1.3: Export new lists
Update the module exports to include new lists.

#### Step 1.4: Fix STV Composite Checks
Location: Lines 494-500

**Replace:**
```python
if to_int(req.get('credit_stv')) == 1:
    cond = has_credit(all_sci) or is_credit(g.get('tech')) or is_credit(g.get('voc'))
    if not check("chk_credit_stv", cond, "fail_credit_stv"): passed_academics = False

if to_int(req.get('pass_stv')) == 1:
    cond = has_pass(all_sci) or is_pass(g.get('tech')) or is_pass(g.get('voc'))
    if not check("chk_pass_stv", cond, "fail_pass_stv"): passed_academics = False
```

**With:**
```python
if to_int(req.get('credit_stv')) == 1:
    has_tech_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
    has_voc_credit = any(is_credit(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
    cond = has_credit(all_sci) or has_tech_credit or has_voc_credit
    if not check("chk_credit_stv", cond, "fail_credit_stv"): passed_academics = False

if to_int(req.get('pass_stv')) == 1:
    has_tech_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_TECHNICAL)
    has_voc_pass = any(is_pass(g.get(s)) for s in SUBJ_GROUP_VOCATIONAL)
    cond = has_pass(all_sci) or has_tech_pass or has_voc_pass
    if not check("chk_pass_stv", cond, "fail_pass_stv"): passed_academics = False
```

#### Step 1.5: Update TVET Composite Checks
Location: Search for `pass_science_tech`, `credit_math_sci_tech`

Apply similar fixes using the new subject groups.

---

### Phase 2: UI Layer Updates (main.py)

**File:** `main.py`

#### Step 2.1: Update KEY_DISPLAY Mapping
Location: Inside `render_grade_inputs()` function (~line 100)

**Add new entries:**
```python
KEY_DISPLAY = {
    # Existing Science
    "chem": "Chemistry", "phy": "Physics", "bio": "Biology", "addmath": "Add Maths",

    # Existing Arts
    "b_cina": "Bahasa Cina", "b_tamil": "Bahasa Tamil",
    "ekonomi": "Economy", "geo": "Geography",
    "lit_bm": "Literature (BM)", "lit_eng": "Literature (English)",
    "lit_cina": "Literature (Chinese)", "lit_tamil": "Literature (Tamil)",
    "lukisan": "Lukisan", "psv": "Seni Visual",
    "business": "Perniagaan", "poa": "Prinsip Perakaunan",
    "keusahawanan": "Pengajian Keusahawanan",

    # Technical/Engineering (NEW)
    "eng_civil": "Peng. Kejuruteraan Awam",
    "eng_mech": "Peng. Kejuruteraan Mekanikal",
    "eng_elec": "Peng. Kejuruteraan Elektrik",
    "eng_draw": "Lukisan Kejuruteraan",
    "gkt": "Grafik Komunikasi Teknikal",
    "kelestarian": "Asas Kelestarian",
    "reka_cipta": "Reka Cipta",

    # IT/Computing (NEW)
    "comp_sci": "Sains Komputer",
    "multimedia": "Produksi Multimedia",
    "digital_gfx": "Reka Bentuk Grafik Digital",

    # Vocational (NEW)
    "voc_construct": "Pembinaan Domestik",
    "voc_plumb": "Kerja Paip Domestik",
    "voc_wiring": "Pendawaian Domestik",
    "voc_weld": "Kimpalan Arka",
    "voc_auto": "Menservis Automobil",
    "voc_elec_serv": "Servis Peralatan Elektrik",
    "voc_food": "Tanaman Makanan",
    "voc_landscape": "Landskap dan Nurseri",
    "voc_catering": "Katering dan Penyajian",
    "voc_tailoring": "Jahitan dan Rekaan Pakaian",

    # Other (NEW + Updated)
    "moral": "Pendidikan Moral",
    "pertanian": "Pertanian", "sci": "Sains",
    "srt": "Sains Rumah Tangga", "addsci": "Sains Tambahan",
    "sports_sci": "Sains Sukan",
    "music": "Pendidikan Muzik"
}
```

#### Step 2.2: Update Stream Mode Logic
Location: Stream selection radio (~line 122)

**Current:**
```python
stream_mode = st.radio("Select Stream", ["STEM A (Science)", "ARTS (Sastra)"], horizontal=True)
```

**Change to:**
```python
stream_mode = st.radio(
    "Select Stream",
    ["Science", "Arts", "Technical/Vocational"],
    horizontal=True,
    key=f"stream_mode{key_suffix}"
)
```

#### Step 2.3: Update Subject Pool Logic
Location: After stream selection

```python
if "Science" in stream_mode:
    pool_2_keys = SUBJ_LIST_SCIENCE
elif "Arts" in stream_mode:
    pool_2_keys = SUBJ_LIST_ARTS
else:  # Technical/Vocational
    pool_2_keys = SUBJ_LIST_TECHNICAL + SUBJ_LIST_IT + SUBJ_LIST_VOCATIONAL
```

---

### Phase 3: Translation Updates (translations.py)

**File:** `src/translations.py`

Add translations for all new subjects in EN, BM, and TA sections.

```python
# Example structure - add to each language dict
"subj_eng_civil": {
    "en": "Civil Engineering Studies",
    "bm": "Pengajian Kejuruteraan Awam",
    "ta": "சிவில் பொறியியல் படிப்பு"
},
"subj_comp_sci": {
    "en": "Computer Science",
    "bm": "Sains Komputer",
    "ta": "கணினி அறிவியல்"
},
# ... etc for all 23 new subjects
```

---

### Phase 4: Backward Compatibility

#### 4.1 Handle Legacy 'tech' and 'voc' Keys
Add fallback mapping in engine for existing user data:

```python
# Legacy key mapping (for users who entered grades before expansion)
LEGACY_KEY_MAP = {
    "tech": "eng_civil",  # Map generic 'tech' to most common technical subject
    "voc": "voc_weld"     # Map generic 'voc' to most common vocational subject
}

# In grade processing:
def normalize_grades(grades_dict):
    """Convert legacy keys to new keys."""
    normalized = {}
    for k, v in grades_dict.items():
        new_key = LEGACY_KEY_MAP.get(k, k)
        normalized[new_key] = v
    return normalized
```

#### 4.2 Database Migration (Supabase)
No schema changes needed - grades are stored as JSON. New keys will simply be added to existing structures.

---

## 5. Testing Plan

### 5.1 Unit Tests

**File:** `tests/test_subject_expansion.py`

```python
class TestSubjectExpansion(unittest.TestCase):

    def test_technical_subject_satisfies_stv(self):
        """Technical subject should satisfy pass_stv requirement."""
        student = StudentProfile(
            grades={'bm': 'B', 'eng': 'C', 'math': 'C', 'hist': 'E',
                    'eng_civil': 'B'}  # Technical subject with credit
        )
        # Course requiring credit_stv=1
        result = engine.check_eligibility(student, course_with_credit_stv)
        self.assertTrue(result.eligible)

    def test_vocational_subject_satisfies_stv(self):
        """Vocational subject should satisfy pass_stv requirement."""
        student = StudentProfile(
            grades={'bm': 'B', 'eng': 'C', 'math': 'C', 'hist': 'E',
                    'voc_weld': 'C'}  # Vocational subject with credit
        )
        result = engine.check_eligibility(student, course_with_credit_stv)
        self.assertTrue(result.eligible)

    def test_it_subject_counted_as_technical(self):
        """IT subjects should count toward technical group."""
        student = StudentProfile(
            grades={'bm': 'B', 'eng': 'C', 'math': 'C', 'hist': 'E',
                    'comp_sci': 'A'}
        )
        result = engine.check_eligibility(student, course_with_credit_stv)
        self.assertTrue(result.eligible)

    def test_legacy_tech_key_still_works(self):
        """Legacy 'tech' key should still be recognized."""
        student = StudentProfile(
            grades={'bm': 'B', 'eng': 'C', 'math': 'C', 'hist': 'E',
                    'tech': 'B'}  # Old-style key
        )
        result = engine.check_eligibility(student, course_with_credit_stv)
        self.assertTrue(result.eligible)
```

### 5.2 Golden Master Update
After implementation, update golden master snapshots:
```bash
python -m unittest tests/test_golden_master.py
```

### 5.3 Manual Testing Checklist
- [ ] Science stream student can select standard science subjects
- [ ] Arts stream student can select arts subjects
- [ ] Technical student can select engineering subjects
- [ ] Vocational student can select MPV subjects
- [ ] IT student can select computing subjects
- [ ] Mixed stream student can select from all pools in "Additional Subjects"
- [ ] Eligibility correctly identifies technical/vocational credits for STV courses
- [ ] Existing user profiles with old keys still work
- [ ] All translations display correctly (EN, BM, TA)

---

## 6. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Existing user grades break | LOW | HIGH | Legacy key mapping, backward-compatible processing |
| Golden master tests fail | MEDIUM | MEDIUM | Review failures case-by-case, update snapshots after verification |
| Incorrect subject categorization | LOW | MEDIUM | Cross-reference with official SPM subject list from MOE |
| Translation errors | MEDIUM | LOW | Native speaker review for Tamil translations |
| Performance degradation (more loops) | LOW | LOW | Subject groups are small lists (<20 items) |

---

## 7. Official SPM Subject Reference

Based on official SPM curriculum (Lembaga Peperiksaan Malaysia):

### Technical Subjects (Mata Pelajaran Teknikal)
1. Pengajian Kejuruteraan Awam
2. Pengajian Kejuruteraan Mekanikal
3. Pengajian Kejuruteraan Elektrik dan Elektronik
4. Lukisan Kejuruteraan
5. Grafik Komunikasi Teknikal
6. Asas Kelestarian
7. Reka Cipta

### IT Subjects
1. Sains Komputer
2. Reka Bentuk Grafik Digital
3. Produksi Multimedia

### Vocational Subjects (Mata Pelajaran Vokasional - MPV)
Grouped by cluster:

**Pembinaan (Construction):**
- Pembinaan Domestik
- Kerja Paip Domestik
- Pendawaian Domestik

**Pembuatan (Manufacturing):**
- Kimpalan Arka
- Fabrikasi Logam

**Automotif:**
- Menservis Automobil
- Menservis Motosikal

**Elektrik:**
- Menservis Peralatan Elektrik Domestik

**Pertanian:**
- Tanaman Makanan
- Landskap dan Nurseri
- Akuakultur

**Hospitaliti:**
- Katering dan Penyajian

**Fesyen:**
- Jahitan dan Rekaan Pakaian

---

## 8. Implementation Checklist

### Pre-Implementation
- [ ] Review this plan with stakeholder
- [ ] Confirm subject list completeness
- [ ] Create backup of current engine.py
- [ ] Create backup of current main.py

### Phase 1: Engine (engine.py)
- [ ] Add new subject list constants
- [ ] Add composite group constants
- [ ] Update STV check logic
- [ ] Update TVET composite checks
- [ ] Add legacy key mapping
- [ ] Export new constants

### Phase 2: UI (main.py)
- [ ] Update KEY_DISPLAY mapping
- [ ] Add stream mode "Technical/Vocational"
- [ ] Update subject pool selection logic
- [ ] Test dropdown rendering

### Phase 3: Translations (translations.py)
- [ ] Add English translations (23 subjects)
- [ ] Add Bahasa Malaysia translations (23 subjects)
- [ ] Add Tamil translations (23 subjects)

### Phase 4: Testing
- [ ] Write unit tests for new subjects
- [ ] Run golden master tests
- [ ] Manual UI testing
- [ ] Verify backward compatibility

### Post-Implementation
- [ ] Update DATA_DICTIONARY.md
- [ ] Update CHANGELOG.md
- [ ] Commit with descriptive message
- [ ] Monitor for user-reported issues

---

## 9. Estimated Effort

| Phase | Tasks | Effort |
|-------|-------|--------|
| Phase 1: Engine | Subject lists, composite checks, legacy mapping | 2-3 hours |
| Phase 2: UI | KEY_DISPLAY, stream selection, pool logic | 1-2 hours |
| Phase 3: Translations | 23 subjects × 3 languages = 69 entries | 1-2 hours |
| Phase 4: Testing | Unit tests, golden master, manual | 2-3 hours |
| **Total** | | **6-10 hours** |

---

## 10. Approval

- [ ] **Technical Review:** Confirm architecture approach
- [ ] **Data Review:** Confirm subject list completeness
- [ ] **UX Review:** Confirm stream selection approach
- [ ] **Approved to Implement**

---

## Appendix A: Full Subject Code Reference

| Code | BM Name | EN Name | Category |
|------|---------|---------|----------|
| `chem` | Kimia | Chemistry | Science |
| `phy` | Fizik | Physics | Science |
| `bio` | Biologi | Biology | Science |
| `addmath` | Matematik Tambahan | Additional Mathematics | Science |
| `b_cina` | Bahasa Cina | Chinese Language | Arts |
| `b_tamil` | Bahasa Tamil | Tamil Language | Arts |
| `ekonomi` | Ekonomi | Economics | Arts |
| `geo` | Geografi | Geography | Arts |
| `lit_bm` | Kesusasteraan Melayu | Malay Literature | Arts |
| `lit_eng` | Kesusasteraan Inggeris | English Literature | Arts |
| `lit_cina` | Kesusasteraan Cina | Chinese Literature | Arts |
| `lit_tamil` | Kesusasteraan Tamil | Tamil Literature | Arts |
| `lukisan` | Pendidikan Seni Visual | Visual Arts Education | Arts |
| `psv` | Seni Visual | Visual Arts | Arts |
| `business` | Perniagaan | Business Studies | Arts |
| `poa` | Prinsip Perakaunan | Principles of Accounting | Arts |
| `keusahawanan` | Pengajian Keusahawanan | Entrepreneurship Studies | Arts |
| `eng_civil` | Peng. Kejuruteraan Awam | Civil Engineering Studies | Technical |
| `eng_mech` | Peng. Kejuruteraan Mekanikal | Mechanical Engineering Studies | Technical |
| `eng_elec` | Peng. Kejuruteraan Elektrik | Electrical Engineering Studies | Technical |
| `eng_draw` | Lukisan Kejuruteraan | Engineering Drawing | Technical |
| `gkt` | Grafik Komunikasi Teknikal | Technical Communication Graphics | Technical |
| `kelestarian` | Asas Kelestarian | Sustainability Basics | Technical |
| `reka_cipta` | Reka Cipta | Design & Innovation | Technical |
| `comp_sci` | Sains Komputer | Computer Science | IT |
| `multimedia` | Produksi Multimedia | Multimedia Production | IT |
| `digital_gfx` | Reka Bentuk Grafik Digital | Digital Graphics Design | IT |
| `voc_construct` | Pembinaan Domestik | Domestic Construction | Vocational |
| `voc_plumb` | Kerja Paip Domestik | Domestic Plumbing | Vocational |
| `voc_wiring` | Pendawaian Domestik | Domestic Wiring | Vocational |
| `voc_weld` | Kimpalan Arka | Arc Welding | Vocational |
| `voc_auto` | Menservis Automobil | Automobile Servicing | Vocational |
| `voc_elec_serv` | Menservis Peralatan Elektrik | Electrical Equipment Servicing | Vocational |
| `voc_food` | Tanaman Makanan | Food Crops | Vocational |
| `voc_landscape` | Landskap dan Nurseri | Landscape & Nursery | Vocational |
| `voc_catering` | Katering dan Penyajian | Catering & Serving | Vocational |
| `voc_tailoring` | Jahitan dan Rekaan Pakaian | Tailoring & Fashion Design | Vocational |
| `moral` | Pendidikan Moral | Moral Education | Extra |
| `pertanian` | Pertanian | Agriculture | Extra |
| `sci` | Sains | General Science | Extra |
| `srt` | Sains Rumah Tangga | Home Science | Extra |
| `addsci` | Sains Tambahan | Additional Science | Extra |
| `sports_sci` | Sains Sukan | Sports Science | Extra |
| `music` | Pendidikan Muzik | Music Education | Extra |

**Total: 45 subjects**

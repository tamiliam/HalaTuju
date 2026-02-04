# STPM Eligibility System Implementation Plan

> **Status:** DEFERRED (v2.x)
> **Last Updated:** 2026-02-04
> **Rationale:** Requires UI/UX rethink for STPM grade entry. Data exists but integration is complex.

---

**Goal:** Transform scraped STPM university program data into a machine-readable eligibility checking system, similar to HalaTuju's SPM engine.

**Current State:**
- 1,113 unique programs (677 Arts + 436 Science-only)
- Raw HTML requirements text in natural language
- No structured eligibility fields

**Target State:**
- Structured CSV with binary/numeric eligibility fields
- Programmatic eligibility checking: `is_eligible(student_results, program_requirements) -> bool`
- Integration-ready for HalaTuju or standalone use

---

## Phase 1: Requirements Pattern Analysis (1-2 days)

### Objective
Understand and document all requirement patterns in the data.

### Tasks

#### 1.1 Extract and catalog all requirement patterns
- Strip HTML tags from requirements text
- Identify unique phrase patterns (e.g., "PNGK 2.50", "Gred C dalam")
- Count frequency of each pattern

#### 1.2 Document STPM-specific requirement types
| Requirement Type | Example Pattern | Frequency |
|-----------------|-----------------|-----------|
| CGPA (PNGK) | "PNGK 2.50", "PNGK 3.00" | TBD |
| STPM Subject Grade | "Gred C dalam Matematik" | TBD |
| STPM Subject Count | "DUA (2) mata pelajaran" | TBD |
| SPM Prerequisites | "Gred C dalam BM di SPM" | TBD |
| MUET Band | "BAND 2.0", "BAND 3.0" | TBD |
| Interview | "Lulus temu duga" | TBD |
| Medical | "Tidak buta warna" | TBD |

#### 1.3 Map STPM subjects to standardized codes
- Create subject mapping: `{"Mathematics T": "MATH_T", "Pengajian Am": "PA", ...}`
- Handle variations (English/Malay names, abbreviations)

### Deliverables
- `docs/stpm_requirement_patterns.md` - Pattern catalog
- `data/stpm_subject_codes.json` - Subject standardization mapping

---

## Phase 2: Schema Design (1 day)

### Objective
Design the target CSV schema for machine-readable requirements.

### Tasks

#### 2.1 Define STPM-specific columns

**Core STPM Requirements:**
| Column | Type | Description |
|--------|------|-------------|
| `program_id` | String | Unique identifier (e.g., UA6145015) |
| `min_cgpa` | Float | Minimum STPM CGPA (PNGK), e.g., 2.00, 2.50, 3.00 |
| `min_stpm_subjects` | Integer | Minimum STPM subjects with qualifying grade |
| `min_stpm_grade` | String | Minimum grade for counted subjects (C-, C, C+, B-, etc.) |

**SPM Prerequisites (existing HalaTuju format):**
| Column | Type | Description |
|--------|------|-------------|
| `spm_credit_bm` | Binary | Credit in BM required |
| `spm_pass_sejarah` | Binary | Pass in Sejarah required |
| `spm_credit_math` | Binary | Credit in Math required |
| `spm_credit_english` | Binary | Credit in English required |
| `spm_credit_science` | Binary | Credit in any Science subject |

**STPM Subject Requirements:**
| Column | Type | Description |
|--------|------|-------------|
| `stpm_req_pa` | Binary | Pengajian Am required |
| `stpm_req_math` | Binary | Math T/M required |
| `stpm_req_physics` | Binary | Physics required |
| `stpm_req_chemistry` | Binary | Chemistry required |
| `stpm_req_biology` | Binary | Biology required |
| `stpm_subject_group` | String | JSON list of acceptable subjects |

**MUET & Other:**
| Column | Type | Description |
|--------|------|-------------|
| `min_muet_band` | Float | Minimum MUET band (1.0 to 5.0) |
| `req_interview` | Binary | Interview required |
| `no_colorblind` | Binary | Cannot be colorblind |
| `stream` | String | "arts", "science", "both" |

#### 2.2 Create sample data for validation
- Manually code 10-20 programs to validate schema
- Test edge cases (multiple subject options, composite requirements)

### Deliverables
- `data/stpm_requirements_schema.md` - Column definitions
- `data/stpm_requirements_sample.csv` - 20 manually coded programs

---

## Phase 3: Parser Development (3-5 days)

### Objective
Build automated parser to extract structured requirements from HTML text.

### Tasks

#### 3.1 HTML text preprocessor
```python
def preprocess_requirements(html_text):
    # Strip HTML tags
    # Normalize whitespace
    # Split into requirement items
    return structured_items
```

#### 3.2 Pattern extractors (one per requirement type)
```python
def extract_cgpa(text) -> float | None
def extract_muet_band(text) -> float | None
def extract_stpm_subjects(text) -> list[dict]
def extract_spm_requirements(text) -> dict
def extract_interview_required(text) -> bool
def extract_medical_requirements(text) -> dict
```

#### 3.3 Main parser pipeline
```python
def parse_program_requirements(row) -> dict:
    requirements = {}
    requirements['min_cgpa'] = extract_cgpa(row['syarat_am'])
    requirements['min_muet_band'] = extract_muet_band(row['requirements'])
    # ... etc
    return requirements
```

#### 3.4 Confidence scoring
- Track which fields were successfully parsed vs. defaulted
- Flag programs needing manual review

### Deliverables
- `scripts/parse_stpm_requirements.py` - Main parser
- `data/stpm_requirements_parsed.csv` - Parsed output
- `data/stpm_parse_report.json` - Parse success/failure stats

---

## Phase 4: Validation & Manual Review (2-3 days)

### Objective
Validate parser accuracy and manually correct errors.

### Tasks

#### 4.1 Automated validation checks
- Sanity checks (CGPA between 2.0-4.0, MUET band 1-5)
- Cross-reference with original text
- Flag outliers and anomalies

#### 4.2 Manual review queue
- Programs with low parse confidence
- Programs with unusual patterns
- Edge cases flagged by parser

#### 4.3 Create golden test set
- 50-100 manually verified programs
- Use for regression testing parser changes

### Deliverables
- `data/stpm_requirements_validated.csv` - Final validated data
- `tests/test_stpm_parser.py` - Parser unit tests
- `data/stpm_manual_review_log.csv` - Review decisions

---

## Phase 5: Eligibility Engine (2-3 days)

### Objective
Build the eligibility checking engine.

### Tasks

#### 5.1 Student results data model
```python
@dataclass
class StudentResults:
    # SPM results
    spm_grades: dict[str, str]  # {"BM": "A", "MATH": "B+", ...}

    # STPM results
    stpm_cgpa: float
    stpm_grades: dict[str, str]  # {"PA": "B", "MATH_T": "A-", ...}

    # MUET
    muet_band: float

    # Demographics
    is_malaysian: bool
    is_colorblind: bool
```

#### 5.2 Eligibility checker
```python
def check_eligibility(student: StudentResults, program: dict) -> tuple[bool, list[str]]:
    """
    Returns:
        (is_eligible: bool, failed_requirements: list[str])
    """
    failures = []

    # Check CGPA
    if student.stpm_cgpa < program['min_cgpa']:
        failures.append(f"CGPA {student.stpm_cgpa} < required {program['min_cgpa']}")

    # Check MUET
    if student.muet_band < program['min_muet_band']:
        failures.append(f"MUET {student.muet_band} < required {program['min_muet_band']}")

    # Check SPM prerequisites
    # Check STPM subject requirements
    # ...

    return (len(failures) == 0, failures)
```

#### 5.3 Batch eligibility calculation
- Given student results, find all eligible programs
- Rank by fit (similar to HalaTuju ranking engine)

### Deliverables
- `src/stpm_engine.py` - Eligibility checking engine
- `tests/test_stpm_engine.py` - Engine unit tests

---

## Phase 6: Integration & Testing (2-3 days)

### Objective
Integrate with HalaTuju or create standalone tool.

### Tasks

#### 6.1 Integration option A: Extend HalaTuju
- Add STPM track alongside existing SPM track
- Reuse existing UI components (dashboard, quiz, reports)
- Share common infrastructure (auth, translations)

#### 6.2 Integration option B: Standalone tool
- Simple CLI or web interface
- Student enters SPM + STPM + MUET results
- Shows eligible programs with details

#### 6.3 End-to-end testing
- Test with realistic student profiles
- Verify results against manual checking
- Performance testing (1000+ programs)

### Deliverables
- Working integration (HalaTuju or standalone)
- User documentation
- Test coverage report

---

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| 1. Pattern Analysis | 1-2 days | None |
| 2. Schema Design | 1 day | Phase 1 |
| 3. Parser Development | 3-5 days | Phase 2 |
| 4. Validation | 2-3 days | Phase 3 |
| 5. Engine | 2-3 days | Phase 4 |
| 6. Integration | 2-3 days | Phase 5 |
| **Total** | **11-17 days** | |

---

## Risk Mitigation

### Risk 1: Highly variable requirement patterns
**Mitigation:** Start with most common patterns (80/20 rule), flag unusual cases for manual coding.

### Risk 2: Parser accuracy issues
**Mitigation:** Confidence scoring, manual review queue, golden test set for regression.

### Risk 3: Incomplete subject mapping
**Mitigation:** Build comprehensive subject code dictionary in Phase 1, iterate as new subjects discovered.

### Risk 4: Bilingual text complexity
**Mitigation:** Normalize to single language (Malay preferred since more consistent), maintain translation mapping.

---

## Success Criteria

1. **Parser Coverage:** >90% of programs parsed without manual intervention
2. **Accuracy:** >95% accuracy on eligibility decisions (validated against manual checks)
3. **Performance:** <100ms per eligibility check
4. **Completeness:** All 1,113 programs have structured requirements

---

## Next Steps

1. [ ] Approve this implementation plan
2. [ ] Begin Phase 1: Pattern Analysis
3. [ ] Create tracking issues/tasks for each phase

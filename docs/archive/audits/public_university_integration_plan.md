# University Program Requirements (SPM Stream)

**Version:** 1.0
**Last Updated:** 2026-02-01
**Status:** Draft
**Source:** `data/university_requirements.csv`

This document describes the eligibility requirements for SPM-entry university programs (Foundation/Diploma), excluding Polytechnic, Kolej Komuniti, and Bumiputera-only programs.

---

## Section 1: Data Source & Scope

### Source
- **MOHE e-Panduan Portal:** https://online.mohe.gov.my/epanduan/
- **Category:** SPM (Sijil Pelajaran Malaysia) Entry
- **Programs:** 103 university programs (non-Bumi, non-Poly/Kolej)

### Excluded Programs
| Category | Reason |
|----------|--------|
| Politeknik | Captured in `requirements.csv` (POLY-*) |
| Kolej Komuniti | Captured in `requirements.csv` (KKOM-*) |
| Bumiputera-only | Restricted eligibility |

---

## Section 2: Column Definitions

### 2.1 Identification
| Column | Type | Description |
|--------|------|-------------|
| `course_id` | String | MOHE program code (e.g., `UZ0520001`) |

### 2.2 General Requirements
| Column | Type | Description |
|--------|------|-------------|
| `min_credits` | Integer | Minimum SPM credits required (3-7) |
| `req_malaysian` | Boolean (0/1) | Malaysian citizenship required |

### 2.3 Subject Grade Requirements

Grade values use SPM grading scale: `A+`, `A`, `A-`, `B+`, `B`, `C+`, `C`, `D`, `E`
- Empty string = Not required
- Any grade = Minimum grade for that subject

| Column | Subject | Example |
|--------|---------|---------|
| `bm_req` | Bahasa Melayu | `B` = Min Gred B |
| `eng_req` | Bahasa Inggeris | `C+` = Min Gred C+ |
| `history_req` | Sejarah | `C` = Min Gred C |
| `math_req` | Matematik | `C` = Min Gred C |
| `add_math_req` | Matematik Tambahan | `B` = Min Gred B |
| `physics_req` | Fizik | `B` = Min Gred B |
| `chemistry_req` | Kimia | `B` = Min Gred B |
| `biology_req` | Biologi | `B` = Min Gred B |
| `science_req` | Sains | `C` = Min Gred C |

### 2.4 Science Choice Requirements

For programs requiring "Gred X in N science subjects":

| Column | Type | Description |
|--------|------|-------------|
| `science_choice_req` | Grade | Min grade for science subjects |
| `science_choice_count` | Integer | How many science subjects needed |

**Example:** `science_choice_req=B, science_choice_count=1` means:
- Need Gred B in at least ONE of: Fizik/Kimia/Biologi/Sains

### 2.5 Additional Subject Requirements

For programs requiring "Gred X in N additional subjects":

| Column | Type | Description |
|--------|------|-------------|
| `other_req_count` | Integer | Number of additional subjects needed |
| `other_req_min_grade` | Grade | Min grade for additional subjects |

**Example:** `other_req_count=2, other_req_min_grade=C` means:
- Need Gred C in any 2 other subjects not yet counted

### 2.6 Special Requirements
| Column | Type | Description |
|--------|------|-------------|
| `req_male` | Boolean (0/1) | Male only |
| `req_female` | Boolean (0/1) | Female only |
| `no_colorblind` | Boolean (0/1) | Cannot be colorblind |
| `no_disability` | Boolean (0/1) | Physical fitness required |

---

## Section 3: Grade Comparison Logic

### SPM Grade Hierarchy (Best to Worst)
```
A+ > A > A- > B+ > B > C+ > C > D > E > (Fail)
```

### Eligibility Check
```python
def meets_requirement(student_grade, required_grade):
    """Returns True if student_grade >= required_grade"""
    hierarchy = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E']
    if not required_grade:  # Empty = no requirement
        return True
    student_rank = hierarchy.index(student_grade)
    required_rank = hierarchy.index(required_grade)
    return student_rank <= required_rank  # Lower index = better grade
```

---

## Section 4: Sample Data

### Example 1: UZ0520001 (ASASI SAINS KESIHATAN BERSEKUTU)
```
bm_req: B
eng_req: C
science_choice_req: B
science_choice_count: 1
other_req_count: 1
other_req_min_grade: B
```
**Interpretation:** Need Gred B in BM, Gred C in English, Gred B in 1 science, Gred B in 1 other subject.

### Example 2: UP0000001 (ASASI PERUBATAN)
```
eng_req: C+
add_math_req: C
science_choice_req: B
science_choice_count: 4
```
**Interpretation:** Need Gred C+ in English, Gred C in Add Math, Gred B in 4 science subjects (high requirement).

---

## Section 5: Grade Distribution (Statistics)

### Bahasa Melayu Requirements
| Grade | Programs |
|-------|----------|
| C | 17 |
| B | 3 |
| A- | 1 |
| Not required | 82 |

### English Requirements
| Grade | Programs |
|-------|----------|
| E (Pass) | 38 |
| D | 14 |
| C | 11 |
| B/B+ | 3 |
| A- | 1 |
| Not required | 36 |

### Mathematics Requirements
| Grade | Programs |
|-------|----------|
| C | 41 |
| E | 7 |
| D | 2 |
| Not required | 53 |

---

## Section 6: Integration Notes

### To use with HalaTuju Engine

1. **Load CSV:** Read `university_requirements.csv` into DataFrame
2. **Filter by eligibility:** Check student grades against each `*_req` column
3. **Handle science choice:** Check if student has `science_choice_count` subjects with grade >= `science_choice_req`
4. **Handle other subjects:** Check if student has `other_req_count` remaining subjects with grade >= `other_req_min_grade`

### Future Enhancements

- [ ] Add `interview_required` column
- [ ] Add `merit_score_min` column (from MOHE data)
- [ ] Map to course details (name, university, duration)
- [ ] Extend to STPM entry programs

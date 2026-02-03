# 📖 Data Dictionary

This document explains the columns used in `data/requirements.csv` (Polytechnic/KK) and `data/tvet_requirements.csv` (ILKBS/ILJTM).

## ℹ️ General Legend
Unless otherwise specified, requirement columns are **Binary Flags**:
-   `1`: **Required** (The student MUST meet this condition).
-   `0`: **Not Required** (Empty or 0 means no constraint).

## 📋 Column Definitions

### 1. Identity & Minimums
| Column | Description | Type |
| :--- | :--- | :--- |
| `course_id` | Unique identifier for the course (e.g., `POLY-DIP-001`). | String |
| `min_credits` | Minimum total number of "Credit" grades required (A+ to C). | Integer |
| `min_pass` | Minimum total number of "Pass" grades required (A+ to E). | Integer |

### 2. Citizenship & Gender
| Column | Description |
| :--- | :--- |
| `req_malaysian` | `1` = Student must be a Malaysian citizen (Warganegara). |
| `req_male` | `1` = Course is limited to **Male** applicants only. |
| `req_female` | `1` = Course is limited to **Female** applicants only. |
*(Note: A course should never have both `req_male` and `req_female` set to 1)*

### 3. Core Academic Requirements (Pass/Credit)
These columns enforce specific grades for core subjects.

| Column | Requirement |
| :--- | :--- |
| `pass_bm` | Pass in Bahasa Malaysia. |
| `pass_history` | Pass in Sejarah (History). |
| `pass_eng` | Pass in English. |
| `pass_math` | Pass in Mathematics (Modern). |
| `credit_bm` | Credit in Bahasa Malaysia. |
| `credit_english` | Credit in English. |
| `credit_math` | Credit in Mathematics (Modern). |

### 4. Composite & Group Requirements (Polytechnic/KK)
These checks allow flexibility (OR conditions). If a student meets **ANY** of the listed subjects in the group, they pass.

| Column | Logic |
| :--- | :--- |
| `pass_stv` | Pass in **any Science** (Bio/Phy/Chem/Sci), **Technical**, OR **Vocational** subject. |
| `credit_stv` | Credit in **any Science**, **Technical**, OR **Vocational** subject. |
| `credit_sf` | Credit in **General Science** OR **Physics**. |
| `credit_sfmt` | Credit in **General Science**, **Physics**, OR **Add Math**. |
| `credit_bmbi` | Credit in **Bahasa Malaysia** OR **English**. |

### 5. TVET Specific Requirements (ILKBS/ILJTM)
Specialized groupings used often in technical training.

| Column | Logic |
| :--- | :--- |
| `3m_only` | If `1`, user only needs to be able to Read, Write, Count. (Checks for *Attempted* BM & Math). Overrides other academic rules. |
| `single` | `1` = Applicant must be **Unmarried**. |
| `pass_math_addmath` | Pass in **Math** OR **Add Math**. |
| `pass_math_science` | Pass in **Math** OR **Science** (excludes Biology). |
| `pass_science_tech` | Pass in **Science** (excludes Biology) OR **Technical** subject. |
| `credit_math_sci` | Credit in **Math** OR **any Science**. |
| `credit_math_sci_tech`| Credit in **Math**, **any Science**, OR **Technical** subject. |

### 6. Medical & Interview
| Column | Description |
| :--- | :--- |
| `no_colorblind` | `1` = Applicant must **NOT** be colorblind. |
| `no_disability` | `1` = Applicant must be physically fit (no disabilities hindering practical work). |
| `req_interview` | `1` = Interview is required. (Note: Does not disqualify eligibility in the engine; purely informational). |

### 7. University/Asasi (UA) Requirements

These columns are used for Asasi and Foundation programs. Source: `data/university_requirements.csv`.

#### Grade B Requirements (stricter than Credit C)
| Column | Requirement |
| :--- | :--- |
| `credit_bm_b` | Grade **B** or better in Bahasa Malaysia. |
| `credit_eng_b` | Grade **B** or better in English. |
| `credit_math_b` | Grade **B** or better in Mathematics. |
| `credit_addmath_b` | Grade **B** or better in Additional Mathematics. |

#### Distinction Requirements (Grade A-)
| Column | Requirement |
| :--- | :--- |
| `distinction_bm` | Grade **A-** or better in Bahasa Malaysia. |
| `distinction_eng` | Grade **A-** or better in English. |
| `distinction_addmath` | Grade **A-** or better in Additional Mathematics. |

#### OR-Group Requirements
| Column | Logic |
| :--- | :--- |
| `credit_science_group` | Credit in **any** Science (Phy/Chem/Bio/Sci/AddSci/CompSci). |
| `credit_math_or_addmath` | Credit in **Math** OR **Add Math**. |

#### PI/PM Requirements
| Column | Requirement |
| :--- | :--- |
| `pass_islam` | Pass in Pendidikan Islam. |
| `credit_islam` | Credit in Pendidikan Islam. |
| `pass_moral` | Pass in Pendidikan Moral. |
| `credit_moral` | Credit in Pendidikan Moral. |

### 8. Other
| Column | Description |
| :--- | :--- |
| `remarks` | Free text notes (not used for logic). |
| `syarat_khas_raw` | Original special requirements text from MOHE (for debugging). |

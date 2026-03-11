# Pre-University Unified Scoring Design

## Problem

Three pre-university pathways (Asasi, Matric, STPM) are scored inconsistently:

- Asasi uses generic course-tag matching designed for vocational courses
- Matric/STPM use a custom signal adjustment but don't match field preferences
- All three get the same prestige bonus despite different real-world selectivity

## Design

### Prestige Bonus (reflects selectivity)

| Pathway | Bonus |
|---------|-------|
| Asasi   | +12   |
| Matric  | +8    |
| STPM    | +5    |

### Academic Bonus

**Matric** (merit score, 0-100):

| Merit  | Bonus |
|--------|-------|
| >= 94  | +8    |
| >= 89  | +4    |
| < 89   | +0    |

**Asasi** (same merit formula, lower thresholds due to lower cutoffs, avg ~84.6):

| Merit  | Bonus |
|--------|-------|
| >= 90  | +8    |
| >= 84  | +4    |
| < 84   | +0    |

**STPM** (mata gred, both Science and Arts):

| Mata Gred | Bonus |
|-----------|-------|
| <= 4      | +8    |
| <= 10     | +4    |
| > 10      | +0    |

### Field Preference Adjustment (+3 if matching signal)

| Pathway Variant                          | Mapped Field Signals                                                     |
|------------------------------------------|--------------------------------------------------------------------------|
| Matric Engineering, Asasi Kejuruteraan   | field_mechanical, field_electrical, field_civil, field_heavy_industry     |
| Matric Comp Sci                          | field_digital                                                            |
| Matric Accounting, Asasi Pengurusan      | field_business                                                           |
| Asasi Perubatan                          | field_health                                                             |
| STPM Social Science, Asasi Sains Sosial  | creative work preference signal                                          |
| All other science variants               | neutral (no field boost)                                                 |

### Unified Signal Adjustment (all three pathways, cap +/-6)

**Work style:**

- Problem solving: +2 (not SocSci)
- Creative: +1 (SocSci only)
- Hands-on: -1

**Environment:**

- Workshop/field env: -1 each

**Learning style:**

- Concept first: +2
- Rote tolerant: +1
- Learning by doing: -1

**Values:**

- Pathway priority: +3
- Fast employment: -2
- Quality priority: +2
- Allowance priority: +2 (Matric only)
- Proximity priority: +1 (STPM only)
- Employment guarantee: -1

**Energy:**

- Mental fatigue sensitive: -2
- High stamina: +1

### Score Ranges (BASE = 100)

| Pathway | Min | Typical | Max |
|---------|-----|---------|-----|
| Asasi   | 106 | 119     | 131 |
| Matric  | 102 | 115     | 125 |
| STPM    | 99  | 109     | 122 |

### Architecture

- Matric + STPM: frontend `pathways.ts` (no change)
- Asasi: backend `ranking_engine.py` -- skip generic `calculate_fit_score` for `pathway_type == 'asasi'`, use unified pre-U scoring instead

### Merit note

Merit is calculated from 8 subjects (4 compulsory + 2 stream + 2 electives) + 10% co-curriculum. Same 0-100 scale for Asasi, Matric, Poly, KKOM. Asasi cutoffs range from 77.8 (Asasi Sains) to 95.0 (Asasipintar UKM).

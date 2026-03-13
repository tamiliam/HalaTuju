# Design: Pre-University Courses as Real Database Entries

**Date:** 2026-03-13
**Status:** Approved

## Problem

Matric tracks (4) and STPM bidangs (2) were synthetic entries generated on-the-fly in the eligibility API. This caused confusion — they didn't appear in search, had inconsistent badges, and used a separate code path from all other courses. They need to be first-class `Course` rows in the database, appearing everywhere like any other course.

## Decision

Extend `Course` + `CourseRequirement` with a `merit_type` field to support different merit calculation formulas. Add 6 new course rows for the pre-university pathways.

## Data Model

### 6 New Course Rows

| course_id | course (name) | level | field |
|---|---|---|---|
| `matric-sains` | Matrikulasi — Sains | Pra-U | Sains & Teknologi |
| `matric-kejuruteraan` | Matrikulasi — Kejuruteraan | Pra-U | Kejuruteraan |
| `matric-sains-komputer` | Matrikulasi — Sains Komputer | Pra-U | Teknologi Maklumat |
| `matric-perakaunan` | Matrikulasi — Perakaunan | Pra-U | Perakaunan & Kewangan |
| `stpm-sains` | Tingkatan 6 — Sains | Pra-U | Sains & Teknologi |
| `stpm-sains-sosial` | Tingkatan 6 — Sains Sosial | Pra-U | Sains Sosial |

### CourseRequirement Changes

- **New field: `merit_type`** — CharField, choices: `standard` (default), `matric`, `stpm_mata_gred`
- **New choices for `source_type`**: `matric` and `stpm` added alongside existing `poly`, `kkom`, `tvet`, `ua`, `pismp`
- **`merit_cutoff`**: 94 for matric tracks, 18 for STPM bidangs (max mata gred)
- **`complex_requirements` JSON**: Encodes track-specific subject rules

### complex_requirements JSON Format

Matric example (sains track):
```json
{
  "merit_type": "matric",
  "slots": [
    {"subjects": ["math"], "min_grade": "B"},
    {"subjects": ["addmath"], "min_grade": "C"},
    {"subjects": ["chem"], "min_grade": "C"},
    {"subjects": ["phy", "bio"], "min_grade": "C"}
  ],
  "electives_needed": 0,
  "total_slots": 4
}
```

STPM example (sains bidang):
```json
{
  "merit_type": "stpm_mata_gred",
  "min_groups": 3,
  "max_mata_gred": 18,
  "groups": [
    ["math", "addmath"],
    ["phy"],
    ["chem"],
    ["bio"],
    ["eng_draw", "eng_mech", "eng_civil", "eng_elec", "reka_cipta", "sports_sci", "srt", "comp_sci", "gkt"]
  ]
}
```

## Engine Integration

### Eligibility Check

`engine.py` processes matric/stpm courses through the same loop as all other courses. Standard boolean fields handle simple checks (credit_bm, pass_history). The `complex_requirements` JSON handles track-specific logic:

- **Matric**: Check each slot — student must have the required subject at the required grade. Alternatives allowed (e.g. Physics OR Biology). Fill remaining slots with best electives at min C.
- **STPM**: Check BM credit. Find best credit from each subject group. Student needs credits in at least `min_groups` different groups, with total mata gred ≤ `max_mata_gred`.

### Merit Calculation

After eligibility passes, branch by `merit_type`:

- **`standard`** (existing): Compare student_merit vs merit_cutoff directly.
- **`matric`**: Sum grade points of 4 best subjects per track rules. Merit = `(points / 100) × 90 + CoQ`. High ≥ 94, Fair ≥ 89, Low < 89.
- **`stpm_mata_gred`**: Sum mata gred of 3 best credits. Convert to percentage for progress bar: `(27 - mata_gred) / 24 × 100`. Display raw mata gred values (You: 8 | Need: 18). High ≤ 12, Fair 13-18, Low > 18.

CoQ score comes from the eligibility request payload (`coq_score` field, default 5.0).

Grade point scales (from `pathways.py`):
- Matric: A+=25, A=24, A-=23, B+=22, B=21, C+=20, C=19, D=18, E=17, G=0
- STPM mata gred: A+=1, A=1, A-=2, B+=3, B=4, C+=5, C=6, D=7, E=8, G=9

## Frontend

No special handling needed — these are regular courses:

- **Search**: Appear naturally. Filter by `level=Pra-U` or `source_type=matric`/`stpm`.
- **Dashboard**: Returned by eligibility engine like any other course.
- **CourseCard**: Source badge `Matrikulasi` (orange) / `Tingkatan 6` (indigo). Level badge `Pra-U` (orange).
- **Merit bar**: Matric shows standard percentage. STPM shows raw mata gred via `merit_display_student`/`merit_display_cutoff`.
- **Detail page**: `/course/matric-sains` etc. Requirements section from `complex_requirements` JSON.
- **Field images**: Mapped by field name in `getImageSlug()`.

## Migration

1. Django migration: add `merit_type` field, expand `source_type` choices
2. Data migration: insert 6 courses + 6 requirements with correct JSON
3. Supabase: run migration, enable RLS on new rows

## Testing

- Add 6 courses to test fixtures
- Test matric merit calculation (grade points + CoQ → merit score)
- Test STPM mata gred calculation (best 3 credits → mata gred)
- Test eligibility: subject requirements, alternatives, elective slot filling
- Golden master baseline increases (6 new courses × qualifying students)
- Existing `test_pathways.py` tests remain valid — formulas unchanged

## Trade-offs

- `engine.py` gains ~50 lines of merit calculation branching. Acceptable for correctness.
- `complex_requirements` JSON is more complex for matric/stpm than for regular courses. But it avoids adding 10+ new boolean fields.
- The 6 courses are manually inserted, not loaded from CSV. Acceptable since they're stable government programmes.

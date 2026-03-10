# Matriculation & STPM Pathways — Design Document

**Date:** 10 March 2026
**Status:** Approved

---

## Goal

Show SPM students which Matriculation tracks and STPM bidang they qualify for, with merit/eligibility scores, directly on the dashboard alongside existing course recommendations.

## Architecture

Three changes: (1) expand grades page to capture 4 stream subjects instead of 2, (2) build a pathway eligibility engine, (3) add pathway cards to the dashboard. The pathway engine runs entirely on the frontend — no new backend endpoints needed since we already have all the student's grades in localStorage.

---

## 1. Grades Page — Expand Stream to 4 Subjects

### Current State
- Section 1: 4 core (BM, BI, Math, Sejarah) — fixed
- Section 2: Pick **2** stream subjects from pool
- Section 3: Pick 0-2 elective subjects
- Section 4: PI/PM (optional)
- Section 5: CoQ (0-10)

### New State
- Section 1: 4 core — unchanged
- Section 2: Pick **4** stream subjects from pool
- Section 3: Pick **2** elective subjects
- Section 4: PI/PM — unchanged
- Section 5: CoQ — unchanged

Total: 4 core + 4 stream + 2 elective + 0-2 PI/PM = 10-12 subjects.

### Merit Calculation Change

The UPU merit formula uses 3 sections:
- **Section 1 (best 5)**: Core + best stream subjects
- **Section 2 (next 3)**: Remaining stream + electives
- **Section 3 (Sejarah)**: History

When 4 stream subjects are entered, the **best 2** count as stream (flow into Section 1 with core). The **weaker 2** compete with electives for Section 2 slots. This is consistent with how SPM merit actually works — students sit all 4 stream subjects but only the best ones count in the higher-weighted section.

---

## 2. Pathway Eligibility Engine

Pure frontend TypeScript module (`lib/pathways.ts`). No backend changes.

### 2A. Matriculation — 4 Tracks

**Grade Point Scale (Matriculation-specific):**

| Grade | Points |
|-------|--------|
| A+ | 25 |
| A | 24 |
| A- | 23 |
| B+ | 22 |
| B | 21 |
| C+ | 20 |
| C | 19 |
| D | 18 |
| E | 17 |
| G | 0 |

**Track Requirements:**

| Track | Subject 1 | Subject 2 | Subject 3 | Subject 4 |
|-------|-----------|-----------|-----------|-----------|
| **Sains** | Math (min B) | Add Math (min C) | Chemistry (min C) | Physics OR Biology (min C) |
| **Kejuruteraan** | Math (min B) | Add Math (min C) | Physics (min C) | 1 elective (min C) |
| **Sains Komputer** | Math (min C) | Add Math (min C) | Comp Sci (min C) | 1 elective (min C) |
| **Perakaunan** | Math (min C) | 3 electives (min C each) | — | — |

**Merit Formula:**
```
Academic (A) = (sum of 4 subject points / 100) * 90
Co-curricular (B) = CoQ / 10 * 10
Merit = A + B
```

Max merit = (25*4/100)*90 + 10 = 90 + 10 = 100.

**Eligibility check per track:**
1. Does the student have grades for all required subjects?
2. Do grades meet the minimum thresholds?
3. If eligible, calculate merit score.

### 2B. STPM (Form 6) — 2 Bidang

**Grade Point Scale (STPM — lower is better):**

| Grade | Mata Gred |
|-------|-----------|
| A+, A | 1 |
| A- | 2 |
| B+ | 3 |
| B | 4 |
| C+ | 5 |
| C | 6 |
| D | 7 |
| E | 8 |
| G | 9 |

**Bidang Requirements:**

| Bidang | Requirement | Max Mata Gred |
|--------|-------------|---------------|
| **Sains** | 3 credits (C or better) from different science groups | 18 |
| **Sains Sosial** | 3 credits (C or better) from different subject groups | 12 |

**Science subject groups** (pick 1 from each of 3 different groups):
- Math / Add Math
- Physics
- Chemistry
- Biology
- Engineering subjects / Comp Sci / Sports Sci / etc.

**Social Science subject groups** (pick 1 from each of 3 different groups):
- BM
- BI / Kesusasteraan
- Sejarah
- Geografi / Seni Visual
- PI / PM
- Math / Add Math
- Prinsip Perakaunan
- Sains / Sains Tambahan
- Ekonomi / Perniagaan / Keusahawanan
- (and many more groups)

**Eligibility check per bidang:**
1. Find best 3 subjects from different groups
2. All 3 must be credit (C or better, i.e. mata gred <= 6)
3. Sum of their mata gred must be <= threshold (18 for Sains, 12 for Sains Sosial)
4. Must have credit in BM (general requirement)

**Score shown:** Total mata gred (e.g. "8/18" for Sains) — lower is better.

### 2C. Implementation Notes

- The engine takes `grades: Record<string, string>` and `coq: number` as input
- Returns array of pathway results: `{ pathway, track, eligible, merit/score, reason }`
- Subject mapping reuses existing subject IDs from the grades page
- For tracks with "1 elective (min C)", pick the best available subject that isn't already used

---

## 3. Dashboard — Pathway Cards

### Placement

New "Pathways" section on the dashboard, displayed **above** the existing course recommendations. This is the first thing students see — "Here's where you can go next."

### Card Design

Each pathway card shows:
- **Icon**: Graduation cap (Matric) or book (STPM)
- **Title**: "Matrikulasi — Sains" or "Tingkatan 6 — Sains Sosial"
- **Status badge**: "Layak" (green) or "Tidak Layak" (grey)
- **Score**: Merit score for Matric (e.g. "Merit: 87/100") or mata gred for STPM (e.g. "Mata Gred: 8/12")
- **Reason** (if not eligible): "Memerlukan kepujian Matematik Tambahan" etc.

### Layout

- Horizontal scrollable row on mobile (2 visible at a time)
- 3-column grid on desktop
- Up to 6 cards total (4 Matric tracks + 2 STPM bidang)
- Non-eligible cards shown with reduced opacity but still visible (student should see what they're missing)

### i18n

Card labels, status badges, and reason text in EN/BM/TA.

---

## 4. What This Does NOT Include

- **No backend changes** — all calculation is frontend
- **No new database models** — pathways aren't stored, just computed from grades
- **No STPM merit formula** — STPM selection uses mata gred sum, not a computed merit score
- **No Sains Sosial (Agama) bidang** — requires Bahasa Arab which most of our target students (Tamil school) won't have. Can add later.
- **No grade modulation layer** — deferred from quiz redesign, still deferred
- **No matriculation programme details** — just eligibility + merit, not which Matric college to attend

---

## 5. Testing

- Unit tests for pathway engine (each track eligible/not eligible, edge cases)
- Merit calculation accuracy (verify against official calculator)
- Grade page: 4 stream subjects save/load correctly
- Dashboard: pathway cards render for eligible/ineligible students
- UPU merit formula still works correctly with 4 stream subjects

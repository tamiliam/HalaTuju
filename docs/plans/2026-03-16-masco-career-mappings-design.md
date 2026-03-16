# Design: MASCO Career Mappings for All Courses

**Date:** 2026-03-16
**Status:** Approved

## Goal

Every course detail page (except Matric and STPM pre-U pathways) shows a **Kerjaya (Career Pathways)** section with ~3 relevant MASCO job titles, each linking to the official eMASCO portal.

## Current State

| Source Type | Courses | Career Coverage |
|-------------|---------|-----------------|
| poly | 85 | 100% (all linked) |
| kkom | 54 | 100% (all linked) |
| tvet (ILJTM/ILKBS) | 83 | 100% (all linked) |
| ua (university) | 89 | 0% |
| pismp (teaching) | 73 | 0% |
| matric (pre-U) | 4 | Excluded |
| stpm (pre-U) | 2 | Excluded |
| STPM degrees | 1,113 | 0% (no model support) |

**After this work:** ~1,275 courses gain ~3 career mappings each (~3,825 new links).

## Data Source

- `halatuju_api/data/masco_full.csv` — 4,854 MASCO 2020 jobs (complete, digits 0-9)
- Columns: `no`, `kod_masco`, `tajuk_pekerjaan`
- Hierarchical codes: `3` (broad) → `33` → `332` → `3322` → `3322-24` (specific)
- eMASCO URL pattern: `https://emasco.mohr.gov.my/masco/{kod_masco}`
- Full index: https://emasco.mohr.gov.my/index

## Design Decisions

### 1. Data lives in DB, not i18n

MASCO job titles are course content, stored in `MascoOccupation.job_title` (BM only, as per official MASCO classification). UI labels (section headings) stay in i18n JSON.

### 2. Consistent M2M across both course models

Add `career_occupations = ManyToManyField('MascoOccupation')` to `StpmCourse`, mirroring the existing `Course` model. Same serializer, same API shape, same frontend component.

### 3. Shared CareerPathways component

Extract the career section from `/app/course/[id]/page.tsx` into a reusable `CareerPathways` component used by both SPM and STPM detail pages. Jobs with `emasco_url` render as clickable links; jobs without render as plain tags (backwards-compatible).

### 4. AI-assisted mapping with field_key pre-filtering (Approach C)

Rather than sending all 4,854 jobs to AI or doing manual field-level mapping:

1. **Deterministic pre-filter**: Map each `field_key` (37 taxonomy keys) to 1-2 MASCO major groups (first digit). E.g. `field_health` → digit `2` (Professionals) + `3` (Associate Professionals).
2. **AI matching**: Send the filtered subset (~200-400 jobs) + course name to Gemini. Ask it to pick ~3 most relevant specific job codes.
3. **Human review**: Output a CSV for approval before writing to DB.

This is economical (small Gemini calls on free tier), accurate (less noise), and leverages the `field_key` work from Field Taxonomy Sprints 2-3.

### 5. eMASCO URLs generated from code

Every MASCO record gets `emasco_url = https://emasco.mohr.gov.my/masco/{kod_masco}`. No need to scrape or manually enter URLs.

## Architecture Changes

### Backend — Model

```python
# In StpmCourse (mirrors Course)
career_occupations = models.ManyToManyField(
    'MascoOccupation',
    related_name='stpm_courses',
    blank=True,
    help_text="MASCO occupation codes this programme leads to"
)
```

New migration for the M2M field + through table.

### Backend — Management Commands

1. **`load_masco_full`** — Load all 4,854 MASCO codes from CSV into `MascoOccupation` table. Generates `emasco_url` from `kod_masco`. Idempotent (skips existing records).

2. **`map_course_careers`** — AI-assisted mapping pipeline:
   - Reads `field_key` → MASCO digit mapping (deterministic)
   - For each unmapped course, filters MASCO jobs by relevant digits
   - Sends filtered list + course name to Gemini
   - Outputs review CSV: `course_id, course_name, masco_code, job_title`
   - `--apply` flag writes approved mappings to DB
   - `--source-type` flag to run in batches (pismp first, then ua, then stpm)

### Backend — API

- STPM detail endpoint includes `career_occupations` (same `MascoOccupationSerializer`)
- No change to SPM detail endpoint (already works)

### Frontend

- Extract `CareerPathways` component from SPM course detail page
- Use in both `/app/course/[id]/page.tsx` and `/app/stpm/[id]/page.tsx`
- Component accepts `career_occupations` array, renders job tags
- Hidden when array is empty (backwards-compatible)

## What This Does NOT Touch

- Eligibility engine (golden master safe)
- Ranking engine
- Matric/STPM pre-U virtual courses (excluded)
- Existing 222 poly/kkom/tvet mappings (preserved)
- i18n JSON files (no new content keys)

## Exclusions

- **Matric courses** (4): Pre-university, no direct career path
- **STPM pre-U courses** (2): Pre-university stream selectors
- **Asasi**: TBD — may exclude if confirmed as pre-university only

## Risks

| Risk | Mitigation |
|------|------------|
| Gemini maps wrong jobs | Human review CSV before applying |
| Encoding issues in CSV | File has latin-1 encoding (non-breaking spaces in some titles) — handle in loader |
| Duplicate `kod_masco` in CSV | Same code appears for military vs civilian roles — deduplicate by taking civilian title |
| Free tier Gemini rate limits | Batch with delays; ~1,275 calls is well within daily limits |

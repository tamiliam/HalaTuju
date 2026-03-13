# Unified Explore Page — Design

**Date:** 2026-03-13
**Status:** Approved

## Goal

Merge SPM and STPM courses into a single `/search` page with a "Qualification" filter (SPM/STPM). Students see all courses by default. The "Eligible only" toggle checks STPM grades first, falls back to SPM if missing.

## Prerequisites

### AI Metadata Enrichment
- One-time Gemini batch job to classify all 1,113 STPM courses
- Output per course: `field`, `category`, `description`
- Match against existing SPM field list (~30 categories) first
- Add new categories as needed: medicine, veterinary, pharmacy, archaeology, arts, health sciences, etc.
- Store in `stpm_courses` table (new columns)
- Review results before going live

## Backend

### Unified Search Endpoint
- Extend or replace `CourseSearchView` to query both `course_requirements` and `stpm_courses`
- Return combined result set with a `qualification` field (`SPM` or `STPM`)
- Pagination across both result sets

### Filters
- Add `qualification` to existing filter set (level, field, source_type, state)
- `field` filter works across both since STPM courses will have AI-assigned fields matching the same taxonomy
- Filter metadata response includes qualification options

### Eligible Only Toggle
- When toggled on, check STPM eligibility first (if STPM grades exist in profile)
- Fall back to SPM eligibility if no STPM grades
- Return merged eligible set with IDs from the appropriate engine

## Frontend

### Qualification Filter Pill
- New `SPM` / `STPM` pill alongside existing Level, Field, Type, State pills
- Default: no filter (show all)

### STPM Cards Use CourseCard Component
Field mapping from STPM data to existing card layout:

| Card field | STPM source |
|-----------|-------------|
| course_name | program_name |
| level | "Ijazah Sarjana Muda" (hardcoded) |
| field | AI-assigned field |
| source_type | "University" |
| merit_cutoff | merit_score |
| institution_name | university |
| institution_count | 1 |
| institution_state | (derived from university) |

### Remove /stpm/search
- Redirect `/stpm/search` to `/search?qualification=STPM`
- Keep `/stpm/[id]` detail page as-is

## Data Flow

```
Student opens /search
  -> Backend queries both tables
  -> Returns unified list with qualification badge
  -> Student toggles "Eligible only"
    -> Frontend sends grades (STPM first, fallback SPM)
    -> Backend returns eligible IDs from appropriate engine
    -> Frontend filters displayed cards
```

## Out of Scope
- Institution name display on SPM cards (separate exercise)
- STPM course detail page changes (already exists at /stpm/[id])
- PISMP level label change to "Ijazah Sarjana Muda" (can be done but is a data fix, not this feature)

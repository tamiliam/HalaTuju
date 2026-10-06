# Sprint 19 Retrospective — 37-Category Course Image Classification

**Date**: 2026-02-23
**Version**: 1.21.0

## What Was Built

Replaced the broken 9-image course classification system with a comprehensive 37-category system. Every course (383 total) now shows a relevant field image on the course card.

### Key deliverables:
- 37 AI-generated images via Gemini 2.5 Flash Image (Malaysian educational context)
- Multi-level keyword matcher in `CourseCard.tsx` (field name + course name routing)
- Sub-routing for large umbrella fields: Pendidikan (5 sub-images), Mekanikal & Pembuatan (4), Elektrik & Elektronik (3), Teknologi Maklumat (2)
- "Umum" catch-all dissolved into proper categories via course name keywords
- Future STPM images pre-created (Undang-undang, Farmasi)
- 15-max rule enforced: no image category covers more than 15 courses

## What Went Well

1. **Data-driven approach**: Querying the actual database for all 158 distinct field values and 383 courses before writing any code meant the matcher was correct from the start.
2. **Systematic verification**: Traced every field value through the matcher logic, found and fixed 2 edge cases (Senibina Kapal, Teknologi Kimia Lemak dan Minyak) before they reached production.
3. **Gemini image quality**: All 37 images generated successfully on first attempt with good quality for the Malaysian educational context.
4. **Build stayed clean**: No TypeScript errors or warnings throughout the implementation.

## What Went Wrong

1. **Supabase Storage RLS blocked uploads**: The anon key couldn't upload to the `field-images` bucket (INSERT policy missing). Lost time debugging this. Fix was straightforward — temporary INSERT policy, upload, then drop policy — but should have checked RLS policies before running the 37-image generation.
2. **Hardcoded anon key in script**: The `generate_field_images.py` script has the Supabase anon key hardcoded. Should use `.env` variable instead. Not a security risk (anon key is public) but bad practice.

## Design Decisions

| Decision | Why |
|----------|-----|
| Keyword matching over DB lookup | Images are static assets; a code-based matcher avoids database queries on every card render and is simpler to maintain |
| 37 categories (not 9 or 158) | 9 was too coarse (97% broken). 158 (one per field) is too many images to maintain. 37 balances specificity with manageability |
| 15-max rule | User requirement — prevents students in large fields (e.g. Pendidikan with 73 courses) from seeing identical images everywhere |
| Sub-route by course name | Umbrella fields like "Pendidikan" contain diverse courses that need different images; course name contains the distinguishing information |
| Pre-create STPM images | When STPM data is added later, images will already be in place |

## Numbers

| Metric | Value |
|--------|-------|
| Images generated | 37 |
| Image size range | 1.35-2.07 MB |
| Courses with images (before) | 13/383 (3%) |
| Courses with images (after) | 383/383 (100%) |
| Fields verified | 158 distinct values |
| Edge cases fixed | 2 (Senibina Kapal, Teknologi Kimia) |
| Files modified | 3 (CourseCard.tsx, generate_field_images.py, CHANGELOG.md) |
| Frontend build | 20 routes, 0 errors |
| Backend tests | 176 (unchanged) |
| Cloud Run revisions | Frontend rev 22 |

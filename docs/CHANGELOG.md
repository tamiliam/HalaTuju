# Changelog — HalaTuju

## STPM Sprint 6 — Merit Scoring + UX Polish (2026-03-13)

### Added
- `merit_score` field on `StpmCourse` model — stores UPU average merit percentage (0–100)
- Merit data loader (`_load_merit_data`) in `load_stpm_data.py` — reads slim CSVs, handles "Tiada" as null
- Slim merit CSV files: `stpm_science_merit.csv` (1,003 rows), `stpm_arts_merit.csv` (677 rows)
- `merit_score` exposed in STPM eligibility API response and ranking pipeline
- `cgpaToMeritPercent()` utility in `stpm.ts` for consistent CGPA→merit conversion
- Merit traffic lights on STPM dashboard — High (green), Fair (amber), Low (red) badges per course card
- Merit summary counts in dashboard header (e.g. "302 High, 75 Fair, 77 Low")
- Empty state UI for STPM dashboard when zero courses qualify
- Elective add-button UX pattern (replaces permanent dropdown) on STPM grade entry
- 1,080 merit scores loaded into Supabase `stpm_courses` table (33 are "Tiada" = null)

### Changed
- Koko score scale corrected: `max="4"` → `max="10"`, formula `× 0.1` → `× 0.04`
- CGPA formula now: `(academicCgpa × 0.9) + (kokoScore × 0.04)` where koko is 0–10

### Fixed
- STPM dashboard crash when API returns zero eligible courses (missing `setStpmResults([])` in catch block)
- ICT stream classification: `'both'` → `'arts'` in `subjects.ts`
- Hardcoded English "degree programmes" replaced with i18n key `dashboard.qualifyCourses`
- Inline CGPA→merit calculation replaced with shared `cgpaToMeritPercent()` function

## STPM Sprint 5 — Grade Scale Fix + UX Redesign (2026-03-13)

See `retrospective-stpm-sprint5.md`

## STPM Sprint 4 — Search + Detail Pages (2026-03-13)

See `retrospective-stpm-sprint4.md`

## v1.33.0 — Unified Pre-U Backend & IPGM Integration (2026-03-12)

See `release-notes-v1.33.0.md`

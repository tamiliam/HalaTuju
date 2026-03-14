# Retrospective — Data Integrity Sprint (2026-03-14)

## What Was Built

1. **STPM terminology rename**: "programmes" → "courses" across 23 files (models, views, serializers, tests, URLs, i18n in 3 languages)
2. **Supabase column rename**: `program_id` → `course_id`, `program_name` → `course_name` on `stpm_courses` table
3. **db_column workaround removal**: Eliminated Django `db_column` parameter that was masking the real column names — migration generated
4. **MOHE course audit**: Compared 363 ePanduan CSV courses against Supabase, identified gaps
5. **2 new courses added**: FB0500001 (Asasi TVET, 10 polytechnics) and UL0481001 (Asasi IT Huffaz, UMK)
6. **2 name fixes**: Corrected "Rekabentuk Industri" and "Food & Beverage" spelling

## What Went Well

- The rename was systematic — grep-based search caught all 23 files, no manual discovery needed
- User caught that `db_column` was cosmetic tech debt before it shipped — led to the proper Supabase column rename
- MOHE audit pipeline was methodical: 363 → filter UiTM (87) → filter bumi (47) → filter Islamic (24) → 208 eligible → match against Supabase → only 2 genuinely missing
- Parallel tool calls (Supabase SQL + file reads) kept the session efficient

## What Went Wrong

1. **Wrong Supabase table name assumed**: Tried `courses_stpmcourse` (Django default naming) but actual table was `stpm_courses` (custom `db_table`). Root cause: didn't check `class Meta: db_table` before writing SQL. Fix: lesson already exists in `docs/lessons.md` — reinforced this sprint.

2. **CSV bumiputera column was unreliable**: `university_courses.csv` had `bumiputra=No` for all 363 rows including UiTM. Root cause: CSV data quality issue — the column wasn't populated correctly in the source. Fix: cross-referenced with `mohe_programs_with_khas.csv` which had the real data. Lesson: always verify critical filter columns against a second source.

3. **Name-based matching missed due to ID scheme differences**: Initial matching used only `course_id`, which missed all Poly/KKom courses (CSV uses FB/FC codes, Supabase uses POLY-DIP/KKOM-CET codes). Root cause: assumed ID schemes were consistent across institution types. Fix: added name-based fuzzy matching as fallback.

## Design Decisions

- Real column rename over cosmetic `db_column` — eliminates a layer of indirection and prevents future confusion about what the actual DB schema looks like
- Kept UiTM's 162 STPM courses in database but filtered at API level (bumiputera exclusion) — data completeness preserved while search results remain relevant to non-bumi users

## Numbers

- Files changed: 23 (rename) + 2 (migration)
- Supabase operations: 2 column renames, 2 name fixes, 2 course inserts, 2 requirement inserts, 11 institution link inserts
- Tests: 332 pass / 13 pre-existing failures / 30 skipped
- Deploys: 2 (API only — frontend was deployed earlier in session)

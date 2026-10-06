# Retrospective — Legacy Cleanup Sprint (2026-03-15)

## What Was Built

Removed legacy files and migrated STPM tests from CSV-based loader to Django fixtures:
- **TD-029**: Deleted `_archive/streamlit/` (246 files, 80MB)
- **TD-028**: Deleted `data/stpm/` (4 CSV files)
- **TD-031**: Deleted 6 one-time management commands, extracted reusable functions to `utils.py`
- **TD-032**: Resolved by deleting `load_csv_data.py`
- Created STPM fixture files (`stpm_courses.json` + `stpm_requirements.json`, 1,113 courses)
- Migrated 6 test files from `call_command('load_stpm_data')` to `loaddata` fixtures

## What Went Well

- Initial scoping identified that `load_stpm_data` was heavily referenced by tests (42+ tests) — prevented a naive "just delete everything" approach that would have broken the suite
- Fixture generation from the dev DB was straightforward — run the loader once, dump, done
- All 424 tests pass on first run after migration — zero fixture data issues
- Extracted `proper_case_name` and `build_mohe_url` to `utils.py` before deleting source commands — preserved test coverage

## What Went Wrong

Nothing significant. The only friction was needing to run `migrate` on the dev SQLite before generating fixtures, since `db.sqlite3` had been deleted in the previous sprint.

## Design Decisions

No architectural decisions — straightforward deletion with fixture migration.

## Numbers

| Metric | Value |
|--------|-------|
| Backend tests | 424 pass, 0 fail (was 425 — removed loader idempotency test) |
| Files deleted | 256 (246 Streamlit + 4 CSVs + 6 commands) |
| Files added | 3 (utils.py + 2 fixture JSONs) |
| Repo size reduction | ~80MB (Streamlit archive) |
| Tech debt resolved | 4 items (TD-028, TD-029, TD-031, TD-032) |
| Total resolved | 29/52 |

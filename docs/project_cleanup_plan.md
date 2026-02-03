# Project Cleanup & Reorganization Plan

## 1. Goal
Streamline the repository by:
- Moving one-off scripts to `scripts/analysis/` or `scripts/legacy/`.
- Centralizing documentation in `docs/`.
- Archiving raw inputs/PDFs.
- Ensuring `src/` only contains application code.

## 2. 'HalaTuju' Folder Cleanup

| File | Action | Destination | Reason |
| :--- | :--- | :--- | :--- |
| `analyze_data_consistency.py` | MOVE | `scripts/analysis/` | Analysis tool, not app code. |
| `analyze_poly_kk_overlap.py` | MOVE | `scripts/analysis/` | Analysis tool. |
| `analyze_spm_subjects.py` | MOVE | `scripts/analysis/` | Analysis tool. |
| `check_kk_wbl.py` | MOVE | `scripts/analysis/` | QA script. |
| `check_mohe_orphans.py` | MOVE | `scripts/analysis/` | QA script. |
| `verify_data_load.py` | MOVE | `tests/manual/` | Verification script. |
| `test_score.py` | MOVE | `tests/unit/` | Unit test. |

**New Directories Needed**:
- `HalaTuju/scripts/analysis/`
- `HalaTuju/tests/manual/`
- `HalaTuju/tests/unit/`

## 3. 'SchoolScraper' Folder Cleanup

| File | Action | Destination | Reason |
| :--- | :--- | :--- | :--- |
| `*.pdf` | MOVE | `input_docs/` | Source PDF documents. |
| `scrape_schools.py` | KEEP | - | Main scraper script. |

**New Directories Needed**:
- `SchoolScraper/input_docs/`

## 4. 'Random' Folder Cleanup
This folder seems to be a staging area.

| File | Action | Destination | Reason |
| :--- | :--- | :--- | :--- |
| `extract_pdfs.py` | MOVE | `scripts/pdf_tools/` | Reusable utility. |
| `merge_requirements.py` | MOVE | `scripts/etl/` | ETL script. |
| `parse_pismp.py` | MOVE | `scripts/etl/` | ETL script. |
| `headers_report.txt` | DELETE | - | Temporary output. |

**New Directories Needed**:
- `Random/scripts/pdf_tools/`
- `Random/scripts/etl/`

## 5. Execution Steps
1.  **Create Directories**: Run `mkdir` commands for all new paths.
2.  **Move Files**: Execute batch `move` commands.
3.  **Update Imports**: Check if moving `analyze_*.py` breaks any `sys.path` imports (likely need to adjust `sys.path.append`).
4.  **Verify**: Run `verify_data_load.py` from its new location to ensure it still works.

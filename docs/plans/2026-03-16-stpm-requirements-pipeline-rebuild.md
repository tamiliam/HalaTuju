# STPM Requirements Pipeline Rebuild

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the STPM requirements parsing pipeline from scratch — reliable, auditable, reusable yearly when MOHE updates course requirements.

**Architecture:** A 5-stage pipeline with audit checkpoints between each stage. Stage 0 (scraping) uses Playwright to handle dynamic content. Stage 1 (HTML → structured JSON) is the critical rewrite. Each stage is an independent Python tool in `Settings/_tools/`, orchestrated by a workflow in `Settings/_workflows/`. The JSON schema supports multi-tier requirements (multiple grade thresholds per level), exclusion lists, and all special conditions discovered in the HTML corpus.

**Tech Stack:** Python 3, Playwright (scraping), BeautifulSoup4 (HTML parsing), csv, json (stdlib), pytest (testing)

**Scope:** 1,680 STPM courses (1,003 science + 677 arts) across 2 source CSVs. Does NOT touch the SPM pipeline (separate tool, separate data).

---

## Problem Statement

The current parser (`scripts/parse_stpm_requirements.py`, 883 lines) has 4 critical bugs affecting **62% of courses (618/1,003)**:

1. **Single subject group per level** — `parse_subject_group()` uses `re.search()` which returns only the first match. Courses with "A in 2 AND A- in 1" lose the second group.
2. **Subject cross-contamination** — `extract_subjects_from_html()` extracts from the entire HTML blob, mixing STPM and SPM subjects.
3. **SPM grade groups ignored** — `detect_spm_subjects()` only handles credit/pass, not "Gred B in 4 named subjects".
4. **No exclusion list handling** — "tidak termasuk mata pelajaran berikut" patterns (70 courses) are silently dropped.

## Pipeline Architecture

```
Stage 0: Scrape detail pages       (scrape_stpm_requirements.py)  ← Playwright
  ↓ audit checkpoint (row count, HTTP errors)
Stage 1: HTML → Structured JSON    (parse_stpm_html.py)
  ↓ audit checkpoint
Stage 2: JSON → Fixture JSON       (stpm_json_to_fixture.py)
  ↓ audit checkpoint
Stage 3: Validate                   (validate_stpm_requirements.py)
  ↓
Stage 4: Load                       (manage.py loaddata)
```

**Workflow:** `Settings/_workflows/stpm-requirements-update.md`

Each stage reads the previous stage's output file. No stage does two things. Each stage can be re-run independently.

## Stage 0: The Scraping Challenge

The MOHE ePanduan portal (`online.mohe.gov.my/epanduan/`) uses a **modal popup with dynamically-loaded tabs**:

1. User clicks a course card → modal opens showing **Syarat Am** (general requirements)
2. The **Syarat Khas** tab (special requirements) loads via AJAX **only when clicked**
3. The Syarat Khas tab contains the detailed HTML with subject groups, grade thresholds, exclusion lists — this is the data we need

**Why this is hard:**
- Simple HTTP requests cannot get Syarat Khas content (it's loaded dynamically via JavaScript)
- The tab click triggers an AJAX call; the content renders after a delay
- Playwright/Selenium must: open modal → click "Syarat Khas" tab → wait for content → extract HTML

**Existing tools:**
- `scrape_mohe_stpm.py` (Playwright) — scrapes course **listings** (name, merit, university), NOT detail pages
- `validate_stpm_urls.py` (Selenium) — validates URLs but doesn't extract requirements

**Stage 0 tool** (`scrape_stpm_requirements.py`) will:
1. Read the course listing CSV (output of `scrape_mohe_stpm.py`)
2. For each course, navigate to its detail page
3. Click the "Syarat Khas" tab and wait for dynamic content
4. Extract both `syarat_am` (text) and `requirements` (HTML from Syarat Khas)
5. Also extract: `interview` flag, `bumiputera` flag, `kampus`, `merit`
6. Write to CSV matching the current `mohe_programs_merged.csv` schema
7. Support `--resume` flag (skip already-scraped courses) for crash recovery
8. Configurable delay between requests (respect MOHE servers)

**This tool is Sprint 3** (after parser is proven correct with existing data). We have the HTML already — building Stage 0 is for next year's refresh.

## Data Flow

```
Input (Stage 0): MOHE ePanduan website (live)
  ↓
Stage 0 output:  data/stpm_science/mohe_programs_merged.csv   (1,003 courses)
                 data/stpm_arts/mohe_programs_merged.csv       (677 courses)
                 (CSV with raw HTML in 'requirements' column)
                              ↓
Stage 1 output:  data/stpm_requirements_structured.json
                 (1,680 entries, one per course, all requirements as structured objects)
                              ↓
Stage 2 output:  halatuju_api/apps/courses/fixtures/stpm_requirements.json
                 (Django fixture format, ready for loaddata)
                              ↓
Stage 3 output:  data/stpm_requirements_audit_report.txt
                 (Validation results — pass/fail per course, flagged anomalies)
                              ↓
Stage 4:         Database updated via `manage.py loaddata stpm_requirements`
```

## Schema Design

### Structured JSON (Stage 1 output)

Each course produces one object:

```json
{
  "course_id": "UM6724001",
  "program_name": "SARJANA MUDA PEMBEDAHAN PERGIGIAN",
  "university": "Universiti Malaya",
  "source_file": "stpm_science",
  "raw_html": "<ol>...</ol>",

  "min_cgpa": 3.80,

  "stpm_groups": [
    {
      "min_count": 2,
      "min_grade": "A",
      "subjects": ["BIOLOGY", "CHEMISTRY", "PHYSICS", "MATH_M", "MATH_T"]
    },
    {
      "min_count": 1,
      "min_grade": "A-",
      "subjects": ["BIOLOGY", "CHEMISTRY", "PHYSICS", "MATH_M", "MATH_T"]
    }
  ],
  "stpm_named_subjects": [
    { "subject": "PA", "min_grade": "C" }
  ],
  "stpm_any_subjects": {
    "min_count": 2,
    "min_grade": "C",
    "exclude_already_counted": true
  },

  "spm_groups": [
    {
      "min_count": 4,
      "min_grade": "B",
      "subjects": ["BIOLOGY_SPM", "CHEMISTRY_SPM", "PHYSICS_SPM", "MATH"]
    },
    {
      "min_count": 1,
      "min_grade": "B",
      "subjects": null,
      "exclude": ["EKONOMI", "PERNIAGAAN", "PRINSIP_PERAKAUNAN", ...]
    }
  ],
  "spm_named_subjects": [
    { "subject": "BM", "min_grade": "C" },
    { "subject": "SEJARAH", "min_grade": "E" }
  ],

  "min_muet_band": 4.0,
  "req_interview": true,
  "no_colorblind": false,
  "req_medical_fitness": true,
  "req_malaysian": true,
  "req_bumiputera": false,
  "req_male": false,
  "req_female": false,
  "single": false,
  "no_disability": true,

  "atau_groups": null,
  "catatan": "Disahkan sihat daripada ketidakupayaan fizikal...",
  "parse_warnings": []
}
```

Key design decisions:
- **`stpm_groups` is a LIST** — supports multiple grade thresholds (Bug 1 fix)
- **`stpm_named_subjects` is separate** — individual subject requirements (e.g., "Gred C in PA") are NOT mixed into groups
- **`stpm_any_subjects`** — "mana-mana N subjects" with optional exclusion flag
- **`spm_groups` is a LIST** — supports multiple SPM grade groups (Bug 3 fix)
- **`spm_groups[].exclude`** — exclusion list support (Bug 4 fix)
- **`subjects` are scoped per `<li>` block** — no cross-contamination (Bug 2 fix)
- **`raw_html` preserved** — enables re-validation without re-scraping
- **`parse_warnings`** — flags anything the parser couldn't handle confidently

### Django Model Changes

The `StpmRequirement` model's JSONFields change from single dict to list:

```python
# BEFORE (current — broken)
stpm_subject_group = JSONField(null=True)  # {"min_count": 2, "min_grade": "A", "subjects": [...]}

# AFTER (fixed)
stpm_subject_group = JSONField(null=True)  # [{"min_count": 2, "min_grade": "A", "subjects": [...]}, ...]
spm_subject_group = JSONField(null=True)   # [{"min_count": 4, "min_grade": "B", "subjects": [...]}, ...]
```

New boolean fields:
```python
req_male = BooleanField(default=False)
req_female = BooleanField(default=False)
single = BooleanField(default=False)
no_disability = BooleanField(default=False)
```

No DB migration needed for JSON structure change (JSONField is schema-less). Migration needed only for new boolean fields.

### Subject Key Registry

Canonical keys used across the pipeline. Must match the engine's existing key maps.

**STPM subjects:**
```
PA, MATH_T, MATH_M, PHYSICS, CHEMISTRY, BIOLOGY, ICT,
ECONOMICS, ACCOUNTING, BUSINESS, PENGAJIAN_PERNIAGAAN,
GEOGRAFI, SEJARAH, KESUSASTERAAN_MELAYU, BAHASA_MELAYU,
BAHASA_CINA, BAHASA_TAMIL, BAHASA_ARAB, SENI_VISUAL,
SYARIAH, USULUDDIN, TASAWWUR_ISLAM, PENDIDIKAN_ISLAM
```

**SPM subjects:**
```
BM, BI, MATH, ADD_MATH, SEJARAH, PHYSICS_SPM, CHEMISTRY_SPM,
BIOLOGY_SPM, SCIENCE_SPM, PENDIDIKAN_ISLAM, PENDIDIKAN_MORAL,
GEOGRAFI_SPM, EKONOMI_SPM, PRINSIP_PERAKAUNAN_SPM,
PERDAGANGAN_SPM, SAINS_KOMPUTER_SPM, LUKISAN_KEJURUTERAAN_SPM,
BAHASA_ARAB_SPM, BAHASA_CINA_SPM, BAHASA_TAMIL_SPM
```

These must be defined in one place (`subject_keys.py`) and imported by all stages.

---

## Sprint Plan

This work spans **5 sprints**.

### Sprint 1: Parser Rewrite (Stage 1 tool)
Build the new HTML parser with full test coverage. Tasks 1–9.

### Sprint 2: Fixture Generator + Schema Migration (Stage 2 tool + Django changes)
Convert structured JSON to Django fixtures, update the model, update downstream code. Tasks 10–13.

### Sprint 3: Validator + Workflow (Stage 3 tool + workflow doc)
Build the audit tool and write the reusable workflow. Tasks 14–16.

### Sprint 4: Data Load + End-to-End Verification
Load the new data, verify against source, run full test suite. Task 15 (load + verify).

### Sprint 5: Scraper Rewrite (Stage 0 tool) — for next year's refresh
Build the Playwright-based detail-page scraper that handles the dynamic Syarat Khas tab. Tasks 17–19.

---

## Sprint 1: Parser Rewrite

### Task 1: Set up project structure and subject key registry

**Files:**
- Create: `Settings/_tools/stpm_requirements/subject_keys.py`
- Create: `Settings/_tools/stpm_requirements/__init__.py`

**Step 1: Create the subject key registry**

```python
# Settings/_tools/stpm_requirements/subject_keys.py
"""
Canonical subject keys for STPM requirements pipeline.
Single source of truth — imported by parser, fixture generator, and validator.
"""

# STPM subject display name → canonical key
STPM_SUBJECT_MAP = {
    # English names (as they appear in MOHE HTML)
    'Biology': 'BIOLOGY',
    'Chemistry': 'CHEMISTRY',
    'Physics': 'PHYSICS',
    'Mathematics T': 'MATH_T',
    'Mathematics M': 'MATH_M',
    'Mathematics': 'MATH_T',  # ambiguous, default to T
    'Information and Communications Technology': 'ICT',
    'Pengajian Am': 'PA',
    # Malay names
    'Biologi': 'BIOLOGY',
    'Kimia': 'CHEMISTRY',
    'Fizik': 'PHYSICS',
    'Matematik T': 'MATH_T',
    'Matematik M': 'MATH_M',
    'Matematik': 'MATH_T',
    'Ekonomi': 'ECONOMICS',
    'Perakaunan': 'ACCOUNTING',
    'Pengajian Perniagaan': 'BUSINESS',
    'Geografi': 'GEOGRAFI',
    'Sejarah': 'SEJARAH',
    'Kesusasteraan Melayu': 'KESUSASTERAAN_MELAYU',
    'Kesusasteraan Melayu Komunikatif': 'KESUSASTERAAN_MELAYU',
    'Bahasa Melayu': 'BAHASA_MELAYU',
    'Bahasa Cina': 'BAHASA_CINA',
    'Bahasa Tamil': 'BAHASA_TAMIL',
    'Bahasa Arab': 'BAHASA_ARAB',
    'Seni Visual': 'SENI_VISUAL',
    'Syariah': 'SYARIAH',
    'Usuluddin': 'USULUDDIN',
    'Tasawwur Islam': 'TASAWWUR_ISLAM',
    'Pendidikan Islam': 'PENDIDIKAN_ISLAM',
    # Combined / slash patterns
    'Physics / Mathematics M / Mathematics T': ['PHYSICS', 'MATH_M', 'MATH_T'],
    'Physics / Mathematics M': ['PHYSICS', 'MATH_M'],
    'Physics / Mathematics T': ['PHYSICS', 'MATH_T'],
    'Mathematics M / Mathematics T': ['MATH_M', 'MATH_T'],
}

# SPM subject display name → canonical key
SPM_SUBJECT_MAP = {
    'Bahasa Melayu': 'BM',
    'Bahasa Inggeris': 'BI',
    'Matematik': 'MATH',
    'Matematik Tambahan': 'ADD_MATH',
    'Sejarah': 'SEJARAH',
    'Fizik': 'PHYSICS_SPM',
    'Kimia': 'CHEMISTRY_SPM',
    'Biologi': 'BIOLOGY_SPM',
    'Sains': 'SCIENCE_SPM',
    'Sains Komputer': 'SAINS_KOMPUTER_SPM',
    'Pendidikan Islam': 'PENDIDIKAN_ISLAM_SPM',
    'Pendidikan Moral': 'PENDIDIKAN_MORAL_SPM',
    'Geografi': 'GEOGRAFI_SPM',
    'Ekonomi': 'EKONOMI_SPM',
    'Perniagaan': 'PERNIAGAAN_SPM',
    'Prinsip Perakaunan': 'PRINSIP_PERAKAUNAN_SPM',
    'Perdagangan': 'PERDAGANGAN_SPM',
    'Lukisan Kejuruteraan': 'LUKISAN_KEJURUTERAAN_SPM',
    'Bahasa Arab': 'BAHASA_ARAB_SPM',
    'Bahasa Cina': 'BAHASA_CINA_SPM',
    'Bahasa Tamil': 'BAHASA_TAMIL_SPM',
}

# Malay number words → integers
MALAY_NUMBERS = {
    'SATU': 1, 'DUA': 2, 'TIGA': 3, 'EMPAT': 4,
    'LIMA': 5, 'ENAM': 6, 'TUJUH': 7, 'LAPAN': 8,
    'SEMBILAN': 9, 'SEPULUH': 10,
}

# Valid STPM grades in order (best to worst)
STPM_GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'F']

# Valid SPM grades in order (best to worst)
SPM_GRADE_ORDER = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']


def normalise_stpm_subject(name: str) -> str | list[str]:
    """Convert a display name to canonical key(s). Returns str or list for slash-separated subjects."""
    name = name.strip()
    if name in STPM_SUBJECT_MAP:
        return STPM_SUBJECT_MAP[name]
    # Try case-insensitive
    for display, key in STPM_SUBJECT_MAP.items():
        if display.lower() == name.lower():
            return key
    return f'UNKNOWN:{name}'


def normalise_spm_subject(name: str) -> str:
    """Convert an SPM display name to canonical key."""
    name = name.strip()
    if name in SPM_SUBJECT_MAP:
        return SPM_SUBJECT_MAP[name]
    for display, key in SPM_SUBJECT_MAP.items():
        if display.lower() == name.lower():
            return key
    return f'UNKNOWN:{name}'
```

**Step 2: Create empty `__init__.py`**

```python
# Settings/_tools/stpm_requirements/__init__.py
```

**Step 3: Commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: add subject key registry for STPM requirements pipeline"
```

---

### Task 2: Build the HTML parser — `<li>` block splitter

The critical fix: parse each `<li>` independently, not the entire HTML.

**Files:**
- Create: `Settings/_tools/stpm_requirements/parse_stpm_html.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_parse_li_blocks.py`

**Step 1: Write tests for `<li>` block splitting**

```python
# Settings/_tools/stpm_requirements/tests/test_parse_li_blocks.py
import pytest
from parse_stpm_html import split_li_blocks

# UM6724001 — dentistry, complex requirements
SAMPLE_HTML_COMPLEX = '''<ol style="padding-left: 2em;">
<li style="padding-left: .3em; margin-bottom:8px;"> Mendapat sekurang-kurangnya <b>PNGK 3.80</b> pada peringkat <b>STPM</b>. </li>
<li style="padding-left: .3em; margin-bottom:8px;"> Mendapat sekurang-kurangnya Gred <b>A</b> dalam <b>DUA (2)</b> mata pelajaran di peringkat DAN <b>A-</b> dalam <b>SATU (1)</b> mata pelajaran di peringkat <b>STPM</b> : <div><table><tr><td>&#8226;</td><td>Biology</td></tr><tr><td>&#8226;</td><td>Chemistry</td></tr><tr><td>&#8226;</td><td>Physics / Mathematics M / Mathematics T</td></tr></table></div></li>
<li style="padding-left: .3em; margin-bottom:8px;"> Mendapat sekurang-kurangnya Gred <b>B</b> dalam <b>EMPAT (4)</b> mata pelajaran di peringkat <b>SPM</b> : <div><table><tr><td>&#8226;</td><td>Biologi</td></tr><tr><td>&#8226;</td><td>Kimia</td></tr><tr><td>&#8226;</td><td>Fizik</td></tr><tr><td>&#8226;</td><td>Matematik</td></tr></table></div></li>
<li style="padding-left: .3em; margin-bottom:8px;"> MUET BAND 4.0 </li>
<li style="padding-left: .3em; margin-bottom:8px;"><b>Lulus ujian dan / atau temu duga</b></li>
</ol>'''


def test_split_li_blocks_count():
    blocks = split_li_blocks(SAMPLE_HTML_COMPLEX)
    assert len(blocks) == 5


def test_split_li_blocks_preserves_inner_html():
    blocks = split_li_blocks(SAMPLE_HTML_COMPLEX)
    # First block should contain PNGK
    assert 'PNGK 3.80' in blocks[0]
    # Second block should contain both grade thresholds AND subjects
    assert 'Biology' in blocks[1]
    assert 'Chemistry' in blocks[1]
    # Third block should contain SPM subjects
    assert 'Biologi' in blocks[2]
    assert 'Kimia' in blocks[2]


def test_split_li_blocks_isolates_subjects():
    """Bug 2 fix: each block's subjects must not leak into other blocks."""
    blocks = split_li_blocks(SAMPLE_HTML_COMPLEX)
    # Block 1 (STPM) should NOT contain SPM subjects
    assert 'Biologi' not in blocks[1]  # Biologi is SPM Malay name
    # Block 2 (SPM) should NOT contain STPM subjects
    assert 'Biology' not in blocks[2]  # Biology is STPM English name
```

**Step 2: Run tests to verify they fail**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/test_parse_li_blocks.py -v`
Expected: FAIL (ImportError — module doesn't exist yet)

**Step 3: Implement `split_li_blocks()`**

```python
# In parse_stpm_html.py (start of file)
"""
Stage 1: Parse STPM requirements HTML into structured JSON.

Input:  CSV with raw HTML in 'requirements' column
Output: JSON file with one structured object per course

Usage:
    python parse_stpm_html.py <input_csv> [<input_csv_2> ...] -o <output.json>
"""
import csv
import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString
from subject_keys import (
    normalise_stpm_subject, normalise_spm_subject,
    MALAY_NUMBERS, STPM_GRADE_ORDER, SPM_GRADE_ORDER,
)


def split_li_blocks(html: str) -> list[str]:
    """Split HTML into individual <li> blocks. Each block is self-contained."""
    soup = BeautifulSoup(html, 'html.parser')
    blocks = []
    for li in soup.find_all('li'):
        blocks.append(str(li))
    return blocks
```

**Step 4: Run tests to verify they pass**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/test_parse_li_blocks.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: split_li_blocks — isolate each requirement item"
```

---

### Task 3: Build the `<li>` block classifier

Each `<li>` block is one of these types: PNGK, STPM_GROUP, STPM_NAMED, STPM_ANY, SPM_GROUP, SPM_NAMED, MUET, INTERVIEW, ATAU, CATATAN, UNKNOWN.

**Files:**
- Modify: `Settings/_tools/stpm_requirements/parse_stpm_html.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_classify_block.py`

**Step 1: Write tests for block classification**

```python
# Settings/_tools/stpm_requirements/tests/test_classify_block.py
import pytest
from parse_stpm_html import classify_block

def test_pngk_block():
    html = '<li> Mendapat sekurang-kurangnya <b>PNGK 3.80</b> pada peringkat <b>STPM</b>. </li>'
    assert classify_block(html) == 'PNGK'

def test_stpm_group_block():
    html = '<li> Mendapat sekurang-kurangnya Gred <b>C</b> dalam <b>DUA (2)</b> mata pelajaran di peringkat <b>STPM</b> : <div><table>...</table></div></li>'
    assert classify_block(html) == 'STPM_GROUP'

def test_stpm_multi_tier_block():
    """A in 2 AND A- in 1 — still classified as STPM_GROUP."""
    html = '<li> Gred <b>A</b> dalam <b>DUA (2)</b> mata pelajaran di peringkat DAN <b>A-</b> dalam <b>SATU (1)</b> mata pelajaran di peringkat <b>STPM</b> : <div><table>...</table></div></li>'
    assert classify_block(html) == 'STPM_GROUP'

def test_stpm_any_block():
    html = '<li> Gred <b>C</b> dalam mana-mana <b>DUA (2)</b> mata pelajaran pada peringkat <b>STPM</b>. </li>'
    assert classify_block(html) == 'STPM_ANY'

def test_stpm_remainder_block():
    html = '<li> Gred <b>C</b> dalam mana-mana <b>SATU (1)</b> mata pelajaran yang belum diambil kira pada peringkat <b>STPM</b> </li>'
    assert classify_block(html) == 'STPM_ANY'

def test_stpm_named_block():
    html = '<li> Gred <b>B</b> dalam mata pelajaran <b>Mathematics T</b> di peringkat <b>STPM</b>. </li>'
    assert classify_block(html) == 'STPM_NAMED'

def test_spm_group_block():
    html = '<li> Gred <b>B</b> dalam <b>EMPAT (4)</b> mata pelajaran di peringkat <b>SPM</b> : <div><table>...</table></div></li>'
    assert classify_block(html) == 'SPM_GROUP'

def test_spm_named_block():
    html = '<li> Gred <b>C</b> dalam mata pelajaran <b>Matematik</b> di peringkat <b>SPM</b>. </li>'
    assert classify_block(html) == 'SPM_NAMED'

def test_spm_exclusion_block():
    html = '<li> Gred <b>B</b> dalam <b>SATU (1)</b> mata pelajaran pada peringkat <b>SPM</b> tidak termasuk mata pelajaran berikut : <div><table>...</table></div></li>'
    assert classify_block(html) == 'SPM_GROUP'

def test_muet_block():
    html = '<li> Mendapat sekurang-kurangnya <b>BAND 2.0</b> dalam <b>Malaysian University English Test (MUET)</b> </li>'
    assert classify_block(html) == 'MUET'

def test_interview_block():
    html = '<li><b>Lulus ujian dan / atau temu duga</b> yang ditetapkan oleh Universiti Awam. </li>'
    assert classify_block(html) == 'INTERVIEW'
```

**Step 2: Run tests to verify they fail**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/test_classify_block.py -v`
Expected: FAIL

**Step 3: Implement `classify_block()`**

Add to `parse_stpm_html.py`:

```python
def classify_block(li_html: str) -> str:
    """Classify a single <li> block by its requirement type."""
    soup = BeautifulSoup(li_html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    text_upper = text.upper()

    # PNGK (CGPA)
    if re.search(r'PNGK\s+\d', text):
        return 'PNGK'

    # MUET
    if 'MUET' in text_upper or 'BAND' in text_upper:
        return 'MUET'

    # Interview
    if 'temu duga' in text.lower() or 'temuduga' in text.lower():
        return 'INTERVIEW'

    # Determine level (STPM or SPM)
    is_stpm = 'STPM' in text_upper or 'peringkat' in text.lower()
    is_spm = 'SPM' in text_upper

    # "mana-mana" or "belum diambil kira" = ANY pattern
    if 'mana-mana' in text.lower() or 'belum diambil kira' in text.lower():
        if is_spm and not is_stpm:
            return 'SPM_ANY'
        return 'STPM_ANY'

    # Has a subject list (table inside) = GROUP pattern
    has_table = soup.find('table') is not None
    # Has count pattern like "DUA (2)" or "EMPAT (4)"
    has_count = bool(re.search(r'(?:SATU|DUA|TIGA|EMPAT|LIMA|ENAM)\s*\(\d+\)', text_upper))

    if has_count and (has_table or 'tidak termasuk' in text.lower()):
        if is_spm and not is_stpm:
            return 'SPM_GROUP'
        return 'STPM_GROUP'

    # Named subject ("dalam mata pelajaran <b>NAME</b>")
    if re.search(r'mata pelajaran\s*<b>', li_html, re.IGNORECASE) or \
       re.search(r'dalam mata pelajaran\b', text, re.IGNORECASE):
        if is_spm and not is_stpm:
            return 'SPM_NAMED'
        return 'STPM_NAMED'

    # Count without table (generic group)
    if has_count:
        if is_spm and not is_stpm:
            return 'SPM_GROUP'
        return 'STPM_GROUP'

    return 'UNKNOWN'
```

**Step 4: Run tests to verify they pass**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/test_classify_block.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: classify_block — categorise each requirement li block"
```

---

### Task 4: Build extractors for each block type

This is the core parsing logic. One extractor function per block type.

**Files:**
- Modify: `Settings/_tools/stpm_requirements/parse_stpm_html.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_extractors.py`

**Step 1: Write tests for each extractor**

```python
# Settings/_tools/stpm_requirements/tests/test_extractors.py
import pytest
from parse_stpm_html import (
    extract_pngk, extract_muet, extract_stpm_group,
    extract_stpm_named, extract_stpm_any, extract_spm_group,
    extract_spm_named, extract_subjects_from_table,
)


class TestExtractPngk:
    def test_basic(self):
        html = '<li> Mendapat sekurang-kurangnya <b>PNGK 3.80</b> pada peringkat <b>STPM</b>. </li>'
        assert extract_pngk(html) == 3.80

    def test_integer(self):
        html = '<li> PNGK <b>PNGK 2.00</b> </li>'
        assert extract_pngk(html) == 2.00


class TestExtractMuet:
    def test_band_decimal(self):
        html = '<li> <b>BAND 4.0</b> dalam <b>MUET</b> </li>'
        assert extract_muet(html) == 4.0

    def test_band_integer(self):
        html = '<li> <b>BAND 2</b> dalam <b>MUET</b> </li>'
        assert extract_muet(html) == 2.0


class TestExtractSubjectsFromTable:
    def test_simple_subjects(self):
        html = '''<table><tr><td>&#8226;</td><td>Biology</td></tr>
                  <tr><td>&#8226;</td><td>Chemistry</td></tr></table>'''
        result = extract_subjects_from_table(html, level='stpm')
        assert result == ['BIOLOGY', 'CHEMISTRY']

    def test_slash_subjects_expand(self):
        """Physics / Mathematics M / Mathematics T should expand to 3 keys."""
        html = '<table><tr><td>&#8226;</td><td>Physics / Mathematics M / Mathematics T</td></tr></table>'
        result = extract_subjects_from_table(html, level='stpm')
        assert set(result) == {'PHYSICS', 'MATH_M', 'MATH_T'}

    def test_spm_subjects(self):
        html = '<table><tr><td>&#8226;</td><td>Biologi</td></tr><tr><td>&#8226;</td><td>Kimia</td></tr></table>'
        result = extract_subjects_from_table(html, level='spm')
        assert result == ['BIOLOGY_SPM', 'CHEMISTRY_SPM']


class TestExtractStpmGroup:
    def test_single_tier(self):
        html = '<li> Gred <b>C</b> dalam <b>DUA (2)</b> mata pelajaran di peringkat <b>STPM</b> : <div><table><tr><td>&#8226;</td><td>Biology</td></tr><tr><td>&#8226;</td><td>Chemistry</td></tr><tr><td>&#8226;</td><td>Physics</td></tr></table></div></li>'
        result = extract_stpm_group(html)
        assert len(result) == 1
        assert result[0]['min_count'] == 2
        assert result[0]['min_grade'] == 'C'
        assert set(result[0]['subjects']) == {'BIOLOGY', 'CHEMISTRY', 'PHYSICS'}

    def test_multi_tier(self):
        """Bug 1 fix: A in 2 AND A- in 1 → two group objects."""
        html = '<li> Gred <b>A</b> dalam <b>DUA (2)</b> mata pelajaran di peringkat DAN <b>A-</b> dalam <b>SATU (1)</b> mata pelajaran di peringkat <b>STPM</b> : <div><table><tr><td>&#8226;</td><td>Biology</td></tr><tr><td>&#8226;</td><td>Chemistry</td></tr><tr><td>&#8226;</td><td>Physics / Mathematics M / Mathematics T</td></tr></table></div></li>'
        result = extract_stpm_group(html)
        assert len(result) == 2
        assert result[0] == {'min_count': 2, 'min_grade': 'A', 'subjects': ['BIOLOGY', 'CHEMISTRY', 'PHYSICS', 'MATH_M', 'MATH_T']}
        assert result[1] == {'min_count': 1, 'min_grade': 'A-', 'subjects': ['BIOLOGY', 'CHEMISTRY', 'PHYSICS', 'MATH_M', 'MATH_T']}


class TestExtractStpmNamed:
    def test_single_named(self):
        html = '<li> Gred <b>B</b> dalam mata pelajaran <b>Mathematics T</b> di peringkat <b>STPM</b>. </li>'
        result = extract_stpm_named(html)
        assert result == {'subject': 'MATH_T', 'min_grade': 'B'}


class TestExtractStpmAny:
    def test_any_subjects(self):
        html = '<li> Gred <b>C</b> dalam mana-mana <b>DUA (2)</b> mata pelajaran pada peringkat <b>STPM</b>. </li>'
        result = extract_stpm_any(html)
        assert result == {'min_count': 2, 'min_grade': 'C', 'exclude_already_counted': False}

    def test_remainder(self):
        html = '<li> Gred <b>C</b> dalam mana-mana <b>SATU (1)</b> mata pelajaran yang belum diambil kira pada peringkat <b>STPM</b> </li>'
        result = extract_stpm_any(html)
        assert result == {'min_count': 1, 'min_grade': 'C', 'exclude_already_counted': True}


class TestExtractSpmGroup:
    def test_inclusion_group(self):
        html = '<li> Gred <b>B</b> dalam <b>EMPAT (4)</b> mata pelajaran di peringkat <b>SPM</b> : <div><table><tr><td>&#8226;</td><td>Biologi</td></tr><tr><td>&#8226;</td><td>Kimia</td></tr><tr><td>&#8226;</td><td>Fizik</td></tr><tr><td>&#8226;</td><td>Matematik</td></tr></table></div></li>'
        result = extract_spm_group(html)
        assert len(result) == 1
        assert result[0]['min_count'] == 4
        assert result[0]['min_grade'] == 'B'
        assert set(result[0]['subjects']) == {'BIOLOGY_SPM', 'CHEMISTRY_SPM', 'PHYSICS_SPM', 'MATH'}
        assert 'exclude' not in result[0]

    def test_exclusion_group(self):
        """Bug 4 fix: 'tidak termasuk' → exclude list."""
        html = '<li> Gred <b>B</b> dalam <b>SATU (1)</b> mata pelajaran pada peringkat <b>SPM</b> tidak termasuk mata pelajaran berikut : <div><table><tr><td>&#8226;</td><td>Ekonomi</td></tr><tr><td>&#8226;</td><td>Perniagaan</td></tr></table></div></li>'
        result = extract_spm_group(html)
        assert len(result) == 1
        assert result[0]['min_count'] == 1
        assert result[0]['min_grade'] == 'B'
        assert result[0]['subjects'] is None  # any subject
        assert set(result[0]['exclude']) == {'EKONOMI_SPM', 'PERNIAGAAN_SPM'}
```

**Step 2: Run tests to verify they fail**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/test_extractors.py -v`
Expected: FAIL

**Step 3: Implement all extractors**

Add to `parse_stpm_html.py`:

```python
def extract_subjects_from_table(html: str, level: str = 'stpm') -> list[str]:
    """Extract subject keys from a <table> inside one <li> block.

    Handles slash-separated subjects (e.g., 'Physics / Mathematics M / Mathematics T')
    by expanding them into individual keys.
    """
    soup = BeautifulSoup(html, 'html.parser')
    subjects = []
    normalise = normalise_stpm_subject if level == 'stpm' else normalise_spm_subject

    for row in soup.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) >= 2:
            raw_name = cells[-1].get_text(strip=True)
            if not raw_name:
                continue
            # Check for slash-separated (STPM only)
            if level == 'stpm' and ' / ' in raw_name:
                # Try the full string first (it might be a known combo)
                result = normalise_stpm_subject(raw_name)
                if isinstance(result, list):
                    subjects.extend(result)
                else:
                    # Fall back to splitting
                    for part in raw_name.split(' / '):
                        key = normalise_stpm_subject(part.strip())
                        if isinstance(key, list):
                            subjects.extend(key)
                        else:
                            subjects.append(key)
            else:
                key = normalise(raw_name)
                if isinstance(key, list):
                    subjects.extend(key)
                else:
                    subjects.append(key)
    return subjects


def extract_pngk(li_html: str) -> float:
    """Extract PNGK (CGPA) value from a PNGK-type <li> block."""
    match = re.search(r'PNGK\s+(\d+\.?\d*)', li_html)
    if match:
        return float(match.group(1))
    return 2.0  # default


def extract_muet(li_html: str) -> float:
    """Extract MUET band from a MUET-type <li> block."""
    match = re.search(r'BAND\s+(\d+\.?\d*)', li_html, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return 1.0  # default


def _extract_grade_count_pairs(text: str) -> list[tuple[str, int]]:
    """Extract all (grade, count) pairs from text.

    Handles patterns like:
    - 'Gred A dalam DUA (2)' → [('A', 2)]
    - 'Gred A dalam DUA (2) ... DAN A- dalam SATU (1)' → [('A', 2), ('A-', 1)]
    """
    pairs = []
    # Pattern: Gred <grade> dalam <word> (<digit>)
    # The grade may be in <b> tags or plain text
    pattern = r'Gred\s+(?:<b>)?([A-Z][+-]?)(?:</b>)?\s+dalam\s+(?:<b>)?(\w+)\s*\((\d+)\)(?:</b>)?'
    for m in re.finditer(pattern, text, re.IGNORECASE):
        grade = m.group(1)
        count = int(m.group(3))
        pairs.append((grade, count))

    if not pairs:
        # Try alternative: just <b>GRADE</b> ... <b>WORD (N)</b>
        pattern2 = r'<b>([A-Z][+-]?)</b>\s+dalam\s+<b>(\w+)\s*\((\d+)\)</b>'
        for m in re.finditer(pattern2, text, re.IGNORECASE):
            grade = m.group(1)
            count = int(m.group(3))
            pairs.append((grade, count))

    return pairs


def extract_stpm_group(li_html: str) -> list[dict]:
    """Extract STPM subject group(s) from one <li> block.

    Returns a LIST of groups — handles multi-tier requirements (Bug 1 fix).
    All groups share the same subject pool (from the table in this block).
    """
    subjects = extract_subjects_from_table(li_html, level='stpm')
    pairs = _extract_grade_count_pairs(li_html)

    if not pairs:
        return []

    groups = []
    for grade, count in pairs:
        groups.append({
            'min_count': count,
            'min_grade': grade,
            'subjects': subjects if subjects else None,
        })
    return groups


def extract_stpm_named(li_html: str) -> dict | None:
    """Extract a named STPM subject requirement."""
    soup = BeautifulSoup(li_html, 'html.parser')
    text = soup.get_text(' ', strip=True)

    # Grade
    grade_match = re.search(r'Gred\s+([A-Z][+-]?)', text, re.IGNORECASE)
    if not grade_match:
        return None
    grade = grade_match.group(1)

    # Subject name — text inside <b> after "mata pelajaran"
    subject_match = re.search(r'mata pelajaran\s*<b>([^<]+)</b>', li_html, re.IGNORECASE)
    if not subject_match:
        # Try: mata pelajaran <b>NAME</b>
        subject_match = re.search(r'mata pelajaran\s+([A-Z][a-z][\w\s]+)', text)
    if not subject_match:
        return None

    subject_name = subject_match.group(1).strip()
    key = normalise_stpm_subject(subject_name)
    if isinstance(key, list):
        key = key[0]  # Take first if slash-separated

    return {'subject': key, 'min_grade': grade}


def extract_stpm_any(li_html: str) -> dict | None:
    """Extract 'any N subjects' requirement."""
    soup = BeautifulSoup(li_html, 'html.parser')
    text = soup.get_text(' ', strip=True)

    pairs = _extract_grade_count_pairs(li_html)
    if not pairs:
        # Try to extract from plain text
        match = re.search(r'([A-Z][+-]?)\s+.*?(\w+)\s*\((\d+)\)', text)
        if match:
            pairs = [(match.group(1), int(match.group(3)))]

    if not pairs:
        return None

    grade, count = pairs[0]
    exclude_already = 'belum diambil kira' in text.lower() or 'belum dikira' in text.lower()

    return {
        'min_count': count,
        'min_grade': grade,
        'exclude_already_counted': exclude_already,
    }


def extract_spm_group(li_html: str) -> list[dict]:
    """Extract SPM subject group(s) from one <li> block.

    Handles both inclusion lists and exclusion lists ('tidak termasuk').
    """
    is_exclusion = 'tidak termasuk' in li_html.lower()
    pairs = _extract_grade_count_pairs(li_html)

    if not pairs:
        return []

    grade, count = pairs[0]

    if is_exclusion:
        excluded = extract_subjects_from_table(li_html, level='spm')
        return [{
            'min_count': count,
            'min_grade': grade,
            'subjects': None,  # any subject
            'exclude': excluded,
        }]
    else:
        subjects = extract_subjects_from_table(li_html, level='spm')
        return [{
            'min_count': count,
            'min_grade': grade,
            'subjects': subjects if subjects else None,
        }]


def extract_spm_named(li_html: str) -> dict | None:
    """Extract a named SPM subject requirement."""
    soup = BeautifulSoup(li_html, 'html.parser')
    text = soup.get_text(' ', strip=True)

    grade_match = re.search(r'Gred\s+([A-Z][+-]?)', text, re.IGNORECASE)
    if not grade_match:
        return None

    subject_match = re.search(r'mata pelajaran\s*<b>([^<]+)</b>', li_html, re.IGNORECASE)
    if not subject_match:
        return None

    key = normalise_spm_subject(subject_match.group(1).strip())
    return {'subject': key, 'min_grade': grade_match.group(1)}
```

**Step 4: Run tests to verify they pass**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/test_extractors.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: extractors for all requirement block types"
```

---

### Task 5: Build the catatan (notes) parser

The `<br><div>Catatan` section after the `<ol>` contains special conditions.

**Files:**
- Modify: `Settings/_tools/stpm_requirements/parse_stpm_html.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_catatan.py`

**Step 1: Write tests**

```python
# Settings/_tools/stpm_requirements/tests/test_catatan.py
import pytest
from parse_stpm_html import extract_catatan

def test_medical_fitness():
    html = '<span>Disahkan sihat daripada ketidakupayaan fizikal dan penyakit mental</span>'
    result = extract_catatan(html)
    assert result['req_medical_fitness'] is True
    assert result['no_disability'] is True

def test_colorblind():
    html = '<span>Calon yang mempunyai buta warna tidak layak</span>'
    result = extract_catatan(html)
    assert result['no_colorblind'] is True

def test_no_conditions():
    html = '<span>Maklumat lanjut di laman web universiti.</span>'
    result = extract_catatan(html)
    assert result['no_colorblind'] is False
    assert result['req_medical_fitness'] is False
```

**Step 2: Run to verify failure, then implement**

```python
def extract_catatan(html: str) -> dict:
    """Extract special conditions from Catatan (notes) section."""
    text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True).lower()
    return {
        'no_colorblind': 'buta warna' in text,
        'req_medical_fitness': 'sihat' in text or 'kesihatan' in text or 'medical' in text.lower(),
        'no_disability': 'ketidakupayaan fizikal' in text or 'kecacatan' in text,
        'req_male': 'lelaki sahaja' in text,
        'req_female': 'perempuan sahaja' in text or 'wanita sahaja' in text,
        'single': 'belum berkahwin' in text,
        'raw_text': BeautifulSoup(html, 'html.parser').get_text(' ', strip=True),
    }
```

**Step 3: Run tests, commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: catatan parser for special conditions"
```

---

### Task 6: Build the ATAU (alternative pathway) handler

Some courses have `<p><b>ATAU</b></p>` blocks separating two valid subject combinations.

**Files:**
- Modify: `Settings/_tools/stpm_requirements/parse_stpm_html.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_atau.py`

**Step 1: Write tests**

```python
# Settings/_tools/stpm_requirements/tests/test_atau.py
import pytest
from parse_stpm_html import split_atau_sections

def test_no_atau():
    html = '<ol><li>Req 1</li><li>Req 2</li></ol>'
    sections = split_atau_sections(html)
    assert len(sections) == 1

def test_single_atau():
    html = '<ol><li>Req 1</li></ol><p><b>ATAU</b></p><ol><li>Alt Req 1</li></ol>'
    sections = split_atau_sections(html)
    assert len(sections) == 2
    assert 'Req 1' in sections[0]
    assert 'Alt Req 1' in sections[1]
```

**Step 2: Implement**

```python
def split_atau_sections(html: str) -> list[str]:
    """Split HTML at ATAU markers into alternative requirement sections."""
    # Split on <p><b>ATAU</b></p> or variants
    parts = re.split(r'<p[^>]*>\s*<b>\s*ATAU\s*</b>\s*</p>', html, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]
```

**Step 3: Run tests, commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: ATAU section splitter for alternative pathways"
```

---

### Task 7: Assemble the full course parser

Wire all extractors together into `parse_course()` → one structured dict per course.

**Files:**
- Modify: `Settings/_tools/stpm_requirements/parse_stpm_html.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_parse_course.py`

**Step 1: Write integration test using UM6724001**

```python
# Settings/_tools/stpm_requirements/tests/test_parse_course.py
import pytest
from parse_stpm_html import parse_course

UM6724001_HTML = '''<ol style="padding-left: 2em; line-height: 1.5rem;" style="list-style-type:decimal;"><li style="padding-left: .3em; margin-bottom:8px;"> Mendapat sekurang-kurangnya <b>PNGK 3.80</b> pada peringkat <b>STPM</b>. </li><li style="padding-left: .3em; margin-bottom:8px;"> Mendapat sekurang-kurangnya Gred <b>A</b> dalam <b>DUA (2)</b> mata pelajaran di peringkat DAN <b>A-</b> dalam <b>SATU (1)</b> mata pelajaran di peringkat <b>STPM</b> : <div style="border:1px solid rgba(0, 0, 0, 0.125); border-radius:0.25rem; padding:0.25rem; background-color: #e9ecef52 !important; margin-top:5px;"><table cellpadding="2" width="100%"><tr><td style="vertical-align:top;">&#8226;</td><td style="vertical-align:top; width:95%">Biology</td></tr><tr><td style="vertical-align:top;">&#8226;</td><td style="vertical-align:top; width:95%">Chemistry</td></tr><tr><td style="vertical-align:top;">&#8226;</td><td style="vertical-align:top; width:95%">Physics / Mathematics M / Mathematics T</td></tr></table></div></li><li style="padding-left: .3em; margin-bottom:8px;"> Mendapat sekurang-kurangnya Gred <b>B</b> dalam <b>EMPAT (4)</b> mata pelajaran di peringkat <b>SPM</b> : <div style="border:1px solid rgba(0, 0, 0, 0.125); border-radius:0.25rem; padding:0.25rem; background-color: #e9ecef52 !important; margin-top:5px;"><table cellpadding="2" width="100%"><tr><td style="vertical-align:top;">&#8226;</td><td style="vertical-align:top; width:95%">Biologi</td></tr><tr><td style="vertical-align:top;">&#8226;</td><td style="vertical-align:top; width:95%">Kimia</td></tr><tr><td style="vertical-align:top;">&#8226;</td><td style="vertical-align:top; width:95%">Fizik</td></tr><tr><td style="vertical-align:top;">&#8226;</td><td style="vertical-align:top; width:95%">Matematik</td></tr></table></div></li><li style="padding-left: .3em; margin-bottom:8px;"> Mendapat sekurang-kurangnya Gred <b>B</b> dalam <b>SATU (1)</b> mata pelajaran pada peringkat <b>SPM</b> tidak termasuk mata pelajaran berikut : <div><table cellpadding="2" width="100%"><tr><td>&#8226;</td><td>Ekonomi</td></tr><tr><td>&#8226;</td><td>Perniagaan</td></tr></table></div></li><li style="padding-left: .3em; margin-bottom:8px;"> Mendapat sekurang-kurangnya <b>BAND 4.0</b> dalam <b>Malaysian University English Test (MUET)</b> untuk keputusan yang diperolehi mulai sesi 1 Tahun 2021. </li><li style="padding-left: .3em; margin-bottom:8px;"><b>Lulus ujian dan / atau temu duga</b> yang ditetapkan oleh Universiti Awam. </li><br><div style="line-height: 1.5rem; font-weight:bold;">Catatan :</div><span style="color:#000000">Disahkan sihat daripada ketidakupayaan fizikal dan penyakit mental yang serius.</span></ol>'''

UM6724001_ROW = {
    'code': 'UM6724001',
    'program_name': 'SARJANA MUDA PEMBEDAHAN PERGIGIAN',
    'university': 'Universiti Malaya',
    'interview': 'Ya',
    'bumiputera': '',
    'requirements': UM6724001_HTML,
}


class TestParseCourseUM6724001:
    def setup_method(self):
        self.result = parse_course(UM6724001_ROW, source_file='stpm_science')

    def test_basic_fields(self):
        assert self.result['course_id'] == 'UM6724001'
        assert self.result['university'] == 'Universiti Malaya'

    def test_cgpa(self):
        assert self.result['min_cgpa'] == 3.80

    def test_stpm_groups_multi_tier(self):
        """Bug 1 fix: must have 2 groups with different grades."""
        groups = self.result['stpm_groups']
        assert len(groups) == 2
        assert groups[0]['min_grade'] == 'A'
        assert groups[0]['min_count'] == 2
        assert groups[1]['min_grade'] == 'A-'
        assert groups[1]['min_count'] == 1
        # Both share same subject pool
        for g in groups:
            assert 'BIOLOGY' in g['subjects']
            assert 'CHEMISTRY' in g['subjects']
            assert 'PHYSICS' in g['subjects'] or 'MATH_T' in g['subjects']
        # Bug 2 fix: no SPM subjects contaminating STPM groups
        for g in groups:
            for s in g['subjects']:
                assert '_SPM' not in s, f"SPM subject {s} leaked into STPM group"

    def test_spm_groups(self):
        """Bug 3 fix: SPM Gred B in 4 subjects must be captured."""
        groups = self.result['spm_groups']
        assert len(groups) >= 1
        main_group = groups[0]
        assert main_group['min_count'] == 4
        assert main_group['min_grade'] == 'B'
        assert 'BIOLOGY_SPM' in main_group['subjects']
        assert 'CHEMISTRY_SPM' in main_group['subjects']

    def test_spm_exclusion_group(self):
        """Bug 4 fix: exclusion list captured."""
        groups = self.result['spm_groups']
        excl_groups = [g for g in groups if g.get('exclude')]
        assert len(excl_groups) == 1
        assert excl_groups[0]['min_count'] == 1
        assert excl_groups[0]['subjects'] is None
        assert 'EKONOMI_SPM' in excl_groups[0]['exclude']

    def test_muet(self):
        assert self.result['min_muet_band'] == 4.0

    def test_interview(self):
        assert self.result['req_interview'] is True

    def test_medical_from_catatan(self):
        assert self.result['req_medical_fitness'] is True
        assert self.result['no_disability'] is True

    def test_no_stpm_spm_subject_contamination(self):
        """Bug 2 fix: STPM groups must not contain ECONOMICS or PA from HTML blob."""
        for g in self.result['stpm_groups']:
            assert 'ECONOMICS' not in g['subjects'], "ECONOMICS leaked into STPM group"
            assert 'PA' not in g['subjects'], "PA leaked into STPM group (should be in named)"
```

**Step 2: Run to verify failure**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/test_parse_course.py -v`
Expected: FAIL

**Step 3: Implement `parse_course()`**

```python
def parse_course(row: dict, source_file: str) -> dict:
    """Parse one course's CSV row into structured requirements JSON."""
    html = row.get('requirements', '') or ''
    course_id = row.get('code', '').strip()
    warnings = []

    result = {
        'course_id': course_id,
        'program_name': row.get('program_name', '').strip(),
        'university': row.get('university', '').strip(),
        'source_file': source_file,
        'raw_html': html,
        'min_cgpa': None,
        'stpm_groups': [],
        'stpm_named_subjects': [],
        'stpm_any_subjects': None,
        'spm_groups': [],
        'spm_named_subjects': [],
        'min_muet_band': None,
        'req_interview': row.get('interview', '').strip().lower() in ('ya', 'yes', 'true', '1'),
        'no_colorblind': False,
        'req_medical_fitness': False,
        'req_malaysian': True,  # all STPM courses require citizenship
        'req_bumiputera': row.get('bumiputera', '').strip().lower() in ('ya', 'yes', 'true', '1'),
        'req_male': False,
        'req_female': False,
        'single': False,
        'no_disability': False,
        'atau_groups': None,
        'catatan': None,
        'parse_warnings': warnings,
    }

    if not html or 'HTTP Error' in html:
        warnings.append('NO_HTML')
        return result

    # Handle ATAU alternatives
    atau_sections = split_atau_sections(html)
    if len(atau_sections) > 1:
        # Parse each alternative separately
        alt_results = []
        for section in atau_sections:
            alt_row = dict(row)
            alt_row['requirements'] = section
            alt = parse_course(alt_row, source_file)
            alt_results.append(alt)
        # Use the first section as primary, store alternatives
        result = alt_results[0]
        result['atau_groups'] = [
            {
                'stpm_groups': alt['stpm_groups'],
                'stpm_named_subjects': alt['stpm_named_subjects'],
                'stpm_any_subjects': alt['stpm_any_subjects'],
                'spm_groups': alt['spm_groups'],
                'spm_named_subjects': alt['spm_named_subjects'],
            }
            for alt in alt_results[1:]
        ]
        return result

    # Extract catatan (notes after the <ol>)
    catatan_match = re.search(r'(?:Catatan|Nota)\s*:?\s*</div>(.*?)(?:</ol>|$)', html, re.DOTALL | re.IGNORECASE)
    if catatan_match:
        catatan_html = catatan_match.group(1)
        catatan = extract_catatan(catatan_html)
        result['catatan'] = catatan['raw_text']
        result['no_colorblind'] = result['no_colorblind'] or catatan['no_colorblind']
        result['req_medical_fitness'] = result['req_medical_fitness'] or catatan['req_medical_fitness']
        result['no_disability'] = result['no_disability'] or catatan['no_disability']
        result['req_male'] = result['req_male'] or catatan['req_male']
        result['req_female'] = result['req_female'] or catatan['req_female']
        result['single'] = result['single'] or catatan['single']

    # Split into <li> blocks and classify each
    blocks = split_li_blocks(html)

    for block in blocks:
        block_type = classify_block(block)

        if block_type == 'PNGK':
            result['min_cgpa'] = extract_pngk(block)

        elif block_type == 'STPM_GROUP':
            groups = extract_stpm_group(block)
            result['stpm_groups'].extend(groups)

        elif block_type == 'STPM_NAMED':
            named = extract_stpm_named(block)
            if named:
                result['stpm_named_subjects'].append(named)

        elif block_type == 'STPM_ANY':
            result['stpm_any_subjects'] = extract_stpm_any(block)

        elif block_type == 'SPM_GROUP':
            groups = extract_spm_group(block)
            result['spm_groups'].extend(groups)

        elif block_type == 'SPM_NAMED':
            named = extract_spm_named(block)
            if named:
                result['spm_named_subjects'].append(named)

        elif block_type == 'MUET':
            result['min_muet_band'] = extract_muet(block)

        elif block_type == 'INTERVIEW':
            result['req_interview'] = True

        elif block_type == 'UNKNOWN':
            warnings.append(f'UNKNOWN_BLOCK: {BeautifulSoup(block, "html.parser").get_text(" ", strip=True)[:80]}')

    return result
```

**Step 4: Run tests**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/test_parse_course.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: parse_course — full course parser with all extractors"
```

---

### Task 8: Build the CLI entry point and batch processor

**Files:**
- Modify: `Settings/_tools/stpm_requirements/parse_stpm_html.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_batch.py`

**Step 1: Write batch test**

```python
# Settings/_tools/stpm_requirements/tests/test_batch.py
import json
import tempfile
import os
import pytest
from parse_stpm_html import process_csv_files


def test_process_single_csv(tmp_path):
    """Integration test: CSV → JSON."""
    csv_path = tmp_path / 'test_input.csv'
    csv_path.write_text(
        'program_name,code,university,merit,duration,level,interview,kampus,bumiputera,syarat_am,requirements\n'
        'Test Course,TC001,Test Uni,50%,8 Semester,Sarjana Muda,Ya,Main,,syarat,'
        '"<ol><li>PNGK <b>PNGK 3.00</b> pada peringkat <b>STPM</b>.</li>'
        '<li>Gred <b>C</b> dalam <b>DUA (2)</b> mata pelajaran di peringkat <b>STPM</b> : '
        '<div><table><tr><td>&#8226;</td><td>Biology</td></tr><tr><td>&#8226;</td><td>Chemistry</td></tr></table></div></li>'
        '<li><b>BAND 2.0</b> dalam <b>MUET</b></li></ol>"\n',
        encoding='utf-8'
    )

    out_path = tmp_path / 'output.json'
    stats = process_csv_files([str(csv_path)], str(out_path))

    assert stats['total'] == 1
    assert stats['warnings'] == 0

    with open(out_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]['course_id'] == 'TC001'
    assert data[0]['min_cgpa'] == 3.00
    assert len(data[0]['stpm_groups']) == 1
```

**Step 2: Implement CLI and batch processor**

Add to `parse_stpm_html.py`:

```python
def process_csv_files(csv_paths: list[str], output_path: str) -> dict:
    """Process multiple source CSVs and write structured JSON output.

    Returns stats dict with counts.
    """
    all_courses = []
    total_warnings = 0

    for csv_path in csv_paths:
        source_file = Path(csv_path).parent.name  # e.g., 'stpm_science'
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                parsed = parse_course(row, source_file)
                all_courses.append(parsed)
                if parsed['parse_warnings']:
                    total_warnings += 1

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_courses, f, indent=2, ensure_ascii=False)

    stats = {
        'total': len(all_courses),
        'warnings': total_warnings,
        'output': output_path,
    }
    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Parse STPM requirements HTML into structured JSON')
    parser.add_argument('inputs', nargs='+', help='Input CSV file(s) with raw HTML requirements')
    parser.add_argument('-o', '--output', required=True, help='Output JSON file path')
    args = parser.parse_args()

    stats = process_csv_files(args.inputs, args.output)
    print(f"Parsed {stats['total']} courses → {stats['output']}")
    if stats['warnings']:
        print(f"  ⚠ {stats['warnings']} courses with parse warnings")


if __name__ == '__main__':
    main()
```

**Step 3: Run tests**

Run: `cd Settings/_tools/stpm_requirements && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: CLI entry point and batch processor for parse_stpm_html"
```

---

### Task 9: Run against real data and audit

**Step 1: Run the parser against both source CSVs**

```bash
cd Settings/_tools/stpm_requirements
python parse_stpm_html.py \
  ../../Archived/Random/data/stpm_science/mohe_programs_merged.csv \
  ../../Archived/Random/data/stpm_arts/mohe_programs_merged.csv \
  -o ../../Archived/Random/data/stpm_requirements_structured.json
```

**Step 2: Audit — check warning count, verify UM6724001**

```python
import json
with open('../../Archived/Random/data/stpm_requirements_structured.json') as f:
    data = json.load(f)

# Overall stats
print(f"Total: {len(data)}")
warned = [c for c in data if c['parse_warnings']]
print(f"With warnings: {len(warned)}")
for w in warned[:10]:
    print(f"  {w['course_id']}: {w['parse_warnings']}")

# Spot-check UM6724001
um = next(c for c in data if c['course_id'] == 'UM6724001')
assert len(um['stpm_groups']) == 2, f"Expected 2 STPM groups, got {len(um['stpm_groups'])}"
assert len(um['spm_groups']) >= 2, f"Expected >=2 SPM groups, got {len(um['spm_groups'])}"
print("UM6724001: PASS")
```

**Step 3: Fix any parser issues discovered, re-run, iterate until warnings < 5%**

This is exploratory — fix edge cases as they appear. Each fix should have a test.

**Step 4: Commit**

```bash
git add Settings/_tools/stpm_requirements/ ../../Archived/Random/data/stpm_requirements_structured.json
git commit -m "feat: run parser against 1,680 STPM courses, audit results"
```

---

## Sprint 2: Fixture Generator + Schema Migration + Backend Updates

### Task 10: Build Stage 2 — JSON → Django fixture converter

**Files:**
- Create: `Settings/_tools/stpm_requirements/stpm_json_to_fixture.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_fixture_gen.py`

This tool reads `stpm_requirements_structured.json` and produces `stpm_requirements.json` (Django fixture format).

Key mapping decisions:
- `stpm_groups` → `stpm_subject_group` (list of dicts, was single dict)
- `spm_groups` → `spm_subject_group` (list of dicts, was single dict)
- `stpm_named_subjects` → individual boolean fields (`stpm_req_pa`, `stpm_req_math_t`, etc.) + remaining go into the group list
- `spm_named_subjects` → individual boolean fields (`spm_credit_bm`, `spm_credit_bi`, etc.)
- `stpm_any_subjects` → append to `stpm_subject_group` list with `subjects: null`
- New booleans: `req_male`, `req_female`, `single`, `no_disability`

**Step 1: Write tests**

```python
# Settings/_tools/stpm_requirements/tests/test_fixture_gen.py
import pytest
from stpm_json_to_fixture import structured_to_fixture

def test_um6724001_fixture():
    structured = {
        'course_id': 'UM6724001',
        'min_cgpa': 3.80,
        'stpm_groups': [
            {'min_count': 2, 'min_grade': 'A', 'subjects': ['BIOLOGY', 'CHEMISTRY', 'PHYSICS', 'MATH_M', 'MATH_T']},
            {'min_count': 1, 'min_grade': 'A-', 'subjects': ['BIOLOGY', 'CHEMISTRY', 'PHYSICS', 'MATH_M', 'MATH_T']},
        ],
        'stpm_named_subjects': [],
        'stpm_any_subjects': None,
        'spm_groups': [
            {'min_count': 4, 'min_grade': 'B', 'subjects': ['BIOLOGY_SPM', 'CHEMISTRY_SPM', 'PHYSICS_SPM', 'MATH']},
            {'min_count': 1, 'min_grade': 'B', 'subjects': None, 'exclude': ['EKONOMI_SPM', 'PERNIAGAAN_SPM']},
        ],
        'spm_named_subjects': [],
        'min_muet_band': 4.0,
        'req_interview': True,
        'no_colorblind': False,
        'req_medical_fitness': True,
        'req_malaysian': True,
        'req_bumiputera': False,
        'req_male': False,
        'req_female': False,
        'single': False,
        'no_disability': True,
    }
    fixture = structured_to_fixture(structured)
    assert fixture['pk'] == 'UM6724001'
    assert fixture['model'] == 'courses.stpmrequirement'

    fields = fixture['fields']
    assert fields['min_cgpa'] == 3.80
    assert isinstance(fields['stpm_subject_group'], list)
    assert len(fields['stpm_subject_group']) == 2
    assert fields['stpm_subject_group'][0]['min_grade'] == 'A'
    assert fields['stpm_subject_group'][1]['min_grade'] == 'A-'
    assert isinstance(fields['spm_subject_group'], list)
    assert len(fields['spm_subject_group']) == 2
    assert fields['min_muet_band'] == 4
    assert fields['req_interview'] is True
    assert fields['no_disability'] is True
```

**Step 2: Implement**

```python
# Settings/_tools/stpm_requirements/stpm_json_to_fixture.py
"""
Stage 2: Convert structured JSON to Django fixture format.

Usage:
    python stpm_json_to_fixture.py <structured.json> -o <fixture.json>
"""
import json
import sys
from subject_keys import normalise_stpm_subject

# Map named STPM subjects to boolean field names
STPM_BOOL_MAP = {
    'PA': 'stpm_req_pa',
    'MATH_T': 'stpm_req_math_t',
    'MATH_M': 'stpm_req_math_m',
    'PHYSICS': 'stpm_req_physics',
    'CHEMISTRY': 'stpm_req_chemistry',
    'BIOLOGY': 'stpm_req_biology',
    'ECONOMICS': 'stpm_req_economics',
    'ACCOUNTING': 'stpm_req_accounting',
    'BUSINESS': 'stpm_req_business',
}

# Map named SPM subjects to boolean field names
SPM_NAMED_MAP = {
    'BM': ('spm_credit_bm', True),
    'SEJARAH': ('spm_pass_sejarah', True),
    'BI': None,  # depends on grade — C = credit, E = pass
    'MATH': ('spm_credit_math', True),
    'ADD_MATH': ('spm_credit_addmath', True),
    'SCIENCE_SPM': ('spm_credit_science', True),
}


def structured_to_fixture(course: dict) -> dict:
    """Convert one structured course dict to Django fixture format."""
    fields = {
        'min_cgpa': course.get('min_cgpa') or 2.0,
        'stpm_min_subjects': 2,  # will be recalculated
        'stpm_min_grade': 'C',   # will be recalculated
        # Boolean STPM subject flags
        'stpm_req_pa': False,
        'stpm_req_math_t': False,
        'stpm_req_math_m': False,
        'stpm_req_physics': False,
        'stpm_req_chemistry': False,
        'stpm_req_biology': False,
        'stpm_req_economics': False,
        'stpm_req_accounting': False,
        'stpm_req_business': False,
        # STPM subject group (now a list)
        'stpm_subject_group': None,
        # SPM booleans
        'spm_credit_bm': False,
        'spm_pass_sejarah': False,
        'spm_credit_bi': False,
        'spm_pass_bi': False,
        'spm_credit_math': False,
        'spm_pass_math': False,
        'spm_credit_addmath': False,
        'spm_credit_science': False,
        # SPM subject group (now a list)
        'spm_subject_group': None,
        # MUET and conditions
        'min_muet_band': int(course.get('min_muet_band') or 1),
        'req_interview': course.get('req_interview', False),
        'no_colorblind': course.get('no_colorblind', False),
        'req_medical_fitness': course.get('req_medical_fitness', False),
        'req_malaysian': course.get('req_malaysian', False),
        'req_bumiputera': course.get('req_bumiputera', False),
        # New fields
        'req_male': course.get('req_male', False),
        'req_female': course.get('req_female', False),
        'single': course.get('single', False),
        'no_disability': course.get('no_disability', False),
    }

    # Set named STPM subject booleans
    for named in course.get('stpm_named_subjects', []):
        subj = named['subject']
        if subj in STPM_BOOL_MAP:
            fields[STPM_BOOL_MAP[subj]] = True

    # Set named SPM subject booleans
    for named in course.get('spm_named_subjects', []):
        subj = named['subject']
        grade = named.get('min_grade', 'C')
        if subj == 'BI':
            if grade in ('A+', 'A', 'A-', 'B+', 'B', 'C+', 'C'):
                fields['spm_credit_bi'] = True
            else:
                fields['spm_pass_bi'] = True
        elif subj in SPM_NAMED_MAP and SPM_NAMED_MAP[subj]:
            field_name, value = SPM_NAMED_MAP[subj]
            fields[field_name] = value

    # STPM subject groups (list)
    stpm_groups = list(course.get('stpm_groups', []))
    any_subj = course.get('stpm_any_subjects')
    if any_subj:
        stpm_groups.append({
            'min_count': any_subj['min_count'],
            'min_grade': any_subj['min_grade'],
            'subjects': None,
            'exclude_already_counted': any_subj.get('exclude_already_counted', False),
        })
    fields['stpm_subject_group'] = stpm_groups if stpm_groups else None

    # Derive stpm_min_subjects and stpm_min_grade from groups
    if stpm_groups:
        total_subjects = sum(g['min_count'] for g in stpm_groups)
        fields['stpm_min_subjects'] = total_subjects
        # Use the highest (most demanding) grade
        grades_used = [g['min_grade'] for g in stpm_groups if g.get('min_grade')]
        if grades_used:
            fields['stpm_min_grade'] = grades_used[0]  # first group is typically the hardest

    # SPM subject groups (list)
    spm_groups = list(course.get('spm_groups', []))
    fields['spm_subject_group'] = spm_groups if spm_groups else None

    return {
        'model': 'courses.stpmrequirement',
        'pk': course['course_id'],
        'fields': fields,
    }
```

**Step 3: Run tests, commit**

---

### Task 11: Django model migration — new boolean fields

**Files:**
- Modify: `halatuju_api/apps/courses/models.py`
- Create: migration via `manage.py makemigrations`

Add to `StpmRequirement`:

```python
req_male = models.BooleanField(default=False)
req_female = models.BooleanField(default=False)
single = models.BooleanField(default=False)
no_disability = models.BooleanField(default=False)
```

Run: `python manage.py makemigrations courses`
Run: `python manage.py migrate`
Run: `python manage.py test apps.courses -v2`

---

### Task 12: Update backend — stpm_engine.py (list-aware subject group checks)

**Files:**
- Modify: `halatuju_api/apps/courses/stpm_engine.py`

Change `check_stpm_subject_group()` and `check_spm_prerequisites()` to handle lists:

```python
def check_stpm_subject_group(req, stpm_grades):
    group = req.stpm_subject_group
    if not group:
        return True
    # Support both old (dict) and new (list) formats
    groups = group if isinstance(group, list) else [group]
    for g in groups:
        min_count = g.get('min_count', 1)
        min_grade = g.get('min_grade', 'C')
        subjects = g.get('subjects')
        # ... existing matching logic per group ...
        # ALL groups must be satisfied (AND semantics)
        matched = 0
        for subj_key, student_grade in stpm_grades.items():
            if subjects and subj_key.upper() not in [s.upper() for s in subjects]:
                continue
            if grade_meets_minimum(student_grade, min_grade, STPM_GRADE_ORDER):
                matched += 1
        if matched < min_count:
            return False
    return True
```

Same pattern for SPM groups in `check_spm_prerequisites()`.

Run: `python manage.py test apps.courses -v2`
Expected: ALL PASS

---

### Task 13: Update API views — include new fields in response

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`

Add `req_male`, `req_female`, `single`, `no_disability` to the STPM detail API response alongside existing `req_interview`, `no_colorblind`, `req_medical_fitness`.

---

### Task 14: Build Stage 3 — Validator tool

**Files:**
- Create: `Settings/_tools/stpm_requirements/validate_stpm_requirements.py`

This tool reads the structured JSON and runs automated checks:

1. **Completeness**: Every course has at least MUET or CGPA
2. **Subject key validity**: No `UNKNOWN:*` keys
3. **Grade validity**: All grades are in the valid grade list
4. **Count sanity**: min_count > 0 and <= 10
5. **Cross-reference**: course_id matches between structured JSON and source CSV
6. **Sample audit**: Pick 20 random courses, extract text from raw_html, verify key fields match

Output: text report with PASS/FAIL per check, list of flagged courses.

---

### Task 15: Generate new fixtures and load

**Step 1: Run fixture generator**

```bash
python stpm_json_to_fixture.py data/stpm_requirements_structured.json \
  -o halatuju_api/apps/courses/fixtures/stpm_requirements.json
```

**Step 2: Run validator**

```bash
python validate_stpm_requirements.py data/stpm_requirements_structured.json
```

**Step 3: Load into local DB**

```bash
cd halatuju_api && python manage.py loaddata stpm_requirements
```

**Step 4: Run full test suite**

```bash
python manage.py test apps.courses -v2
```

**Step 5: Spot-check UM6724001 in API**

```bash
curl http://localhost:8000/api/v1/stpm/courses/UM6724001/
```

Verify the response now shows:
- 2 STPM subject groups (A in 2, A- in 1)
- 2 SPM subject groups (B in 4 named, B in 1 excluding arts)
- MUET 4.0
- Interview, medical fitness, no disability

---

### Task 16: Write the reusable workflow

**Files:**
- Create: `Settings/_workflows/stpm-requirements-update.md`

```markdown
# Workflow: Update STPM Requirements

## When to Use
- Annually when MOHE publishes updated course requirements
- After re-scraping MOHE/ePanduan data

## Prerequisites
- Fresh HTML scraped into `data/stpm_science/mohe_programs_merged.csv` and `data/stpm_arts/mohe_programs_merged.csv`
- Python 3.10+, BeautifulSoup4 installed

## Steps

### Stage 1: Parse HTML → Structured JSON
```
cd Settings/_tools/stpm_requirements
python parse_stpm_html.py \
  ../../data/stpm_science/mohe_programs_merged.csv \
  ../../data/stpm_arts/mohe_programs_merged.csv \
  -o ../../data/stpm_requirements_structured.json
```
**Checkpoint:** Check warning count. Investigate any UNKNOWN_BLOCK warnings.

### Stage 2: Validate
```
python validate_stpm_requirements.py ../../data/stpm_requirements_structured.json
```
**Checkpoint:** All checks must PASS. Fix parser issues if any FAIL.

### Stage 3: Generate Django Fixture
```
python stpm_json_to_fixture.py \
  ../../data/stpm_requirements_structured.json \
  -o ../../halatuju_api/apps/courses/fixtures/stpm_requirements.json
```

### Stage 4: Load and Verify
```
cd ../../halatuju_api
python manage.py loaddata stpm_requirements
python manage.py test apps.courses -v2
```

### Stage 5: Deploy
Follow standard deployment workflow.

## Failure Modes
- **New HTML pattern**: Parser returns UNKNOWN_BLOCK → add new extractor, add test, re-run
- **New subject name**: Parser returns UNKNOWN:SubjectName → add to subject_keys.py
- **Fixture load fails**: Check for missing StpmCourse entries (course must exist before requirement)
```

---

## File Inventory

### New files (to create)
| File | Purpose |
|------|---------|
| `Settings/_tools/stpm_requirements/__init__.py` | Package init |
| `Settings/_tools/stpm_requirements/subject_keys.py` | Canonical subject key registry |
| `Settings/_tools/stpm_requirements/parse_stpm_html.py` | Stage 1: HTML → structured JSON |
| `Settings/_tools/stpm_requirements/stpm_json_to_fixture.py` | Stage 2: JSON → Django fixture |
| `Settings/_tools/stpm_requirements/validate_stpm_requirements.py` | Stage 3: Automated validation |
| `Settings/_tools/stpm_requirements/tests/__init__.py` | Test package |
| `Settings/_tools/stpm_requirements/tests/test_parse_li_blocks.py` | Tests for block splitting |
| `Settings/_tools/stpm_requirements/tests/test_classify_block.py` | Tests for block classification |
| `Settings/_tools/stpm_requirements/tests/test_extractors.py` | Tests for each extractor |
| `Settings/_tools/stpm_requirements/tests/test_catatan.py` | Tests for notes parser |
| `Settings/_tools/stpm_requirements/tests/test_atau.py` | Tests for ATAU handler |
| `Settings/_tools/stpm_requirements/tests/test_parse_course.py` | Integration tests (UM6724001) |
| `Settings/_tools/stpm_requirements/tests/test_batch.py` | Batch processing tests |
| `Settings/_tools/stpm_requirements/tests/test_fixture_gen.py` | Fixture generator tests |
| `Settings/_tools/stpm_requirements/scrape_stpm_requirements.py` | Stage 0: Playwright scraper for dynamic Syarat Khas |
| `Settings/_tools/stpm_requirements/tests/test_scraper.py` | Scraper smoke test |
| `Settings/_workflows/stpm-requirements-update.md` | Reusable workflow doc |

### Files to modify
| File | Change |
|------|--------|
| `halatuju_api/apps/courses/models.py` | Add 4 boolean fields to StpmRequirement |
| `halatuju_api/apps/courses/stpm_engine.py` | List-aware subject group checks |
| `halatuju_api/apps/courses/views.py` | Include new fields in API response |
| `halatuju_api/apps/courses/fixtures/stpm_requirements.json` | Regenerated from new pipeline |

### Files NOT touched (downstream — no changes needed)
| File | Why |
|------|-----|
| `RequirementsCard.tsx` | Already handles arrays via `subject_group_req` (PISMP) |
| `stpm/[id]/page.tsx` | Already displays `stpm_subject_group` |
| `api.ts` | Already types subject_group as any/object |

---

## Sprint 5: Scraper Rewrite (Stage 0 — for yearly refresh)

### Context

The MOHE ePanduan portal (`online.mohe.gov.my/epanduan/`) renders course requirements in a **modal popup with two tabs**:
- **Syarat Am** (general requirements) — loads immediately when modal opens
- **Syarat Khas** (special requirements) — **loads dynamically via AJAX only when the tab is clicked**

This means simple HTTP requests cannot fetch the detailed requirements. A headless browser must:
1. Navigate to the listing page
2. Click a course card to open the modal
3. Click the "Syarat Khas" tab
4. Wait for the dynamic content to render
5. Extract the HTML

The existing `scrape_mohe_stpm.py` (Playwright) scrapes **listings only** — not detail pages. The Syarat Khas content was previously scraped with difficulty using Selenium, and the scripts were not preserved as reusable tools.

---

### Task 17: Build the Playwright-based requirements scraper

**Files:**
- Create: `Settings/_tools/stpm_requirements/scrape_stpm_requirements.py`
- Create: `Settings/_tools/stpm_requirements/tests/test_scraper.py`

**Step 1: Implement the scraper**

```python
# Settings/_tools/stpm_requirements/scrape_stpm_requirements.py
"""
Stage 0: Scrape STPM course requirements from MOHE ePanduan.

Navigates to each course's detail page, clicks the "Syarat Khas" tab,
waits for dynamic content to load, and extracts the HTML.

Usage:
    python scrape_stpm_requirements.py <input_listing.csv> -o <output.csv> [--delay 2.0] [--resume]

Input:  CSV from scrape_mohe_stpm.py (course_id, course_name, university, mohe_url, ...)
Output: CSV matching mohe_programs_merged.csv schema (with requirements HTML column)
"""
import csv
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


MOHE_BASE = 'https://online.mohe.gov.my'
DEFAULT_DELAY = 2.0  # seconds between requests — respect MOHE servers
SYARAT_KHAS_TAB_SELECTOR = 'text=Syarat Khas'
SYARAT_KHAS_CONTENT_SELECTOR = '.tab-pane.active ol, .tab-pane.active .card-body'  # adjust after testing
MODAL_SELECTOR = '.modal-content, [role="dialog"]'


def scrape_course_requirements(page, course_url: str, delay: float = DEFAULT_DELAY) -> dict:
    """Scrape requirements for a single course.

    Returns dict with 'syarat_am' (text), 'requirements' (HTML), 'error' (if any).
    """
    result = {'syarat_am': '', 'requirements': '', 'error': None}

    try:
        # Navigate to course detail page
        page.goto(course_url, wait_until='networkidle', timeout=30000)
        time.sleep(delay)

        # The page may show requirements directly, or in a modal
        # Try clicking the course card/button to open the modal
        # (Exact selector needs verification against live site)

        # Wait for Syarat Am content to appear
        page.wait_for_selector('text=Syarat Am', timeout=10000)

        # Extract Syarat Am content
        syarat_am_el = page.query_selector('.tab-pane.active')
        if syarat_am_el:
            result['syarat_am'] = syarat_am_el.inner_text()

        # Click Syarat Khas tab
        syarat_khas_tab = page.query_selector(SYARAT_KHAS_TAB_SELECTOR)
        if syarat_khas_tab:
            syarat_khas_tab.click()
            # Wait for dynamic content to load
            time.sleep(delay)
            # Wait for the content to actually appear
            page.wait_for_selector('.tab-pane.active ol', timeout=15000)

            # Extract Syarat Khas HTML (the full <ol> with all <li> items)
            content_el = page.query_selector('.tab-pane.active')
            if content_el:
                result['requirements'] = content_el.inner_html()
        else:
            result['error'] = 'NO_SYARAT_KHAS_TAB'

    except PlaywrightTimeout:
        result['error'] = 'TIMEOUT'
    except Exception as e:
        result['error'] = f'ERROR: {str(e)[:200]}'

    return result


def scrape_batch(input_csv: str, output_csv: str, delay: float = DEFAULT_DELAY, resume: bool = False):
    """Scrape requirements for all courses in the input CSV.

    Args:
        input_csv: Path to listing CSV (from scrape_mohe_stpm.py)
        output_csv: Path to output CSV (mohe_programs_merged.csv format)
        delay: Seconds between requests
        resume: If True, skip courses already in output CSV
    """
    # Load already-scraped course IDs if resuming
    done_ids = set()
    if resume and Path(output_csv).exists():
        with open(output_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                done_ids.add(row.get('code', '').strip())
        print(f"Resuming — {len(done_ids)} courses already scraped")

    # Read input listings
    with open(input_csv, 'r', encoding='utf-8') as f:
        listings = list(csv.DictReader(f))

    # Output fields (match mohe_programs_merged.csv schema)
    fieldnames = [
        'program_name', 'code', 'university', 'merit', 'duration',
        'level', 'interview', 'kampus', 'bumiputera', 'syarat_am',
        'requirements'
    ]

    # Open output (append if resuming, write if fresh)
    mode = 'a' if resume and done_ids else 'w'
    with open(output_csv, mode, newline='', encoding='utf-8') as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        if mode == 'w':
            writer.writeheader()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            total = len(listings)
            scraped = 0
            errors = 0

            for i, listing in enumerate(listings):
                course_id = listing.get('course_id', '').strip()
                if course_id in done_ids:
                    continue

                url = listing.get('mohe_url', '')
                if not url:
                    continue

                print(f"[{i+1}/{total}] {course_id}...", end=' ', flush=True)

                req_data = scrape_course_requirements(page, url, delay)

                row = {
                    'program_name': listing.get('course_name', ''),
                    'code': course_id,
                    'university': listing.get('university', ''),
                    'merit': listing.get('merit', ''),
                    'duration': '',
                    'level': '',
                    'interview': '',
                    'kampus': '',
                    'bumiputera': '',
                    'syarat_am': req_data['syarat_am'],
                    'requirements': req_data['requirements'],
                }
                writer.writerow(row)
                out_f.flush()  # flush after each row for crash recovery

                if req_data['error']:
                    print(f"⚠ {req_data['error']}")
                    errors += 1
                else:
                    print("✓")
                    scraped += 1

            browser.close()

    print(f"\nDone: {scraped} scraped, {errors} errors, {len(done_ids)} resumed")


def main():
    parser = argparse.ArgumentParser(description='Scrape STPM requirements from MOHE ePanduan')
    parser.add_argument('input', help='Input CSV (course listings from scrape_mohe_stpm.py)')
    parser.add_argument('-o', '--output', required=True, help='Output CSV path')
    parser.add_argument('--delay', type=float, default=DEFAULT_DELAY, help='Delay between requests (seconds)')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    args = parser.parse_args()

    scrape_batch(args.input, args.output, args.delay, args.resume)


if __name__ == '__main__':
    main()
```

**Important notes for the implementer:**
- The CSS selectors (`SYARAT_KHAS_TAB_SELECTOR`, `SYARAT_KHAS_CONTENT_SELECTOR`, `MODAL_SELECTOR`) are **best guesses** and MUST be verified against the live site. Open `https://online.mohe.gov.my/epanduan/ProgramPengajian/kategoriCalon/S` in a browser, inspect the modal, and update selectors accordingly.
- The scraper flushes after each row so a crash doesn't lose progress. The `--resume` flag reads existing output and skips those course IDs.
- MOHE's site can be slow. Default 2s delay between requests. Don't go lower.

**Step 2: Write a smoke test**

```python
# Settings/_tools/stpm_requirements/tests/test_scraper.py
import pytest
from scrape_stpm_requirements import scrape_batch

# NOTE: This test requires Playwright and internet access.
# Mark it as slow/integration so it's not run in CI.

@pytest.mark.skipif(True, reason="Requires live MOHE access — run manually")
def test_scrape_single_course(tmp_path):
    """Smoke test: scrape one known course and verify output."""
    # Create a minimal input CSV with one course
    input_csv = tmp_path / 'input.csv'
    input_csv.write_text(
        'course_id,course_name,university,mohe_url,merit\n'
        'UM6724001,SARJANA MUDA PEMBEDAHAN PERGIGIAN,Universiti Malaya,'
        'https://online.mohe.gov.my/epanduan/carianNamaProgram/UM/UM6724001/S/stpm,99.92%\n'
    )

    output_csv = tmp_path / 'output.csv'
    scrape_batch(str(input_csv), str(output_csv), delay=3.0)

    import csv
    with open(output_csv, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]['code'] == 'UM6724001'
    assert 'PNGK' in rows[0]['requirements'], "Requirements HTML should contain PNGK"
    assert '<ol' in rows[0]['requirements'] or '<li' in rows[0]['requirements'], "Should have HTML structure"
```

**Step 3: Commit**

```bash
git add Settings/_tools/stpm_requirements/
git commit -m "feat: Stage 0 — Playwright scraper for MOHE Syarat Khas (dynamic tab)"
```

---

### Task 18: Test scraper against live site and calibrate selectors

**This is a manual/exploratory task.**

**Step 1: Open MOHE ePanduan in browser, inspect the modal**

Navigate to `https://online.mohe.gov.my/epanduan/ProgramPengajian/kategoriCalon/S`
- Click any course card
- Inspect the modal DOM: find the exact selectors for Syarat Am tab, Syarat Khas tab, content panels
- Note any loading spinners or delay patterns

**Step 2: Update selectors in `scrape_stpm_requirements.py`**

Replace the placeholder selectors with verified ones from Step 1.

**Step 3: Run smoke test on 5 courses**

```bash
cd Settings/_tools/stpm_requirements
# Create a 5-course test CSV
python -c "
import csv
with open('test_5.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['course_id','course_name','university','mohe_url','merit'])
    w.writerow(['UM6724001','PERGIGIAN','UM','https://online.mohe.gov.my/epanduan/carianNamaProgram/UM/UM6724001/S/stpm','99%'])
    w.writerow(['UP6723001','KEJURUTERAAN','UPM','https://online.mohe.gov.my/epanduan/carianNamaProgram/UP/UP6723001/S/stpm','80%'])
"
python scrape_stpm_requirements.py test_5.csv -o test_output.csv --delay 3.0
```

**Step 4: Verify output matches expected HTML structure**

Open `test_output.csv`, check that `requirements` column contains the same HTML we see in our existing `mohe_programs_merged.csv` files.

**Step 5: Commit selector fixes**

```bash
git add Settings/_tools/stpm_requirements/scrape_stpm_requirements.py
git commit -m "fix: calibrate MOHE selectors from live site testing"
```

---

### Task 19: Full scrape and diff against existing data

**Step 1: Run full scrape (with --resume for crash recovery)**

```bash
# Science stream
python scrape_stpm_requirements.py data/stpm_science_listings.csv \
  -o data/stpm_science/mohe_programs_merged_2026.csv --delay 2.0 --resume

# Arts stream
python scrape_stpm_requirements.py data/stpm_arts_listings.csv \
  -o data/stpm_arts/mohe_programs_merged_2026.csv --delay 2.0 --resume
```

**Step 2: Diff against existing data**

```python
import csv
# Compare old vs new — check for courses added/removed and HTML differences
# This validates the scraper produces equivalent output
```

**Step 3: If diffs are clean, replace the old CSVs and re-run the full pipeline (Stages 1-4)**

**Step 4: Commit**

```bash
git add data/
git commit -m "feat: fresh MOHE scrape with Stage 0 tool"
```

---

## Risk Register

| Risk | Mitigation |
|------|-----------|
| New HTML patterns in arts CSV not seen in science | Run parser against both CSVs in Task 9, fix edge cases |
| Subject name not in registry | `UNKNOWN:*` prefix makes these visible; validator catches them |
| ATAU alternatives create duplicate courses | Stored as `atau_groups` on primary course, not separate entries |
| Backend list format breaks old single-dict data | `isinstance(group, list)` check provides backward compatibility |
| 1,680 courses × re-parse takes too long | Parser is pure Python, no API calls — should complete in <30s |
| MOHE changes their HTML structure | Selectors in scraper need manual recalibration; raw_html preserved for debugging |
| Syarat Khas tab AJAX takes too long | 15s timeout + retry logic; `--resume` flag for crash recovery |
| MOHE rate-limits scraping | Default 2s delay; increase to 5s if needed; scrape during off-hours |

# Report Prompt Improvements — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve AI report quality by wiring real student data into prompts, creating a separate STPM prompt, translating raw signals to human-readable text, and selecting courses by fit score.

**Architecture:** Two-track prompts (SPM + STPM) in `prompts.py`, improved data formatters in `report_engine.py`, view passes student name + exam_type. Drop persona system — use a single consistent counsellor voice with no named character. EN prompt already exists, just needs updates matching BM changes.

**Tech Stack:** Django, Gemini API (google-genai), pytest

---

## Context for the Implementer

### Current State
- `apps/reports/prompts.py` has `PROMPT_BM` and `PROMPT_EN` — both SPM-specific
- `apps/reports/report_engine.py` has formatters (`_format_grades`, `_format_signals`, `_format_courses`, `_format_insights`) and `generate_report()`
- `apps/reports/views.py` has `GenerateReportView` — does NOT pass `student_name` or `exam_type`
- `apps/reports/models.py` has `GeneratedReport` model (stores report + snapshots)
- `apps/reports/tests/test_report_engine.py` has 12 existing tests
- `StudentProfile` has fields: `name`, `exam_type` (spm/stpm), `grades` (SPM), `stpm_grades`, `stpm_cgpa`, `muet_band`, `student_signals`
- Quiz signals are JSON: `{"field_interest": {"field_mechanical": 3, ...}, "work_preference_signals": {...}, ...}`
- `_format_signals()` currently dumps raw JSON: `Kecenderungan: {"field_mechanical": 3}`

### Signal Taxonomy (for human-readable labels)
```python
SIGNAL_LABELS = {
    # field_interest
    'field_mechanical': ('Mekanikal & Automotif', 'Mechanical & Automotive'),
    'field_digital': ('Teknologi Digital', 'Digital Technology'),
    'field_business': ('Perniagaan & Pengurusan', 'Business & Management'),
    'field_health': ('Kesihatan & Perubatan', 'Health & Medical'),
    'field_creative': ('Seni & Kreatif', 'Arts & Creative'),
    'field_hospitality': ('Hospitaliti & Pelancongan', 'Hospitality & Tourism'),
    'field_agriculture': ('Pertanian & Alam Sekitar', 'Agriculture & Environment'),
    'field_heavy_industry': ('Industri Berat', 'Heavy Industry'),
    'field_electrical': ('Elektrik & Elektronik', 'Electrical & Electronics'),
    'field_civil': ('Kejuruteraan Awam', 'Civil Engineering'),
    'field_aero_marine': ('Aero & Marin', 'Aerospace & Marine'),
    'field_oil_gas': ('Minyak & Gas', 'Oil & Gas'),
    # work_preference_signals
    'hands_on': ('Kerja Amali', 'Hands-on Work'),
    'problem_solving': ('Penyelesaian Masalah', 'Problem Solving'),
    'people_helping': ('Bantu Orang', 'Helping People'),
    'creative': ('Kreatif', 'Creative'),
    # environment_signals
    'workshop_environment': ('Persekitaran Bengkel', 'Workshop Environment'),
    'office_environment': ('Persekitaran Pejabat', 'Office Environment'),
    'high_people_environment': ('Ramai Orang', 'High People Environment'),
    'field_environment': ('Kerja Luar', 'Fieldwork'),
    # energy_sensitivity_signals
    'high_stamina': ('Stamina Tinggi', 'High Stamina'),
    'mental_fatigue_sensitive': ('Sensitif Penat Mental', 'Mentally Sensitive'),
    'physical_fatigue_sensitive': ('Sensitif Penat Fizikal', 'Physically Sensitive'),
}
```

### STPM Subject Labels (for academic section)
Use `STPM_SUBJECT_LABELS` dict from `stpm_engine.py`:
```python
STPM_SUBJECT_LABELS = {
    'PA': 'Pengajian Am', 'MATH_T': 'Matematik T', 'MATH_M': 'Matematik M',
    'PHYSICS': 'Fizik', 'CHEMISTRY': 'Kimia', 'BIOLOGY': 'Biologi',
    'ECONOMICS': 'Ekonomi', 'ACCOUNTING': 'Perakaunan', 'BUSINESS': 'Perniagaan',
    ...
}
```

### Field Taxonomy
The `FieldTaxonomy` model has `key`, `name_en`, `name_ms`, `name_ta`. Courses link via `field_key` FK. Use this to add field descriptions to course context in the prompt.

---

## Task 1: Wire Student Name into Report Generation

Currently `generate_report()` accepts `student_name` but the view never passes it. The profile has `name`.

**Files:**
- Modify: `apps/reports/views.py:82-88`
- Modify: `apps/reports/tests/test_report_engine.py`

**Step 1: Write the failing test**

Add to `test_report_engine.py`:

```python
class TestStudentNamePassthrough(TestCase):
    """Test that student name reaches the prompt."""

    @patch('apps.reports.report_engine.genai')
    def test_student_name_in_prompt(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = 'Report text'
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        result = generate_report(
            grades={'bm': 'A'},
            eligible_courses=[{'course_name': 'Test', 'field': 'IT'}],
            insights={},
            student_signals={},
            student_name='Ahmad bin Abu',
            lang='bm',
        )
        # Verify the name was passed to Gemini
        call_args = mock_genai.Client.return_value.models.generate_content.call_args
        prompt_sent = call_args[1]['contents'] if 'contents' in call_args[1] else call_args[0][0]
        # Handle both keyword and positional arg styles
        if isinstance(prompt_sent, str):
            self.assertIn('Ahmad bin Abu', prompt_sent)
        else:
            # contents= kwarg
            self.assertIn('Ahmad bin Abu', str(call_args))

    @patch('apps.reports.report_engine.genai')
    def test_default_student_name_is_pelajar(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = 'Report text'
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        result = generate_report(
            grades={'bm': 'A'},
            eligible_courses=[{'course_name': 'Test', 'field': 'IT'}],
            insights={},
            lang='bm',
        )
        call_args = mock_genai.Client.return_value.models.generate_content.call_args
        self.assertIn('pelajar', str(call_args))
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/test_report_engine.py -v -k "student_name"`
Expected: These should actually PASS because `generate_report()` already accepts `student_name`. The real gap is in the view.

**Step 3: Write a view-level test**

Add to `apps/reports/tests/test_views.py` (or the existing view test file):

```python
class TestGenerateReportPassesStudentName(TestCase):
    """Verify the view passes profile.name to generate_report."""

    @patch('apps.reports.views.generate_report')
    def test_view_passes_student_name(self, mock_gen):
        mock_gen.return_value = {
            'markdown': 'text',
            'model_used': 'gemini-2.5-flash',
            'counsellor_name': 'Kaunselor',
            'generation_time_ms': 100,
        }
        profile = StudentProfile.objects.create(
            supabase_user_id='test-user-name',
            name='Siti binti Ali',
            grades={'bm': 'A'},
        )
        # Simulate authenticated POST
        factory = APIRequestFactory()
        request = factory.post('/api/v1/reports/generate/', {
            'eligible_courses': [{'course_name': 'Test'}],
            'insights': {},
        }, format='json')
        request.user_id = 'test-user-name'
        view = GenerateReportView.as_view()
        response = view(request)

        # Verify generate_report was called with student_name
        call_kwargs = mock_gen.call_args[1]
        self.assertEqual(call_kwargs['student_name'], 'Siti binti Ali')
```

**Step 4: Run test — expect FAIL** (view doesn't pass student_name yet)

Run: `cd halatuju_api && python -m pytest apps/reports/tests/ -v -k "passes_student_name"`
Expected: FAIL — `student_name` not in call_kwargs

**Step 5: Implement — pass student_name in the view**

In `apps/reports/views.py`, change the `generate_report()` call (line 82-88):

```python
        # Call Gemini via report engine
        result = generate_report(
            grades=grades,
            eligible_courses=eligible_courses,
            insights=insights,
            student_signals=student_signals,
            student_name=profile.name or 'pelajar',
            lang=lang,
        )
```

**Step 6: Run tests — expect PASS**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/ -v`
Expected: All pass

**Step 7: Commit**

```bash
git add apps/reports/views.py apps/reports/tests/
git commit -m "feat: wire student name into report generation prompt"
```

---

## Task 2: Translate Quiz Signals to Human-Readable Text

Currently `_format_signals()` outputs raw JSON like `{"field_mechanical": 3}`. Replace with labelled text like `Mekanikal & Automotif (kuat)`.

**Files:**
- Modify: `apps/reports/report_engine.py:91-106`
- Modify: `apps/reports/tests/test_report_engine.py`

**Step 1: Write the failing test**

```python
class TestHumanReadableSignals(TestCase):
    """Test that signals are formatted as readable text, not JSON."""

    def test_format_signals_human_readable_bm(self):
        signals = {
            'field_interest': {'field_mechanical': 3, 'field_digital': 1},
            'work_preference_signals': {'hands_on': 2},
            'environment_signals': {'workshop_environment': 1},
        }
        result = _format_signals(signals, lang='bm')
        self.assertIn('Mekanikal & Automotif', result)
        self.assertIn('kuat', result)  # score >= 2
        self.assertIn('Teknologi Digital', result)
        self.assertIn('sederhana', result)  # score == 1
        self.assertNotIn('{', result)  # No JSON braces
        self.assertNotIn('field_mechanical', result)  # No raw keys

    def test_format_signals_human_readable_en(self):
        signals = {
            'field_interest': {'field_mechanical': 3},
            'work_preference_signals': {'hands_on': 2},
        }
        result = _format_signals(signals, lang='en')
        self.assertIn('Mechanical & Automotive', result)
        self.assertIn('strong', result)
        self.assertNotIn('field_mechanical', result)

    def test_format_signals_empty(self):
        result = _format_signals(None, lang='bm')
        self.assertIn('Tiada', result)

    def test_format_signals_no_dominant(self):
        signals = {'field_interest': {'field_mechanical': 0}}
        result = _format_signals(signals, lang='bm')
        self.assertIn('Tiada', result)
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/test_report_engine.py -v -k "human_readable"`
Expected: FAIL — `_format_signals` doesn't accept `lang` param, outputs JSON

**Step 3: Implement human-readable signal formatter**

Replace `_format_signals()` in `report_engine.py`:

```python
# Signal display labels: (BM, EN)
SIGNAL_LABELS = {
    # field_interest
    'field_mechanical': ('Mekanikal & Automotif', 'Mechanical & Automotive'),
    'field_digital': ('Teknologi Digital', 'Digital Technology'),
    'field_business': ('Perniagaan & Pengurusan', 'Business & Management'),
    'field_health': ('Kesihatan & Perubatan', 'Health & Medical'),
    'field_creative': ('Seni & Kreatif', 'Arts & Creative'),
    'field_hospitality': ('Hospitaliti & Pelancongan', 'Hospitality & Tourism'),
    'field_agriculture': ('Pertanian & Alam Sekitar', 'Agriculture & Environment'),
    'field_heavy_industry': ('Industri Berat', 'Heavy Industry'),
    'field_electrical': ('Elektrik & Elektronik', 'Electrical & Electronics'),
    'field_civil': ('Kejuruteraan Awam', 'Civil Engineering'),
    'field_aero_marine': ('Aero & Marin', 'Aerospace & Marine'),
    'field_oil_gas': ('Minyak & Gas', 'Oil & Gas'),
    # work_preference
    'hands_on': ('Kerja Amali', 'Hands-on Work'),
    'problem_solving': ('Penyelesaian Masalah', 'Problem Solving'),
    'people_helping': ('Bantu Orang', 'Helping People'),
    'creative': ('Kreatif', 'Creative'),
    # environment
    'workshop_environment': ('Persekitaran Bengkel', 'Workshop Environment'),
    'office_environment': ('Persekitaran Pejabat', 'Office Environment'),
    'high_people_environment': ('Ramai Orang', 'High People Environment'),
    'field_environment': ('Kerja Luar', 'Fieldwork'),
    # energy
    'high_stamina': ('Stamina Tinggi', 'High Stamina'),
    'mental_fatigue_sensitive': ('Sensitif Penat Mental', 'Mentally Sensitive'),
    'physical_fatigue_sensitive': ('Sensitif Penat Fizikal', 'Physically Sensitive'),
    'low_people_tolerance': ('Kurang Selesa Ramai Orang', 'Low People Tolerance'),
    # learning
    'learning_by_doing': ('Belajar Sambil Buat', 'Learning by Doing'),
    'concept_first': ('Konsep Dahulu', 'Concept First'),
    'rote_tolerant': ('Boleh Hafal', 'Rote Tolerant'),
    'project_based': ('Berasaskan Projek', 'Project-based'),
    # value tradeoffs
    'stability_priority': ('Keutamaan Kestabilan', 'Stability Priority'),
    'quality_priority': ('Keutamaan Kualiti', 'Quality Priority'),
    'fast_employment_priority': ('Nak Kerja Cepat', 'Fast Employment'),
    'income_risk_tolerant': ('Sanggup Risiko Gaji', 'Income Risk Tolerant'),
    'pathway_priority': ('Laluan Kerjaya', 'Career Pathway'),
    'proximity_priority': ('Dekat Rumah', 'Proximity'),
    'allowance_priority': ('Elaun Penting', 'Allowance Priority'),
    'employment_guarantee': ('Jaminan Kerja', 'Employment Guarantee'),
}

STRENGTH_LABELS = {
    'bm': {2: 'kuat', 1: 'sederhana'},
    'en': {2: 'strong', 1: 'moderate'},
}


def _format_signals(student_signals, lang='bm'):
    """Format quiz signals into human-readable personality summary."""
    if not student_signals:
        return 'Tiada maklumat kecenderungan (kuiz belum diambil).' if lang == 'bm' \
            else 'No inclination data (quiz not taken).'

    lang_idx = 0 if lang == 'bm' else 1
    strength = STRENGTH_LABELS.get(lang, STRENGTH_LABELS['bm'])
    lines = []

    for category, sig_dict in student_signals.items():
        if not isinstance(sig_dict, dict):
            continue
        for key, score in sig_dict.items():
            if not score or score <= 0:
                continue
            label_pair = SIGNAL_LABELS.get(key)
            label = label_pair[lang_idx] if label_pair else key
            level = strength.get(2, 'kuat') if score >= 2 else strength.get(1, 'sederhana')
            lines.append(f'- {label} ({level})')

    if not lines:
        return 'Tiada kecenderungan dominan dikesan.' if lang == 'bm' \
            else 'No dominant inclinations detected.'

    header = 'Kecenderungan pelajar:' if lang == 'bm' else 'Student inclinations:'
    return header + '\n' + '\n'.join(lines)
```

**Step 4: Update the caller** — `generate_report()` must pass `lang` to `_format_signals`:

Change line ~193:
```python
    student_profile = _format_signals(student_signals, lang=lang)
```

**Step 5: Update existing tests that test `_format_signals`**

The old tests (e.g., `test_format_signals_empty`, `test_format_signals_dominant`) need updating to pass `lang='bm'`. Find them and update.

**Step 6: Run all tests**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/test_report_engine.py -v`
Expected: All pass

**Step 7: Commit**

```bash
git add apps/reports/report_engine.py apps/reports/tests/test_report_engine.py
git commit -m "feat: translate quiz signals to human-readable text in reports"
```

---

## Task 3: Smart Course Selection (Top 5 by Fit Score)

Currently `_format_courses()` takes the first 3 courses. Instead, take up to 5 and sort by fit_score descending.

**Files:**
- Modify: `apps/reports/report_engine.py:109-128` (`_format_courses`)
- Modify: `apps/reports/tests/test_report_engine.py`

**Step 1: Write the failing test**

```python
class TestSmartCourseSelection(TestCase):
    def test_courses_sorted_by_fit_score(self):
        courses = [
            {'course_name': 'Low', 'field': 'A', 'fit_score': 30},
            {'course_name': 'High', 'field': 'B', 'fit_score': 70},
            {'course_name': 'Mid', 'field': 'C', 'fit_score': 50},
        ]
        result = _format_courses(courses)
        lines = result.strip().split('\n')
        self.assertTrue(lines[0].startswith('1. High'))
        self.assertTrue(lines[1].startswith('2. Mid'))
        self.assertTrue(lines[2].startswith('3. Low'))

    def test_courses_limit_5(self):
        courses = [{'course_name': f'C{i}', 'field': 'X', 'fit_score': i}
                   for i in range(10)]
        result = _format_courses(courses)
        lines = [l for l in result.strip().split('\n') if l.strip()]
        self.assertEqual(len(lines), 5)

    def test_courses_without_fit_score_still_work(self):
        courses = [
            {'course_name': 'A', 'field': 'X'},
            {'course_name': 'B', 'field': 'Y'},
        ]
        result = _format_courses(courses)
        self.assertIn('A', result)
        self.assertIn('B', result)
```

**Step 2: Run test to verify it fails**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/test_report_engine.py -v -k "smart_course"`
Expected: FAIL — courses not sorted by fit_score

**Step 3: Implement**

Replace `_format_courses()`:

```python
def _format_courses(eligible_courses, limit=5):
    """Format top courses for the prompt, sorted by fit_score descending."""
    if not eligible_courses:
        return 'Tiada kursus layak.'

    # Sort by fit_score descending (courses without score go last)
    sorted_courses = sorted(
        eligible_courses,
        key=lambda c: c.get('fit_score', 0),
        reverse=True,
    )

    lines = []
    for i, c in enumerate(sorted_courses[:limit]):
        name = c.get('course_name', c.get('course_id', '?'))
        field = c.get('field', '')
        source = c.get('source_type', '')
        merit = c.get('merit_label', '')
        fit = c.get('fit_score')
        line = f'{i + 1}. {name}'
        if field:
            line += f' (Bidang: {field})'
        if source:
            line += f' [{source.upper()}]'
        if merit:
            line += f' — Peluang: {merit}'
        if fit is not None:
            line += f' [Skor Kesesuaian: {fit}]'
        lines.append(line)
    return '\n'.join(lines)
```

**Step 4: Run tests**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/test_report_engine.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add apps/reports/report_engine.py apps/reports/tests/test_report_engine.py
git commit -m "feat: sort report courses by fit score, increase to top 5"
```

---

## Task 4: Add Field Descriptions to Course Context

Add the field's human-readable description (from FieldTaxonomy) to each course in the prompt so Gemini can explain *why* a field suits the student.

**Files:**
- Modify: `apps/reports/report_engine.py` (`_format_courses`)
- Modify: `apps/reports/views.py` (enrich courses before passing)
- Modify: `apps/reports/tests/test_report_engine.py`

**Step 1: Write the failing test**

```python
class TestFieldDescriptionInCourses(TestCase):
    def test_field_name_included_in_course_format(self):
        courses = [
            {
                'course_name': 'Diploma Kejuruteraan',
                'field': 'kejuruteraan',
                'field_display': 'Kejuruteraan Mekanikal',
            },
        ]
        result = _format_courses(courses)
        self.assertIn('Kejuruteraan Mekanikal', result)
```

**Step 2: Run — expect FAIL**

**Step 3: Implement**

In `_format_courses()`, use `field_display` if present, else fall back to `field`:

```python
        field = c.get('field_display', c.get('field', ''))
```

In `apps/reports/views.py`, enrich eligible_courses with field display names before passing to `generate_report()`:

```python
        # Enrich courses with field display names
        from apps.courses.models import FieldTaxonomy
        field_cache = {}
        for course in eligible_courses:
            fk = course.get('field_key') or course.get('field', '')
            if fk and fk not in field_cache:
                try:
                    ft = FieldTaxonomy.objects.get(key=fk)
                    field_cache[fk] = ft.name_ms if lang == 'bm' else ft.name_en
                except FieldTaxonomy.DoesNotExist:
                    field_cache[fk] = ''
            course['field_display'] = field_cache.get(fk, '')
```

**Step 4: Run tests**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/ -v`
Expected: All pass

**Step 5: Commit**

```bash
git add apps/reports/report_engine.py apps/reports/views.py apps/reports/tests/
git commit -m "feat: add field display names to report course context"
```

---

## Task 5: Drop Persona System

Remove `COUNSELOR_PERSONAS`, `get_persona_for_model()`, and `{counsellor_name}`/`{gender_context}` from prompts. Replace with a fixed, neutral counsellor voice.

**Files:**
- Modify: `apps/reports/prompts.py`
- Modify: `apps/reports/report_engine.py`
- Modify: `apps/reports/views.py` (remove counsellor_name from response)
- Modify: `apps/reports/tests/test_report_engine.py`

**Step 1: Write the failing test**

```python
class TestNoPersona(TestCase):
    def test_prompt_has_no_counsellor_name_placeholder(self):
        prompt_bm = get_prompt('bm')
        prompt_en = get_prompt('en')
        self.assertNotIn('{counsellor_name}', prompt_bm)
        self.assertNotIn('{gender_context}', prompt_bm)
        self.assertNotIn('{counsellor_name}', prompt_en)
        self.assertNotIn('{gender_context}', prompt_en)

    @patch('apps.reports.report_engine.genai')
    def test_generate_report_returns_no_counsellor_name(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = 'Report text'
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        result = generate_report(
            grades={'bm': 'A'},
            eligible_courses=[{'course_name': 'Test', 'field': 'IT'}],
            insights={},
            lang='bm',
        )
        self.assertNotIn('counsellor_name', result)
```

**Step 2: Run — expect FAIL**

**Step 3: Implement**

In `prompts.py`:
1. Remove `COUNSELOR_PERSONAS` dict and `get_persona_for_model()` function
2. In `PROMPT_BM`, replace `Anda ialah "{counsellor_name}" — seorang kaunselor laluan kerjaya {gender_context}` with `Anda ialah seorang kaunselor laluan kerjaya`
3. Remove all `{counsellor_name}` references from greeting examples — use just "saya kaunselor awak" or similar
4. Remove `{gender_context}` placeholder entirely
5. Same changes in `PROMPT_EN`
6. Remove `{counsellor_name}` and `{gender_context}` from the docstring placeholders list

In `report_engine.py`:
1. Remove `from .prompts import get_persona_for_model` from imports
2. In `generate_report()`, remove persona lookup and the `counsellor_name`/`gender_context` keys from `prompt_template.format()` call
3. Return dict without `counsellor_name` key

In `views.py`:
1. Remove `counsellor_name` from the title stored in `GeneratedReport` — use fixed title like `'Laporan Kaunseling'`
2. Remove `counsellor_name` from the API response dict

**Step 4: Update existing persona tests**

Remove or update `test_persona_mapping_*` tests. Update `test_prompt_bm_template` and `test_prompt_en_template` assertions.

**Step 5: Run all tests**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/ -v`
Expected: All pass

**Step 6: Commit**

```bash
git add apps/reports/prompts.py apps/reports/report_engine.py apps/reports/views.py apps/reports/tests/
git commit -m "refactor: drop counsellor persona system, use neutral voice"
```

---

## Task 6: Create STPM Prompt Templates (BM + EN)

Create new `PROMPT_STPM_BM` and `PROMPT_STPM_EN` templates tailored for STPM students applying to degree programmes.

**Files:**
- Modify: `apps/reports/prompts.py`
- Modify: `apps/reports/report_engine.py`
- Modify: `apps/reports/tests/test_report_engine.py`

**Step 1: Write the failing test**

```python
class TestStpmPrompt(TestCase):
    def test_get_prompt_stpm_bm(self):
        prompt = get_prompt('bm', exam_type='stpm')
        self.assertIn('{student_name}', prompt)
        self.assertIn('{academic_context}', prompt)
        self.assertIn('STPM', prompt)
        self.assertNotIn('SPM', prompt.split('STRUKTUR')[0])  # Header should say STPM not SPM

    def test_get_prompt_stpm_en(self):
        prompt = get_prompt('en', exam_type='stpm')
        self.assertIn('{student_name}', prompt)
        self.assertIn('STPM', prompt)

    def test_get_prompt_defaults_to_spm(self):
        prompt = get_prompt('bm')
        self.assertIn('SPM', prompt)
```

**Step 2: Run — expect FAIL** (get_prompt doesn't accept exam_type)

**Step 3: Implement**

In `prompts.py`, add `PROMPT_STPM_BM` and `PROMPT_STPM_EN`:

```python
PROMPT_STPM_BM = """
Anda ialah seorang kaunselor laluan kerjaya yang jujur, membumi, dan mengambil berat terhadap pelajar lepasan STPM (umur sekitar 19 tahun), terutamanya dari latar B40.

Matlamat anda:
Memberi nasihat kerjaya yang REALISTIK dan BOLEH DIFAHAMI, berdasarkan:
1) Keputusan STPM dan CGPA pelajar
2) Corak kecenderungan / personaliti kerja
3) Realiti sebenar dunia kerja dan pengajian tinggi di Malaysia

❗PENTING: Ini BUKAN motivasi kosong. Ini kaunseling sebenar.

-----------------------------------
PANDUAN BAHASA & NADA (SANGAT PENTING)
-----------------------------------
1. Gunakan Bahasa Melayu MUDAH dan santai (tahap pelajar sekolah).
   - Elakkan istilah korporat berat
   - Gantikan dengan bahasa biasa

2. Nada seperti:
   - Pensyarah yang jujur
   - Abang/kakak yang ambil berat
   - Tegas bila perlu, tetapi tidak menjatuhkan semangat

3. Jangan:
   - Gunakan ayat berbunga
   - Anggap pelajar ada keyakinan tinggi atau kabel
   - Bagi nasihat yang "terlalu ideal" atau susah dibuat

-----------------------------------
STRUKTUR LAPORAN (WAJIB IKUT URUTAN)
-----------------------------------

❗PENTING: Mulakan laporan TERUS dengan salam dan sapaan NAMA PELAJAR.
Contoh BETUL: "Salam sejahtera {student_name}. Terima kasih sebab sudi kongsi keputusan dan minat awak."
Gunakan "Salam sejahtera" (bukan "Assalamualaikum") kerana ia lebih inklusif untuk semua rakyat Malaysia.

A. Cermin Diri (Self-Reflection)
Terangkan kecenderungan kerja pelajar dalam bahasa mudah.
Jika data kecenderungan tiada (kuiz belum diambil), langkau bahagian ini dan terus ke bahagian B.

B. Isyarat Akademik STPM (WAJIB DIGUNAKAN)
Gunakan gred STPM dan CGPA sebagai isyarat sebenar.
Untuk setiap subjek penting:
- Terangkan apa maksud gred itu dari segi kelayakan universiti
- Puji kekuatan
- Tegur kelemahan dengan jujur tetapi berhemah
- Nyatakan CGPA dan apa peluang yang dibuka/ditutup oleh CGPA tersebut

MUET:
Terangkan dengan jelas band MUET dan impaknya kepada permohonan universiti.

C. Kenapa Program Ini Sesuai (Realiti Sebenar)
Terangkan:
- Apa yang pelajar akan belajar di universiti
- Apa kerja harian sebenar selepas graduasi
- Suasana kerja (pejabat / tapak / makmal / hospital)
- Kenapa program ini sesuai berdasarkan profil pelajar

Gunakan ayat pendek dan contoh dunia sebenar Malaysia.

D. Cabaran & Pertukaran Realiti
WAJIB nyatakan harga yang perlu dibayar.
Contoh:
- Tempoh pengajian panjang (3-5 tahun)
- Persaingan tinggi dalam bidang ini
- Gaji permulaan mungkin tidak seperti dijangka
- Kos sara hidup di bandar universiti

Jangan lembutkan kebenaran.

E. Siapa Laluan Ini TAK Sesuai
Nyatakan dengan jelas dalam bentuk bullet.

F. Langkah Seterusnya (MESTI BOLEH BUAT DI RUMAH)
Beri 3 langkah MUDAH dan realistik:
- Semak syarat program di portal UPU (upu.mohe.gov.my)
- Cari video pelajar universiti dalam bidang ini di YouTube
- Tanya senior atau guru tentang pengalaman sebenar

❌ JANGAN:
- Suruh telefon universiti
- Suruh buat lawatan kampus tanpa tujuan jelas
- Suruh jumpa profesional asing

-----------------------------------
PERATURAN TAMBAHAN
-----------------------------------
- Ayat pendek
- Banyak bullet points
- Sesuai dibaca di telefon
- Panjang maksimum: ~500-600 patah perkataan
- Fokus bantu pelajar buat keputusan, bukan rasa "hebat"
-----------------------------------

DATA KONTEKS (DIBERIKAN):
Nama Pelajar: {student_name}
Profil Pelajar: {student_profile}
Keputusan STPM & CGPA: {academic_context}
Program Dicadangkan: {recommended_courses}
Ringkasan Kelayakan: {insights_summary}
"""
```

Create equivalent `PROMPT_STPM_EN` (English version with same structure).

Update `get_prompt()`:

```python
def get_prompt(lang='bm', exam_type='spm'):
    """Return the prompt template for the given language and exam type."""
    if exam_type == 'stpm':
        return PROMPT_STPM_EN if lang == 'en' else PROMPT_STPM_BM
    return PROMPT_EN if lang == 'en' else PROMPT_BM
```

**Step 4: Run tests**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/test_report_engine.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add apps/reports/prompts.py apps/reports/tests/test_report_engine.py
git commit -m "feat: add STPM-specific report prompt templates (BM + EN)"
```

---

## Task 7: Add STPM Academic Formatter

Create `_format_stpm_grades()` to format STPM grades + CGPA + MUET band for the prompt.

**Files:**
- Modify: `apps/reports/report_engine.py`
- Modify: `apps/reports/tests/test_report_engine.py`

**Step 1: Write the failing test**

```python
class TestStpmGradeFormatting(TestCase):
    def test_format_stpm_grades(self):
        stpm_grades = {'PA': 'B+', 'MATH_T': 'A-', 'PHYSICS': 'B'}
        result = _format_stpm_grades(stpm_grades, cgpa=3.33, muet_band=4)
        self.assertIn('Pengajian Am: B+', result)
        self.assertIn('Matematik T: A-', result)
        self.assertIn('Fizik: B', result)
        self.assertIn('CGPA: 3.33', result)
        self.assertIn('MUET: Band 4', result)

    def test_format_stpm_grades_empty(self):
        result = _format_stpm_grades({}, cgpa=None, muet_band=None)
        self.assertIn('Tiada', result)
```

**Step 2: Run — expect FAIL**

**Step 3: Implement**

```python
# STPM subject labels (BM display names)
STPM_SUBJECT_LABELS = {
    'PA': 'Pengajian Am',
    'MATH_T': 'Matematik T',
    'MATH_M': 'Matematik M',
    'PHYSICS': 'Fizik',
    'CHEMISTRY': 'Kimia',
    'BIOLOGY': 'Biologi',
    'ECONOMICS': 'Ekonomi',
    'ACCOUNTING': 'Perakaunan',
    'BUSINESS': 'Perniagaan',
    'BAHASA_MELAYU': 'Bahasa Melayu',
    'BAHASA_CINA': 'Bahasa Cina',
    'BAHASA_TAMIL': 'Bahasa Tamil',
    'SEJARAH': 'Sejarah',
    'GEOGRAFI': 'Geografi',
    'ICT': 'ICT',
    'SENI_VISUAL': 'Seni Visual',
    'SAINS_SUKAN': 'Sains Sukan',
}


def _format_stpm_grades(stpm_grades, cgpa=None, muet_band=None):
    """Format STPM grades + CGPA + MUET for the prompt."""
    if not stpm_grades and cgpa is None:
        return 'Tiada maklumat gred STPM.'

    lines = []
    for subj, grade in (stpm_grades or {}).items():
        label = STPM_SUBJECT_LABELS.get(subj, subj)
        lines.append(f'- {label}: {grade}')

    if cgpa is not None:
        lines.append(f'- CGPA: {cgpa}')
    if muet_band is not None:
        lines.append(f'- MUET: Band {muet_band}')

    return '\n'.join(lines) if lines else 'Tiada maklumat gred STPM.'
```

**Step 4: Run tests**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/test_report_engine.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add apps/reports/report_engine.py apps/reports/tests/test_report_engine.py
git commit -m "feat: add STPM grade formatter for report prompt"
```

---

## Task 8: Route Report Generation by exam_type

Update `generate_report()` to accept `exam_type` and route to the correct prompt + formatter. Update the view to pass `exam_type`.

**Files:**
- Modify: `apps/reports/report_engine.py`
- Modify: `apps/reports/views.py`
- Modify: `apps/reports/tests/test_report_engine.py`

**Step 1: Write the failing test**

```python
class TestExamTypeRouting(TestCase):
    @patch('apps.reports.report_engine.genai')
    def test_stpm_uses_stpm_prompt(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = 'STPM report'
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        result = generate_report(
            grades={},
            eligible_courses=[{'course_name': 'BSc CS', 'field': 'IT'}],
            insights={},
            student_signals={},
            student_name='Ali',
            lang='bm',
            exam_type='stpm',
            stpm_grades={'PA': 'A', 'MATH_T': 'B+'},
            stpm_cgpa=3.50,
            muet_band=4,
        )
        # Verify STPM prompt was used (contains "STPM" not "SPM" in prompt text)
        call_args = mock_genai.Client.return_value.models.generate_content.call_args
        prompt_text = str(call_args)
        self.assertIn('STPM', prompt_text)
        self.assertIn('CGPA: 3.5', prompt_text)
        self.assertIn('MUET: Band 4', prompt_text)

    @patch('apps.reports.report_engine.genai')
    def test_spm_default_uses_spm_prompt(self, mock_genai):
        mock_response = MagicMock()
        mock_response.text = 'SPM report'
        mock_genai.Client.return_value.models.generate_content.return_value = mock_response

        result = generate_report(
            grades={'bm': 'A'},
            eligible_courses=[{'course_name': 'Diploma IT', 'field': 'IT'}],
            insights={},
            lang='bm',
        )
        call_args = mock_genai.Client.return_value.models.generate_content.call_args
        prompt_text = str(call_args)
        self.assertIn('SPM', prompt_text)
```

**Step 2: Run — expect FAIL**

**Step 3: Implement**

Update `generate_report()` signature:

```python
def generate_report(grades, eligible_courses, insights,
                    student_signals=None, student_name='pelajar',
                    lang='bm', exam_type='spm',
                    stpm_grades=None, stpm_cgpa=None, muet_band=None):
```

Inside `generate_report()`, route academic context:

```python
    # Format data for prompt
    if exam_type == 'stpm':
        academic_context = _format_stpm_grades(stpm_grades, stpm_cgpa, muet_band)
    else:
        academic_context = _format_grades(grades)

    student_profile = _format_signals(student_signals, lang=lang)
    recommended_courses = _format_courses(eligible_courses)
    insights_summary = _format_insights(insights)

    prompt_template = get_prompt(lang, exam_type=exam_type)
```

Update `apps/reports/views.py` to pass exam_type and STPM data:

```python
        exam_type = profile.exam_type or 'spm'

        result = generate_report(
            grades=grades,
            eligible_courses=eligible_courses,
            insights=insights,
            student_signals=student_signals,
            student_name=profile.name or 'pelajar',
            lang=lang,
            exam_type=exam_type,
            stpm_grades=profile.stpm_grades if exam_type == 'stpm' else None,
            stpm_cgpa=profile.stpm_cgpa if exam_type == 'stpm' else None,
            muet_band=profile.muet_band if exam_type == 'stpm' else None,
        )
```

**Step 4: Run all tests**

Run: `cd halatuju_api && python -m pytest apps/reports/tests/ -v`
Expected: All pass

**Step 5: Commit**

```bash
git add apps/reports/report_engine.py apps/reports/views.py apps/reports/tests/
git commit -m "feat: route report generation by exam_type (SPM vs STPM)"
```

---

## Task 9: Run Full Test Suite + Final Verification

**Step 1: Run the complete test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v
```

Expected: 654+ tests pass (new tests added), 0 failures.

**Step 2: Verify golden masters unchanged**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_golden_master.py apps/courses/tests/test_stpm_golden_master.py -v
```

Expected: SPM = 5319, STPM = 2026 (unchanged — we didn't touch eligibility logic)

**Step 3: Manual smoke test**

```bash
cd halatuju_api && python -c "
from apps.reports.report_engine import _format_signals, _format_stpm_grades, _format_courses
print('=== Signals (BM) ===')
print(_format_signals({'field_interest': {'field_mechanical': 3, 'field_digital': 1}}, lang='bm'))
print()
print('=== Signals (EN) ===')
print(_format_signals({'field_interest': {'field_mechanical': 3}}, lang='en'))
print()
print('=== STPM Grades ===')
print(_format_stpm_grades({'PA': 'A', 'MATH_T': 'B+'}, cgpa=3.50, muet_band=4))
print()
print('=== Courses (sorted) ===')
print(_format_courses([
    {'course_name': 'Low', 'field': 'X', 'fit_score': 30},
    {'course_name': 'High', 'field': 'Y', 'fit_score': 70},
]))
"
```

**Step 4: Final commit if any fixups needed**

---

## Summary of Changes

| Task | What | Files |
|------|------|-------|
| 1 | Wire student name | `views.py` |
| 2 | Human-readable signals | `report_engine.py` |
| 3 | Smart course selection (top 5 by fit) | `report_engine.py` |
| 4 | Field display names in courses | `report_engine.py`, `views.py` |
| 5 | Drop persona system | `prompts.py`, `report_engine.py`, `views.py` |
| 6 | STPM prompt templates (BM + EN) | `prompts.py` |
| 7 | STPM grade formatter | `report_engine.py` |
| 8 | Route by exam_type | `report_engine.py`, `views.py` |
| 9 | Full test suite verification | — |

### Not in Scope (Future)
- MASCO career data in prompt (needs career occupations wired through)
- Institution/location context (needs student location + institution geo data)
- STPM quiz signals (quiz being designed — will slot into Section A when ready)
- EN language selector in frontend (frontend change, not backend)

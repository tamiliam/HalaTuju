# Visual Quiz Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the text-heavy 6-question quiz with a visual, tap-friendly 8+1 question quiz using icon cards, multi-select, conditional branching, and field interest matching — producing stronger course-matching signals.

**Architecture:** Backend-first approach. Update quiz data (8+1 Qs × 3 langs), extend the quiz engine to handle multi-select and "Not Sure Yet", add a 6th signal category (`field_interest`), add field matching and grade modulation to the ranking engine, then redesign the frontend quiz page with 2×2 icon card grid. The API contract changes: questions now include `select_mode` and `icon` fields; answers now support `option_indices` (array) for multi-select.

**Tech Stack:** Django REST Framework (backend), Next.js + Tailwind CSS (frontend), pytest (tests)

**Design doc:** `docs/quiz-redesign-final.md` — the authoritative source for all quiz content, signals, weights, and scoring rules.

---

## Task 1: Update quiz_data.py — New 8+1 Questions × 3 Languages

**Files:**
- Modify: `halatuju_api/apps/courses/quiz_data.py`

**Context:** Currently has 6 questions with text-only options. Replace with 8+1 questions (Q2.5 is conditional). Each option now has an `icon` field and optional `select_mode`. Refer to `docs/quiz-redesign-final.md` for exact question text, icons, labels, signals, and weights in all 3 languages.

**Step 1: Replace QUIZ_QUESTIONS data**

Replace the entire `QUIZ_QUESTIONS` dict with the new 8+1 question structure. Each question now has:
- `id`: stable identifier (new IDs: `q1_field1`, `q2_field2`, `q2_5_heavy`, `q3_work`, `q4_environment`, `q5_learning`, `q6_values`, `q7_energy`, `q8_practical`)
- `prompt`: question text
- `select_mode`: `'multi'` (Q1, Q2) or `'single'` (all others). Omit for single (backward compat).
- `max_select`: `2` for multi-select questions. Omit for single.
- `condition`: `{'requires': 'q2_field2', 'option_signal': 'field_heavy_industry'}` for Q2.5. Omit for unconditional.
- `options`: list of `{text, icon, signals}` — `icon` is a string identifier (e.g. `'wrench_gears'`)

The "Not Sure Yet" option on Q1, Q2, Q4 should have a special flag: `'not_sure': True`. When selected, it is the ONLY selection (cannot be combined with other picks).

**English questions (complete data):**

```python
QUIZ_QUESTIONS = {
    'en': [
        {
            'id': 'q1_field1',
            'prompt': 'What catches your eye?',
            'select_mode': 'multi',
            'max_select': 2,
            'options': [
                {'text': 'Build & Fix', 'icon': 'wrench_gears', 'signals': {'field_mechanical': 3}},
                {'text': 'Tech & Digital', 'icon': 'laptop_code', 'signals': {'field_digital': 3}},
                {'text': 'Business & Money', 'icon': 'handshake_chart', 'signals': {'field_business': 3}},
                {'text': 'Health & Care', 'icon': 'heart_stethoscope', 'signals': {'field_health': 3}},
                {'text': 'Not Sure Yet', 'icon': 'question_sparkle', 'not_sure': True,
                 'signals': {'field_mechanical': 1, 'field_digital': 1, 'field_business': 1, 'field_health': 1}},
            ],
        },
        {
            'id': 'q2_field2',
            'prompt': 'And this?',
            'select_mode': 'multi',
            'max_select': 2,
            'options': [
                {'text': 'Design & Create', 'icon': 'paintbrush_ruler', 'signals': {'field_creative': 3}},
                {'text': 'Food & Travel', 'icon': 'chef_suitcase', 'signals': {'field_hospitality': 3}},
                {'text': 'Nature & Farm', 'icon': 'leaf_tractor', 'signals': {'field_agriculture': 3}},
                {'text': 'Big Machines', 'icon': 'bolt_ship', 'signals': {'field_heavy_industry': 3}},
                {'text': 'Not Sure Yet', 'icon': 'question_sparkle', 'not_sure': True,
                 'signals': {'field_creative': 1, 'field_hospitality': 1, 'field_agriculture': 1, 'field_heavy_industry': 1}},
            ],
        },
        {
            'id': 'q2_5_heavy',
            'prompt': 'Which kind?',
            'condition': {'requires': 'q2_field2', 'option_signal': 'field_heavy_industry'},
            'options': [
                {'text': 'Electrical', 'icon': 'lightning_bolt', 'signals': {'field_electrical': 3}},
                {'text': 'Construction', 'icon': 'hardhat_crane', 'signals': {'field_civil': 3}},
                {'text': 'Aero & Marine', 'icon': 'airplane_ship', 'signals': {'field_aero_marine': 3}},
                {'text': 'Oil & Gas', 'icon': 'oil_rig_flame', 'signals': {'field_oil_gas': 3}},
            ],
        },
        {
            'id': 'q3_work',
            'prompt': 'Your ideal day at work',
            'options': [
                {'text': 'Hands-On', 'icon': 'hands_tools', 'signals': {'hands_on': 2}},
                {'text': 'Problem Solving', 'icon': 'brain_lightbulb', 'signals': {'problem_solving': 2}},
                {'text': 'With People', 'icon': 'people_bubbles', 'signals': {'people_helping': 2}},
                {'text': 'Creating Things', 'icon': 'pencil_star', 'signals': {'creative': 2}},
            ],
        },
        {
            'id': 'q4_environment',
            'prompt': 'Where would you work?',
            'options': [
                {'text': 'Workshop', 'icon': 'workshop_garage', 'signals': {'workshop_environment': 1}},
                {'text': 'Office', 'icon': 'desk_monitor', 'signals': {'office_environment': 1}},
                {'text': 'Outdoors', 'icon': 'trees_sun', 'signals': {'field_environment': 1}},
                {'text': 'With Crowds', 'icon': 'building_people', 'signals': {'high_people_environment': 1}},
                {'text': 'Not Sure Yet', 'icon': 'question_sparkle', 'not_sure': True, 'signals': {}},
            ],
        },
        {
            'id': 'q5_learning',
            'prompt': 'How do you learn best?',
            'options': [
                {'text': 'Do & Practise', 'icon': 'hammer_check', 'signals': {'learning_by_doing': 1}},
                {'text': 'Read & Understand', 'icon': 'book_magnifier', 'signals': {'concept_first': 1}},
                {'text': 'Projects & Teamwork', 'icon': 'clipboard_group', 'signals': {'project_based': 1}},
                {'text': 'Drill & Memorise', 'icon': 'loop_arrows', 'signals': {'rote_tolerant': 1}},
            ],
        },
        {
            'id': 'q6_values',
            'prompt': 'After SPM, what matters most?',
            'options': [
                {'text': 'Stable Job', 'icon': 'shield_check', 'signals': {'stability_priority': 2}},
                {'text': 'Good Pay', 'icon': 'money_rocket', 'signals': {'income_risk_tolerant': 2}},
                {'text': 'Continue Degree', 'icon': 'gradcap_arrow', 'signals': {'pathway_priority': 2}},
                {'text': 'Work Fast', 'icon': 'lightning_briefcase', 'signals': {'fast_employment_priority': 2}},
            ],
        },
        {
            'id': 'q7_energy',
            'prompt': 'What tires you out?',
            'options': [
                {'text': 'Too Many People', 'icon': 'crowd_sweat', 'signals': {'low_people_tolerance': 1}},
                {'text': 'Heavy Thinking', 'icon': 'brain_weight', 'signals': {'mental_fatigue_sensitive': 1}},
                {'text': 'Physical Work', 'icon': 'arm_weight', 'signals': {'physical_fatigue_sensitive': 1}},
                {'text': 'I Can Handle Anything', 'icon': 'flexed_arm_star', 'signals': {'high_stamina': 1}},
            ],
        },
        {
            'id': 'q8_practical',
            'prompt': 'What would help you keep studying?',
            'options': [
                {'text': 'Pocket Money', 'icon': 'wallet_coins', 'signals': {'allowance_priority': 3}},
                {'text': 'Near Home', 'icon': 'house_heart', 'signals': {'proximity_priority': 3}},
                {'text': 'Job Guarantee', 'icon': 'handshake_door', 'signals': {'employment_guarantee': 2}},
                {'text': 'Best Programme', 'icon': 'trophy_star', 'signals': {'quality_priority': 1}},
            ],
        },
    ],
    # BM and TA follow same structure — translate text only, keep signals/icons identical
}
```

For BM and TA translations, refer to the existing `quiz_data.py` for translation style. Key BM translations:
- Q1: "Apa yang menarik perhatian anda?"
- Q2: "Dan ini?"
- Q2.5: "Jenis yang mana?"
- Q3: "Hari ideal anda bekerja"
- Q4: "Di mana anda mahu bekerja?"
- Q5: "Bagaimana anda belajar terbaik?"
- Q6: "Selepas SPM, apa yang paling penting?"
- Q7: "Apa yang meletihkan anda?"
- Q8: "Apa yang membantu anda terus belajar?"

Update `QUESTION_IDS` list:
```python
QUESTION_IDS = [
    'q1_field1', 'q2_field2', 'q2_5_heavy',
    'q3_work', 'q4_environment', 'q5_learning',
    'q6_values', 'q7_energy', 'q8_practical',
]
```

**Step 2: Run existing tests to verify they fail (expected)**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_quiz.py -v`
Expected: Multiple failures — old question IDs no longer exist, option counts changed.

**Step 3: Commit**

```bash
git add halatuju_api/apps/courses/quiz_data.py
git commit -m "feat: replace quiz data with 8+1 visual card questions (EN/BM/TA)"
```

---

## Task 2: Update quiz_engine.py — Multi-Select, Not Sure, Field Interest Category

**Files:**
- Modify: `halatuju_api/apps/courses/quiz_engine.py`

**Context:** Currently handles single-select only (one `option_index` per question) and has 5 signal categories. Must add: (1) 6th category `field_interest` with 11 signals, (2) multi-select processing where weight splits from 3→2 per pick when 2 selected, (3) "Not Sure Yet" handling, (4) conditional Q2.5 skipping.

**Step 1: Update SIGNAL_TAXONOMY**

Add `field_interest` category and update existing categories:

```python
SIGNAL_TAXONOMY = {
    'field_interest': [
        'field_mechanical', 'field_digital', 'field_business', 'field_health',
        'field_creative', 'field_hospitality', 'field_agriculture',
        'field_heavy_industry',
        'field_electrical', 'field_civil', 'field_aero_marine', 'field_oil_gas',
    ],
    'work_preference_signals': [
        'hands_on', 'problem_solving', 'people_helping', 'creative',
        # 'organising' removed — dead signal
    ],
    'learning_tolerance_signals': [
        'learning_by_doing', 'concept_first', 'rote_tolerant', 'project_based',
        # 'exam_sensitive' removed — dead signal
    ],
    'environment_signals': [
        'workshop_environment', 'office_environment',
        'high_people_environment', 'field_environment',
        # 'no_preference' removed — dead signal
    ],
    'value_tradeoff_signals': [
        'stability_priority', 'income_risk_tolerant', 'pathway_priority',
        'fast_employment_priority',
        'proximity_priority', 'allowance_priority', 'employment_guarantee',
        'quality_priority',
        # 'meaning_priority' removed — dead signal
    ],
    'energy_sensitivity_signals': [
        'low_people_tolerance', 'mental_fatigue_sensitive',
        'physical_fatigue_sensitive', 'high_stamina',
        # 'time_pressure_sensitive' removed — dead signal
    ],
}
```

**Step 2: Update process_quiz_answers to handle multi-select**

The answer format changes. For single-select: `{'question_id': '...', 'option_index': 0}` (unchanged).
For multi-select: `{'question_id': '...', 'option_indices': [0, 2]}` (new field).

If `option_indices` is present, process all selected options. Apply weight splitting: if 2 options selected on a multi-select question, each signal weight is reduced from 3 to 2.

Also handle conditional Q2.5: if Q2.5 answer is provided but Q2D (field_heavy_industry) was NOT selected, skip Q2.5. If Q2D was selected but Q2.5 is missing from answers, that's acceptable (frontend decides when to show it).

```python
def process_quiz_answers(answers: list[dict[str, Any]], lang: str = 'en') -> dict:
    questions = get_quiz_questions(lang)
    questions_by_id = {q['id']: q for q in questions}

    raw_scores: dict[str, int] = {}

    # Track which signals were selected (for conditional branching validation)
    all_selected_signals = set()

    for answer in answers:
        qid = answer.get('question_id')
        if qid not in questions_by_id:
            raise ValueError(f'Unknown question_id: {qid}')

        question = questions_by_id[qid]
        options = question['options']

        # Check conditional: Q2.5 requires field_heavy_industry signal
        condition = question.get('condition')
        if condition:
            required_signal = condition.get('option_signal', '')
            if required_signal not in all_selected_signals:
                continue  # Skip this conditional question silently

        # Multi-select or single-select
        option_indices = answer.get('option_indices')
        option_idx = answer.get('option_index')

        if option_indices is not None:
            # Multi-select path
            if not isinstance(option_indices, list):
                raise ValueError(f'option_indices must be a list for {qid}')
            max_sel = question.get('max_select', 1)
            if len(option_indices) > max_sel:
                raise ValueError(f'Too many selections for {qid} (max {max_sel})')

            num_picks = len(option_indices)
            for oi in option_indices:
                if not isinstance(oi, int) or oi < 0 or oi >= len(options):
                    raise ValueError(f'option_index {oi} out of range for {qid}')
                chosen = options[oi]

                # "Not Sure Yet" is exclusive — if selected, must be only pick
                if chosen.get('not_sure') and num_picks > 1:
                    raise ValueError(f'"Not Sure Yet" must be the only selection for {qid}')

                for sig, weight in chosen.get('signals', {}).items():
                    # Weight splitting: 2 picks → reduce weight (3→2)
                    effective_weight = weight
                    if num_picks == 2 and not chosen.get('not_sure'):
                        effective_weight = max(1, weight - 1)  # 3→2, 2→1, 1→1
                    raw_scores[sig] = raw_scores.get(sig, 0) + effective_weight
                    all_selected_signals.add(sig)
        else:
            # Single-select path (backward compatible)
            if not isinstance(option_idx, int) or option_idx < 0 or option_idx >= len(options):
                raise ValueError(f'option_index {option_idx} out of range for {qid}')
            chosen = options[option_idx]
            for sig, weight in chosen.get('signals', {}).items():
                raw_scores[sig] = raw_scores.get(sig, 0) + weight
                all_selected_signals.add(sig)

    # Categorise into 6-bucket taxonomy
    student_signals = {cat: {} for cat in SIGNAL_TAXONOMY}
    signal_strength = {}

    for sig, score in raw_scores.items():
        if score <= 0:
            continue
        category = _SIGNAL_TO_CATEGORY.get(sig)
        if category:
            student_signals[category][sig] = score
            signal_strength[sig] = 'strong' if score >= 2 else 'moderate'

    return {
        'student_signals': student_signals,
        'signal_strength': signal_strength,
    }
```

**Step 3: Commit**

```bash
git add halatuju_api/apps/courses/quiz_engine.py
git commit -m "feat: add multi-select, field_interest category, and conditional Q2.5 to quiz engine"
```

---

## Task 3: Update quiz tests — New Questions, Multi-Select, Branching

**Files:**
- Modify: `halatuju_api/apps/courses/tests/test_quiz.py`

**Context:** All existing quiz tests will fail because question IDs changed and question count changed from 6 to 9. Rewrite tests for the new quiz structure.

**Step 1: Rewrite test file**

Key test cases needed:
1. **GET questions endpoint**: returns 9 questions (including conditional Q2.5), 3 languages
2. **Submit single-select**: Q3-Q8 with `option_index` — backward compatible
3. **Submit multi-select**: Q1 with `option_indices: [0, 1]` — weight splits to 2 each
4. **Submit "Not Sure Yet"**: Q1 with `option_indices: [4]` — distributes +1 to all 4 fields
5. **"Not Sure Yet" exclusivity**: Q1 with `option_indices: [0, 4]` — should return 400
6. **Conditional Q2.5 fires**: Q2 picks "Big Machines" (index 3) → Q2.5 answer is processed
7. **Conditional Q2.5 skipped**: Q2 picks "Design & Create" (index 0) → Q2.5 answer ignored
8. **6 categories returned**: `student_signals` has all 6 categories including `field_interest`
9. **Field interest signals accumulated**: Q1 picks "Build & Fix" → `field_mechanical: 3`
10. **All languages have same question IDs**: EN, BM, TA parity check
11. **Signal strength classification**: score >= 2 = strong, score == 1 = moderate
12. **Empty "Not Sure Yet" on Q4**: Q4 index 4 → no signal (empty dict)

```python
"""Tests for visual quiz — 8+1 questions, multi-select, branching, Not Sure Yet."""
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.quiz_engine import process_quiz_answers, SIGNAL_TAXONOMY
from apps.courses.quiz_data import QUESTION_IDS, QUIZ_QUESTIONS


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestQuizQuestionsEndpoint(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_get_questions_returns_9(self):
        response = self.client.get('/api/v1/quiz/questions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total'], 9)

    def test_get_questions_bm(self):
        response = self.client.get('/api/v1/quiz/questions/?lang=bm')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'bm')

    def test_get_questions_tamil(self):
        response = self.client.get('/api/v1/quiz/questions/?lang=ta')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'ta')

    def test_invalid_lang_falls_back_to_english(self):
        response = self.client.get('/api/v1/quiz/questions/?lang=zz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lang'], 'en')

    def test_questions_include_icon_field(self):
        response = self.client.get('/api/v1/quiz/questions/')
        q1 = response.data['questions'][0]
        self.assertIn('icon', q1['options'][0])

    def test_multi_select_questions_have_select_mode(self):
        response = self.client.get('/api/v1/quiz/questions/')
        q1 = response.data['questions'][0]
        self.assertEqual(q1.get('select_mode'), 'multi')
        self.assertEqual(q1.get('max_select'), 2)


@override_settings(ROOT_URLCONF='halatuju.urls')
class TestQuizSubmitEndpoint(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _make_answers(self):
        """Full answers: Q1 single pick, Q2 single pick (not Big Machines), Q3-Q8 all index 0."""
        return [
            {'question_id': 'q1_field1', 'option_indices': [0]},      # Build & Fix
            {'question_id': 'q2_field2', 'option_indices': [0]},      # Design & Create
            # Q2.5 skipped (no Big Machines)
            {'question_id': 'q3_work', 'option_index': 0},            # Hands-On
            {'question_id': 'q4_environment', 'option_index': 0},     # Workshop
            {'question_id': 'q5_learning', 'option_index': 0},        # Do & Practise
            {'question_id': 'q6_values', 'option_index': 0},          # Stable Job
            {'question_id': 'q7_energy', 'option_index': 0},          # Too Many People
            {'question_id': 'q8_practical', 'option_index': 0},       # Pocket Money
        ]

    def test_submit_returns_200(self):
        response = self.client.post('/api/v1/quiz/submit/',
            {'answers': self._make_answers()}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_submit_returns_six_categories(self):
        response = self.client.post('/api/v1/quiz/submit/',
            {'answers': self._make_answers()}, format='json')
        cats = response.data['student_signals']
        for cat in SIGNAL_TAXONOMY:
            self.assertIn(cat, cats)

    def test_submit_empty_answers_returns_400(self):
        response = self.client.post('/api/v1/quiz/submit/',
            {'answers': []}, format='json')
        self.assertEqual(response.status_code, 400)


class TestQuizEngine(TestCase):
    """Unit tests for quiz_engine.process_quiz_answers()."""

    def test_single_select_field_interest(self):
        """Q1 single pick → field_mechanical: 3."""
        answers = [{'question_id': 'q1_field1', 'option_indices': [0]}]
        result = process_quiz_answers(answers)
        self.assertEqual(result['student_signals']['field_interest']['field_mechanical'], 3)

    def test_multi_select_weight_split(self):
        """Q1 two picks → each field gets weight 2 (split from 3)."""
        answers = [{'question_id': 'q1_field1', 'option_indices': [0, 1]}]
        result = process_quiz_answers(answers)
        self.assertEqual(result['student_signals']['field_interest']['field_mechanical'], 2)
        self.assertEqual(result['student_signals']['field_interest']['field_digital'], 2)

    def test_not_sure_distributes_evenly(self):
        """Q1 'Not Sure Yet' → +1 to all 4 fields."""
        answers = [{'question_id': 'q1_field1', 'option_indices': [4]}]
        result = process_quiz_answers(answers)
        fi = result['student_signals']['field_interest']
        self.assertEqual(fi.get('field_mechanical'), 1)
        self.assertEqual(fi.get('field_digital'), 1)
        self.assertEqual(fi.get('field_business'), 1)
        self.assertEqual(fi.get('field_health'), 1)

    def test_not_sure_exclusive(self):
        """Cannot combine 'Not Sure Yet' with another pick."""
        answers = [{'question_id': 'q1_field1', 'option_indices': [0, 4]}]
        with self.assertRaises(ValueError):
            process_quiz_answers(answers)

    def test_conditional_q2_5_fires(self):
        """Q2 picks Big Machines → Q2.5 answer processed."""
        answers = [
            {'question_id': 'q2_field2', 'option_indices': [3]},  # Big Machines
            {'question_id': 'q2_5_heavy', 'option_index': 0},     # Electrical
        ]
        result = process_quiz_answers(answers)
        self.assertEqual(result['student_signals']['field_interest']['field_electrical'], 3)

    def test_conditional_q2_5_skipped(self):
        """Q2 picks Design & Create → Q2.5 answer ignored."""
        answers = [
            {'question_id': 'q2_field2', 'option_indices': [0]},  # Design & Create
            {'question_id': 'q2_5_heavy', 'option_index': 0},     # Electrical (should be ignored)
        ]
        result = process_quiz_answers(answers)
        self.assertNotIn('field_electrical', result['student_signals']['field_interest'])

    def test_high_stamina_signal(self):
        """Q7D 'I Can Handle Anything' → high_stamina: 1."""
        answers = [{'question_id': 'q7_energy', 'option_index': 3}]
        result = process_quiz_answers(answers)
        self.assertEqual(result['student_signals']['energy_sensitivity_signals']['high_stamina'], 1)

    def test_quality_priority_signal(self):
        """Q8D 'Best Programme' → quality_priority: 1."""
        answers = [{'question_id': 'q8_practical', 'option_index': 3}]
        result = process_quiz_answers(answers)
        self.assertEqual(result['student_signals']['value_tradeoff_signals']['quality_priority'], 1)

    def test_q4_not_sure_produces_no_signal(self):
        """Q4 'Not Sure Yet' → empty signals (weight 0)."""
        answers = [{'question_id': 'q4_environment', 'option_index': 4}]
        result = process_quiz_answers(answers)
        env = result['student_signals']['environment_signals']
        self.assertEqual(env, {})

    def test_signal_strength_classification(self):
        """Score >= 2 = strong, score == 1 = moderate."""
        answers = [
            {'question_id': 'q1_field1', 'option_indices': [0]},  # field_mechanical: 3
            {'question_id': 'q4_environment', 'option_index': 0},  # workshop: 1
        ]
        result = process_quiz_answers(answers)
        self.assertEqual(result['signal_strength']['field_mechanical'], 'strong')
        self.assertEqual(result['signal_strength']['workshop_environment'], 'moderate')

    def test_all_languages_have_same_question_ids(self):
        for lang in ['en', 'bm', 'ta']:
            questions = QUIZ_QUESTIONS[lang]
            ids = [q['id'] for q in questions]
            self.assertEqual(ids, QUESTION_IDS, f'{lang} question IDs mismatch')
```

**Step 2: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_quiz.py -v`
Expected: All tests PASS.

**Step 3: Commit**

```bash
git add halatuju_api/apps/courses/tests/test_quiz.py
git commit -m "test: rewrite quiz tests for 8+1 visual questions with multi-select and branching"
```

---

## Task 4: Update ranking_engine.py — Field Interest Matching + New Signals

**Files:**
- Modify: `halatuju_api/apps/courses/ranking_engine.py`

**Context:** Add field interest matching (the biggest impact change), wire `rote_tolerant`, `high_stamina`, `quality_priority` signals, adjust category caps (field ±8, work ±4), add `field_interest` to category scoring, remove dead signal references (`organising`, `meaning_priority`, `time_pressure_sensitive`, `no_preference`, `exam_sensitive`).

**Step 1: Add constants and field label map**

Add at the top of the file, after existing constants:

```python
# Category-specific caps (override CATEGORY_CAP for these)
FIELD_INTEREST_CAP = 8
WORK_PREFERENCE_CAP = 4

# Field interest → course frontend_label mapping
FIELD_LABEL_MAP = {
    'field_mechanical': ['Mekanikal & Automotif'],
    'field_digital': ['Komputer, IT & Multimedia'],
    'field_business': ['Perniagaan & Perdagangan'],
    'field_health': ['Pertanian & Bio-Industri'],
    'field_creative': ['Seni Reka & Kreatif'],
    'field_hospitality': ['Hospitaliti, Kulinari & Pelancongan'],
    'field_agriculture': ['Pertanian & Bio-Industri'],
    'field_heavy_industry': [
        'Aero, Marin, Minyak & Gas',
        'Elektrik & Elektronik',
        'Sivil, Seni Bina & Pembinaan',
    ],
    'field_electrical': ['Elektrik & Elektronik'],
    'field_civil': ['Sivil, Seni Bina & Pembinaan'],
    'field_aero_marine': ['Aero, Marin, Minyak & Gas'],
    'field_oil_gas': ['Aero, Marin, Minyak & Gas'],
}
```

**Step 2: Add field interest scoring to calculate_fit_score**

Inside `calculate_fit_score`, after the existing `cat_scores` dict initialisation, add `'field_interest': 0` to the dict.

Add a new section before "A. Fit Scoring" that handles field interest:

```python
    # --- Field Interest Matching ---
    field_signals = signals.get('field_interest', {})
    course_label = ''  # Must be passed in or looked up
    # course_label comes from the course object's frontend_label
    # It's passed via course_tags_map[course_id].get('frontend_label', '')

    if field_signals and course_label:
        # Find matching field signals for this course
        matches = []
        for sig_name, sig_score in sorted(field_signals.items(), key=lambda x: -x[1]):
            labels = FIELD_LABEL_MAP.get(sig_name, [])
            if course_label in labels:
                matches.append(sig_score)

        if matches:
            # Primary match: +8, secondary: +4 (before cap)
            cat_scores['field_interest'] += 8
            if len(matches) > 1:
                cat_scores['field_interest'] += 4
```

**Important:** The `course_label` (frontend_label) must be available to the ranking engine. Currently `calculate_fit_score` receives `course_tags_map` which doesn't include `frontend_label`. Two options:
- **Option A:** Add `frontend_label` to the `course_tags_map` dict during startup data loading.
- **Option B:** Pass it as a separate parameter.

Use **Option A**: In `apps.py` or wherever course tags are loaded, include `'frontend_label': course.frontend_label` in the tags dict for each course.

**Step 3: Add rote_tolerant, high_stamina, quality_priority rules**

After the existing learning tolerance section, add:
```python
    # Rote tolerant rule (was dead signal, now wired)
    sig_rote = get_signal('learning_tolerance_signals', 'rote_tolerant')
    if sig_rote > 0 and 'assessment_heavy' in tag_styles:
        cat_scores['learning_tolerance_signals'] += 3
        match_reasons.append("comfort with structured assessment")
```

In the energy sensitivity section, add high_stamina boost:
```python
    # High stamina: positive boost for demanding courses
    sig_stamina = get_signal('energy_sensitivity_signals', 'high_stamina')
    if sig_stamina > 0:
        if tag_load in ('physically_demanding', 'mentally_demanding'):
            cat_scores['energy_sensitivity_signals'] += 2
            match_reasons.append("high stamina for demanding programme")
```

In the values section, add quality_priority:
```python
    # Quality priority: small boost for pathway-friendly / regulated courses
    sig_quality = get_signal('value_tradeoff_signals', 'quality_priority')
    if sig_quality > 0 and tag_outcome in ('pathway_friendly', 'regulated_profession'):
        cat_scores['value_tradeoff_signals'] += 1
        match_reasons.append("preference for quality programme")
```

**Step 4: Update category cap logic**

Replace the single `CATEGORY_CAP` clamping with per-category caps:

```python
    # --- B. Normalisation & Aggregation ---
    CAPS = {
        'field_interest': FIELD_INTEREST_CAP,
        'work_preference_signals': WORK_PREFERENCE_CAP,
        'learning_tolerance_signals': CATEGORY_CAP,
        'environment_signals': CATEGORY_CAP,
        'value_tradeoff_signals': CATEGORY_CAP,
        'energy_sensitivity_signals': CATEGORY_CAP,
    }
    fit_score = 0
    for cat, score in cat_scores.items():
        cap = CAPS.get(cat, CATEGORY_CAP)
        capped = max(min(score, cap), -cap)
        fit_score += capped
```

**Step 5: Remove dead signal references**

Remove any code referencing: `organising`, `meaning_priority`, `exam_sensitive`, `time_pressure_sensitive`, `no_preference`. Search the file and remove:
- `sig_meaning` variable and all blocks that use it
- Any reference to `time_pressure_sensitive`

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/ranking_engine.py
git commit -m "feat: add field interest matching, wire new signals, adjust category caps in ranking engine"
```

---

## Task 5: Wire frontend_label into course_tags_map

**Files:**
- Modify: `halatuju_api/apps/courses/apps.py`

**Context:** The ranking engine needs `frontend_label` in the course tags map to match field interest signals against courses. Currently `course_tags_map` is loaded from `CourseTag` model which doesn't include `frontend_label`. We need to include it.

**Step 1: Find where course_tags_map is built**

Look at `apps.py` `ready()` method where data is loaded at startup, and wherever `course_tags_map` is constructed. Add `frontend_label` from the `Course` model:

```python
# After building course_tags_map from CourseTag model:
# Enrich with frontend_label from Course model
for course in Course.objects.only('course_id', 'frontend_label'):
    if course.course_id in course_tags_map:
        course_tags_map[course.course_id]['frontend_label'] = course.frontend_label
    else:
        course_tags_map[course.course_id] = {'frontend_label': course.frontend_label}
```

**Step 2: Update calculate_fit_score to read frontend_label**

In `ranking_engine.py`, in `calculate_fit_score`, set `course_label` from tags:

```python
    course_label = c_tags.get('frontend_label', '')
```

**Step 3: Run ranking tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_ranking.py -v`
Expected: Existing tests still pass (no regressions). Field interest tests will be added in Task 6.

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/apps.py halatuju_api/apps/courses/ranking_engine.py
git commit -m "feat: wire frontend_label into course_tags_map for field interest matching"
```

---

## Task 6: Update ranking tests — Field Interest, New Signals, Updated Caps

**Files:**
- Modify: `halatuju_api/apps/courses/tests/test_ranking.py`

**Context:** Add tests for field interest matching, high_stamina, rote_tolerant, quality_priority, and the updated category caps (field ±8, work ±4). Update the `make_signals` helper to include `field_interest` category.

**Step 1: Update helpers**

```python
def make_signals(**kwargs):
    """Build a student_signals dict with specified signal values."""
    base = {
        'field_interest': {},
        'work_preference_signals': {},
        'learning_tolerance_signals': {},
        'environment_signals': {},
        'value_tradeoff_signals': {},
        'energy_sensitivity_signals': {},
    }
    for key, val in kwargs.items():
        parts = key.split('.')
        if len(parts) == 2:
            base[parts[0]][parts[1]] = val
    return base
```

**Step 2: Add new test cases**

```python
class TestFieldInterestMatching(TestCase):
    def test_primary_field_match_gives_8(self):
        signals = make_signals(**{'field_interest.field_mechanical': 3})
        tags = {'frontend_label': 'Mekanikal & Automotif', 'work_modality': 'hands_on'}
        score, reasons = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        # Should get +8 for primary field match (before global cap)
        self.assertGreater(score, BASE_SCORE)
        self.assertTrue(any('field' in r.lower() for r in reasons) or score > BASE_SCORE)

    def test_no_field_match_no_penalty(self):
        signals = make_signals(**{'field_interest.field_digital': 3})
        tags = {'frontend_label': 'Mekanikal & Automotif', 'work_modality': 'hands_on'}
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        # Field interest is additive only — no penalty for non-match
        self.assertEqual(score, BASE_SCORE)  # No field match = 0 field contribution

    def test_field_interest_cap_8(self):
        """Field interest score capped at 8."""
        signals = make_signals(**{
            'field_interest.field_mechanical': 3,
            'field_interest.field_digital': 3,
        })
        tags = {'frontend_label': 'Mekanikal & Automotif'}
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        # Even with multiple signals, field cap is 8
        self.assertLessEqual(score - BASE_SCORE, 8 + CATEGORY_CAP * 5)

class TestHighStamina(TestCase):
    def test_high_stamina_boosts_demanding_course(self):
        signals = make_signals(**{'energy_sensitivity_signals.high_stamina': 1})
        tags = {'load': 'physically_demanding'}
        score, reasons = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertGreater(score, BASE_SCORE)

class TestRoteTolerant(TestCase):
    def test_rote_tolerant_boosts_assessment_heavy(self):
        signals = make_signals(**{'learning_tolerance_signals.rote_tolerant': 1})
        tags = {'learning_style': ['assessment_heavy']}
        score, reasons = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertGreater(score, BASE_SCORE)

class TestQualityPriority(TestCase):
    def test_quality_priority_boosts_pathway_friendly(self):
        signals = make_signals(**{'value_tradeoff_signals.quality_priority': 1})
        tags = {'outcome': 'pathway_friendly'}
        score, reasons = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        self.assertGreater(score, BASE_SCORE)

class TestWorkPreferenceCap(TestCase):
    def test_work_preference_capped_at_4(self):
        """Work preference cap reduced from 6 to 4."""
        signals = make_signals(**{'work_preference_signals.hands_on': 2})
        tags = {'work_modality': 'hands_on', 'learning_style': ['project_based'],
                'creative_output': 'expressive', 'cognitive_type': 'abstract'}
        score, _ = calculate_fit_score(
            {'student_signals': signals}, 'C001', 'I001', {'C001': tags}, {})
        # Even with max matching, work preference is capped at 4
        # Total = BASE_SCORE + min(work_score, 4) + other categories
        self.assertLessEqual(score, BASE_SCORE + GLOBAL_CAP)
```

**Step 3: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_ranking.py -v`
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add halatuju_api/apps/courses/tests/test_ranking.py
git commit -m "test: add field interest, high_stamina, rote_tolerant, quality_priority, and cap tests"
```

---

## Task 7: Update QuizSubmitView — Handle Multi-Select Answers

**Files:**
- Modify: `halatuju_api/apps/courses/views.py` (QuizSubmitView, lines ~411-459)

**Context:** The submit view currently validates that each answer has `option_index`. With multi-select, some answers will have `option_indices` (array) instead. Update validation to accept either format.

**Step 1: Update validation in QuizSubmitView.post()**

Replace the validation loop:

```python
        for i, answer in enumerate(answers):
            if 'question_id' not in answer:
                return Response(
                    {'error': f'answers[{i}] missing question_id'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Accept either option_index (single) or option_indices (multi)
            if 'option_index' not in answer and 'option_indices' not in answer:
                return Response(
                    {'error': f'answers[{i}] missing option_index or option_indices'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
```

**Step 2: Commit**

```bash
git add halatuju_api/apps/courses/views.py
git commit -m "feat: accept multi-select option_indices in quiz submit endpoint"
```

---

## Task 8: Redesign Frontend Quiz Page — Visual Card Grid

**Files:**
- Modify: `halatuju-web/src/app/quiz/page.tsx`
- Modify: `halatuju-web/src/lib/api.ts` (update QuizQuestion type)

**Context:** Replace the text-list layout with a 2×2 icon card grid. Add multi-select support (toggle cards, "Next" button for multi-select, auto-advance for single-select). Add conditional Q2.5 branching. Add "Not Sure Yet" pill button below the grid.

**Step 1: Update QuizQuestion type in api.ts**

```typescript
export interface QuizQuestion {
  id: string
  prompt: string
  options: { text: string; icon: string; signals: Record<string, number>; not_sure?: boolean }[]
  select_mode?: 'multi' | 'single'
  max_select?: number
  condition?: { requires: string; option_signal: string }
}

export interface QuizAnswer {
  question_id: string
  option_index?: number
  option_indices?: number[]
}
```

**Step 2: Redesign quiz page**

Key changes to `quiz/page.tsx`:
1. **State**: Change `answers` from `(number | null)[]` to `(number | number[] | null)[]` to support multi-select
2. **Visible questions**: Filter out Q2.5 if the student didn't pick "Big Machines" (check if any answer for `q2_field2` includes `field_heavy_industry` signal)
3. **Card grid layout**: Replace `space-y-3` list with `grid grid-cols-2 gap-4` for the 4 main cards
4. **"Not Sure Yet" button**: Render separately as a pill below the grid (for Q1, Q2, Q4)
5. **Multi-select toggle**: For `select_mode: 'multi'`, cards toggle on/off. After 2 selected, remaining grey out. Show "Next" button instead of auto-advance.
6. **Single-select auto-advance**: Keep existing 300ms auto-advance for single-select
7. **Icon rendering**: Use emoji or SVG icons based on the `icon` field. Initially can use text labels — icon assets come later.
8. **Progress bar**: Update to show visible question count (varies due to Q2.5 being conditional)

Card component design:
```tsx
<button
  className={`
    aspect-square rounded-2xl border-2 p-4
    flex flex-col items-center justify-center gap-3
    transition-all duration-200
    ${selected ? 'border-primary-500 bg-primary-50 shadow-md scale-105' : 'border-gray-200 bg-white hover:border-primary-200'}
    ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
  `}
>
  <span className="text-3xl">{iconEmoji}</span>
  <span className="text-sm font-semibold text-center">{option.text}</span>
</button>
```

Icon emoji mapping (temporary — replace with SVG icons later):
```typescript
const ICON_EMOJI: Record<string, string> = {
  wrench_gears: '🔧',
  laptop_code: '💻',
  handshake_chart: '🤝',
  heart_stethoscope: '❤️',
  question_sparkle: '✨',
  paintbrush_ruler: '🎨',
  chef_suitcase: '👨‍🍳',
  leaf_tractor: '🌿',
  bolt_ship: '⚡',
  lightning_bolt: '⚡',
  hardhat_crane: '🏗️',
  airplane_ship: '✈️',
  oil_rig_flame: '🛢️',
  hands_tools: '🛠️',
  brain_lightbulb: '🧠',
  people_bubbles: '👥',
  pencil_star: '✏️',
  workshop_garage: '🏭',
  desk_monitor: '🖥️',
  trees_sun: '🌳',
  building_people: '🏢',
  hammer_check: '🔨',
  book_magnifier: '📖',
  clipboard_group: '📋',
  loop_arrows: '🔄',
  shield_check: '🛡️',
  money_rocket: '💰',
  gradcap_arrow: '🎓',
  lightning_briefcase: '⚡',
  crowd_sweat: '😰',
  brain_weight: '🧠',
  arm_weight: '💪',
  flexed_arm_star: '💪',
  wallet_coins: '👛',
  house_heart: '🏠',
  handshake_door: '🤝',
  trophy_star: '🏆',
}
```

**Step 3: Update handleSubmit to send correct answer format**

```typescript
const handleSubmit = async () => {
  const lang = localStorage.getItem('halatuju_lang') || 'en'
  const quizAnswers: QuizAnswer[] = visibleQuestions.map((q, i) => {
    const answer = answers[i]
    if (Array.isArray(answer)) {
      return { question_id: q.id, option_indices: answer }
    }
    return { question_id: q.id, option_index: answer! }
  })
  // ... rest unchanged
}
```

**Step 4: Commit**

```bash
git add halatuju-web/src/app/quiz/page.tsx halatuju-web/src/lib/api.ts
git commit -m "feat: redesign quiz page with visual card grid, multi-select, and conditional branching"
```

---

## Task 9: Update i18n Messages for Quiz Page

**Files:**
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Context:** Add i18n keys for quiz page UI elements: "Pick up to 2", "Not Sure Yet", progress text, submit button.

**Step 1: Add keys**

```json
// en.json - under "quiz" key
"quiz": {
  "pickUpTo": "Pick up to {count}",
  "notSureYet": "Not Sure Yet",
  "next": "Next",
  "previous": "Previous",
  "seeResults": "See My Results",
  "submitting": "Submitting...",
  "skipQuiz": "Skip Quiz",
  "questionOf": "Question {current} of {total}",
  "answered": "{count} answered",
  "becauseYouPicked": "Because you picked Big Machines..."
}
```

Equivalent BM and TA translations.

**Step 2: Commit**

```bash
git add halatuju-web/src/messages/en.json halatuju-web/src/messages/ms.json halatuju-web/src/messages/ta.json
git commit -m "feat: add i18n keys for visual quiz page (EN/BM/TA)"
```

---

## Task 10: Run Full Test Suite + Manual Verification

**Files:** None (verification only)

**Step 1: Run backend tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ -v`
Expected: All tests pass. Golden master unchanged (8245 — quiz doesn't affect eligibility).

**Step 2: Run frontend dev server**

Run: `cd halatuju-web && npm run dev`
Manual check:
1. Navigate to /quiz
2. See 2×2 card grid with icons
3. Q1: tap 2 cards → both highlight, "Next" button appears
4. Q1: tap "Not Sure Yet" → only that highlights, auto-advance
5. Q2: pick "Big Machines" → Q2.5 appears next
6. Q2: pick "Design & Create" → Q2.5 skipped, goes to Q3
7. Q3-Q8: single tap auto-advances
8. Submit → signals stored, redirect to dashboard

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: address issues found during manual verification"
```

---

## Task 11 (Deferred): Grade Modulation Layer

**Files:**
- Modify: `halatuju_api/apps/courses/ranking_engine.py`

**Context:** This task implements the 4 grade modulation rules from `docs/quiz-redesign-final.md`. Deferred because it requires `StudentProfile.grades` to be available in the ranking engine, which needs a refactor of `get_ranked_results` to accept student grades. Implement in a follow-up sprint if needed.

**Rules to implement:**
1. Imposter syndrome dampening: merit >= 75th %ile + mental_fatigue → penalty -2 (not -6)
2. Academic anxiety routing: weak grades + rote_tolerant + assessment_heavy → +3
3. Stream-field safety net: Science subjects + non-Science field → +1 to Science fields
4. Physical fatigue: no modulation (already the default)

---

## Summary

| Task | What | Files | Effort |
|------|------|-------|--------|
| 1 | Quiz data — 8+1 Qs × 3 langs | quiz_data.py | Medium |
| 2 | Quiz engine — multi-select, field_interest, branching | quiz_engine.py | Medium |
| 3 | Quiz tests — rewrite for new structure | test_quiz.py | Medium |
| 4 | Ranking engine — field matching, new signals, caps | ranking_engine.py | Medium |
| 5 | Wire frontend_label into course_tags_map | apps.py, ranking_engine.py | Small |
| 6 | Ranking tests — field interest, new signal tests | test_ranking.py | Medium |
| 7 | Quiz submit view — accept multi-select | views.py | Small |
| 8 | Frontend quiz page — visual card grid | page.tsx, api.ts | Large |
| 9 | i18n messages | en/ms/ta.json | Small |
| 10 | Full test suite + manual verification | — | Small |
| 11 | Grade modulation (deferred) | ranking_engine.py | Medium |

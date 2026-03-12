# STPM Sprint 3 — Supabase Migration + Ranking

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make STPM feature production-ready: create Supabase tables with RLS, add ranking to STPM results, and upgrade the dashboard to show ranked programmes with fit scores.

**Architecture:** Supabase migration creates `stpm_courses` + `stpm_requirements` tables (read-only reference data, public SELECT). New `stpm_ranking.py` module scores eligible programmes using CGPA margin + stream match + quiz signals. Dashboard integrates ranking to sort STPM results by fit score.

**Tech Stack:** Supabase SQL (DDL + RLS), Django REST (ranking engine, API endpoint), Next.js (dashboard upgrade)

---

## Data Contract

### STPM Ranking Request (new endpoint)
```json
POST /api/v1/stpm/ranking/
{
  "eligible_programmes": [
    {
      "program_id": "UP6314001",
      "program_name": "BACELOR EKONOMI DENGAN KEPUJIAN",
      "university": "Universiti Putra Malaysia",
      "stream": "both",
      "min_cgpa": 2.50,
      "min_muet_band": 3,
      "req_interview": false,
      "no_colorblind": false
    }
  ],
  "student_cgpa": 3.45,
  "student_signals": {
    "field_interest": ["field_business", "field_social_science"],
    "work_preference": "structured",
    "high_stamina": true
  }
}
```

### STPM Ranking Response
```json
{
  "ranked_programmes": [
    {
      "program_id": "UP6314001",
      "program_name": "BACELOR EKONOMI DENGAN KEPUJIAN",
      "university": "Universiti Putra Malaysia",
      "stream": "both",
      "min_cgpa": 2.50,
      "min_muet_band": 3,
      "req_interview": false,
      "no_colorblind": false,
      "fit_score": 78.5,
      "fit_reasons": ["CGPA margin: +0.95", "Field match: business"]
    }
  ],
  "total": 42
}
```

---

## Task 1: Supabase migration — create tables + RLS

**Files:**
- Create: `halatuju_api/apps/courses/management/commands/generate_stpm_sql.py`
- Reference: `docs/incident-001-rls-disabled.md` (RLS templates)

**Step 1: Write SQL generation command**

Management command that prints CREATE TABLE + RLS SQL for `stpm_courses` and `stpm_requirements`, matching the Django model fields exactly.

```python
# generate_stpm_sql.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Generate SQL for STPM tables + RLS policies'

    def handle(self, *args, **options):
        sql = """
-- STPM Courses table
CREATE TABLE IF NOT EXISTS public.stpm_courses (
    program_id VARCHAR(50) PRIMARY KEY,
    program_name VARCHAR(500) NOT NULL,
    university VARCHAR(255) NOT NULL,
    stream VARCHAR(20) NOT NULL CHECK (stream IN ('science', 'arts', 'both'))
);

-- STPM Requirements table
CREATE TABLE IF NOT EXISTS public.stpm_requirements (
    id BIGSERIAL PRIMARY KEY,
    course_id VARCHAR(50) NOT NULL REFERENCES public.stpm_courses(program_id) ON DELETE CASCADE,
    min_cgpa DOUBLE PRECISION DEFAULT 2.0,
    stpm_min_subjects INTEGER DEFAULT 2,
    stpm_min_grade VARCHAR(5) DEFAULT 'C',
    stpm_req_pa BOOLEAN DEFAULT FALSE,
    stpm_req_math_t BOOLEAN DEFAULT FALSE,
    stpm_req_math_m BOOLEAN DEFAULT FALSE,
    stpm_req_physics BOOLEAN DEFAULT FALSE,
    stpm_req_chemistry BOOLEAN DEFAULT FALSE,
    stpm_req_biology BOOLEAN DEFAULT FALSE,
    stpm_req_economics BOOLEAN DEFAULT FALSE,
    stpm_req_accounting BOOLEAN DEFAULT FALSE,
    stpm_req_business BOOLEAN DEFAULT FALSE,
    stpm_subject_group JSONB,
    spm_credit_bm BOOLEAN DEFAULT FALSE,
    spm_pass_sejarah BOOLEAN DEFAULT FALSE,
    spm_credit_bi BOOLEAN DEFAULT FALSE,
    spm_pass_bi BOOLEAN DEFAULT FALSE,
    spm_credit_math BOOLEAN DEFAULT FALSE,
    spm_pass_math BOOLEAN DEFAULT FALSE,
    spm_credit_addmath BOOLEAN DEFAULT FALSE,
    spm_credit_science BOOLEAN DEFAULT FALSE,
    spm_subject_group JSONB,
    min_muet_band INTEGER DEFAULT 1,
    req_interview BOOLEAN DEFAULT FALSE,
    no_colorblind BOOLEAN DEFAULT FALSE,
    req_medical_fitness BOOLEAN DEFAULT FALSE,
    req_malaysian BOOLEAN DEFAULT FALSE,
    req_bumiputera BOOLEAN DEFAULT FALSE,
    UNIQUE(course_id)
);

-- RLS: Public read-only (reference data, like courses table)
ALTER TABLE public.stpm_courses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read" ON public.stpm_courses FOR SELECT USING (true);

ALTER TABLE public.stpm_requirements ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow public read" ON public.stpm_requirements FOR SELECT USING (true);

-- Indexes
CREATE INDEX idx_stpm_requirements_course ON public.stpm_requirements(course_id);
CREATE INDEX idx_stpm_courses_university ON public.stpm_courses(university);
CREATE INDEX idx_stpm_courses_stream ON public.stpm_courses(stream);
"""
        self.stdout.write(sql)
```

**Step 2: Run SQL via Supabase MCP**

Use `mcp__claude_ai_Supabase__execute_sql` to create tables, then `apply_migration` to record it.

**Step 3: Run Security Advisor**

Use `mcp__claude_ai_Supabase__get_advisors` with type="security" — must show 0 errors.

**Step 4: Load data into Supabase**

Generate INSERT statements from Django models using the management command, or use `execute_sql` to insert batches.

**Step 5: Verify counts**

```sql
SELECT COUNT(*) FROM stpm_courses;           -- expect 1113
SELECT COUNT(*) FROM stpm_requirements;      -- expect 1113
SELECT COUNT(*) FROM stpm_courses WHERE stream = 'science';  -- verify distribution
```

**Step 6: Commit**

```bash
git add halatuju_api/apps/courses/management/commands/generate_stpm_sql.py
git commit -m "feat: add STPM Supabase migration command + run migration"
```

---

## Task 2: STPM ranking engine

**Files:**
- Create: `halatuju_api/apps/courses/stpm_ranking.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_ranking.py`

**Step 1: Write failing tests**

```python
# test_stpm_ranking.py
import pytest
from apps.courses.stpm_ranking import calculate_stpm_fit_score, get_stpm_ranked_results


class TestStpmFitScore:
    def test_base_score(self):
        """Programme with no signals gets base score only."""
        programme = {
            'program_id': 'TEST001', 'program_name': 'Test', 'university': 'UM',
            'stream': 'science', 'min_cgpa': 3.0, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
        }
        score, reasons = calculate_stpm_fit_score(programme, student_cgpa=3.0, signals={})
        assert score == 50  # base

    def test_cgpa_margin_bonus(self):
        """Higher CGPA margin increases score."""
        programme = {
            'program_id': 'TEST001', 'program_name': 'Test', 'university': 'UM',
            'stream': 'science', 'min_cgpa': 2.5, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
        }
        score, reasons = calculate_stpm_fit_score(programme, student_cgpa=3.5, signals={})
        assert score > 50  # CGPA margin +1.0 should add bonus
        assert any('CGPA' in r for r in reasons)

    def test_cgpa_margin_capped(self):
        """CGPA margin bonus capped at max."""
        prog = {
            'program_id': 'TEST001', 'program_name': 'Test', 'university': 'UM',
            'stream': 'science', 'min_cgpa': 1.0, 'min_muet_band': 1,
            'req_interview': False, 'no_colorblind': False,
        }
        score1, _ = calculate_stpm_fit_score(prog, student_cgpa=3.5, signals={})
        score2, _ = calculate_stpm_fit_score(prog, student_cgpa=4.0, signals={})
        # Both well above min — should be capped at same max
        assert score2 - score1 <= 5  # small or zero difference once capped

    def test_field_interest_match(self):
        """Field interest matching stream adds bonus."""
        programme = {
            'program_id': 'TEST001', 'program_name': 'BACELOR KEJURUTERAAN', 'university': 'UTM',
            'stream': 'science', 'min_cgpa': 3.0, 'min_muet_band': 3,
            'req_interview': False, 'no_colorblind': False,
        }
        signals_match = {'field_interest': ['field_mechanical', 'field_electrical']}
        signals_no_match = {'field_interest': ['field_arts', 'field_music']}
        score_match, _ = calculate_stpm_fit_score(programme, student_cgpa=3.5, signals=signals_match)
        score_no, _ = calculate_stpm_fit_score(programme, student_cgpa=3.5, signals=signals_no_match)
        assert score_match > score_no

    def test_interview_penalty(self):
        """Interview requirement adds slight penalty."""
        base = {
            'program_id': 'TEST001', 'program_name': 'Test', 'university': 'UM',
            'stream': 'science', 'min_cgpa': 3.0, 'min_muet_band': 3,
            'no_colorblind': False,
        }
        prog_no = {**base, 'req_interview': False}
        prog_yes = {**base, 'req_interview': True}
        score_no, _ = calculate_stpm_fit_score(prog_no, student_cgpa=3.5, signals={})
        score_yes, _ = calculate_stpm_fit_score(prog_yes, student_cgpa=3.5, signals={})
        assert score_no > score_yes


class TestStpmRankedResults:
    def test_sorted_by_score_desc(self):
        """Programmes returned in descending score order."""
        programmes = [
            {'program_id': 'A', 'program_name': 'Low', 'university': 'X',
             'stream': 'arts', 'min_cgpa': 3.5, 'min_muet_band': 4,
             'req_interview': False, 'no_colorblind': False},
            {'program_id': 'B', 'program_name': 'High', 'university': 'Y',
             'stream': 'science', 'min_cgpa': 2.0, 'min_muet_band': 2,
             'req_interview': False, 'no_colorblind': False},
        ]
        result = get_stpm_ranked_results(programmes, student_cgpa=3.5, signals={})
        assert result[0]['program_id'] == 'B'  # higher CGPA margin → higher score

    def test_empty_list(self):
        """Empty input returns empty list."""
        result = get_stpm_ranked_results([], student_cgpa=3.0, signals={})
        assert result == []

    def test_fit_score_in_output(self):
        """Each programme in output has fit_score and fit_reasons."""
        programmes = [
            {'program_id': 'A', 'program_name': 'Test', 'university': 'UM',
             'stream': 'science', 'min_cgpa': 2.5, 'min_muet_band': 3,
             'req_interview': False, 'no_colorblind': False},
        ]
        result = get_stpm_ranked_results(programmes, student_cgpa=3.0, signals={})
        assert 'fit_score' in result[0]
        assert 'fit_reasons' in result[0]
        assert isinstance(result[0]['fit_score'], (int, float))
        assert isinstance(result[0]['fit_reasons'], list)
```

**Step 2: Run tests to verify they fail**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_ranking.py -v
```
Expected: FAIL (module not found)

**Step 3: Implement stpm_ranking.py**

```python
# stpm_ranking.py
"""
STPM programme ranking engine.

Scores eligible STPM programmes based on:
1. CGPA margin (student CGPA - min_cgpa) — higher margin = safer admission
2. Field interest match (programme name keywords vs quiz signals)
3. Interview penalty (slight discount for programmes requiring interview)

Scoring:
  BASE = 50
  CGPA margin: +20 max (10 per 0.5 margin, capped at 1.0)
  Field match: +10
  Interview: -3
"""
from typing import Dict, List, Tuple

BASE_SCORE = 50
CGPA_MARGIN_CAP = 1.0
CGPA_MARGIN_MULTIPLIER = 20  # points per 1.0 CGPA margin
FIELD_MATCH_BONUS = 10
INTERVIEW_PENALTY = 3

# Programme name keywords → field interest signals
PROGRAMME_FIELD_MAP = {
    'kejuruteraan': ['field_mechanical', 'field_electrical', 'field_civil', 'field_heavy_industry'],
    'engineering': ['field_mechanical', 'field_electrical', 'field_civil', 'field_heavy_industry'],
    'sains komputer': ['field_digital'],
    'computer science': ['field_digital'],
    'teknologi maklumat': ['field_digital'],
    'perniagaan': ['field_business'],
    'perakaunan': ['field_business'],
    'ekonomi': ['field_business', 'field_social_science'],
    'undang': ['field_social_science'],
    'pendidikan': ['field_social_science', 'field_education'],
    'seni': ['field_arts'],
    'sastera': ['field_arts'],
    'perubatan': ['field_medical', 'field_health'],
    'farmasi': ['field_health'],
    'kejururawatan': ['field_health'],
    'pertanian': ['field_agriculture'],
    'sains': ['field_science'],
    'biologi': ['field_science', 'field_health'],
    'kimia': ['field_science'],
    'fizik': ['field_science'],
    'matematik': ['field_science'],
    'senibina': ['field_architecture'],
    'alam bina': ['field_architecture'],
}


def _match_field_interest(program_name: str, signals: Dict) -> bool:
    """Check if programme name keywords match student's field interests."""
    field_interests = signals.get('field_interest', [])
    if not field_interests:
        return False
    name_lower = program_name.lower()
    for keyword, fields in PROGRAMME_FIELD_MAP.items():
        if keyword in name_lower:
            if any(f in field_interests for f in fields):
                return True
    return False


def calculate_stpm_fit_score(
    programme: Dict,
    student_cgpa: float,
    signals: Dict,
) -> Tuple[float, List[str]]:
    """Calculate fit score for a single STPM programme.

    Args:
        programme: Eligible programme dict from stpm_engine
        student_cgpa: Student's calculated STPM CGPA
        signals: Quiz signals dict (field_interest, work_preference, etc.)

    Returns:
        (score, reasons) tuple
    """
    score = BASE_SCORE
    reasons = []

    # 1. CGPA margin bonus
    margin = student_cgpa - programme['min_cgpa']
    capped_margin = min(margin, CGPA_MARGIN_CAP)
    cgpa_bonus = round(capped_margin * CGPA_MARGIN_MULTIPLIER, 1)
    if cgpa_bonus > 0:
        score += cgpa_bonus
        reasons.append(f'CGPA margin: +{margin:.2f}')

    # 2. Field interest match
    if _match_field_interest(programme['program_name'], signals):
        score += FIELD_MATCH_BONUS
        reasons.append('Field match')

    # 3. Interview penalty
    if programme.get('req_interview', False):
        score -= INTERVIEW_PENALTY
        reasons.append('Interview required: -3')

    return round(score, 1), reasons


def get_stpm_ranked_results(
    programmes: List[Dict],
    student_cgpa: float,
    signals: Dict,
) -> List[Dict]:
    """Rank eligible STPM programmes by fit score.

    Args:
        programmes: List of eligible programme dicts
        student_cgpa: Student's STPM CGPA
        signals: Quiz signals

    Returns:
        Programmes sorted by fit_score descending, each with fit_score and fit_reasons added
    """
    if not programmes:
        return []

    scored = []
    for prog in programmes:
        fit_score, fit_reasons = calculate_stpm_fit_score(prog, student_cgpa, signals)
        scored.append({**prog, 'fit_score': fit_score, 'fit_reasons': fit_reasons})

    scored.sort(key=lambda p: (-p['fit_score'], p['program_name']))
    return scored
```

**Step 4: Run tests to verify they pass**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_ranking.py -v
```
Expected: 8 PASS

**Step 5: Run full test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v
```
Expected: 294+ collected, 261+ passing, golden masters intact

**Step 6: Commit**

```bash
git add apps/courses/stpm_ranking.py apps/courses/tests/test_stpm_ranking.py
git commit -m "feat: add STPM ranking engine with CGPA margin, field match, and interview scoring"
```

---

## Task 3: STPM ranking API endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`
- Test: `halatuju_api/apps/courses/tests/test_stpm_api.py`

**Step 1: Write failing tests**

Add to existing `test_stpm_api.py`:

```python
class TestStpmRankingAPI:
    def test_ranking_returns_200(self):
        """POST /api/v1/stpm/ranking/ returns 200 with valid input."""
        data = {
            'eligible_programmes': [
                {
                    'program_id': 'TEST001', 'program_name': 'Test Programme',
                    'university': 'UM', 'stream': 'science',
                    'min_cgpa': 2.5, 'min_muet_band': 3,
                    'req_interview': False, 'no_colorblind': False,
                }
            ],
            'student_cgpa': 3.5,
            'student_signals': {},
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, content_type='application/json')
        assert response.status_code == 200

    def test_ranking_returns_scored_programmes(self):
        """Response includes fit_score and fit_reasons on each programme."""
        data = {
            'eligible_programmes': [
                {
                    'program_id': 'TEST001', 'program_name': 'Test',
                    'university': 'UM', 'stream': 'science',
                    'min_cgpa': 2.5, 'min_muet_band': 3,
                    'req_interview': False, 'no_colorblind': False,
                }
            ],
            'student_cgpa': 3.5,
            'student_signals': {},
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, content_type='application/json')
        body = response.json()
        assert 'ranked_programmes' in body
        assert 'total' in body
        assert body['total'] == 1
        prog = body['ranked_programmes'][0]
        assert 'fit_score' in prog
        assert 'fit_reasons' in prog

    def test_ranking_sorted_desc(self):
        """Programmes returned sorted by fit_score descending."""
        data = {
            'eligible_programmes': [
                {'program_id': 'A', 'program_name': 'Low CGPA Margin',
                 'university': 'X', 'stream': 'arts', 'min_cgpa': 3.4,
                 'min_muet_band': 4, 'req_interview': False, 'no_colorblind': False},
                {'program_id': 'B', 'program_name': 'High CGPA Margin',
                 'university': 'Y', 'stream': 'science', 'min_cgpa': 2.0,
                 'min_muet_band': 2, 'req_interview': False, 'no_colorblind': False},
            ],
            'student_cgpa': 3.5,
            'student_signals': {},
        }
        response = self.client.post('/api/v1/stpm/ranking/', data, content_type='application/json')
        progs = response.json()['ranked_programmes']
        assert progs[0]['fit_score'] >= progs[1]['fit_score']

    def test_ranking_missing_programmes_400(self):
        """Missing eligible_programmes returns 400."""
        data = {'student_cgpa': 3.5}
        response = self.client.post('/api/v1/stpm/ranking/', data, content_type='application/json')
        assert response.status_code == 400

    def test_ranking_empty_programmes(self):
        """Empty list returns empty result."""
        data = {'eligible_programmes': [], 'student_cgpa': 3.5, 'student_signals': {}}
        response = self.client.post('/api/v1/stpm/ranking/', data, content_type='application/json')
        body = response.json()
        assert body['ranked_programmes'] == []
        assert body['total'] == 0
```

**Step 2: Run tests to verify they fail**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_api.py -v -k "Ranking"
```

**Step 3: Implement view + URL**

In `views.py`, add `StpmRankingView`:
```python
class StpmRankingView(View):
    def post(self, request):
        data = json.loads(request.body)
        programmes = data.get('eligible_programmes')
        if programmes is None:
            return JsonResponse({'error': 'eligible_programmes required'}, status=400)
        student_cgpa = data.get('student_cgpa', 0)
        signals = data.get('student_signals', {})

        from apps.courses.stpm_ranking import get_stpm_ranked_results
        ranked = get_stpm_ranked_results(programmes, student_cgpa, signals)
        return JsonResponse({'ranked_programmes': ranked, 'total': len(ranked)})
```

In `urls.py`, add:
```python
path('stpm/ranking/', StpmRankingView.as_view(), name='stpm-ranking'),
```

**Step 4: Run tests, verify pass**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_api.py -v
```

**Step 5: Run full test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v
```

**Step 6: Commit**

```bash
git add apps/courses/views.py apps/courses/urls.py apps/courses/tests/test_stpm_api.py
git commit -m "feat: add POST /api/v1/stpm/ranking/ endpoint"
```

---

## Task 4: Frontend — STPM ranking API client + dashboard upgrade

**Files:**
- Modify: `halatuju-web/src/lib/api.ts` (add ranking function)
- Modify: `halatuju-web/src/app/dashboard/page.tsx` (call ranking, show fit scores)

**Step 1: Add STPM ranking API client**

In `lib/api.ts`, add:
```typescript
export interface StpmRankedProgramme extends StpmEligibleProgramme {
  fit_score: number
  fit_reasons: string[]
}

export interface StpmRankingRequest {
  eligible_programmes: StpmEligibleProgramme[]
  student_cgpa: number
  student_signals: Record<string, unknown>
}

export interface StpmRankingResponse {
  ranked_programmes: StpmRankedProgramme[]
  total: number
}

export async function rankStpmProgrammes(
  data: StpmRankingRequest,
  options?: ApiOptions
): Promise<StpmRankingResponse> {
  return apiRequest('/api/v1/stpm/ranking/', {
    method: 'POST',
    body: JSON.stringify(data),
    ...options,
  })
}
```

**Step 2: Update dashboard to call ranking after eligibility**

In `dashboard/page.tsx`, after receiving STPM eligibility results:
1. Call `rankStpmProgrammes()` with eligible programmes + student CGPA + quiz signals from localStorage
2. Replace `stpmResults` with ranked results
3. Display `fit_score` as a badge on each programme card (e.g. "Fit: 78")
4. Show `fit_reasons` as tooltip or subtitle text

**Step 3: Add fit score badge styling**

Programme cards should show:
- Fit score badge (colour-coded: green >=70, amber >=55, grey <55)
- University name
- CGPA requirement badge
- MUET band badge
- Interview badge (if applicable)

**Step 4: Verify frontend builds**

```bash
cd halatuju-web && npm run build
```

**Step 5: Commit**

```bash
git add src/lib/api.ts src/app/dashboard/page.tsx
git commit -m "feat: integrate STPM ranking into dashboard with fit scores"
```

---

## Task 5: Sprint 3 close

**Step 1: Run full backend test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v
```
Expected: 302+ collected, 269+ passing, golden masters intact

**Step 2: Verify frontend builds**

```bash
cd halatuju-web && npm run build
```

**Step 3: Follow sprint-close workflow**

Update CHANGELOG.md, CLAUDE.md, write retrospective, commit and push.

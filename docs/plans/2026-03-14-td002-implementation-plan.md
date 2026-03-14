# TD-002 + TD-017: Eliminate Frontend Calculation Duplication — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move all eligibility formulas to the backend. Frontend calls API endpoints instead of computing locally. Delete `merit.ts`, `stpm.ts`, and `pathways.ts`.

**Architecture:** Three new lightweight POST endpoints in Django. Frontend pages replace local function calls with `fetch()` via `api.ts`. The `getPathwayFitScore()` function (currently frontend-only) is ported to `pathways.py`. All calculations happen server-side; frontend is display-only.

**Tech Stack:** Django REST Framework (backend), Next.js + TypeScript (frontend), existing `api.ts` client.

---

### Task 1: Backend — Add merit calculation endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`
- Test: `halatuju_api/apps/courses/tests/test_api.py`

**Step 1: Write the failing test**

Add to `halatuju_api/apps/courses/tests/test_api.py`:

```python
class TestCalculateEndpoints(TestCase):
    """Tests for /api/v1/calculate/ endpoints."""

    def test_merit_calculation(self):
        """POST /calculate/merit/ returns correct merit score."""
        response = self.client.post(
            '/api/v1/calculate/merit/',
            data={
                'grades': {
                    'BM': 'A', 'BI': 'A', 'MAT': 'A', 'SEJ': 'A',
                    'PHY': 'A', 'CHE': 'A',
                    'AMT': 'A', 'BIO': 'A',
                },
                'coq_score': 8.0,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('academic_merit', data)
        self.assertIn('final_merit', data)
        self.assertAlmostEqual(data['academic_merit'], 90.0, places=1)
        self.assertAlmostEqual(data['final_merit'], 98.0, places=1)

    def test_merit_missing_grades(self):
        """POST /calculate/merit/ with no grades returns 400."""
        response = self.client.post(
            '/api/v1/calculate/merit/',
            data={},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest apps/courses/tests/test_api.py::TestCalculateEndpoints -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Write minimal implementation**

Add to `halatuju_api/apps/courses/views.py`:

```python
class CalculateMeritView(APIView):
    """Calculate UPU merit score from grades.

    POST /api/v1/calculate/merit/
    Body: { grades: {BM: "A", BI: "B+", ...}, coq_score: 8.0 }
    Response: { academic_merit: 85.5, final_merit: 93.5 }
    """

    def post(self, request):
        grades = request.data.get('grades')
        if not grades:
            return Response(
                {'error': 'grades is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        coq_score = float(request.data.get('coq_score', 0))

        # Map frontend keys to engine keys via serializer mapping
        from .serializers import EligibilityRequestSerializer
        mapped = {}
        for key, value in grades.items():
            engine_key = EligibilityRequestSerializer.GRADE_KEY_MAP.get(key, key.lower())
            mapped[engine_key] = value

        # Prepare sections and calculate
        if 'hist' in mapped:
            mapped['history'] = mapped.pop('hist')
        sec1, sec2, sec3 = prepare_merit_inputs(mapped)
        result = calculate_merit_score(sec1, sec2, sec3, coq_score=coq_score)

        return Response({
            'academic_merit': result['academic_merit'],
            'final_merit': result['final_merit'],
        })
```

Add to `halatuju_api/apps/courses/urls.py`:

```python
    # Calculation endpoints (stateless, public)
    path('calculate/merit/', views.CalculateMeritView.as_view(), name='calculate-merit'),
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest apps/courses/tests/test_api.py::TestCalculateEndpoints -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/courses/views.py apps/courses/urls.py apps/courses/tests/test_api.py
git commit -m "feat: add /calculate/merit/ endpoint (TD-002)"
```

---

### Task 2: Backend — Add CGPA calculation endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`
- Modify: `halatuju_api/apps/courses/tests/test_api.py`

**Step 1: Write the failing test**

Add to `TestCalculateEndpoints`:

```python
    def test_cgpa_calculation(self):
        """POST /calculate/cgpa/ returns CGPA and merit percent."""
        response = self.client.post(
            '/api/v1/calculate/cgpa/',
            data={
                'stpm_grades': {'Pengajian Am': 'A', 'Physics': 'B+', 'Chemistry': 'B'},
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('cgpa', data)
        self.assertIn('merit_percent', data)
        # A=4.00, B+=3.33, B=3.00 → avg = 3.44
        self.assertAlmostEqual(data['cgpa'], 3.44, places=2)
        self.assertAlmostEqual(data['merit_percent'], 86.0, places=0)

    def test_cgpa_missing_grades(self):
        """POST /calculate/cgpa/ with no grades returns 400."""
        response = self.client.post(
            '/api/v1/calculate/cgpa/',
            data={},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest apps/courses/tests/test_api.py::TestCalculateEndpoints::test_cgpa_calculation -v`
Expected: FAIL with 404

**Step 3: Write minimal implementation**

Add to `halatuju_api/apps/courses/views.py`:

```python
class CalculateCgpaView(APIView):
    """Calculate STPM CGPA from grades.

    POST /api/v1/calculate/cgpa/
    Body: { stpm_grades: {"Pengajian Am": "A", "Physics": "B+", ...}, koko_score: 8 }
    Response: { cgpa: 3.44, merit_percent: 86.0 }
    """

    def post(self, request):
        stpm_grades = request.data.get('stpm_grades')
        if not stpm_grades:
            return Response(
                {'error': 'stpm_grades is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        koko_score = float(request.data.get('koko_score', 0))

        academic_cgpa = calculate_stpm_cgpa(stpm_grades)
        overall_cgpa = round(academic_cgpa * 0.9 + min(koko_score, 10) * 0.04, 2)
        merit_percent = round((overall_cgpa / 4.0) * 100, 2)

        return Response({
            'cgpa': overall_cgpa,
            'academic_cgpa': academic_cgpa,
            'merit_percent': merit_percent,
        })
```

Add to `urls.py`:

```python
    path('calculate/cgpa/', views.CalculateCgpaView.as_view(), name='calculate-cgpa'),
```

Add import at top of `views.py` (if not already present):

```python
from .stpm_engine import calculate_stpm_cgpa
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest apps/courses/tests/test_api.py::TestCalculateEndpoints -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/courses/views.py apps/courses/urls.py apps/courses/tests/test_api.py
git commit -m "feat: add /calculate/cgpa/ endpoint (TD-002)"
```

---

### Task 3: Backend — Port getPathwayFitScore to pathways.py

**Files:**
- Modify: `halatuju_api/apps/courses/pathways.py`
- Test: `halatuju_api/apps/courses/tests/test_pathways.py`

**Step 1: Write the failing test**

Add to `halatuju_api/apps/courses/tests/test_pathways.py`:

```python
class TestPathwayFitScore(TestCase):
    """Tests for get_pathway_fit_score() — ported from frontend pathways.ts."""

    def test_eligible_matric_base_score(self):
        """Eligible matric track gets base + prestige."""
        result = {
            'pathway': 'matric', 'track_id': 'sains',
            'eligible': True, 'merit': 85.0,
            'mata_gred': None, 'max_mata_gred': None,
        }
        score = get_pathway_fit_score(result)
        # BASE_SCORE (100) + prestige (8) + academic bonus (0, merit < 89)
        self.assertEqual(score, 108)

    def test_eligible_matric_high_merit(self):
        """High merit matric gets academic bonus."""
        result = {
            'pathway': 'matric', 'track_id': 'sains',
            'eligible': True, 'merit': 95.0,
            'mata_gred': None, 'max_mata_gred': None,
        }
        score = get_pathway_fit_score(result)
        # 100 + 8 (prestige) + 8 (academic, merit >= 94)
        self.assertEqual(score, 116)

    def test_eligible_stpm_low_mata_gred(self):
        """Low mata gred (good) gets academic bonus."""
        result = {
            'pathway': 'stpm', 'track_id': 'sains',
            'eligible': True, 'merit': None,
            'mata_gred': 4, 'max_mata_gred': 18,
        }
        score = get_pathway_fit_score(result)
        # 100 + 5 (prestige) + 8 (academic, mata_gred <= 4)
        self.assertEqual(score, 113)

    def test_not_eligible_returns_zero(self):
        """Not eligible → score 0."""
        result = {
            'pathway': 'matric', 'track_id': 'sains',
            'eligible': False, 'merit': None,
            'mata_gred': None, 'max_mata_gred': None,
        }
        score = get_pathway_fit_score(result)
        self.assertEqual(score, 0)

    def test_signal_adjustment_capped(self):
        """Signal adjustment is capped at ±6."""
        result = {
            'pathway': 'matric', 'track_id': 'sains',
            'eligible': True, 'merit': 85.0,
            'mata_gred': None, 'max_mata_gred': None,
        }
        # Extreme positive signals
        signals = {
            'work_preference_signals': {'problem_solving': 1},
            'learning_tolerance_signals': {'concept_first': 1, 'rote_tolerant': 1},
            'value_tradeoff_signals': {
                'pathway_priority': 1, 'quality_priority': 1, 'allowance_priority': 1,
            },
            'energy_sensitivity_signals': {'high_stamina': 1},
        }
        score = get_pathway_fit_score(result, signals)
        # 100 + 8 + 0 + 6 (capped) = 114
        self.assertEqual(score, 114)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest apps/courses/tests/test_pathways.py::TestPathwayFitScore -v`
Expected: FAIL with ImportError (get_pathway_fit_score not defined)

**Step 3: Write minimal implementation**

Add to `halatuju_api/apps/courses/pathways.py`:

```python
# ── Pre-University Unified Scoring ──────────────────────────────────────
# Ported from halatuju-web/src/lib/pathways.ts getPathwayFitScore()

BASE_SCORE = 100
PRESTIGE = {'matric': 8, 'stpm': 5}
SIGNAL_CAP = 6

TRACK_FIELD_MAP = {
    'matric:kejuruteraan': ['field_mechanical', 'field_electrical', 'field_civil', 'field_heavy_industry'],
    'matric:sains_komputer': ['field_digital'],
    'matric:perakaunan': ['field_business'],
    'stpm:sains_sosial': [],
}


def _matric_academic_bonus(merit):
    if merit >= 94:
        return 8
    if merit >= 89:
        return 4
    return 0


def _stpm_academic_bonus(mata_gred):
    if mata_gred <= 4:
        return 8
    if mata_gred <= 10:
        return 4
    return 0


def _field_preference_bonus(result, signals):
    if not signals:
        return 0
    key = f"{result['pathway']}:{result['track_id']}"
    mapped_fields = TRACK_FIELD_MAP.get(key)

    if result['track_id'] == 'sains_sosial':
        return 3 if (signals.get('work_preference_signals', {}).get('creative', 0) > 0) else 0

    if mapped_fields:
        field_signals = signals.get('field_interest', {})
        for f in mapped_fields:
            if field_signals.get(f, 0) > 0:
                return 3
    return 0


def _get_signal(signals, category, key):
    if not signals:
        return 0
    return signals.get(category, {}).get(key, 0)


def _pathway_signal_adjustment(result, signals):
    if not signals:
        return 0

    is_matric = result['pathway'] == 'matric'
    is_socsci = result['track_id'] == 'sains_sosial'
    adj = 0

    # Work style
    if _get_signal(signals, 'work_preference_signals', 'problem_solving') > 0 and not is_socsci:
        adj += 2
    if _get_signal(signals, 'work_preference_signals', 'creative') > 0 and is_socsci:
        adj += 1
    if _get_signal(signals, 'work_preference_signals', 'hands_on') > 0:
        adj -= 1

    # Environment
    if _get_signal(signals, 'environment_signals', 'workshop_environment') > 0:
        adj -= 1
    if _get_signal(signals, 'environment_signals', 'field_environment') > 0:
        adj -= 1

    # Learning style
    if _get_signal(signals, 'learning_tolerance_signals', 'concept_first') > 0:
        adj += 2
    if _get_signal(signals, 'learning_tolerance_signals', 'rote_tolerant') > 0:
        adj += 1
    if _get_signal(signals, 'learning_tolerance_signals', 'learning_by_doing') > 0:
        adj -= 1

    # Values
    if _get_signal(signals, 'value_tradeoff_signals', 'pathway_priority') > 0:
        adj += 3
    if _get_signal(signals, 'value_tradeoff_signals', 'fast_employment_priority') > 0:
        adj -= 2
    if _get_signal(signals, 'value_tradeoff_signals', 'quality_priority') > 0:
        adj += 2
    if _get_signal(signals, 'value_tradeoff_signals', 'allowance_priority') > 0 and is_matric:
        adj += 2
    if _get_signal(signals, 'value_tradeoff_signals', 'proximity_priority') > 0 and not is_matric:
        adj += 1
    if _get_signal(signals, 'value_tradeoff_signals', 'employment_guarantee') > 0:
        adj -= 1

    # Energy
    if _get_signal(signals, 'energy_sensitivity_signals', 'mental_fatigue_sensitive') > 0:
        adj -= 2
    if _get_signal(signals, 'energy_sensitivity_signals', 'high_stamina') > 0:
        adj += 1

    return max(min(adj, SIGNAL_CAP), -SIGNAL_CAP)


def get_pathway_fit_score(result, signals=None):
    """Calculate unified fit score for a pre-U pathway result.

    Args:
        result: Dict from check_matric_track() or check_stpm_bidang().
        signals: Optional student quiz signals dict.

    Returns:
        Integer fit score (0 if not eligible, ~95-120 if eligible).
    """
    if not result.get('eligible'):
        return 0

    score = BASE_SCORE + PRESTIGE.get(result['pathway'], 0)

    if result['pathway'] == 'matric' and result.get('merit') is not None:
        score += _matric_academic_bonus(result['merit'])
    elif result['pathway'] == 'stpm' and result.get('mata_gred') is not None:
        score += _stpm_academic_bonus(result['mata_gred'])

    score += _field_preference_bonus(result, signals)
    score += _pathway_signal_adjustment(result, signals)

    return score
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest apps/courses/tests/test_pathways.py::TestPathwayFitScore -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/courses/pathways.py apps/courses/tests/test_pathways.py
git commit -m "feat: port getPathwayFitScore to backend pathways.py (TD-017)"
```

---

### Task 4: Backend — Add pathways calculation endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`
- Modify: `halatuju_api/apps/courses/tests/test_api.py`

**Step 1: Write the failing test**

Add to `TestCalculateEndpoints`:

```python
    def test_pathways_calculation(self):
        """POST /calculate/pathways/ returns all 6 pathway results with fit scores."""
        response = self.client.post(
            '/api/v1/calculate/pathways/',
            data={
                'grades': {
                    'BM': 'A', 'BI': 'A', 'MAT': 'A', 'SEJ': 'A',
                    'PHY': 'A', 'CHE': 'A', 'AMT': 'A', 'BIO': 'A',
                },
                'coq_score': 8.0,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('pathways', data)
        self.assertEqual(len(data['pathways']), 6)  # 4 matric + 2 stpm
        # First result should be matric sains
        sains = data['pathways'][0]
        self.assertEqual(sains['track_id'], 'sains')
        self.assertTrue(sains['eligible'])
        self.assertIn('merit', sains)
        self.assertIn('fit_score', sains)

    def test_pathways_with_signals(self):
        """POST /calculate/pathways/ accepts optional signals for fit scoring."""
        response = self.client.post(
            '/api/v1/calculate/pathways/',
            data={
                'grades': {
                    'BM': 'A', 'BI': 'A', 'MAT': 'A', 'SEJ': 'A',
                    'PHY': 'A', 'CHE': 'A', 'AMT': 'A', 'BIO': 'A',
                },
                'coq_score': 8.0,
                'signals': {
                    'work_preference_signals': {'problem_solving': 1},
                },
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        sains = data['pathways'][0]
        # With problem_solving signal, fit_score should be higher than base
        self.assertGreater(sains['fit_score'], 108)

    def test_pathways_missing_grades(self):
        """POST /calculate/pathways/ with no grades returns 400."""
        response = self.client.post(
            '/api/v1/calculate/pathways/',
            data={},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest apps/courses/tests/test_api.py::TestCalculateEndpoints::test_pathways_calculation -v`
Expected: FAIL with 404

**Step 3: Write minimal implementation**

Add to `halatuju_api/apps/courses/views.py`:

```python
class CalculatePathwaysView(APIView):
    """Check all pre-U pathway eligibility and fit scores.

    POST /api/v1/calculate/pathways/
    Body: { grades: {BM: "A", ...}, coq_score: 8.0, signals?: {...} }
    Response: { pathways: [{track_id, eligible, merit, mata_gred, fit_score, ...}] }
    """

    def post(self, request):
        grades_raw = request.data.get('grades')
        if not grades_raw:
            return Response(
                {'error': 'grades is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        coq_score = float(request.data.get('coq_score', 0))
        signals = request.data.get('signals')

        # Map frontend keys to engine keys
        from .serializers import EligibilityRequestSerializer
        grades = {}
        for key, value in grades_raw.items():
            engine_key = EligibilityRequestSerializer.GRADE_KEY_MAP.get(key, key.lower())
            grades[engine_key] = value

        results = check_all_pathways(grades, coq_score)

        # Add fit scores
        for r in results:
            r['fit_score'] = get_pathway_fit_score(r, signals)

        return Response({'pathways': results})
```

Add import at top of `views.py`:

```python
from .pathways import check_all_pathways, get_pathway_fit_score
```

Add to `urls.py`:

```python
    path('calculate/pathways/', views.CalculatePathwaysView.as_view(), name='calculate-pathways'),
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest apps/courses/tests/test_api.py::TestCalculateEndpoints -v`
Expected: ALL PASS

**Step 5: Run full test suite**

Run: `python -m pytest apps/courses/tests/ apps/reports/tests/ -v --tb=short`
Expected: 332+ pass, 13 pre-existing failures, 30 skipped

**Step 6: Commit**

```bash
git add apps/courses/views.py apps/courses/urls.py apps/courses/tests/test_api.py
git commit -m "feat: add /calculate/pathways/ endpoint with fit scores (TD-002 + TD-017)"
```

---

### Task 5: Frontend — Add API client functions

**Files:**
- Modify: `halatuju-web/src/lib/api.ts`

**Step 1: Add the three new API functions**

Add to `halatuju-web/src/lib/api.ts` (before the STPM types section):

```typescript
// Calculation types
export interface MeritResult {
  academic_merit: number
  final_merit: number
}

export interface CgpaResult {
  cgpa: number
  academic_cgpa: number
  merit_percent: number
}

export interface PathwayResult {
  pathway: 'matric' | 'stpm'
  track_id: string
  track_name: string
  track_name_ms: string
  track_name_ta: string
  eligible: boolean
  merit: number | null
  mata_gred: number | null
  max_mata_gred: number | null
  fit_score: number
  reason: string | null
}

// Calculation API functions (stateless, public)
export async function calculateMerit(
  grades: Record<string, string>,
  coqScore: number,
  options?: ApiOptions
): Promise<MeritResult> {
  return apiRequest('/api/v1/calculate/merit/', {
    method: 'POST',
    body: JSON.stringify({ grades, coq_score: coqScore }),
    ...options,
  })
}

export async function calculateCgpa(
  stpmGrades: Record<string, string>,
  kokoScore: number = 0,
  options?: ApiOptions
): Promise<CgpaResult> {
  return apiRequest('/api/v1/calculate/cgpa/', {
    method: 'POST',
    body: JSON.stringify({ stpm_grades: stpmGrades, koko_score: kokoScore }),
    ...options,
  })
}

export async function calculatePathways(
  grades: Record<string, string>,
  coqScore: number,
  signals?: Record<string, Record<string, number>> | null,
  options?: ApiOptions
): Promise<{ pathways: PathwayResult[] }> {
  return apiRequest('/api/v1/calculate/pathways/', {
    method: 'POST',
    body: JSON.stringify({ grades, coq_score: coqScore, signals: signals || undefined }),
    ...options,
  })
}
```

**Step 2: Commit**

```bash
git add halatuju-web/src/lib/api.ts
git commit -m "feat: add calculateMerit/Cgpa/Pathways API client functions"
```

---

### Task 6: Frontend — Replace grades page local merit calculation with API call

**Files:**
- Modify: `halatuju-web/src/app/onboarding/grades/page.tsx`

**Step 1: Replace the import and useMemo**

In `halatuju-web/src/app/onboarding/grades/page.tsx`:

1. **Remove** the import of `calculateMeritScore` from `@/lib/merit` (line 9)
2. **Add** import of `calculateMerit` from `@/lib/api`
3. **Replace** the `useMemo` merit calculation (lines 276-306) with a `useEffect` + `useState` that calls the API with debouncing
4. The API call should fire when grades or CoQ change, with a 400ms debounce
5. Show a loading state while the API call is in flight

Replace the `useMemo` block with:

```typescript
const [meritResult, setMeritResult] = useState<{ academicMerit: number; finalMerit: number } | null>(null)
const [meritLoading, setMeritLoading] = useState(false)

useEffect(() => {
  // Only calculate if we have at least core subjects
  const hasGrades = Object.values(grades).some(g => g !== '')
  if (!hasGrades) {
    setMeritResult(null)
    return
  }

  const timer = setTimeout(async () => {
    setMeritLoading(true)
    try {
      const result = await calculateMerit(grades, coqScore)
      setMeritResult({
        academicMerit: result.academic_merit,
        finalMerit: result.final_merit,
      })
    } catch {
      // Silently fail — merit display is optional
    } finally {
      setMeritLoading(false)
    }
  }, 400)

  return () => clearTimeout(timer)
}, [grades, coqScore])
```

6. Update the merit display section (line 482-492) to show a loading indicator when `meritLoading` is true
7. The `handleSubmit` function (line 323) should still save `meritResult.finalMerit` to localStorage — no change needed there

**Step 2: Verify the page works locally**

Run: `cd halatuju-web && npm run dev`
Navigate to `/onboarding/grades/`, enter grades, verify merit score appears after brief delay.

**Step 3: Commit**

```bash
git add halatuju-web/src/app/onboarding/grades/page.tsx
git commit -m "refactor: grades page uses /calculate/merit/ API instead of local calculation"
```

---

### Task 7: Frontend — Replace STPM grades page local CGPA calculation with API call

**Files:**
- Modify: `halatuju-web/src/app/onboarding/stpm-grades/page.tsx`

**Step 1: Replace the import and useMemo**

1. **Remove** import of `calculateStpmCgpa` from `@/lib/stpm` (line 17)
2. **Add** import of `calculateCgpa` from `@/lib/api`
3. **Replace** the `useMemo` CGPA calculation (lines 107-118) with `useEffect` + `useState` + 400ms debounce:

```typescript
const [academicCgpa, setAcademicCgpa] = useState(0)
const [overallCgpa, setOverallCgpa] = useState(0)
const [cgpaLoading, setCgpaLoading] = useState(false)

useEffect(() => {
  const gradesWithValues = Object.fromEntries(
    Object.entries(stpmGrades).filter(([, v]) => v !== '')
  )
  if (Object.keys(gradesWithValues).length === 0) {
    setAcademicCgpa(0)
    setOverallCgpa(0)
    return
  }

  const timer = setTimeout(async () => {
    setCgpaLoading(true)
    try {
      const result = await calculateCgpa(gradesWithValues, koko)
      setAcademicCgpa(result.academic_cgpa)
      setOverallCgpa(result.cgpa)
    } catch {
      // Silently fail
    } finally {
      setCgpaLoading(false)
    }
  }, 400)

  return () => clearTimeout(timer)
}, [stpmGrades, koko])
```

4. Update the CGPA display section (line 359-373) for optional loading indicator
5. The `handleSubmit` saves `overallCgpa` to localStorage — no change needed

**Step 2: Verify locally**

Run: `cd halatuju-web && npm run dev`
Navigate to `/onboarding/stpm-grades/`, enter grades, verify CGPA appears.

**Step 3: Commit**

```bash
git add halatuju-web/src/app/onboarding/stpm-grades/page.tsx
git commit -m "refactor: STPM grades page uses /calculate/cgpa/ API instead of local calculation"
```

---

### Task 8: Frontend — Replace pathway pages with API calls

**Files:**
- Modify: `halatuju-web/src/app/pathway/matric/page.tsx`
- Modify: `halatuju-web/src/app/pathway/stpm/page.tsx`

**Step 1: Replace matric pathway page**

In `halatuju-web/src/app/pathway/matric/page.tsx`:

1. **Remove** import of `checkAllPathways`, `MATRIC_TRACKS`, `PathwayResult` from `@/lib/pathways` (line 7)
2. **Add** import of `calculatePathways`, `PathwayResult` from `@/lib/api`
3. **Replace** the `useMemo` (lines 64-69) with `useEffect` + `useState`:

```typescript
const [matricResults, setMatricResults] = useState<PathwayResult[]>([])
const [loading, setLoading] = useState(true)

useEffect(() => {
  if (!grades || Object.keys(grades).length === 0) return

  const fetchPathways = async () => {
    setLoading(true)
    try {
      const signals = JSON.parse(localStorage.getItem('halatuju_quiz_signals') || 'null')
      const { pathways } = await calculatePathways(grades, coq, signals)
      setMatricResults(pathways.filter(p => p.pathway === 'matric'))
    } catch {
      setMatricResults([])
    } finally {
      setLoading(false)
    }
  }

  fetchPathways()
}, [grades, coq])
```

4. Update references from the old `MatricTrack` type to use `PathwayResult.track_name_ms` etc.
5. Matric track names come from the API response now — remove `MATRIC_TRACKS` constant usage

**Step 2: Replace STPM pathway page**

Same pattern in `halatuju-web/src/app/pathway/stpm/page.tsx`:

1. **Remove** import of `checkAllPathways`, `STPM_BIDANGS` from `@/lib/pathways` (line 9)
2. **Add** import of `calculatePathways`, `PathwayResult` from `@/lib/api`
3. **Replace** `useMemo` (lines 84-88) with same `useEffect` + `useState` pattern, filtering for `pathway === 'stpm'`

**Step 3: Verify locally**

Navigate to `/pathway/matric/` and `/pathway/stpm/`, verify eligibility and scores display.

**Step 4: Commit**

```bash
git add halatuju-web/src/app/pathway/matric/page.tsx halatuju-web/src/app/pathway/stpm/page.tsx
git commit -m "refactor: pathway pages use /calculate/pathways/ API instead of local calculation"
```

---

### Task 9: Frontend — Replace dashboard cgpaToMeritPercent

**Files:**
- Modify: `halatuju-web/src/app/dashboard/page.tsx`

**Step 1: Remove the import and inline the trivial calculation**

In `halatuju-web/src/app/dashboard/page.tsx`:

1. **Remove** import of `cgpaToMeritPercent` from `@/lib/stpm` (line 30)
2. **Replace** the call at line 612 with inline:

```typescript
const studentMerit = Math.round((stpmData.cgpa / 4.0) * 10000) / 100
```

This is a one-liner (CGPA ÷ 4 × 100). No API call needed — the CGPA was already calculated and stored in localStorage during onboarding via the `/calculate/cgpa/` endpoint.

**Step 2: Commit**

```bash
git add halatuju-web/src/app/dashboard/page.tsx
git commit -m "refactor: dashboard inlines CGPA-to-percent (no stpm.ts import)"
```

---

### Task 10: Frontend — Delete the three frontend calculation files

**Files:**
- Delete: `halatuju-web/src/lib/merit.ts`
- Delete: `halatuju-web/src/lib/stpm.ts`
- Delete: `halatuju-web/src/lib/pathways.ts`

**Step 1: Verify no remaining imports**

Run:
```bash
cd halatuju-web && grep -r "from.*lib/merit" src/ --include="*.ts" --include="*.tsx"
cd halatuju-web && grep -r "from.*lib/stpm" src/ --include="*.ts" --include="*.tsx"
cd halatuju-web && grep -r "from.*lib/pathways" src/ --include="*.ts" --include="*.tsx"
```

Expected: No output (no remaining imports)

**Step 2: Delete the files**

```bash
rm halatuju-web/src/lib/merit.ts
rm halatuju-web/src/lib/stpm.ts
rm halatuju-web/src/lib/pathways.ts
```

**Step 3: Verify the app builds**

Run: `cd halatuju-web && npm run build`
Expected: Build succeeds with no errors

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: delete merit.ts, stpm.ts, pathways.ts — all calculations now server-side (TD-002 + TD-017)"
```

---

### Task 11: Run full test suite and update tech debt register

**Files:**
- Modify: `docs/technical-debt.md`

**Step 1: Run backend tests**

Run: `python -m pytest apps/courses/tests/ apps/reports/tests/ -v --tb=short`
Expected: 340+ pass (332 original + ~8 new), 13 pre-existing failures, 30 skipped

**Step 2: Run frontend build**

Run: `cd halatuju-web && npm run build`
Expected: Build succeeds

**Step 3: Update tech debt register**

In `docs/technical-debt.md`, update the status of:
- TD-002: `Open` → `Resolved (TD-002 Sprint)`
- TD-017: `Open` → `Resolved (TD-002 Sprint)`
- TD-015 (frontend/backend merit may disagree): `Open` → `Resolved (TD-002 Sprint)` — eliminated by single source of truth

**Step 4: Commit**

```bash
git add docs/technical-debt.md
git commit -m "docs: mark TD-002, TD-015, TD-017 as resolved"
```

---

### Task 12: Deploy and verify

**Step 1: Deploy backend**

```bash
cd halatuju_api
gcloud run deploy halatuju-api --source . --region asia-southeast1 --account tamiliam@gmail.com --project gen-lang-client-0871147736 --allow-unauthenticated
```

**Step 2: Test new endpoints on production**

```bash
curl -s -X POST https://halatuju-api-90344691621.asia-southeast1.run.app/api/v1/calculate/merit/ \
  -H "Content-Type: application/json" \
  -d '{"grades":{"BM":"A","BI":"A","MAT":"A","SEJ":"A","PHY":"A","CHE":"A","AMT":"A","BIO":"A"},"coq_score":8}' | python -m json.tool
```

**Step 3: Deploy frontend**

```bash
cd halatuju-web
gcloud run deploy halatuju-web --source . --region asia-southeast1 --account tamiliam@gmail.com --project gen-lang-client-0871147736 --allow-unauthenticated
```

**Step 4: Verify frontend works end-to-end**

Navigate to production URL → Onboarding → Grades → enter grades → verify merit displays → Pathways → verify eligibility → Dashboard → verify course cards.

**Step 5: Push**

```bash
git push
```

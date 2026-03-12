# STPM Sprint 4 — Search, Detail, i18n Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let STPM students browse, search, and view details of all 1,113 degree programmes — not just the ones they're eligible for.

**Architecture:** New `GET /api/v1/stpm/search/` backend endpoint queries StpmCourse + StpmRequirement with filters (text, university, stream). New frontend pages at `/stpm/search` (browse/filter) and `/stpm/[id]` (programme detail). The detail page reads directly from a new `GET /api/v1/stpm/programmes/<id>/` endpoint. i18n keys added for all new UI strings.

**Tech Stack:** Django REST (views, urls), Next.js 14 (App Router, TypeScript, Tailwind, React Query), existing i18n infrastructure.

---

## Task 1: STPM search API endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`
- Create: `halatuju_api/apps/courses/tests/test_stpm_search.py`

**Step 1: Write failing tests**

```python
# test_stpm_search.py
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestStpmSearchAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())
        self.client = APIClient()

    def test_search_returns_200(self):
        """GET /api/v1/stpm/search/ returns 200."""
        resp = self.client.get('/api/v1/stpm/search/')
        assert resp.status_code == 200

    def test_search_returns_programmes(self):
        """Response includes programmes list and total_count."""
        resp = self.client.get('/api/v1/stpm/search/')
        data = resp.json()
        assert 'programmes' in data
        assert 'total_count' in data
        assert 'filters' in data
        assert data['total_count'] > 0

    def test_search_text_filter(self):
        """Text search filters by programme name."""
        resp = self.client.get('/api/v1/stpm/search/?q=kejuruteraan')
        data = resp.json()
        assert data['total_count'] > 0
        for prog in data['programmes']:
            assert 'kejuruteraan' in prog['program_name'].lower() or 'engineering' in prog['program_name'].lower()

    def test_search_university_filter(self):
        """University filter narrows results."""
        resp_all = self.client.get('/api/v1/stpm/search/')
        resp_um = self.client.get('/api/v1/stpm/search/?university=UM')
        assert resp_um.json()['total_count'] <= resp_all.json()['total_count']
        for prog in resp_um.json()['programmes']:
            assert prog['university'] == 'UM'

    def test_search_stream_filter(self):
        """Stream filter narrows results."""
        resp = self.client.get('/api/v1/stpm/search/?stream=science')
        data = resp.json()
        for prog in data['programmes']:
            assert prog['stream'] in ('science', 'both')

    def test_search_pagination(self):
        """Pagination with limit and offset works."""
        resp1 = self.client.get('/api/v1/stpm/search/?limit=5&offset=0')
        resp2 = self.client.get('/api/v1/stpm/search/?limit=5&offset=5')
        data1 = resp1.json()
        data2 = resp2.json()
        assert len(data1['programmes']) == 5
        assert len(data2['programmes']) == 5
        assert data1['programmes'][0]['program_id'] != data2['programmes'][0]['program_id']

    def test_search_filters_list(self):
        """Filters include universities and streams."""
        resp = self.client.get('/api/v1/stpm/search/')
        filters = resp.json()['filters']
        assert 'universities' in filters
        assert 'streams' in filters
        assert len(filters['universities']) > 0

    def test_search_programme_shape(self):
        """Each programme has expected fields."""
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog = resp.json()['programmes'][0]
        assert 'program_id' in prog
        assert 'program_name' in prog
        assert 'university' in prog
        assert 'stream' in prog
        assert 'min_cgpa' in prog
        assert 'min_muet_band' in prog
        assert 'req_interview' in prog
```

**Step 2: Run tests to verify they fail**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_search.py -v
```
Expected: FAIL (404 — URL not found)

**Step 3: Implement StpmSearchView + URL**

In `views.py`, add after `StpmRankingView`:

```python
class StpmSearchView(APIView):
    """
    GET /api/v1/stpm/search/

    Browse and search STPM degree programmes with filters.
    Public endpoint — no auth required.

    Query params:
      ?q=kejuruteraan          (text search on programme name)
      &university=UM           (StpmCourse.university)
      &stream=science          (StpmCourse.stream)
      &limit=24&offset=0       (pagination)
    """

    def get(self, request):
        qs = StpmCourse.objects.select_related('requirement').all()

        # Text search on programme name
        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(program_name__icontains=q)

        # Filter by university
        university = request.query_params.get('university', '').strip()
        if university:
            qs = qs.filter(university=university)

        # Filter by stream
        stream = request.query_params.get('stream', '').strip()
        if stream:
            if stream in ('science', 'arts'):
                qs = qs.filter(stream__in=[stream, 'both'])
            else:
                qs = qs.filter(stream=stream)

        # Total before pagination
        total_count = qs.count()

        # Pagination
        try:
            limit = min(int(request.query_params.get('limit', 24)), 100)
        except (ValueError, TypeError):
            limit = 24
        try:
            offset = max(int(request.query_params.get('offset', 0)), 0)
        except (ValueError, TypeError):
            offset = 0

        programmes = qs.order_by('university', 'program_name')[offset:offset + limit]

        results = []
        for prog in programmes:
            req = getattr(prog, 'requirement', None)
            results.append({
                'program_id': prog.program_id,
                'program_name': prog.program_name,
                'university': prog.university,
                'stream': prog.stream,
                'min_cgpa': req.min_cgpa if req else 2.0,
                'min_muet_band': req.min_muet_band if req else 1,
                'req_interview': req.req_interview if req else False,
                'no_colorblind': req.no_colorblind if req else False,
            })

        # Dynamic filter options from full DB
        filters = {
            'universities': sorted(
                StpmCourse.objects.values_list('university', flat=True)
                .distinct().order_by('university')
            ),
            'streams': sorted(
                StpmCourse.objects.values_list('stream', flat=True)
                .distinct().order_by('stream')
            ),
        }

        return Response({
            'programmes': results,
            'total_count': total_count,
            'filters': filters,
        })
```

Add import at top of `views.py` (alongside existing model imports):
```python
from .models import StpmCourse
```

In `urls.py`, add after the `stpm/ranking/` line:
```python
path('stpm/search/', views.StpmSearchView.as_view(), name='stpm-search'),
```

**Step 4: Run tests to verify they pass**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_search.py -v
```
Expected: 8 PASS

**Step 5: Run full test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v --tb=no -q
```
Expected: 315+ collected, 282+ passing, golden masters intact

**Step 6: Commit**

```bash
git add apps/courses/views.py apps/courses/urls.py apps/courses/tests/test_stpm_search.py
git commit -m "feat: add GET /api/v1/stpm/search/ with text, university, stream filters"
```

---

## Task 2: STPM programme detail API endpoint

**Files:**
- Modify: `halatuju_api/apps/courses/views.py`
- Modify: `halatuju_api/apps/courses/urls.py`
- Modify: `halatuju_api/apps/courses/tests/test_stpm_search.py` (add detail tests)

**Step 1: Write failing tests**

Add to `test_stpm_search.py`:

```python
@pytest.mark.django_db
class TestStpmProgrammeDetailAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        from django.core.management import call_command
        from io import StringIO
        call_command('load_stpm_data', stdout=StringIO())
        self.client = APIClient()

    def test_detail_returns_200(self):
        """GET /api/v1/stpm/programmes/<id>/ returns 200 for existing programme."""
        # Get a valid program_id from search
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog_id = resp.json()['programmes'][0]['program_id']
        resp = self.client.get(f'/api/v1/stpm/programmes/{prog_id}/')
        assert resp.status_code == 200

    def test_detail_returns_programme_data(self):
        """Detail response includes programme + requirements."""
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog_id = resp.json()['programmes'][0]['program_id']
        resp = self.client.get(f'/api/v1/stpm/programmes/{prog_id}/')
        data = resp.json()
        assert data['program_id'] == prog_id
        assert 'program_name' in data
        assert 'university' in data
        assert 'stream' in data
        assert 'requirements' in data
        req = data['requirements']
        assert 'min_cgpa' in req
        assert 'min_muet_band' in req
        assert 'stpm_subjects' in req
        assert 'spm_prerequisites' in req

    def test_detail_404_for_missing(self):
        """GET /api/v1/stpm/programmes/NONEXISTENT/ returns 404."""
        resp = self.client.get('/api/v1/stpm/programmes/NONEXISTENT/')
        assert resp.status_code == 404

    def test_detail_stpm_subjects_list(self):
        """Requirements include list of required STPM subjects."""
        resp = self.client.get('/api/v1/stpm/search/?limit=1')
        prog_id = resp.json()['programmes'][0]['program_id']
        resp = self.client.get(f'/api/v1/stpm/programmes/{prog_id}/')
        subjects = resp.json()['requirements']['stpm_subjects']
        assert isinstance(subjects, list)
```

**Step 2: Run tests to verify they fail**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_search.py::TestStpmProgrammeDetailAPI -v
```
Expected: FAIL (404 — URL not found)

**Step 3: Implement StpmProgrammeDetailView + URL**

In `views.py`, add after `StpmSearchView`:

```python
class StpmProgrammeDetailView(APIView):
    """GET /api/v1/stpm/programmes/<program_id>/ — single programme detail."""

    STPM_SUBJECT_FIELDS = [
        ('stpm_req_pa', 'Pengajian Am'),
        ('stpm_req_math_t', 'Mathematics (T)'),
        ('stpm_req_math_m', 'Mathematics (M)'),
        ('stpm_req_physics', 'Physics'),
        ('stpm_req_chemistry', 'Chemistry'),
        ('stpm_req_biology', 'Biology'),
        ('stpm_req_economics', 'Economics'),
        ('stpm_req_accounting', 'Accounting'),
        ('stpm_req_business', 'Business Studies'),
    ]

    SPM_PREREQ_FIELDS = [
        ('spm_credit_bm', 'Bahasa Melayu (credit)'),
        ('spm_pass_sejarah', 'Sejarah (pass)'),
        ('spm_credit_bi', 'Bahasa Inggeris (credit)'),
        ('spm_pass_bi', 'Bahasa Inggeris (pass)'),
        ('spm_credit_math', 'Matematik (credit)'),
        ('spm_pass_math', 'Matematik (pass)'),
        ('spm_credit_addmath', 'Matematik Tambahan (credit)'),
        ('spm_credit_science', 'Sains (credit)'),
    ]

    def get(self, request, program_id):
        try:
            prog = StpmCourse.objects.select_related('requirement').get(
                program_id=program_id
            )
        except StpmCourse.DoesNotExist:
            return Response(
                {'error': 'Programme not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        req = getattr(prog, 'requirement', None)

        # Build required STPM subjects list
        stpm_subjects = []
        if req:
            for field_name, label in self.STPM_SUBJECT_FIELDS:
                if getattr(req, field_name, False):
                    stpm_subjects.append(label)

        # Build SPM prerequisites list
        spm_prerequisites = []
        if req:
            for field_name, label in self.SPM_PREREQ_FIELDS:
                if getattr(req, field_name, False):
                    spm_prerequisites.append(label)

        requirements = {}
        if req:
            requirements = {
                'min_cgpa': req.min_cgpa,
                'min_muet_band': req.min_muet_band,
                'stpm_min_subjects': req.stpm_min_subjects,
                'stpm_min_grade': req.stpm_min_grade,
                'stpm_subjects': stpm_subjects,
                'stpm_subject_group': req.stpm_subject_group,
                'spm_prerequisites': spm_prerequisites,
                'spm_subject_group': req.spm_subject_group,
                'req_interview': req.req_interview,
                'no_colorblind': req.no_colorblind,
                'req_medical_fitness': req.req_medical_fitness,
                'req_malaysian': req.req_malaysian,
                'req_bumiputera': req.req_bumiputera,
            }

        return Response({
            'program_id': prog.program_id,
            'program_name': prog.program_name,
            'university': prog.university,
            'stream': prog.stream,
            'requirements': requirements,
        })
```

In `urls.py`, add:
```python
path('stpm/programmes/<str:program_id>/', views.StpmProgrammeDetailView.as_view(), name='stpm-programme-detail'),
```

**Step 4: Run tests to verify they pass**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_search.py -v
```
Expected: 12 PASS (8 search + 4 detail)

**Step 5: Run full test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v --tb=no -q
```
Expected: 319+ collected, 286+ passing

**Step 6: Commit**

```bash
git add apps/courses/views.py apps/courses/urls.py apps/courses/tests/test_stpm_search.py
git commit -m "feat: add GET /api/v1/stpm/programmes/<id>/ detail endpoint"
```

---

## Task 3: Frontend API client + i18n keys

**Files:**
- Modify: `halatuju-web/src/lib/api.ts`
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1: Add STPM search + detail types and functions to api.ts**

After the existing `rankStpmProgrammes` function, add:

```typescript
export interface StpmSearchParams {
  q?: string
  university?: string
  stream?: string
  limit?: number
  offset?: number
}

export interface StpmSearchFilters {
  universities: string[]
  streams: string[]
}

export interface StpmSearchResponse {
  programmes: StpmEligibleProgramme[]
  total_count: number
  filters: StpmSearchFilters
}

export interface StpmRequirements {
  min_cgpa: number
  min_muet_band: number
  stpm_min_subjects: number
  stpm_min_grade: string
  stpm_subjects: string[]
  stpm_subject_group: Record<string, unknown> | null
  spm_prerequisites: string[]
  spm_subject_group: Record<string, unknown> | null
  req_interview: boolean
  no_colorblind: boolean
  req_medical_fitness: boolean
  req_malaysian: boolean
  req_bumiputera: boolean
}

export interface StpmProgrammeDetail {
  program_id: string
  program_name: string
  university: string
  stream: string
  requirements: StpmRequirements
}

export async function searchStpmProgrammes(
  params: StpmSearchParams = {},
  options?: ApiOptions
): Promise<StpmSearchResponse> {
  const searchParams = new URLSearchParams()
  if (params.q) searchParams.set('q', params.q)
  if (params.university) searchParams.set('university', params.university)
  if (params.stream) searchParams.set('stream', params.stream)
  if (params.limit) searchParams.set('limit', String(params.limit))
  if (params.offset) searchParams.set('offset', String(params.offset))
  const qs = searchParams.toString()
  return apiRequest(`/api/v1/stpm/search/${qs ? `?${qs}` : ''}`, options)
}

export async function getStpmProgrammeDetail(
  programId: string,
  options?: ApiOptions
): Promise<StpmProgrammeDetail> {
  return apiRequest(`/api/v1/stpm/programmes/${programId}/`, options)
}
```

**Step 2: Add i18n keys**

In `en.json`, add under a new `"stpm"` section:

```json
"stpm": {
  "searchTitle": "Browse STPM Degree Programmes",
  "searchPlaceholder": "Search programmes...",
  "universityFilter": "University",
  "streamFilter": "Stream",
  "allUniversities": "All Universities",
  "allStreams": "All Streams",
  "science": "Science",
  "arts": "Arts",
  "both": "Both",
  "programmesFound": "programmes found",
  "loadMore": "Load More",
  "remaining": "remaining",
  "backToResults": "Back to Results",
  "backToDashboard": "Back to Dashboard",
  "programmeDetail": "Programme Detail",
  "requirements": "Requirements",
  "stpmSubjects": "Required STPM Subjects",
  "spmPrerequisites": "SPM Prerequisites",
  "minimumCGPA": "Minimum CGPA",
  "minimumMUET": "Minimum MUET Band",
  "minimumSubjects": "Minimum STPM Subjects",
  "minimumGrade": "Minimum STPM Grade",
  "interviewRequired": "Interview Required",
  "noColorblind": "No Colourblindness",
  "medicalFitness": "Medical Fitness Required",
  "malaysianOnly": "Malaysian Citizens Only",
  "bumiputeraOnly": "Bumiputera Only",
  "noResults": "No programmes found",
  "noResultsDesc": "Try adjusting your search or filters",
  "browseAll": "Browse All Programmes"
}
```

In `ms.json`, add equivalent BM translations:

```json
"stpm": {
  "searchTitle": "Layari Program Ijazah STPM",
  "searchPlaceholder": "Cari program...",
  "universityFilter": "Universiti",
  "streamFilter": "Aliran",
  "allUniversities": "Semua Universiti",
  "allStreams": "Semua Aliran",
  "science": "Sains",
  "arts": "Sastera",
  "both": "Kedua-dua",
  "programmesFound": "program dijumpai",
  "loadMore": "Muat Lagi",
  "remaining": "lagi",
  "backToResults": "Kembali ke Hasil",
  "backToDashboard": "Kembali ke Papan Pemuka",
  "programmeDetail": "Butiran Program",
  "requirements": "Syarat Kemasukan",
  "stpmSubjects": "Mata Pelajaran STPM Diperlukan",
  "spmPrerequisites": "Prasyarat SPM",
  "minimumCGPA": "PNGK Minimum",
  "minimumMUET": "Band MUET Minimum",
  "minimumSubjects": "Mata Pelajaran STPM Minimum",
  "minimumGrade": "Gred STPM Minimum",
  "interviewRequired": "Temuduga Diperlukan",
  "noColorblind": "Tiada Buta Warna",
  "medicalFitness": "Kecergasan Perubatan Diperlukan",
  "malaysianOnly": "Warganegara Malaysia Sahaja",
  "bumiputeraOnly": "Bumiputera Sahaja",
  "noResults": "Tiada program dijumpai",
  "noResultsDesc": "Cuba laraskan carian atau penapis anda",
  "browseAll": "Layari Semua Program"
}
```

In `ta.json`, add equivalent Tamil translations:

```json
"stpm": {
  "searchTitle": "STPM பட்டப்படிப்பு நிகழ்ச்சிகளை உலாவுக",
  "searchPlaceholder": "நிகழ்ச்சிகளைத் தேடுக...",
  "universityFilter": "பல்கலைக்கழகம்",
  "streamFilter": "பிரிவு",
  "allUniversities": "அனைத்து பல்கலைக்கழகங்களும்",
  "allStreams": "அனைத்து பிரிவுகளும்",
  "science": "அறிவியல்",
  "arts": "கலை",
  "both": "இரண்டும்",
  "programmesFound": "நிகழ்ச்சிகள் கண்டறியப்பட்டன",
  "loadMore": "மேலும் ஏற்றுக",
  "remaining": "மீதமுள்ள",
  "backToResults": "முடிவுகளுக்குத் திரும்பு",
  "backToDashboard": "கட்டுப்பாட்டுப் பலகைக்குத் திரும்பு",
  "programmeDetail": "நிகழ்ச்சி விவரம்",
  "requirements": "தேவைகள்",
  "stpmSubjects": "தேவையான STPM பாடங்கள்",
  "spmPrerequisites": "SPM முன்நிபந்தனைகள்",
  "minimumCGPA": "குறைந்தபட்ச CGPA",
  "minimumMUET": "குறைந்தபட்ச MUET அலகு",
  "minimumSubjects": "குறைந்தபட்ச STPM பாடங்கள்",
  "minimumGrade": "குறைந்தபட்ச STPM தரம்",
  "interviewRequired": "நேர்காணல் தேவை",
  "noColorblind": "நிறக்குருடு இல்லாமை",
  "medicalFitness": "மருத்துவ தகுதி தேவை",
  "malaysianOnly": "மலேசிய குடிமக்கள் மட்டும்",
  "bumiputeraOnly": "பூமிபுத்திரா மட்டும்",
  "noResults": "நிகழ்ச்சிகள் எதுவும் கிடைக்கவில்லை",
  "noResultsDesc": "உங்கள் தேடலை அல்லது வடிகட்டிகளை மாற்றி முயற்சிக்கவும்",
  "browseAll": "அனைத்து நிகழ்ச்சிகளையும் உலாவுக"
}
```

**Step 3: Verify frontend builds**

```bash
cd halatuju-web && npm run build
```
Expected: Build succeeds

**Step 4: Commit**

```bash
git add src/lib/api.ts src/messages/en.json src/messages/ms.json src/messages/ta.json
git commit -m "feat: add STPM search/detail API client + i18n keys (EN/BM/TA)"
```

---

## Task 4: STPM search page

**Files:**
- Create: `halatuju-web/src/app/stpm/search/page.tsx`
- Modify: `halatuju-web/src/app/dashboard/page.tsx` (add "Browse All" link)

**Step 1: Create the search page**

Create `halatuju-web/src/app/stpm/search/page.tsx`:

```tsx
'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { Suspense } from 'react'
import {
  searchStpmProgrammes,
  type StpmEligibleProgramme,
  type StpmSearchFilters,
} from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useTranslation } from '@/lib/i18n'

const ITEMS_PER_PAGE = 24

function StpmSearchContent() {
  const t = useTranslation()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [programmes, setProgrammes] = useState<StpmEligibleProgramme[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [filters, setFilters] = useState<StpmSearchFilters>({ universities: [], streams: [] })
  const [isLoading, setIsLoading] = useState(true)
  const [displayCount, setDisplayCount] = useState(ITEMS_PER_PAGE)

  // Read filters from URL
  const query = searchParams.get('q') || ''
  const university = searchParams.get('university') || ''
  const stream = searchParams.get('stream') || ''

  const updateParam = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    router.replace(`/stpm/search?${params.toString()}`)
  }, [router, searchParams])

  // Debounced search
  const [searchInput, setSearchInput] = useState(query)
  useEffect(() => {
    const timer = setTimeout(() => {
      updateParam('q', searchInput)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput, updateParam])

  // Fetch programmes when filters change
  useEffect(() => {
    setIsLoading(true)
    setDisplayCount(ITEMS_PER_PAGE)
    searchStpmProgrammes({
      q: query || undefined,
      university: university || undefined,
      stream: stream || undefined,
      limit: 200,
    }).then(data => {
      setProgrammes(data.programmes)
      setTotalCount(data.total_count)
      setFilters(data.filters)
    }).catch(err => {
      console.error('STPM search failed:', err)
    }).finally(() => {
      setIsLoading(false)
    })
  }, [query, university, stream])

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader />
      <div className="container mx-auto px-6 py-8 flex-1">
        <div className="mb-6">
          <Link href="/dashboard" className="text-sm text-gray-500 hover:text-primary-500">
            ← {t('stpm.backToDashboard')}
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-2">{t('stpm.searchTitle')}</h1>
        </div>

        {/* Search + Filters */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-3">
            <input
              type="text"
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder={t('stpm.searchPlaceholder')}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <select
              value={university}
              onChange={e => updateParam('university', e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm bg-white"
            >
              <option value="">{t('stpm.allUniversities')}</option>
              {filters.universities.map(u => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
            <select
              value={stream}
              onChange={e => updateParam('stream', e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm bg-white"
            >
              <option value="">{t('stpm.allStreams')}</option>
              {filters.streams.map(s => (
                <option key={s} value={s}>{t(`stpm.${s}`)}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Results count */}
        <p className="text-sm text-gray-500 mb-4">
          {totalCount} {t('stpm.programmesFound')}
        </p>

        {/* Results */}
        {isLoading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent mb-4" />
          </div>
        ) : programmes.length === 0 ? (
          <div className="text-center py-12">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">{t('stpm.noResults')}</h2>
            <p className="text-gray-500">{t('stpm.noResultsDesc')}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {programmes.slice(0, displayCount).map(prog => (
                <Link
                  key={prog.program_id}
                  href={`/stpm/${prog.program_id}`}
                  className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-5 block"
                >
                  <h3 className="font-semibold text-gray-900 text-sm mb-2 line-clamp-2">
                    {prog.program_name}
                  </h3>
                  <p className="text-xs text-gray-500 mb-3">{prog.university}</p>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full">
                      CGPA ≥ {prog.min_cgpa.toFixed(2)}
                    </span>
                    <span className="px-2 py-0.5 bg-green-50 text-green-700 text-xs rounded-full">
                      MUET ≥ Band {prog.min_muet_band}
                    </span>
                    {prog.req_interview && (
                      <span className="px-2 py-0.5 bg-amber-50 text-amber-700 text-xs rounded-full">
                        Interview
                      </span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
            {programmes.length > displayCount && (
              <button
                onClick={() => setDisplayCount(prev => prev + ITEMS_PER_PAGE)}
                className="mt-4 w-full py-3 text-primary-600 hover:text-primary-700 text-sm font-medium"
              >
                {t('stpm.loadMore')} ({programmes.length - displayCount} {t('stpm.remaining')})
              </button>
            )}
          </>
        )}
      </div>
      <AppFooter />
    </div>
  )
}

export default function StpmSearchPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
      <StpmSearchContent />
    </Suspense>
  )
}
```

**Step 2: Add "Browse All Programmes" link on dashboard**

In `dashboard/page.tsx`, find the STPM header section (the `<div className="mb-6">` block that shows the programme count) and add a browse link:

After the existing edit profile link, add:
```tsx
<Link href="/stpm/search" className="text-xs text-primary-500 hover:text-primary-600 underline ml-3">
  {t('stpm.browseAll')}
</Link>
```

**Step 3: Verify frontend builds**

```bash
cd halatuju-web && npm run build
```
Expected: Build succeeds

**Step 4: Commit**

```bash
git add src/app/stpm/search/page.tsx src/app/dashboard/page.tsx
git commit -m "feat: add STPM programme search page with filters + dashboard link"
```

---

## Task 5: STPM programme detail page

**Files:**
- Create: `halatuju-web/src/app/stpm/[id]/page.tsx`

**Step 1: Create the detail page**

Create `halatuju-web/src/app/stpm/[id]/page.tsx`:

```tsx
'use client'

import { use } from 'react'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { getStpmProgrammeDetail } from '@/lib/api'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useTranslation } from '@/lib/i18n'

export default function StpmProgrammeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)
  const t = useTranslation()

  const { data, isLoading, error } = useQuery({
    queryKey: ['stpm_programme', id],
    queryFn: () => getStpmProgrammeDetail(id),
  })

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <AppHeader />
      <div className="container mx-auto px-6 py-8 flex-1">
        {/* Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-sm text-gray-500">
          <Link href="/dashboard" className="hover:text-primary-500">Dashboard</Link>
          <span>›</span>
          <Link href="/stpm/search" className="hover:text-primary-500">{t('stpm.searchTitle')}</Link>
          <span>›</span>
          <span className="text-gray-900">{t('stpm.programmeDetail')}</span>
        </div>

        {isLoading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          </div>
        ) : error || !data ? (
          <div className="text-center py-12">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Programme not found</h2>
            <Link href="/stpm/search" className="text-primary-500 hover:text-primary-600">
              ← {t('stpm.backToResults')}
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main content — 2 cols */}
            <div className="lg:col-span-2 space-y-6">
              {/* Header */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-start gap-3 mb-3">
                  <span className="px-2 py-0.5 bg-purple-50 text-purple-700 text-xs font-medium rounded-full">
                    {t(`stpm.${data.stream}`)}
                  </span>
                </div>
                <h1 className="text-xl font-bold text-gray-900 mb-2">{data.program_name}</h1>
                <p className="text-gray-500">{data.university}</p>
              </div>

              {/* STPM Subject Requirements */}
              {data.requirements.stpm_subjects.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <h2 className="font-semibold text-gray-900 mb-3">{t('stpm.stpmSubjects')}</h2>
                  <div className="flex flex-wrap gap-2">
                    {data.requirements.stpm_subjects.map(subj => (
                      <span key={subj} className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-full">
                        {subj}
                      </span>
                    ))}
                  </div>
                  {data.requirements.stpm_subject_group && (
                    <p className="text-xs text-gray-400 mt-2">
                      + flexible subject group requirement
                    </p>
                  )}
                </div>
              )}

              {/* SPM Prerequisites */}
              {data.requirements.spm_prerequisites.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <h2 className="font-semibold text-gray-900 mb-3">{t('stpm.spmPrerequisites')}</h2>
                  <div className="flex flex-wrap gap-2">
                    {data.requirements.spm_prerequisites.map(prereq => (
                      <span key={prereq} className="px-3 py-1 bg-green-50 text-green-700 text-sm rounded-full">
                        {prereq}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Sidebar — 1 col */}
            <div className="space-y-6">
              {/* Quick Facts */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h2 className="font-semibold text-gray-900 mb-4">{t('stpm.requirements')}</h2>
                <dl className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">{t('stpm.minimumCGPA')}</dt>
                    <dd className="font-medium text-gray-900">{data.requirements.min_cgpa.toFixed(2)}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">{t('stpm.minimumMUET')}</dt>
                    <dd className="font-medium text-gray-900">Band {data.requirements.min_muet_band}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">{t('stpm.minimumSubjects')}</dt>
                    <dd className="font-medium text-gray-900">{data.requirements.stpm_min_subjects}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">{t('stpm.minimumGrade')}</dt>
                    <dd className="font-medium text-gray-900">{data.requirements.stpm_min_grade}</dd>
                  </div>
                </dl>
              </div>

              {/* Flags */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="space-y-2">
                  {data.requirements.req_interview && (
                    <div className="flex items-center gap-2 text-sm text-amber-700">
                      <span className="w-2 h-2 bg-amber-500 rounded-full" />
                      {t('stpm.interviewRequired')}
                    </div>
                  )}
                  {data.requirements.no_colorblind && (
                    <div className="flex items-center gap-2 text-sm text-red-700">
                      <span className="w-2 h-2 bg-red-500 rounded-full" />
                      {t('stpm.noColorblind')}
                    </div>
                  )}
                  {data.requirements.req_medical_fitness && (
                    <div className="flex items-center gap-2 text-sm text-orange-700">
                      <span className="w-2 h-2 bg-orange-500 rounded-full" />
                      {t('stpm.medicalFitness')}
                    </div>
                  )}
                  {data.requirements.req_malaysian && (
                    <div className="flex items-center gap-2 text-sm text-gray-700">
                      <span className="w-2 h-2 bg-gray-500 rounded-full" />
                      {t('stpm.malaysianOnly')}
                    </div>
                  )}
                  {data.requirements.req_bumiputera && (
                    <div className="flex items-center gap-2 text-sm text-gray-700">
                      <span className="w-2 h-2 bg-gray-500 rounded-full" />
                      {t('stpm.bumiputeraOnly')}
                    </div>
                  )}
                  {!data.requirements.req_interview &&
                   !data.requirements.no_colorblind &&
                   !data.requirements.req_medical_fitness &&
                   !data.requirements.req_malaysian &&
                   !data.requirements.req_bumiputera && (
                    <p className="text-sm text-gray-400">No special requirements</p>
                  )}
                </div>
              </div>

              {/* Back link */}
              <Link
                href="/stpm/search"
                className="block text-center py-3 text-primary-600 hover:text-primary-700 text-sm font-medium"
              >
                ← {t('stpm.backToResults')}
              </Link>
            </div>
          </div>
        )}
      </div>
      <AppFooter />
    </div>
  )
}
```

**Step 2: Verify frontend builds**

```bash
cd halatuju-web && npm run build
```
Expected: Build succeeds

**Step 3: Commit**

```bash
git add src/app/stpm/[id]/page.tsx
git commit -m "feat: add STPM programme detail page with requirements and flags"
```

---

## Task 6: Sprint 4 close

**Step 1: Run full backend test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v
```
Expected: 319+ collected, 286+ passing, golden masters intact

**Step 2: Verify frontend builds**

```bash
cd halatuju-web && npm run build
```

**Step 3: Follow sprint-close workflow**

Read and follow `Settings/_workflows/sprint-close.md`:
- Update CLAUDE.md (test counts, new endpoints, key files)
- Update ARCHITECTURE_MAP.md (new pages, test files)
- Write retrospective
- Update lessons.md / decisions.md if applicable
- Workspace cleanup
- Context cleanup (memory files)
- Mission Control update
- Commit and push

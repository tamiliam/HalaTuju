# STPM Detail Page — Requirements Rendering

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render the full STPM and SPM subject group requirements on the STPM course detail page, replacing invisible raw JSON with human-readable tiered cards.

**Architecture:** Backend transforms subject group JSON into display-ready structures with human-readable subject names. Frontend renders each tier as a structured card ("Pick N from [subjects] at grade X"). SpecialConditions component already handles all demographic flags — just needs to be wired up.

**Tech Stack:** Django (backend view), Next.js/React (frontend component), pytest (backend tests)

---

## Context

### The Problem

The STPM course detail page hides the most important requirement data:

| Data | What page shows | What data contains |
|------|----------------|-------------------|
| `stpm_subject_group` (1,112 courses) | 11px grey footnote: "+ flexible subject group requirement" | Multi-tier structures: "2 from {Bio, Chem, Phy} at A, 1 at A-, 2 any at C" |
| `spm_subject_group` (494 courses) | Nothing | Subject+grade combos: "4 from {Bio, Chem, Phy, Math} at B" |
| `spm_subject_group[].exclude` (9 courses) | Nothing | Excluded subject categories |
| `no_disability` (51 courses) | Nothing | Already in SpecialConditions component but not passed |

### JSON Shapes

**`stpm_subject_group`** — array of tier objects:
```json
[
  {"min_count": 2, "min_grade": "A", "subjects": ["BIOLOGY", "CHEMISTRY", "PHYSICS"]},
  {"min_count": 2, "min_grade": "C", "subjects": null}
]
```
- `subjects: null` means "any STPM subject"
- 23 unique STPM subject codes (BIOLOGY, CHEMISTRY, PHYSICS, MATH_T, MATH_M, PA, ECONOMICS, ACCOUNTING, BUSINESS, etc.)

**`spm_subject_group`** — same shape, plus optional `exclude`:
```json
[
  {"min_count": 4, "min_grade": "B", "subjects": ["BIOLOGY_SPM", "CHEMISTRY_SPM", "PHYSICS_SPM", "MATH"]},
  {"min_count": 1, "min_grade": "B", "subjects": null, "exclude": ["EKONOMI_SPM", "PERNIAGAAN_SPM", ...]}
]
```
- 93 unique SPM subject codes
- 9 courses have `exclude` lists (up to 50 codes)

### Design Reference

Stitch screens `24a906feecd14db6926c5f0ccb24e52e` (variant A) and `5b17920a0aa84960af4dc5f5be696c51` (variant B) in project `7363298109642864230`. Use variant B's pattern: "GROUP N (CHOOSE X)" cards with subject pills inside.

### Files Overview

| File | Change | Role |
|------|--------|------|
| `halatuju_api/apps/courses/views.py` | Modify (lines 1503-1610) | Add display name mapping + structured subject group output |
| `halatuju_api/apps/courses/tests/test_stpm_search.py` | Modify | Add tests for new response fields |
| `halatuju-web/src/app/stpm/[id]/page.tsx` | Modify | Render subject group cards + pass all flags to SpecialConditions |
| `halatuju-web/src/lib/api.ts` | Modify | Update StpmRequirements type |
| `halatuju-web/src/messages/en.json` | Modify | Add i18n keys |
| `halatuju-web/src/messages/ms.json` | Modify | Add i18n keys |
| `halatuju-web/src/messages/ta.json` | Modify | Add i18n keys |

---

### Task 1: Backend — Add subject display name maps and transform subject groups

**Files:**
- Modify: `halatuju_api/apps/courses/views.py:1503-1610`
- Test: `halatuju_api/apps/courses/tests/test_stpm_search.py`

**Step 1: Write failing tests**

Add to `test_stpm_search.py` after the existing `TestStpmCourseDetailAPI` class:

```python
class TestStpmDetailSubjectGroups:
    """Tests for human-readable subject group rendering in STPM detail."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from apps.courses.models import StpmCourse, StpmRequirement
        self.client = APIClient()
        self.course = StpmCourse.objects.create(
            course_id='TEST001',
            course_name='Test Engineering',
            university='Test University',
            stream='science',
        )
        self.req = StpmRequirement.objects.create(
            course=self.course,
            stpm_req_physics=True,
            stpm_subject_group=[
                {'min_count': 2, 'min_grade': 'A', 'subjects': ['PHYSICS', 'CHEMISTRY', 'MATH_T']},
                {'min_count': 1, 'min_grade': 'C', 'subjects': None},
            ],
            spm_subject_group=[
                {'min_count': 3, 'min_grade': 'B', 'subjects': ['PHYSICS_SPM', 'CHEMISTRY_SPM', 'MATH']},
                {'min_count': 1, 'min_grade': 'C', 'subjects': None, 'exclude': ['EKONOMI_SPM', 'PERNIAGAAN_SPM']},
            ],
            no_disability=True,
        )

    def test_detail_has_stpm_subject_groups_display(self):
        resp = self.client.get('/api/v1/stpm/courses/TEST001/')
        req = resp.json()['requirements']
        groups = req['stpm_subject_groups_display']
        assert len(groups) == 2
        # First tier: named subjects
        assert groups[0]['min_count'] == 2
        assert groups[0]['min_grade'] == 'A'
        assert 'Physics' in groups[0]['subjects']
        assert 'Chemistry' in groups[0]['subjects']
        assert 'Mathematics (T)' in groups[0]['subjects']
        assert groups[0]['any_subject'] is False
        # Second tier: any subject
        assert groups[1]['min_count'] == 1
        assert groups[1]['any_subject'] is True
        assert groups[1]['subjects'] == []

    def test_detail_has_spm_subject_groups_display(self):
        resp = self.client.get('/api/v1/stpm/courses/TEST001/')
        req = resp.json()['requirements']
        groups = req['spm_subject_groups_display']
        assert len(groups) == 2
        # First tier: named subjects
        assert groups[0]['min_count'] == 3
        assert groups[0]['min_grade'] == 'B'
        assert 'Physics' in groups[0]['subjects']
        assert 'Chemistry' in groups[0]['subjects']
        assert 'Mathematics' in groups[0]['subjects']
        # Second tier: any subject with excludes
        assert groups[1]['any_subject'] is True
        assert len(groups[1]['exclude']) == 2
        assert 'Ekonomi' in groups[1]['exclude']

    def test_detail_empty_groups_when_no_subject_group(self):
        self.req.stpm_subject_group = None
        self.req.spm_subject_group = None
        self.req.save()
        resp = self.client.get('/api/v1/stpm/courses/TEST001/')
        req = resp.json()['requirements']
        assert req['stpm_subject_groups_display'] == []
        assert req['spm_subject_groups_display'] == []

    def test_detail_includes_no_disability(self):
        resp = self.client.get('/api/v1/stpm/courses/TEST001/')
        req = resp.json()['requirements']
        assert req['no_disability'] is True
```

**Step 2: Run tests to verify they fail**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_search.py::TestStpmDetailSubjectGroups -v`
Expected: FAIL — `KeyError: 'stpm_subject_groups_display'`

**Step 3: Implement the display name maps and group transformer**

In `views.py`, add two dicts and a helper method inside `StpmCourseDetailView` (after `SPM_PREREQ_FIELDS`):

```python
    # Display names for STPM subject codes used in stpm_subject_group JSON
    STPM_SUBJECT_DISPLAY = {
        'PA': 'Pengajian Am',
        'MATH_T': 'Mathematics (T)',
        'MATH_M': 'Mathematics (M)',
        'PHYSICS': 'Physics',
        'CHEMISTRY': 'Chemistry',
        'BIOLOGY': 'Biology',
        'ECONOMICS': 'Economics',
        'ACCOUNTING': 'Accounting',
        'BUSINESS': 'Business Studies',
        'BAHASA_MELAYU': 'Bahasa Melayu',
        'BAHASA_CINA': 'Bahasa Cina',
        'BAHASA_TAMIL': 'Bahasa Tamil',
        'BAHASA_ARAB': 'Bahasa Arab',
        'SEJARAH': 'Sejarah',
        'GEOGRAFI': 'Geografi',
        'KESUSASTERAAN_MELAYU': 'Kesusasteraan Melayu',
        'LITERATURE_IN_ENGLISH': 'Literature in English',
        'SENI_VISUAL': 'Seni Visual',
        'SAINS_SUKAN': 'Sains Sukan',
        'ICT': 'ICT',
        'SYARIAH': 'Syariah',
        'USULUDDIN': 'Usuluddin',
        'TAHFIZ_AL_QURAN': 'Tahfiz Al-Quran',
    }

    # Display names for SPM subject codes used in spm_subject_group JSON.
    # Uses proper Malay names (these appear on the course detail page).
    SPM_SUBJECT_DISPLAY = {
        'BM': 'Bahasa Melayu', 'BI': 'Bahasa Inggeris', 'MATH': 'Matematik',
        'ADD_MATH': 'Matematik Tambahan', 'SEJARAH': 'Sejarah',
        'SCIENCE_SPM': 'Sains', 'SAINS_TAMBAHAN_SPM': 'Sains Tambahan',
        'APPLIED_SCIENCE_SPM': 'Sains Gunaan',
        'PHYSICS_SPM': 'Fizik', 'CHEMISTRY_SPM': 'Kimia', 'BIOLOGY_SPM': 'Biologi',
        'EKONOMI_SPM': 'Ekonomi', 'EKONOMI_ASAS_SPM': 'Ekonomi Asas',
        'PRINSIP_PERAKAUNAN_SPM': 'Prinsip Perakaunan',
        'PERNIAGAAN_SPM': 'Perniagaan', 'PERDAGANGAN_SPM': 'Perdagangan',
        'GEOGRAFI_SPM': 'Geografi',
        'PENDIDIKAN_MORAL_SPM': 'Pendidikan Moral',
        'PENDIDIKAN_ISLAM_SPM': 'Pendidikan Islam',
        'ICT_SPM': 'ICT', 'SAINS_KOMPUTER_SPM': 'Sains Komputer',
        'PENDIDIKAN_SENI_VISUAL_SPM': 'Pendidikan Seni Visual',
        'LUKISAN_KEJURUTERAAN_SPM': 'Lukisan Kejuruteraan',
        'GRAFIK_KOMUNIKASI_TEKNIKAL_SPM': 'Grafik Komunikasi Teknikal',
        'TEKNOLOGI_KEJURUTERAAN_SPM': 'Teknologi Kejuruteraan',
        'REKA_CIPTA_SPM': 'Reka Cipta',
        'SAINS_SUKAN_SPM': 'Sains Sukan',
        'PENGETAHUAN_SAINS_SUKAN_SPM': 'Pengetahuan Sains Sukan',
        'SAINS_RUMAH_TANGGA_SPM': 'Sains Rumah Tangga',
        'EKONOMI_RUMAH_TANGGA_SPM': 'Ekonomi Rumah Tangga',
        'SAINS_PERTANIAN_SPM': 'Sains Pertanian',
        'PERTANIAN_SPM': 'Pertanian',
        'PENGAJIAN_KEUSAHAWANAN_SPM': 'Pengajian Keusahawanan',
        'BAHASA_TAMIL_SPM': 'Bahasa Tamil', 'BAHASA_CINA_SPM': 'Bahasa Cina',
        'BAHASA_ARAB_SPM': 'Bahasa Arab', 'BAHASA_ARAB_TINGGI_SPM': 'Bahasa Arab Tinggi',
        'BAHASA_ARAB_MUASIRAH_SPM': 'Bahasa Arab Muasirah',
        'BAHASA_IBAN_SPM': 'Bahasa Iban', 'BAHASA_KADAZANDUSUN_SPM': 'Bahasa Kadazandusun',
        'BAHASA_SEMAI_SPM': 'Bahasa Semai',
        'KESUSASTERAAN_MELAYU_SPM': 'Kesusasteraan Melayu',
        'KESUSASTERAAN_INGGERIS_SPM': 'Kesusasteraan Inggeris',
        'KESUSASTERAAN_TAMIL_SPM': 'Kesusasteraan Tamil',
        'KESUSASTERAAN_CINA_SPM': 'Kesusasteraan Cina',
        'LITERATURE_IN_ENGLISH_SPM': 'Literature in English',
        'REKA_BENTUK_GRAFIK_SPM': 'Reka Bentuk Grafik',
        'REKA_BENTUK_GRAFIK_DIGITAL_SPM': 'Reka Bentuk Grafik Digital',
        'KOMUNIKASI_VISUAL_SPM': 'Komunikasi Visual',
        'PRODUKSI_MULTIMEDIA_SPM': 'Produksi Multimedia',
        'GRAFIK_BERKOMPUTER_SPM': 'Grafik Berkomputer',
        'PENDIDIKAN_SYARIAH_ISLAMIAH_SPM': 'Pendidikan Syariah Islamiah',
        'PENDIDIKAN_AL_QURAN_SPM': 'Pendidikan Al-Quran',
        'TASAWWUR_ISLAM_SPM': 'Tasawwur Islam',
        'AL_SYARIAH_SPM': 'Al-Syariah', 'USUL_AL_DIN_SPM': 'Usul Al-Din',
        'MANAHIJ_SPM': 'Manahij',
        'AL_ADAB_SPM': 'Al-Adab',
        'TURATH_BAHASA_ARAB_SPM': 'Turath Bahasa Arab',
        'TURATH_DIRASAT_ISLAMIAH_SPM': 'Turath Dirasat Islamiah',
        'TURATH_AL_QURAN_SPM': 'Turath Al-Quran',
        'MAHARAT_AL_QURAN_SPM': 'Maharat Al-Quran',
        'HIFZ_AL_QURAN_SPM': 'Hifz Al-Quran',
        'PRINSIP_ELEKTRIK_SPM': 'Prinsip Elektrik',
        'APLIKASI_ELEKTRIK_SPM': 'Aplikasi Elektrik',
        'APLIKASI_KOMPUTER_PERNIAGAAN_SPM': 'Aplikasi Komputer Perniagaan',
        'KEJURUTERAAN_AWAM_SPM': 'Kejuruteraan Awam',
        'KEJURUTERAAN_EE_SPM': 'Kejuruteraan Elektrik & Elektronik',
        'KEJURUTERAAN_MEKANIKAL_SPM': 'Kejuruteraan Mekanikal',
        'TEKNOLOGI_BINAAN_SPM': 'Teknologi Binaan',
        'TEKNOLOGI_BINAAN_BANGUNAN_SPM': 'Teknologi Binaan Bangunan',
        'HIASAN_DALAMAN_SPM': 'Hiasan Dalaman',
        'BAHAN_BINAAN_SPM': 'Bahan Binaan',
        'KATERING_SPM': 'Katering', 'KIMPALAN_SPM': 'Kimpalan',
        'MENSERVIS_AUTOMOBIL_SPM': 'Menservis Automobil',
        'MENSERVIS_MOTOSIKAL_SPM': 'Menservis Motosikal',
        'MENSERVIS_ELEKTRIK_SPM': 'Menservis Elektrik',
        'MENSERVIS_PENYEJUKAN_SPM': 'Menservis Penyejukan',
        'PEMBINAAN_DOMESTIK_SPM': 'Pembinaan Domestik',
        'PEMBUATAN_PERABOT_SPM': 'Pembuatan Perabot',
        'PEMESINAN_BERKOMPUTER_SPM': 'Pemesinan Berkomputer',
        'PEMPROSESAN_MAKANAN_SPM': 'Pemprosesan Makanan',
        'PENDAWAIAN_DOMESTIK_SPM': 'Pendawaian Domestik',
        'KERJA_PAIP_SPM': 'Kerja Paip',
        'REKAAN_JAHITAN_SPM': 'Rekaan Jahitan',
        'PENJAGAAN_MUKA_SPM': 'Penjagaan Muka',
        'ASUHAN_KANAK_KANAK_SPM': 'Asuhan Kanak-kanak',
        'GERONTOLOGI_SPM': 'Gerontologi',
        'AKUAKULTUR_SPM': 'Akuakultur',
        'LANDSKAP_DAN_NURSERI_SPM': 'Landskap dan Nurseri',
        'TANAMAN_MAKANAN_SPM': 'Tanaman Makanan',
        'ASAS_KELESTARIAN_SPM': 'Asas Kelestarian',
        'SENI_REKA_TANDA_SPM': 'Seni Reka Tanda',
        'PRODUKSI_REKA_TANDA_SPM': 'Produksi Reka Tanda',
        'REKA_BENTUK_INDUSTRI_SPM': 'Reka Bentuk Industri',
        'REKA_BENTUK_KRAF_SPM': 'Reka Bentuk Kraf',
        'MULTIMEDIA_KREATIF_SPM': 'Multimedia Kreatif',
        'SENI_HALUS_3D_SPM': 'Seni Halus 3D',
        'SENI_HALUS_2D_SPM': 'Seni Halus 2D',
        'SEJARAH_PENGURUSAN_SENI_SPM': 'Sejarah Pengurusan Seni',
        'PENDIDIKAN_MUZIK_SPM': 'Pendidikan Muzik',
        'AURAL_TEORI_MUZIK_SPM': 'Aural Teori Muzik',
        'MUZIK_KOMPUTER_SPM': 'Muzik Komputer',
        'ALAT_MUZIK_UTAMA_SPM': 'Alat Muzik Utama',
        'PRODUKSI_SENI_PERSEMBAHAN_SPM': 'Produksi Seni Persembahan',
        'SINOGRAFI_SPM': 'Sinografi',
        'PENULISAN_SKRIP_SPM': 'Penulisan Skrip',
        'LAKONAN_SPM': 'Lakonan',
        'APRESIASI_TARI_SPM': 'Apresiasi Tari',
        'KOREOGRAFI_TARI_SPM': 'Koreografi Tari',
        'TARIAN_SPM': 'Tarian',
    }

    @staticmethod
    def _build_groups_display(groups_json, display_map):
        """Transform subject group JSON into display-ready list.

        Input:  [{"min_count": 2, "min_grade": "A", "subjects": ["PHYSICS", "CHEMISTRY"]}, ...]
        Output: [{"min_count": 2, "min_grade": "A", "subjects": ["Physics", "Chemistry"],
                  "any_subject": false, "exclude": []}, ...]
        """
        if not groups_json:
            return []
        result = []
        for group in groups_json:
            if not isinstance(group, dict):
                continue
            entry = {
                'min_count': group.get('min_count', 1),
                'min_grade': group.get('min_grade', 'C'),
                'any_subject': group.get('subjects') is None,
                'subjects': [],
                'exclude': [],
            }
            if group.get('subjects'):
                entry['subjects'] = [
                    display_map.get(code, code.replace('_', ' ').title())
                    for code in group['subjects']
                ]
            if group.get('exclude'):
                entry['exclude'] = [
                    display_map.get(code, code.replace('_', ' ').title())
                    for code in group['exclude']
                ]
            result.append(entry)
        return result
```

Then in the `get()` method, add the new fields to the `requirements` dict (after line 1565):

```python
                'stpm_subject_groups_display': self._build_groups_display(
                    req.stpm_subject_group, self.STPM_SUBJECT_DISPLAY
                ),
                'spm_subject_groups_display': self._build_groups_display(
                    req.spm_subject_group, self.SPM_SUBJECT_DISPLAY
                ),
```

**Step 4: Run tests to verify they pass**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_stpm_search.py::TestStpmDetailSubjectGroups -v`
Expected: 4 PASS

**Step 5: Run full test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: 654+ pass, 0 fail

**Step 6: Commit**

```bash
git add apps/courses/views.py apps/courses/tests/test_stpm_search.py
git commit -m "feat: add human-readable subject group display to STPM detail API"
```

---

### Task 2: Frontend — Update TypeScript types and render subject group cards

**Files:**
- Modify: `halatuju-web/src/lib/api.ts`
- Modify: `halatuju-web/src/app/stpm/[id]/page.tsx`

**Step 1: Update the StpmRequirements type in api.ts**

Find the `StpmRequirements` interface and add:

```typescript
export interface SubjectGroupDisplay {
  min_count: number
  min_grade: string
  subjects: string[]
  any_subject: boolean
  exclude: string[]
}

export interface StpmRequirements {
  // ... existing fields ...
  stpm_subject_groups_display: SubjectGroupDisplay[]
  spm_subject_groups_display: SubjectGroupDisplay[]
  req_male: boolean
  req_female: boolean
  single: boolean
  no_disability: boolean
}
```

**Step 2: Rewrite the Entry Requirements card in page.tsx**

Replace the existing STPM Subjects section (lines 229-247) with a `SubjectGroupCards` component that renders each tier:

```tsx
{/* STPM Subject Requirements */}
{(data.requirements.stpm_subjects.length > 0 ||
  data.requirements.stpm_subject_groups_display.length > 0) && (
  <div>
    <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
      {t('stpm.stpmSubjects')}
    </h3>
    {/* Boolean required subjects as pills */}
    {data.requirements.stpm_subjects.length > 0 && (
      <div className="flex flex-wrap gap-1.5 mb-2">
        {data.requirements.stpm_subjects.map(subj => (
          <span key={subj} className="px-2.5 py-1 bg-blue-50 border border-blue-100 rounded-full text-xs font-medium text-blue-700">
            {subj}
          </span>
        ))}
      </div>
    )}
    {/* Tiered subject groups */}
    {data.requirements.stpm_subject_groups_display.map((group, i) => (
      <div key={i} className="mt-2 rounded-lg border border-blue-100 bg-blue-50/50 p-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-semibold text-blue-800">
            {group.any_subject
              ? t('stpm.anySubject', { count: group.min_count })
              : t('stpm.pickFrom', { count: group.min_count })}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
            group.min_grade <= 'B' ? 'bg-green-100 text-green-700'
              : group.min_grade <= 'C' ? 'bg-amber-100 text-amber-700'
              : 'bg-gray-100 text-gray-600'
          }`}>
            {group.min_grade}
          </span>
        </div>
        {group.subjects.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {group.subjects.map(s => (
              <span key={s} className="px-2 py-0.5 bg-white border border-blue-200 rounded text-[11px] text-blue-700">
                {s}
              </span>
            ))}
          </div>
        )}
        {group.any_subject && group.subjects.length === 0 && (
          <span className="text-[11px] text-blue-600 italic">
            {t('stpm.anyStpmSubject')}
          </span>
        )}
      </div>
    ))}
  </div>
)}
```

Replace the existing SPM Prerequisites section (lines 250-264) with the same pattern but green:

```tsx
{/* SPM Prerequisites */}
{(data.requirements.spm_prerequisites.length > 0 ||
  data.requirements.spm_subject_groups_display.length > 0) && (
  <div>
    <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
      {t('stpm.spmPrerequisites')}
    </h3>
    {/* Boolean prereqs as pills */}
    {data.requirements.spm_prerequisites.length > 0 && (
      <div className="flex flex-wrap gap-1.5 mb-2">
        {data.requirements.spm_prerequisites.map(prereq => (
          <span key={prereq} className="px-2.5 py-1 bg-green-50 border border-green-100 rounded-full text-xs font-medium text-green-700">
            {prereq}
          </span>
        ))}
      </div>
    )}
    {/* SPM subject groups */}
    {data.requirements.spm_subject_groups_display.map((group, i) => (
      <div key={i} className="mt-2 rounded-lg border border-green-100 bg-green-50/50 p-3">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-xs font-semibold text-green-800">
            {group.any_subject
              ? t('stpm.anySubject', { count: group.min_count })
              : t('stpm.pickFrom', { count: group.min_count })}
          </span>
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
            group.min_grade <= 'B' ? 'bg-green-100 text-green-700'
              : group.min_grade <= 'C' ? 'bg-amber-100 text-amber-700'
              : 'bg-gray-100 text-gray-600'
          }`}>
            {group.min_grade}
          </span>
        </div>
        {group.subjects.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {group.subjects.map(s => (
              <span key={s} className="px-2 py-0.5 bg-white border border-green-200 rounded text-[11px] text-green-700">
                {s}
              </span>
            ))}
          </div>
        )}
        {group.any_subject && group.subjects.length === 0 && !group.exclude.length && (
          <span className="text-[11px] text-green-600 italic">
            {t('stpm.anySpmSubject')}
          </span>
        )}
        {group.any_subject && group.subjects.length === 0 && group.exclude.length > 0 && (
          <div>
            <span className="text-[11px] text-green-600 italic">
              {t('stpm.anySpmSubject')}
            </span>
            <div className="mt-1.5">
              <span className="text-[10px] font-semibold text-red-500 uppercase">
                {t('stpm.excluding')}
              </span>
              <div className="flex flex-wrap gap-1 mt-0.5">
                {group.exclude.slice(0, 5).map(ex => (
                  <span key={ex} className="px-1.5 py-0.5 bg-red-50 border border-red-100 rounded text-[10px] text-red-600">
                    {ex}
                  </span>
                ))}
                {group.exclude.length > 5 && (
                  <span className="px-1.5 py-0.5 text-[10px] text-red-400">
                    +{group.exclude.length - 5} {t('common.more')}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    ))}
  </div>
)}
```

**Step 3: Wire up all demographic flags to SpecialConditions**

Replace the current SpecialConditions call (line 269-273):

```tsx
{/* Current — only passes 3 flags */}
<SpecialConditions
  reqInterview={req_interview}
  noColorblind={no_colorblind}
  reqMedicalFitness={req_medical_fitness}
/>
```

With:

```tsx
<SpecialConditions
  reqInterview={data.requirements.req_interview}
  noColorblind={data.requirements.no_colorblind}
  reqMedicalFitness={data.requirements.req_medical_fitness}
  reqMale={data.requirements.req_male}
  reqFemale={data.requirements.req_female}
  single={data.requirements.single}
  noDisability={data.requirements.no_disability}
/>
```

Also remove the destructuring on line 40: `const { req_interview, no_colorblind, req_medical_fitness } = data.requirements` — no longer needed.

**Step 4: Verify TypeScript compiles**

Run: `cd halatuju-web && npx tsc --noEmit`
Expected: 0 errors

**Step 5: Commit**

```bash
git add src/lib/api.ts src/app/stpm/[id]/page.tsx
git commit -m "feat: render STPM/SPM subject group tiers and all demographic flags on detail page"
```

---

### Task 3: Frontend — Add i18n keys

**Files:**
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1: Add keys to en.json**

In the `stpm` section, add:

```json
"pickFrom": "Pick {count} from:",
"anySubject": "Any {count} subject(s):",
"anyStpmSubject": "Any STPM subject",
"anySpmSubject": "Any SPM subject",
"excluding": "Excluding:"
```

In the `common` section, add (if not already present):

```json
"more": "more"
```

**Step 2: Add keys to ms.json**

```json
"pickFrom": "Pilih {count} daripada:",
"anySubject": "Mana-mana {count} mata pelajaran:",
"anyStpmSubject": "Mana-mana mata pelajaran STPM",
"anySpmSubject": "Mana-mana mata pelajaran SPM",
"excluding": "Kecuali:"
```

```json
"more": "lagi"
```

**Step 3: Add keys to ta.json**

```json
"pickFrom": "{count} தேர்வு செய்க:",
"anySubject": "ஏதேனும் {count} பாடங்கள்:",
"anyStpmSubject": "ஏதேனும் STPM பாடம்",
"anySpmSubject": "ஏதேனும் SPM பாடம்",
"excluding": "தவிர்த்து:"
```

```json
"more": "மேலும்"
```

**Step 4: Verify no missing keys**

Run: `cd halatuju-web && npx tsc --noEmit`
Expected: 0 errors

**Step 5: Commit**

```bash
git add src/messages/en.json src/messages/ms.json src/messages/ta.json
git commit -m "feat: add i18n keys for subject group display (EN/MS/TA)"
```

---

### Task 4: Visual verification and edge case testing

**Step 1: Run the full backend test suite**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ apps/reports/tests/ -v`
Expected: 658+ pass (654 existing + 4 new), 0 fail
Golden masters must remain: SPM=5319, STPM=2026

**Step 2: Spot-check the API response for a real course**

Run: `cd halatuju_api && python -c "
import django; import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'halatuju.settings'
django.setup()
from django.test import RequestFactory
from apps.courses.views import StpmCourseDetailView
factory = RequestFactory()
request = factory.get('/api/v1/stpm/courses/UM6724001/')
response = StpmCourseDetailView.as_view()(request, course_id='UM6724001')
import json
req = response.data['requirements']
print('STPM groups:', json.dumps(req['stpm_subject_groups_display'], indent=2))
print('SPM groups:', json.dumps(req['spm_subject_groups_display'], indent=2))
print('no_disability:', req['no_disability'])
"`

Expected: Human-readable subject names (not codes) in all group tiers. Exclude list for the Medicine SPM group should show proper Malay subject names.

**Step 3: Verify TypeScript compiles clean**

Run: `cd halatuju-web && npx tsc --noEmit`
Expected: 0 errors

**Step 4: Commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address edge cases in subject group rendering"
```

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Unknown subject code not in display map | Low — all 23 STPM + 93 SPM codes are mapped | Fallback: `code.replace('_', ' ').title()` produces readable output |
| Grade comparison for badge colour | Medium — string comparison `<=` works for single chars but not `A-`, `B+` | Use simple mapping: `A`/`A-` = green, `B+`/`B`/`B-`/`C+`/`C` = amber, rest = grey |
| Exclude list too long (50 items) | Low — only 9 courses | Truncate to 5 + "+N more" |
| Golden master change | None — this is display-only, no eligibility logic changes | Verify golden master unchanged |

## Scope Exclusions

- **No new models or migrations** — all data already in DB
- **No changes to eligibility engine** — display-only
- **No i18n for subject names** — display names are in Malay (the original MOHE language), which is correct for a Malaysian education context. English/Tamil users see the official Malay subject names.

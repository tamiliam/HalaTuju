# STPM Entrance Sprint 2 — Frontend Onboarding + Grade Entry

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable STPM students to enter their STPM grades, MUET band, and SPM prerequisite grades through the onboarding flow, then call the STPM eligibility API to see results on the dashboard.

**Architecture:** Extend the existing onboarding flow. The exam-type page routes STPM students to a new combined grade entry page (Option A — single page with STPM grades + MUET + SPM prerequisites). The dashboard detects `exam_type=stpm` and calls the STPM eligibility API instead of the SPM one. Backend gets new `exam_type`/`stpm_grades`/`muet_band` fields on `StudentProfile` for sync.

**Tech Stack:** Next.js 14 (App Router, TypeScript, Tailwind), Django REST, localStorage for guest state, Supabase for authenticated state.

**Branch:** `feature/stpm-entrance` (active)

---

## Data Contract

### STPM Subject Keys (must match backend `stpm_engine.py`)

| Key | Subject | Stream |
|-----|---------|--------|
| `PA` | Pengajian Am | compulsory |
| `MATH_T` | Matematik T | science |
| `MATH_M` | Matematik M | arts |
| `PHYSICS` | Fizik | science |
| `CHEMISTRY` | Kimia | science |
| `BIOLOGY` | Biologi | science |
| `ECONOMICS` | Ekonomi | arts |
| `ACCOUNTING` | Perakaunan | arts |
| `BUSINESS` | Pengajian Perniagaan | arts |
| `GEOGRAFI` | Geografi | arts |
| `SEJARAH` | Sejarah | arts |
| `KESUSASTERAAN_MELAYU` | Kesusasteraan Melayu | arts |
| `BAHASA_MELAYU` | Bahasa Melayu | arts |
| `BAHASA_CINA` | Bahasa Cina | arts |
| `BAHASA_TAMIL` | Bahasa Tamil | arts |
| `SENI_VISUAL` | Seni Visual | arts |
| `SYARIAH` | Syariah Islamiah | arts |
| `USULUDDIN` | Usuluddin | arts |
| `ICT` | Sains Komputer/ICT | both |
| `FURTHER_MATH` | Matematik Lanjutan T | science |

### STPM Grade Scale

`A, A-, B+, B, B-, C+, C, C-, D, E, F` (11 options, no A+ in STPM)

### MUET Bands

`1, 2, 3, 4, 5, 6`

### SPM Prerequisite Subjects (6 subjects)

| Engine Key | Subject | Why needed |
|------------|---------|------------|
| `bm` | Bahasa Melayu | 100% of programmes require credit |
| `eng` | Bahasa Inggeris | 100% require credit |
| `hist` | Sejarah | 100% require pass |
| `math` | Matematik | 49% require credit |
| `addmath` | Matematik Tambahan | 49% require credit |
| `sci` | Sains | 11% require credit |

SPM Grade Scale: `A+, A, A-, B+, B, C+, C, D, E, G` (same as existing SPM page)

### API Request Shape

```json
POST /api/v1/stpm/eligibility/check/
{
  "stpm_grades": {"PA": "A", "MATH_T": "B+", "PHYSICS": "A-", "CHEMISTRY": "A"},
  "spm_grades": {"bm": "A", "eng": "B+", "hist": "A", "math": "A", "addmath": "B+", "sci": "A"},
  "cgpa": 3.67,
  "muet_band": 4,
  "gender": "Lelaki",
  "nationality": "Warganegara",
  "colorblind": "Tidak"
}
```

### API Response Shape

```json
{
  "eligible_programmes": [
    {
      "program_id": "UP6314001",
      "program_name": "BACELOR EKONOMI DENGAN KEPUJIAN",
      "university": "Universiti Putra Malaysia",
      "stream": "both",
      "min_cgpa": 2.50,
      "min_muet_band": 3,
      "stpm_req_physics": false,
      "req_interview": false,
      "no_colorblind": false
    }
  ],
  "total_eligible": 245
}
```

### localStorage Keys (new for STPM)

| Key | Value | Example |
|-----|-------|---------|
| `halatuju_exam_type` | `"spm"` or `"stpm"` | `"stpm"` |
| `halatuju_stpm_grades` | JSON object | `{"PA":"A","MATH_T":"B+"}` |
| `halatuju_stpm_cgpa` | string float | `"3.67"` |
| `halatuju_muet_band` | string int | `"4"` |
| `halatuju_spm_prereq` | JSON object | `{"bm":"A","eng":"B+","hist":"A","math":"A","addmath":"B+","sci":"A"}` |

Existing keys unchanged: `halatuju_grades`, `halatuju_stream`, `halatuju_profile`, `halatuju_merit`.

---

## Task 1: STPM subject definitions + CGPA utility

**Files:**
- Modify: `halatuju-web/src/lib/subjects.ts`
- Create: `halatuju-web/src/lib/stpm.ts`

**Step 1: Add STPM constants to `subjects.ts`**

Add at the bottom of `halatuju-web/src/lib/subjects.ts`:

```typescript
// ---------------------------------------------------------------------------
// STPM subject definitions (keys match backend stpm_engine.py)
// ---------------------------------------------------------------------------

export interface StpmSubject {
  id: string
  name: string
  stream: 'science' | 'arts' | 'both' | 'compulsory'
}

export const STPM_SUBJECTS: StpmSubject[] = [
  { id: 'PA', name: 'Pengajian Am', stream: 'compulsory' },
  { id: 'MATH_T', name: 'Matematik T', stream: 'science' },
  { id: 'PHYSICS', name: 'Fizik', stream: 'science' },
  { id: 'CHEMISTRY', name: 'Kimia', stream: 'science' },
  { id: 'BIOLOGY', name: 'Biologi', stream: 'science' },
  { id: 'FURTHER_MATH', name: 'Matematik Lanjutan T', stream: 'science' },
  { id: 'ECONOMICS', name: 'Ekonomi', stream: 'arts' },
  { id: 'ACCOUNTING', name: 'Perakaunan', stream: 'arts' },
  { id: 'BUSINESS', name: 'Pengajian Perniagaan', stream: 'arts' },
  { id: 'GEOGRAFI', name: 'Geografi', stream: 'arts' },
  { id: 'SEJARAH', name: 'Sejarah', stream: 'arts' },
  { id: 'KESUSASTERAAN_MELAYU', name: 'Kesusasteraan Melayu', stream: 'arts' },
  { id: 'BAHASA_MELAYU', name: 'Bahasa Melayu', stream: 'arts' },
  { id: 'BAHASA_CINA', name: 'Bahasa Cina', stream: 'arts' },
  { id: 'BAHASA_TAMIL', name: 'Bahasa Tamil', stream: 'arts' },
  { id: 'SENI_VISUAL', name: 'Seni Visual', stream: 'arts' },
  { id: 'SYARIAH', name: 'Syariah Islamiah', stream: 'arts' },
  { id: 'USULUDDIN', name: 'Usuluddin', stream: 'arts' },
  { id: 'ICT', name: 'Sains Komputer / ICT', stream: 'both' },
  { id: 'MATH_M', name: 'Matematik M', stream: 'arts' },
]

export const STPM_GRADES = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'E', 'F']

export const MUET_BANDS = [1, 2, 3, 4, 5, 6]

// SPM prerequisite subjects for STPM students (6 subjects)
export const SPM_PREREQ_SUBJECTS = [
  { id: 'bm', name: 'Bahasa Melayu' },
  { id: 'eng', name: 'Bahasa Inggeris' },
  { id: 'hist', name: 'Sejarah' },
  { id: 'math', name: 'Matematik' },
  { id: 'addmath', name: 'Matematik Tambahan' },
  { id: 'sci', name: 'Sains' },
]

export const SPM_GRADE_OPTIONS = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']
```

**Step 2: Create STPM utility file `stpm.ts`**

Create `halatuju-web/src/lib/stpm.ts`:

```typescript
/**
 * STPM CGPA calculator — mirrors backend stpm_engine.py STPM_CGPA_POINTS.
 */

const STPM_CGPA_POINTS: Record<string, number> = {
  'A': 4.00, 'A-': 3.67,
  'B+': 3.33, 'B': 3.00, 'B-': 2.67,
  'C+': 2.33, 'C': 2.00, 'C-': 2.00,
  'D': 1.67, 'E': 1.00,
  'F': 0.00,
}

export function calculateStpmCgpa(grades: Record<string, string>): number {
  const entries = Object.values(grades).filter(g => g in STPM_CGPA_POINTS)
  if (entries.length === 0) return 0
  const total = entries.reduce((sum, g) => sum + STPM_CGPA_POINTS[g], 0)
  return Math.round((total / entries.length) * 100) / 100
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd halatuju-web && npx tsc --noEmit`
Expected: No new errors

**Step 4: Commit**

```bash
git add halatuju-web/src/lib/subjects.ts halatuju-web/src/lib/stpm.ts
git commit -m "feat: add STPM subject definitions and CGPA calculator"
```

---

## Task 2: Activate STPM on exam-type page

**Files:**
- Modify: `halatuju-web/src/app/onboarding/exam-type/page.tsx`
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1: Add i18n keys**

In `en.json`, inside `"onboarding"` object, add:

```json
"stpmGetStarted": "Get started",
```

No new keys needed — `stpmDesc` and `comingSoon` already exist. We just need to remove the "coming soon" state.

In `ms.json`, add matching key:
```json
"stpmGetStarted": "Mulakan"
```

In `ta.json`, add matching key:
```json
"stpmGetStarted": "தொடங்கவும்"
```

**Step 2: Update exam-type page**

In `halatuju-web/src/app/onboarding/exam-type/page.tsx`:

1. Add `handleSelectSTPM` function:
```typescript
const handleSelectSTPM = () => {
  localStorage.setItem('halatuju_exam_type', 'stpm')
  router.push('/onboarding/stpm-grades')
}
```

2. Replace the disabled STPM `<div>` (lines 69-89) with an active `<button>` that mirrors the SPM card structure:
```tsx
<button
  onClick={handleSelectSTPM}
  className="group relative overflow-hidden p-8 rounded-xl bg-white border-2 border-primary-100 shadow-sm hover:border-primary-500 hover:shadow-lg transition-all duration-200 text-left"
>
  {/* Same decorative gradient corner as SPM */}
  <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-primary-50 to-transparent rounded-bl-[80px] group-hover:from-primary-100 transition-colors" />
  <div className="relative">
    <div className="w-14 h-14 mb-5 rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-md shadow-primary-500/20">
      <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
      </svg>
    </div>
    <h3 className="text-xl font-semibold text-gray-900 mb-1">STPM</h3>
    <p className="text-gray-500 text-sm mb-4">{t('onboarding.stpmDesc')}</p>
    <span className="inline-flex items-center gap-1.5 text-primary-500 text-sm font-medium group-hover:gap-2.5 transition-all">
      {t('onboarding.stpmGetStarted')}
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
      </svg>
    </span>
  </div>
</button>
```

3. Also update `handleSelectSPM` to set exam type:
```typescript
const handleSelectSPM = () => {
  localStorage.setItem('halatuju_exam_type', 'spm')
  router.push('/onboarding/grades')
}
```

**Step 3: Test manually**

Run: `cd halatuju-web && npm run dev`
- Navigate to `/onboarding/exam-type`
- Verify both SPM and STPM cards are active (no "Coming Soon" badge)
- Click STPM → should navigate to `/onboarding/stpm-grades` (will 404 until Task 3)
- Click SPM → should still navigate to `/onboarding/grades`
- Check `localStorage.getItem('halatuju_exam_type')` → should be `"stpm"` or `"spm"`

**Step 4: Commit**

```bash
git add halatuju-web/src/app/onboarding/exam-type/page.tsx halatuju-web/src/messages/en.json halatuju-web/src/messages/ms.json halatuju-web/src/messages/ta.json
git commit -m "feat: activate STPM option on exam-type selection page"
```

---

## Task 3: STPM grade entry page (Option A — single combined page)

**Files:**
- Create: `halatuju-web/src/app/onboarding/stpm-grades/page.tsx`
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1: Add i18n keys**

In `en.json`, inside `"onboarding"` object, add these keys:

```json
"stpmGradesTitle": "Your STPM Results",
"stpmGradesSubtitle": "Enter your STPM and SPM results so we can find degree programmes you qualify for.",
"stpmSubjects": "STPM Subjects",
"stpmSubjectsHint": "Pengajian Am is compulsory. Select 3-4 more subjects you took.",
"stpmSelectSubject": "— Select subject —",
"stpmGrade": "Grade",
"muetBand": "MUET Band",
"muetHint": "Malaysian University English Test result",
"cgpaLabel": "CGPA",
"cgpaAutoCalc": "Auto-calculated from your STPM grades",
"spmPrerequisites": "SPM Results",
"spmPrereqHint": "Some degree programmes require minimum SPM grades.",
"spmPrereqTooltip": "About half of degree programmes require at least a credit in Mathematics and Additional Mathematics. All require credits in BM and BI, and a pass in Sejarah.",
"enterStpmSubjects": "Please select and grade at least Pengajian Am + 2 other subjects."
```

In `ms.json`, add matching keys:
```json
"stpmGradesTitle": "Keputusan STPM Anda",
"stpmGradesSubtitle": "Masukkan keputusan STPM dan SPM anda supaya kami boleh mencari program ijazah yang sesuai.",
"stpmSubjects": "Mata Pelajaran STPM",
"stpmSubjectsHint": "Pengajian Am wajib. Pilih 3-4 mata pelajaran lain yang anda ambil.",
"stpmSelectSubject": "— Pilih mata pelajaran —",
"stpmGrade": "Gred",
"muetBand": "Band MUET",
"muetHint": "Keputusan Malaysian University English Test",
"cgpaLabel": "PNGK",
"cgpaAutoCalc": "Dikira secara automatik daripada gred STPM anda",
"spmPrerequisites": "Keputusan SPM",
"spmPrereqHint": "Sesetengah program ijazah memerlukan gred SPM minimum.",
"spmPrereqTooltip": "Kira-kira separuh program memerlukan sekurang-kurangnya kepujian dalam Matematik dan Matematik Tambahan. Semua memerlukan kepujian BM dan BI, serta lulus Sejarah.",
"enterStpmSubjects": "Sila pilih dan masukkan gred sekurang-kurangnya Pengajian Am + 2 mata pelajaran lain."
```

In `ta.json`, add matching keys:
```json
"stpmGradesTitle": "உங்கள் STPM முடிவுகள்",
"stpmGradesSubtitle": "நீங்கள் தகுதி பெறும் பட்டப்படிப்புகளைக் கண்டறிய உங்கள் STPM மற்றும் SPM முடிவுகளை உள்ளிடவும்.",
"stpmSubjects": "STPM பாடங்கள்",
"stpmSubjectsHint": "Pengajian Am கட்டாயம். நீங்கள் எடுத்த மற்ற 3-4 பாடங்களைத் தேர்ந்தெடுக்கவும்.",
"stpmSelectSubject": "— பாடம் தேர்ந்தெடுக்கவும் —",
"stpmGrade": "தரம்",
"muetBand": "MUET பேண்ட்",
"muetHint": "Malaysian University English Test முடிவு",
"cgpaLabel": "CGPA",
"cgpaAutoCalc": "உங்கள் STPM தரங்களிலிருந்து தானாகக் கணக்கிடப்படுகிறது",
"spmPrerequisites": "SPM முடிவுகள்",
"spmPrereqHint": "சில பட்டப்படிப்புகளுக்கு குறைந்தபட்ச SPM தரங்கள் தேவை.",
"spmPrereqTooltip": "சுமார் பாதி படிப்புகளுக்கு கணிதம் மற்றும் கூடுதல் கணிதத்தில் குறைந்தது கிரெடிட் தேவை.",
"enterStpmSubjects": "குறைந்தது Pengajian Am + 2 பாடங்களைத் தேர்ந்தெடுத்து தரமிடவும்."
```

**Step 2: Create the STPM grade entry page**

Create `halatuju-web/src/app/onboarding/stpm-grades/page.tsx`:

```tsx
'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import ProgressStepper from '@/components/ProgressStepper'
import { STPM_SUBJECTS, STPM_GRADES, MUET_BANDS, SPM_PREREQ_SUBJECTS, SPM_GRADE_OPTIONS } from '@/lib/subjects'
import { calculateStpmCgpa } from '@/lib/stpm'

export default function StpmGradesPage() {
  const router = useRouter()
  const { t } = useT()

  // STPM grades: PA is always included, user picks 3-4 more
  const [stpmGrades, setStpmGrades] = useState<Record<string, string>>({ PA: '' })
  // Which optional subjects are selected (up to 4 slots)
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>(['', '', '', ''])
  // MUET band
  const [muetBand, setMuetBand] = useState<number | null>(null)
  // SPM prerequisite grades
  const [spmGrades, setSpmGrades] = useState<Record<string, string>>({})

  // Load saved data on mount
  useEffect(() => {
    const savedStpm = localStorage.getItem('halatuju_stpm_grades')
    if (savedStpm) {
      const parsed = JSON.parse(savedStpm)
      setStpmGrades(parsed)
      // Extract selected subjects (everything except PA)
      const subjects = Object.keys(parsed).filter(k => k !== 'PA')
      const padded = [...subjects, '', '', '', ''].slice(0, 4)
      setSelectedSubjects(padded)
    }

    const savedMuet = localStorage.getItem('halatuju_muet_band')
    if (savedMuet) setMuetBand(parseInt(savedMuet))

    const savedSpm = localStorage.getItem('halatuju_spm_prereq')
    if (savedSpm) setSpmGrades(JSON.parse(savedSpm))
  }, [])

  // STPM subject pool (exclude PA and already-selected subjects)
  const optionalSubjects = useMemo(() => {
    return STPM_SUBJECTS.filter(s => s.id !== 'PA')
  }, [])

  const handleSubjectChange = (index: number, newId: string) => {
    const oldId = selectedSubjects[index]
    // Remove old subject grade
    if (oldId) {
      setStpmGrades(prev => {
        const next = { ...prev }
        delete next[oldId]
        return next
      })
    }
    // Update slot
    setSelectedSubjects(prev => prev.map((s, i) => i === index ? newId : s))
  }

  const handleStpmGradeChange = (subjectId: string, grade: string) => {
    setStpmGrades(prev => ({ ...prev, [subjectId]: grade }))
  }

  const handleSpmGradeChange = (subjectId: string, grade: string) => {
    setSpmGrades(prev => ({ ...prev, [subjectId]: grade }))
  }

  // Auto-calculate CGPA from entered STPM grades
  const cgpa = useMemo(() => {
    const gradesWithValues = Object.fromEntries(
      Object.entries(stpmGrades).filter(([_, v]) => v !== '')
    )
    return calculateStpmCgpa(gradesWithValues)
  }, [stpmGrades])

  // Validation: PA graded + at least 2 other subjects graded + MUET selected
  const gradedSubjects = Object.entries(stpmGrades).filter(([_, v]) => v !== '')
  const isComplete = stpmGrades.PA !== '' && stpmGrades.PA !== undefined
    && gradedSubjects.length >= 3
    && muetBand !== null

  const handleContinue = () => {
    if (!isComplete) return

    // Save to localStorage
    const cleanGrades = Object.fromEntries(
      Object.entries(stpmGrades).filter(([_, v]) => v !== '')
    )
    localStorage.setItem('halatuju_stpm_grades', JSON.stringify(cleanGrades))
    localStorage.setItem('halatuju_stpm_cgpa', String(cgpa))
    localStorage.setItem('halatuju_muet_band', String(muetBand))
    localStorage.setItem('halatuju_spm_prereq', JSON.stringify(spmGrades))
    localStorage.setItem('halatuju_exam_type', 'stpm')

    router.push('/onboarding/profile')
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-icon.png" alt="HalaTuju" width={60} height={32} />
            </Link>
            <ProgressStepper currentStep={2} />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-8 max-w-3xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            {t('onboarding.stpmGradesTitle')}
          </h1>
          <p className="text-gray-600">
            {t('onboarding.stpmGradesSubtitle')}
          </p>
        </div>

        {/* Section 1: STPM Subjects & Grades */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">1</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.stpmSubjects')}</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.stpmSubjectsHint')}</p>

          {/* PA — compulsory, grade only */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 bg-white rounded-xl border border-gray-200 shadow-sm p-3">
              <div className="flex-1 flex items-center gap-2">
                <svg className="w-4 h-4 text-primary-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
                <span className="font-medium text-gray-900">Pengajian Am</span>
                <span className="text-red-500 text-xs">*</span>
              </div>
              <select
                value={stpmGrades.PA || ''}
                onChange={(e) => handleStpmGradeChange('PA', e.target.value)}
                className={`w-24 flex-shrink-0 px-3 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
                  stpmGrades.PA
                    ? 'bg-primary-50 border-primary-200 text-primary-700'
                    : 'bg-gray-50 border-gray-300 text-gray-500'
                }`}
              >
                <option value="">{t('onboarding.stpmGrade')}</option>
                {STPM_GRADES.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>

            {/* Optional subjects — 4 dropdown+grade slots */}
            {selectedSubjects.map((subjectId, index) => (
              <div key={index} className="flex items-center gap-2 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-3">
                <select
                  value={subjectId}
                  onChange={(e) => handleSubjectChange(index, e.target.value)}
                  className="flex-1 min-w-0 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                >
                  <option value="">{t('onboarding.stpmSelectSubject')}</option>
                  {optionalSubjects
                    .filter(s => !selectedSubjects.includes(s.id) || s.id === subjectId)
                    .map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
                {subjectId && (
                  <select
                    value={stpmGrades[subjectId] || ''}
                    onChange={(e) => handleStpmGradeChange(subjectId, e.target.value)}
                    className={`w-24 flex-shrink-0 px-3 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
                      stpmGrades[subjectId]
                        ? 'bg-primary-50 border-primary-200 text-primary-700'
                        : 'bg-gray-50 border-gray-300 text-gray-500'
                    }`}
                  >
                    <option value="">{t('onboarding.stpmGrade')}</option>
                    {STPM_GRADES.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                )}
                <button
                  onClick={() => handleSubjectChange(index, '')}
                  className="text-gray-400 hover:text-red-500 p-1 flex-shrink-0"
                  aria-label="Remove"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Section 2: MUET + CGPA */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">2</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.muetBand')}</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.muetHint')}</p>

          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
              {/* MUET band pills */}
              <div className="flex-1">
                <div className="flex gap-2 flex-wrap">
                  {MUET_BANDS.map(band => (
                    <button
                      key={band}
                      onClick={() => setMuetBand(band)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                        muetBand === band
                          ? 'bg-primary-500 text-white shadow-md'
                          : 'bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100'
                      }`}
                    >
                      Band {band}
                    </button>
                  ))}
                </div>
              </div>

              {/* CGPA display */}
              {cgpa > 0 && (
                <div className="text-right">
                  <div className="text-xs text-gray-500 mb-1">{t('onboarding.cgpaLabel')}</div>
                  <div className="flex items-baseline gap-1 justify-end">
                    <span className="text-3xl font-bold text-gray-900">{cgpa.toFixed(2)}</span>
                    <span className="text-sm text-gray-400">/ 4.00</span>
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{t('onboarding.cgpaAutoCalc')}</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Section 3: SPM Prerequisites */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">3</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.spmPrerequisites')}</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.spmPrereqHint')}</p>

          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {SPM_PREREQ_SUBJECTS.map(subject => (
                <div key={subject.id} className="flex items-center gap-3">
                  <span className="text-sm font-medium text-gray-700 flex-1">{subject.name}</span>
                  <select
                    value={spmGrades[subject.id] || ''}
                    onChange={(e) => handleSpmGradeChange(subject.id, e.target.value)}
                    className={`w-24 flex-shrink-0 px-3 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
                      spmGrades[subject.id]
                        ? 'bg-primary-50 border-primary-200 text-primary-700'
                        : 'bg-gray-50 border-gray-300 text-gray-500'
                    }`}
                  >
                    <option value="">{t('onboarding.grade')}</option>
                    {SPM_GRADE_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <Link href="/onboarding/exam-type" className="px-6 py-3 text-gray-600 hover:text-gray-900">
            {t('common.back')}
          </Link>
          <button
            onClick={handleContinue}
            disabled={!isComplete}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t('common.continue')}
          </button>
        </div>

        {!isComplete && (
          <p className="text-center text-sm text-gray-500 mt-4">
            {t('onboarding.enterStpmSubjects')}
          </p>
        )}
      </div>
    </main>
  )
}
```

**Step 3: Test manually**

Run: `cd halatuju-web && npm run dev`
- Navigate to `/onboarding/exam-type` → click STPM
- Verify the STPM grade entry page loads with 3 sections
- Select PA grade, 3 optional subjects + grades → verify CGPA auto-calculates
- Select MUET band → button should become enabled
- Enter SPM grades (optional) → should save
- Click Continue → verify localStorage keys set, navigates to `/onboarding/profile`
- Go back → verify data persists (reload page)

**Step 4: Commit**

```bash
git add halatuju-web/src/app/onboarding/stpm-grades/page.tsx halatuju-web/src/messages/en.json halatuju-web/src/messages/ms.json halatuju-web/src/messages/ta.json
git commit -m "feat: add STPM grade entry page with STPM grades, MUET band, and SPM prerequisites"
```

---

## Task 4: STPM API client function

**Files:**
- Modify: `halatuju-web/src/lib/api.ts`

**Step 1: Add STPM types and API function**

Add to `halatuju-web/src/lib/api.ts`:

```typescript
// STPM types
export interface StpmEligibleProgramme {
  program_id: string
  program_name: string
  university: string
  stream: string
  min_cgpa: number
  min_muet_band: number
  stpm_req_physics: boolean
  req_interview: boolean
  no_colorblind: boolean
}

export interface StpmEligibilityRequest {
  stpm_grades: Record<string, string>
  spm_grades: Record<string, string>
  cgpa: number
  muet_band: number
  gender?: string
  nationality?: string
  colorblind?: string
}

export interface StpmEligibilityResponse {
  eligible_programmes: StpmEligibleProgramme[]
  total_eligible: number
}

export async function checkStpmEligibility(
  data: StpmEligibilityRequest,
  options?: ApiOptions
): Promise<StpmEligibilityResponse> {
  return apiRequest('/api/v1/stpm/eligibility/check/', {
    method: 'POST',
    body: JSON.stringify(data),
    ...options,
  })
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd halatuju-web && npx tsc --noEmit`
Expected: No new errors

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/api.ts
git commit -m "feat: add STPM eligibility API client function"
```

---

## Task 5: Dashboard routes by exam type

**Files:**
- Modify: `halatuju-web/src/app/dashboard/page.tsx`

**Step 1: Read exam type from localStorage**

In `DashboardPage`, inside the existing `useEffect` that loads profile from localStorage (around line 46), add exam type detection:

```typescript
// After existing grade/profile loading...
const examType = localStorage.getItem('halatuju_exam_type') || 'spm'

if (examType === 'stpm') {
  // Load STPM-specific data from localStorage
  const stpmGradesStr = localStorage.getItem('halatuju_stpm_grades')
  const stpmCgpaStr = localStorage.getItem('halatuju_stpm_cgpa')
  const muetBandStr = localStorage.getItem('halatuju_muet_band')
  const spmPrereqStr = localStorage.getItem('halatuju_spm_prereq')

  if (stpmGradesStr && stpmCgpaStr && muetBandStr) {
    const parsedProfile = JSON.parse(profileData || '{}')
    setProfile({
      grades: {}, // SPM grades not used for eligibility
      gender: parsedProfile.gender || 'male',
      nationality: parsedProfile.nationality || 'malaysian',
      colorblind: parsedProfile.colorblind || false,
      disability: parsedProfile.disability || false,
      // Store STPM data in a way the dashboard can access
    })
    setStpmData({
      stpmGrades: JSON.parse(stpmGradesStr),
      cgpa: parseFloat(stpmCgpaStr),
      muetBand: parseInt(muetBandStr),
      spmGrades: spmPrereqStr ? JSON.parse(spmPrereqStr) : {},
    })
  }
} else {
  // Existing SPM profile loading (unchanged)
  ...
}
```

**Step 2: Add STPM state and conditional eligibility call**

Add new state at the top of the component:

```typescript
const [examType, setExamType] = useState<'spm' | 'stpm'>('spm')
const [stpmData, setStpmData] = useState<{
  stpmGrades: Record<string, string>
  cgpa: number
  muetBand: number
  spmGrades: Record<string, string>
} | null>(null)
const [stpmResults, setStpmResults] = useState<StpmEligibleProgramme[] | null>(null)
```

Add a `useEffect` for STPM eligibility check:

```typescript
useEffect(() => {
  if (examType !== 'stpm' || !stpmData || !profile) return

  const genderMap: Record<string, string> = { male: 'Lelaki', female: 'Perempuan' }
  const nationalityMap: Record<string, string> = { malaysian: 'Warganegara', non_malaysian: 'Bukan Warganegara' }

  checkStpmEligibility({
    stpm_grades: stpmData.stpmGrades,
    spm_grades: stpmData.spmGrades,
    cgpa: stpmData.cgpa,
    muet_band: stpmData.muetBand,
    gender: genderMap[profile.gender] || '',
    nationality: nationalityMap[profile.nationality] || 'Warganegara',
    colorblind: profile.colorblind ? 'Ya' : 'Tidak',
  }).then(data => {
    setStpmResults(data.eligible_programmes)
  }).catch(err => {
    console.error('STPM eligibility check failed:', err)
  })
}, [examType, stpmData, profile])
```

**Step 3: Render STPM results section**

In the JSX, add a conditional block. When `examType === 'stpm'`, render STPM programme cards instead of the SPM course cards:

```tsx
{examType === 'stpm' && stpmResults && (
  <div>
    <div className="mb-6">
      <h2 className="text-2xl font-bold text-gray-900">
        {t('dashboard.qualifyFor')} {stpmResults.length} degree programmes
      </h2>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {stpmResults.slice(0, displayCount).map(prog => (
        <div key={prog.program_id} className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-5">
          <h3 className="font-semibold text-gray-900 text-sm mb-2 line-clamp-2">{prog.program_name}</h3>
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
        </div>
      ))}
    </div>
    {stpmResults.length > displayCount && (
      <button
        onClick={() => setDisplayCount(prev => prev + 6)}
        className="mt-4 w-full py-3 text-primary-600 hover:text-primary-700 text-sm font-medium"
      >
        {t('dashboard.loadMore')} ({stpmResults.length - displayCount} {t('dashboard.remaining')})
      </button>
    )}
  </div>
)}
```

**Step 4: Test manually**

Run: `cd halatuju-web && npm run dev`
1. Go through STPM onboarding flow end-to-end
2. Enter STPM grades → profile → dashboard
3. Verify STPM programmes appear on dashboard
4. Verify "Load More" works
5. Verify SPM flow still works (switch exam type to SPM)

**Step 5: Commit**

```bash
git add halatuju-web/src/app/dashboard/page.tsx
git commit -m "feat: dashboard routes STPM students to STPM eligibility API"
```

---

## Task 6: Backend — add exam_type and STPM fields to StudentProfile

**Files:**
- Modify: `halatuju_api/apps/courses/models.py`
- Create migration
- Modify: `halatuju_api/apps/courses/views.py` (profile sync)
- Test: `halatuju_api/apps/courses/tests/test_profile_fields.py` (add tests)

**Step 1: Write failing tests**

Add to `test_profile_fields.py`:

```python
@pytest.mark.django_db
class TestStpmProfileFields:
    def test_exam_type_default(self):
        """StudentProfile defaults to exam_type='spm'."""
        profile = StudentProfile.objects.create(
            user_id='test-stpm-1',
            gender='Lelaki',
            nationality='Warganegara',
        )
        assert profile.exam_type == 'spm'

    def test_stpm_fields_stored(self):
        """STPM-specific fields should be stored on profile."""
        profile = StudentProfile.objects.create(
            user_id='test-stpm-2',
            gender='Lelaki',
            nationality='Warganegara',
            exam_type='stpm',
            stpm_grades={'PA': 'A', 'MATH_T': 'B+'},
            stpm_cgpa=3.67,
            muet_band=4,
        )
        assert profile.exam_type == 'stpm'
        assert profile.stpm_grades == {'PA': 'A', 'MATH_T': 'B+'}
        assert profile.stpm_cgpa == 3.67
        assert profile.muet_band == 4
```

**Step 2: Run to verify fails**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py::TestStpmProfileFields -v`
Expected: FAIL — fields don't exist

**Step 3: Add fields to StudentProfile model**

In `halatuju_api/apps/courses/models.py`, add to the `StudentProfile` model:

```python
exam_type = models.CharField(
    max_length=10,
    choices=[('spm', 'SPM'), ('stpm', 'STPM')],
    default='spm',
)
stpm_grades = models.JSONField(
    default=dict, blank=True,
    help_text="STPM grades: {'PA': 'A', 'MATH_T': 'B+', ...}"
)
stpm_cgpa = models.FloatField(null=True, blank=True)
muet_band = models.IntegerField(null=True, blank=True)
spm_prereq_grades = models.JSONField(
    default=dict, blank=True,
    help_text="SPM prerequisite grades for STPM students: {'bm': 'A', 'eng': 'B+', ...}"
)
```

**Step 4: Generate and run migration**

Run:
```bash
cd halatuju_api
python manage.py makemigrations courses
python manage.py migrate
```

**Step 5: Update profile sync view**

In `views.py`, update the profile sync handler to accept STPM fields:

```python
# In the profile sync view (ProfileSyncView.post)
# After existing field handling...
exam_type = request.data.get('exam_type')
if exam_type:
    profile.exam_type = exam_type
stpm_grades = request.data.get('stpm_grades')
if stpm_grades:
    profile.stpm_grades = stpm_grades
stpm_cgpa = request.data.get('stpm_cgpa')
if stpm_cgpa is not None:
    profile.stpm_cgpa = float(stpm_cgpa)
muet_band = request.data.get('muet_band')
if muet_band is not None:
    profile.muet_band = int(muet_band)
spm_prereq = request.data.get('spm_prereq_grades')
if spm_prereq:
    profile.spm_prereq_grades = spm_prereq
```

**Step 6: Run tests**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/test_profile_fields.py -v`
Expected: All tests pass (existing + 2 new)

**Step 7: Verify full test suite still passes**

Run: `cd halatuju_api && python -m pytest apps/courses/tests/ -v`
Expected: 290 collected, 257 pass (255 + 2 new). SPM golden master: 8283. STPM golden master: 1811.

**Step 8: Commit**

```bash
git add halatuju_api/apps/courses/models.py halatuju_api/apps/courses/migrations/ halatuju_api/apps/courses/views.py halatuju_api/apps/courses/tests/test_profile_fields.py
git commit -m "feat: add exam_type, stpm_grades, muet_band fields to StudentProfile"
```

---

## Task 7: Sprint 2 close

**Step 1: Run full backend test suite**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v
```

Expected: 290 collected, 257 pass, SPM golden master 8283, STPM golden master 1811

**Step 2: Verify frontend builds**

```bash
cd halatuju-web && npm run build
```

Expected: No build errors

**Step 3: Update CHANGELOG.md**

Add under `[Unreleased]`:

```markdown
### STPM Sprint 2 — Frontend Onboarding (2026-03-12)
- STPM option activated on exam-type selection page (was "Coming Soon")
- STPM grade entry page: STPM subjects + grades, MUET band, SPM prerequisites, auto CGPA
- STPM eligibility API client function
- Dashboard routes STPM students to STPM eligibility API, shows degree programme cards
- StudentProfile model: added exam_type, stpm_grades, stpm_cgpa, muet_band, spm_prereq_grades
- Profile sync accepts STPM-specific fields
- i18n: added STPM onboarding strings (EN, BM, Tamil)
```

**Step 4: Update halatuju_api/CLAUDE.md Next Sprint section**

Replace the "STPM Entrance Sprint 2 (next)" section with:

```markdown
**STPM Entrance Sprint 2 DONE — Frontend Onboarding**
- STPM option activated on exam-type page
- STPM grade entry page (single combined: STPM grades + MUET + SPM prerequisites)
- Dashboard shows STPM degree programme cards when exam_type=stpm
- StudentProfile: exam_type, stpm_grades, stpm_cgpa, muet_band, spm_prereq_grades
- Tests: 290 collected, 257 passing | SPM golden master: 8283 | STPM golden master: 1811

**STPM Entrance Sprint 3 (next)**
- Supabase migration: create stpm_courses/stpm_requirements tables + RLS policies
- Dashboard integration polish: STPM ranking engine, course cards with university/CGPA/MUET badges
- Search/filter for STPM programmes
- Course detail page for STPM programmes
- See `docs/plans/2026-03-12-stpm-entrance.md` for full plan (Tasks 15-22)
```

**Step 5: Commit and push**

```bash
git add -A
git commit -m "chore: STPM Sprint 2 close — frontend onboarding complete"
git push origin feature/stpm-entrance
```

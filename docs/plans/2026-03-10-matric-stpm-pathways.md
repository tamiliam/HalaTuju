# Matriculation & STPM Pathways Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the grades page to capture 4 stream subjects (up from 2), then show Matriculation and STPM pathway eligibility cards on the dashboard.

**Architecture:** All pathway logic is frontend-only (TypeScript). No backend changes. The pathway engine reads grades from localStorage, checks eligibility against hardcoded requirements, and computes merit/scores. The grades page expands to 4 stream subject slots and adjusts the UPU merit formula accordingly. Dashboard gets a new "Pathways" section above course cards.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, localStorage

**Key files to understand before starting:**
- `halatuju-web/src/app/onboarding/grades/page.tsx` — grades input page (4 core + 2 stream + 0-2 elective)
- `halatuju-web/src/lib/merit.ts` — UPU merit calculation
- `halatuju-web/src/app/dashboard/page.tsx` — dashboard page
- `halatuju-web/src/messages/en.json`, `ms.json`, `ta.json` — i18n files

---

### Task 1: Expand Grades Page — 4 Stream Subjects

**Files:**
- Modify: `halatuju-web/src/app/onboarding/grades/page.tsx`

**Context:** Currently the grades page has 2 stream subject dropdown slots (`aliranSubj1`, `aliranSubj2`). We need 4 slots. The state management, localStorage persistence, and grade clearing logic all need to handle 4 subjects.

**Step 1: Update state from 2 slots to 4 slots**

In `grades/page.tsx`, replace the individual `aliranSubj1`/`aliranSubj2` state with an array:

```tsx
// REPLACE these lines (around line 136-137):
//   const [aliranSubj1, setAliranSubj1] = useState<string>('')
//   const [aliranSubj2, setAliranSubj2] = useState<string>('')
// WITH:
const [aliranSubjects, setAliranSubjects] = useState<string[]>(['', '', '', ''])
```

**Step 2: Update all references to `aliranSubj1`/`aliranSubj2`**

Every reference to the old state must change. This includes:
- `useEffect` load (lines 143-186): load 4 subjects from `halatuju_aliran`
- `handleStreamChange` (lines 201-209): clear old grades, pre-populate 4 defaults
- `handleAliranSubj1Change`/`handleAliranSubj2Change` (lines 212-219): replace with generic `handleAliranChange(index, newId)`
- `selectedAliranIds` (line 247): derive from `aliranSubjects.filter(Boolean)`
- `meritResult` calculation (lines 279-291): pass 4 stream grades
- `handleContinue` (lines 295-312): save 4 subjects to localStorage

Key replacement patterns:
```tsx
// Generic handler for any aliran slot
const handleAliranChange = (index: number, newId: string) => {
  const oldId = aliranSubjects[index]
  if (oldId) handleGradeClear(oldId)
  setAliranSubjects(prev => prev.map((s, i) => i === index ? newId : s))
}

// selectedAliranIds
const selectedAliranIds = aliranSubjects.filter(Boolean)

// Stream change — pre-populate first 4 from pool (or fewer if pool is smaller)
const handleStreamChange = (newStream: string) => {
  aliranSubjects.forEach(id => { if (id) handleGradeClear(id) })
  setStream(newStream)
  localStorage.setItem('halatuju_stream', newStream)
  const pool = STREAM_POOLS[newStream] || []
  setAliranSubjects([
    pool[0]?.id || '',
    pool[1]?.id || '',
    pool[2]?.id || '',
    pool[3]?.id || '',
  ])
}
```

**Step 3: Update the merit calculation call**

The `calculateMeritScore` function currently takes `streamGrades` (2 items) and `electiveGrades` (0-2 items). With 4 stream subjects, we need to:
- Sort all 4 stream grades by point value (best first)
- Best 2 → streamGrades
- Weaker 2 → compete with electives for electiveGrades slots

```tsx
const meritResult = useMemo(() => {
  const coreGrades = CORE_SUBJECTS.map(s => grades[s.id]).filter(Boolean)
  if (coreGrades.length === 0) return null

  // All 4 stream grades (sorted best-first by merit points)
  const MERIT_PTS: Record<string, number> = {
    'A+': 18, 'A': 16, 'A-': 14, 'B+': 12, 'B': 10,
    'C+': 8, 'C': 6, 'D': 4, 'E': 2, 'G': 0,
  }
  const allStreamGrades = aliranSubjects
    .filter(Boolean)
    .map(id => grades[id])
    .filter(Boolean)
    .sort((a, b) => (MERIT_PTS[b] || 0) - (MERIT_PTS[a] || 0))

  // Best 2 stream grades count as "stream"
  const streamGrades = allStreamGrades.slice(0, 2)
  // Weaker stream grades compete with electives
  const weakerStream = allStreamGrades.slice(2)
  const pureElectives = elektifSlots
    .filter(Boolean)
    .map(id => grades[id])
    .filter(Boolean)

  // Combine weaker stream + electives, sort, take best 2
  const allElective = [...weakerStream, ...pureElectives]
    .sort((a, b) => (MERIT_PTS[b] || 0) - (MERIT_PTS[a] || 0))
    .slice(0, 2)

  return calculateMeritScore(coreGrades, streamGrades, allElective, coqScore)
}, [grades, coqScore, aliranSubjects, elektifSlots])
```

**Step 4: Update the JSX — render 4 `CompactSubjectRow` components**

Replace the 2 hardcoded `CompactSubjectRow` blocks in Section 3 with a loop:

```tsx
{/* Section 3: Stream Subjects */}
<div className="mb-8">
  <div className="flex items-center gap-2 mb-1">
    <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">3</span>
    <h2 className="text-lg font-semibold text-gray-900">
      {t('onboarding.streamSubjects')}
    </h2>
  </div>
  <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.pick4Stream')}</p>
  <div className="space-y-3">
    {aliranSubjects.map((subjectId, index) => (
      <CompactSubjectRow
        key={index}
        pool={streamPool}
        excludeIds={aliranSubjects.filter((_, i) => i !== index && aliranSubjects[i]).filter(Boolean)}
        selectedId={subjectId}
        onSubjectChange={(id) => handleAliranChange(index, id)}
        grade={subjectId ? grades[subjectId] || '' : ''}
        onGradeChange={(grade) => { if (subjectId) handleGradeChange(subjectId, grade) }}
        onRemove={() => { if (subjectId) handleGradeClear(subjectId); handleAliranChange(index, '') }}
      />
    ))}
  </div>
</div>
```

**Step 5: Update `handleContinue` to save 4 aliran subjects**

```tsx
localStorage.setItem(
  'halatuju_aliran',
  JSON.stringify(aliranSubjects.filter(Boolean))
)
```

**Step 6: Update i18n key**

In `en.json`, `ms.json`, `ta.json`, change:
```json
"pickBest2Stream": "Pick your best 2 subjects"
```
to:
```json
"pick4Stream": "Enter grades for your 4 stream subjects"
```

**Step 7: Run the dev server and test**

```bash
cd halatuju-web && npm run dev
```

Visit `/onboarding/grades`, verify:
- 4 stream subject slots appear
- Switching stream pre-populates 4 defaults (Science: PHY, CHE, BIO, AMT)
- Merit score calculates correctly (best 2 stream + weaker 2 compete with electives)
- Saving and reloading preserves all 4 subjects

**Step 8: Commit**

```bash
git add halatuju-web/src/app/onboarding/grades/page.tsx halatuju-web/src/messages/en.json halatuju-web/src/messages/ms.json halatuju-web/src/messages/ta.json
git commit -m "feat: expand stream subjects from 2 to 4 on grades page"
```

---

### Task 2: Create Pathway Engine — `lib/pathways.ts`

**Files:**
- Create: `halatuju-web/src/lib/pathways.ts`

**Context:** This is a pure TypeScript module with no React dependencies. It takes grades (as a `Record<string, string>`) and CoQ score, and returns eligibility results for 4 Matriculation tracks and 2 STPM bidang.

**Step 1: Create the pathway engine file**

```typescript
/**
 * Pathway eligibility engine for Matriculation and STPM (Form 6).
 *
 * Runs entirely on the frontend. No backend calls needed.
 * Input: student's SPM grades + CoQ score.
 * Output: eligibility + merit/score per pathway track.
 */

// --- Grade Point Scales ---

// Matriculation merit scale (from matrikulasi.moe.gov.my calculator)
const MATRIC_GRADE_POINTS: Record<string, number> = {
  'A+': 25, 'A': 24, 'A-': 23, 'B+': 22, 'B': 21,
  'C+': 20, 'C': 19, 'D': 18, 'E': 17, 'G': 0,
}

// STPM (Form 6) mata gred scale — lower is better
const STPM_MATA_GRED: Record<string, number> = {
  'A+': 1, 'A': 1, 'A-': 2, 'B+': 3, 'B': 4,
  'C+': 5, 'C': 6, 'D': 7, 'E': 8, 'G': 9,
}

// Credit = C or better (mata gred <= 6)
function isCredit(grade: string): boolean {
  const mg = STPM_MATA_GRED[grade]
  return mg !== undefined && mg <= 6
}

// Grade meets minimum threshold
function meetsMin(grade: string, minGrade: string): boolean {
  const order = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']
  const gradeIdx = order.indexOf(grade)
  const minIdx = order.indexOf(minGrade)
  if (gradeIdx === -1 || minIdx === -1) return false
  return gradeIdx <= minIdx // lower index = better grade
}

// --- Matriculation ---

export interface MatricTrack {
  id: string
  name: string
  nameMs: string
  nameTa: string
}

export const MATRIC_TRACKS: MatricTrack[] = [
  { id: 'sains', name: 'Science', nameMs: 'Sains', nameTa: 'அறிவியல்' },
  { id: 'kejuruteraan', name: 'Engineering', nameMs: 'Kejuruteraan', nameTa: 'பொறியியல்' },
  { id: 'sains_komputer', name: 'Computer Science', nameMs: 'Sains Komputer', nameTa: 'கணினி அறிவியல்' },
  { id: 'perakaunan', name: 'Accounting', nameMs: 'Perakaunan', nameTa: 'கணக்கியல்' },
]

interface MatricRequirement {
  subjectId: string
  minGrade: string
  alternatives?: string[] // alternative subject IDs (pick one)
}

// Subject requirements per track
// Subject IDs match the grades page: MAT, AMT, CHE, PHY, BIO, COMP_SCI, ACC, etc.
const MATRIC_REQUIREMENTS: Record<string, MatricRequirement[]> = {
  sains: [
    { subjectId: 'MAT', minGrade: 'B' },
    { subjectId: 'AMT', minGrade: 'C' },
    { subjectId: 'CHE', minGrade: 'C' },
    { subjectId: 'PHY', minGrade: 'C', alternatives: ['BIO'] },
  ],
  kejuruteraan: [
    { subjectId: 'MAT', minGrade: 'B' },
    { subjectId: 'AMT', minGrade: 'C' },
    { subjectId: 'PHY', minGrade: 'C' },
    // 4th: any elective with min C — handled separately
  ],
  sains_komputer: [
    { subjectId: 'MAT', minGrade: 'C' },
    { subjectId: 'AMT', minGrade: 'C' },
    { subjectId: 'COMP_SCI', minGrade: 'C' },
    // 4th: any elective with min C — handled separately
  ],
  perakaunan: [
    { subjectId: 'MAT', minGrade: 'C' },
    // 3 electives with min C — handled separately
  ],
}

export interface PathwayResult {
  pathway: 'matric' | 'stpm'
  trackId: string
  trackName: string
  trackNameMs: string
  trackNameTa: string
  eligible: boolean
  merit?: number         // Matric merit score (0-100)
  mataGred?: number      // STPM total mata gred
  maxMataGred?: number   // STPM threshold
  reason?: string        // Why not eligible (i18n key)
  reasonParams?: Record<string, string>
}

function findBestElective(
  grades: Record<string, string>,
  excludeIds: Set<string>,
  minGrade: string
): { id: string; grade: string } | null {
  let best: { id: string; grade: string; pts: number } | null = null
  for (const [id, grade] of Object.entries(grades)) {
    if (excludeIds.has(id)) continue
    if (!meetsMin(grade, minGrade)) continue
    const pts = MATRIC_GRADE_POINTS[grade] || 0
    if (!best || pts > best.pts) {
      best = { id, grade, pts }
    }
  }
  return best ? { id: best.id, grade: best.grade } : null
}

function checkMatricTrack(
  trackId: string,
  grades: Record<string, string>,
  coqScore: number
): PathwayResult {
  const track = MATRIC_TRACKS.find(t => t.id === trackId)!
  const reqs = MATRIC_REQUIREMENTS[trackId]
  const usedSubjects: { id: string; grade: string }[] = []
  const usedIds = new Set<string>()

  // Check fixed requirements
  for (const req of reqs) {
    const candidates = [req.subjectId, ...(req.alternatives || [])]
    let found = false
    for (const subjId of candidates) {
      const grade = grades[subjId]
      if (grade && meetsMin(grade, req.minGrade)) {
        usedSubjects.push({ id: subjId, grade })
        usedIds.add(subjId)
        found = true
        break
      }
    }
    if (!found) {
      // Check if student has the subject but grade too low
      const hasSubject = candidates.some(id => grades[id])
      const subjectName = candidates[0]
      return {
        pathway: 'matric',
        trackId,
        trackName: track.name,
        trackNameMs: track.nameMs,
        trackNameTa: track.nameTa,
        eligible: false,
        reason: hasSubject ? 'pathways.gradeTooLow' : 'pathways.subjectMissing',
        reasonParams: { subject: subjectName, minGrade: req.minGrade },
      }
    }
  }

  // Fill remaining slots with best electives (for tracks that need them)
  const slotsNeeded = 4 - usedSubjects.length
  for (let i = 0; i < slotsNeeded; i++) {
    const minGrade = 'C'
    const elective = findBestElective(grades, usedIds, minGrade)
    if (!elective) {
      return {
        pathway: 'matric',
        trackId,
        trackName: track.name,
        trackNameMs: track.nameMs,
        trackNameTa: track.nameTa,
        eligible: false,
        reason: 'pathways.notEnoughElectives',
      }
    }
    usedSubjects.push(elective)
    usedIds.add(elective.id)
  }

  // Calculate merit
  const subjectPoints = usedSubjects.reduce(
    (sum, s) => sum + (MATRIC_GRADE_POINTS[s.grade] || 0), 0
  )
  const academic = (subjectPoints / 100) * 90
  const coq = Math.min(Math.max(coqScore, 0), 10)
  const merit = Math.min(academic + coq, 100)

  return {
    pathway: 'matric',
    trackId,
    trackName: track.name,
    trackNameMs: track.nameMs,
    trackNameTa: track.nameTa,
    eligible: true,
    merit: Math.round(merit * 100) / 100,
  }
}

// --- STPM (Form 6) ---

// Subject groups for STPM Science bidang
// Student must have credits from 3 DIFFERENT groups
const STPM_SCIENCE_GROUPS: string[][] = [
  ['MAT', 'AMT'],
  ['PHY'],
  ['CHE'],
  ['BIO'],
  ['ENG_DRAW', 'ENG_MECH', 'ENG_CIVIL', 'ENG_ELEC', 'REKA_CIPTA',
   'SPORTS_SCI', 'SRT', 'COMP_SCI', 'GKT'],
]

// Subject groups for STPM Social Science bidang
const STPM_SOCSCI_GROUPS: string[][] = [
  ['BM'],
  ['BI'],
  ['SEJ'],
  ['GEO', 'PSV'],
  ['PI', 'PM'],
  ['MAT', 'AMT'],
  ['ACC'],
  ['SN', 'ADDSCI'],
  ['ECO', 'BUS', 'KEUSAHAWANAN', 'SPORTS_SCI', 'SRT', 'COMP_SCI',
   'GKT', 'PERTANIAN'],
]

export interface StpmBidang {
  id: string
  name: string
  nameMs: string
  nameTa: string
  maxMataGred: number
}

export const STPM_BIDANGS: StpmBidang[] = [
  { id: 'sains', name: 'Science', nameMs: 'Sains', nameTa: 'அறிவியல்', maxMataGred: 18 },
  { id: 'sains_sosial', name: 'Social Science', nameMs: 'Sains Sosial', nameTa: 'சமூக அறிவியல்', maxMataGred: 12 },
]

function checkStpmBidang(
  bidangId: string,
  grades: Record<string, string>
): PathwayResult {
  const bidang = STPM_BIDANGS.find(b => b.id === bidangId)!
  const groups = bidangId === 'sains' ? STPM_SCIENCE_GROUPS : STPM_SOCSCI_GROUPS

  // General requirement: credit in BM
  const bmGrade = grades['BM']
  if (!bmGrade || !isCredit(bmGrade)) {
    return {
      pathway: 'stpm',
      trackId: bidangId,
      trackName: bidang.name,
      trackNameMs: bidang.nameMs,
      trackNameTa: bidang.nameTa,
      eligible: false,
      maxMataGred: bidang.maxMataGred,
      reason: 'pathways.bmCreditRequired',
    }
  }

  // Find best 3 credits from different groups
  // Greedy: try each group, pick the subject with lowest mata gred
  type Pick = { groupIdx: number; subjectId: string; mataGred: number }
  const candidates: Pick[] = []

  for (let gi = 0; gi < groups.length; gi++) {
    let bestInGroup: Pick | null = null
    for (const subjId of groups[gi]) {
      const grade = grades[subjId]
      if (!grade || !isCredit(grade)) continue
      const mg = STPM_MATA_GRED[grade]
      if (!bestInGroup || mg < bestInGroup.mataGred) {
        bestInGroup = { groupIdx: gi, subjectId: subjId, mataGred: mg }
      }
    }
    if (bestInGroup) candidates.push(bestInGroup)
  }

  // Sort by mata gred (lowest first = best)
  candidates.sort((a, b) => a.mataGred - b.mataGred)

  if (candidates.length < 3) {
    return {
      pathway: 'stpm',
      trackId: bidangId,
      trackName: bidang.name,
      trackNameMs: bidang.nameMs,
      trackNameTa: bidang.nameTa,
      eligible: false,
      maxMataGred: bidang.maxMataGred,
      reason: 'pathways.notEnoughCredits',
      reasonParams: { needed: '3', have: String(candidates.length) },
    }
  }

  // Take best 3
  const best3 = candidates.slice(0, 3)
  const totalMataGred = best3.reduce((sum, p) => sum + p.mataGred, 0)

  if (totalMataGred > bidang.maxMataGred) {
    return {
      pathway: 'stpm',
      trackId: bidangId,
      trackName: bidang.name,
      trackNameMs: bidang.nameMs,
      trackNameTa: bidang.nameTa,
      eligible: false,
      mataGred: totalMataGred,
      maxMataGred: bidang.maxMataGred,
      reason: 'pathways.mataGredTooHigh',
      reasonParams: { total: String(totalMataGred), max: String(bidang.maxMataGred) },
    }
  }

  return {
    pathway: 'stpm',
    trackId: bidangId,
    trackName: bidang.name,
    trackNameMs: bidang.nameMs,
    trackNameTa: bidang.nameTa,
    eligible: true,
    mataGred: totalMataGred,
    maxMataGred: bidang.maxMataGred,
  }
}

// --- Public API ---

export function checkAllPathways(
  grades: Record<string, string>,
  coqScore: number
): PathwayResult[] {
  const results: PathwayResult[] = []

  // Matriculation tracks
  for (const track of MATRIC_TRACKS) {
    results.push(checkMatricTrack(track.id, grades, coqScore))
  }

  // STPM bidang
  for (const bidang of STPM_BIDANGS) {
    results.push(checkStpmBidang(bidang.id, grades))
  }

  return results
}
```

**Step 2: Verify file compiles**

```bash
cd halatuju-web && npx tsc --noEmit src/lib/pathways.ts
```

**Step 3: Commit**

```bash
git add halatuju-web/src/lib/pathways.ts
git commit -m "feat: add pathway eligibility engine for Matriculation and STPM"
```

---

### Task 3: Add Pathway Cards Component

**Files:**
- Create: `halatuju-web/src/components/PathwayCards.tsx`

**Context:** A React component that takes `PathwayResult[]` and renders them as cards. Used on the dashboard. Needs i18n support.

**Step 1: Create the component**

```tsx
'use client'

import { type PathwayResult } from '@/lib/pathways'
import { useT } from '@/lib/i18n'

export default function PathwayCards({ results }: { results: PathwayResult[] }) {
  const { t, lang } = useT()

  const matricResults = results.filter(r => r.pathway === 'matric')
  const stpmResults = results.filter(r => r.pathway === 'stpm')
  const anyEligible = results.some(r => r.eligible)

  if (results.length === 0) return null

  function getTrackName(r: PathwayResult): string {
    if (lang === 'ta') return r.trackNameTa
    if (lang === 'ms') return r.trackNameMs
    return r.trackName
  }

  function getReason(r: PathwayResult): string {
    if (!r.reason) return ''
    const translated = t(r.reason)
    if (!r.reasonParams) return translated
    let result = translated
    for (const [key, val] of Object.entries(r.reasonParams)) {
      result = result.replace(`{${key}}`, val)
    }
    return result
  }

  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        {t('pathways.title')}
      </h2>

      {!anyEligible && (
        <p className="text-sm text-gray-500 mb-4">
          {t('pathways.noneEligible')}
        </p>
      )}

      {/* Matriculation */}
      {matricResults.length > 0 && (
        <div className="mb-4">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">
            {t('pathways.matriculation')}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {matricResults.map(r => (
              <div
                key={r.trackId}
                className={`rounded-xl border p-4 transition-all ${
                  r.eligible
                    ? 'border-green-200 bg-green-50'
                    : 'border-gray-100 bg-gray-50 opacity-60'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">🎓</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {getTrackName(r)}
                  </span>
                </div>
                {r.eligible ? (
                  <>
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 mb-1">
                      {t('pathways.eligible')}
                    </span>
                    <div className="text-xs text-gray-600">
                      {t('pathways.merit')}: <span className="font-bold">{r.merit?.toFixed(1)}</span>/100
                    </div>
                  </>
                ) : (
                  <>
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-500 mb-1">
                      {t('pathways.notEligible')}
                    </span>
                    <div className="text-xs text-gray-400">{getReason(r)}</div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* STPM */}
      {stpmResults.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-2">
            {t('pathways.stpm')}
          </h3>
          <div className="grid grid-cols-2 gap-3">
            {stpmResults.map(r => (
              <div
                key={r.trackId}
                className={`rounded-xl border p-4 transition-all ${
                  r.eligible
                    ? 'border-blue-200 bg-blue-50'
                    : 'border-gray-100 bg-gray-50 opacity-60'
                }`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">📚</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {getTrackName(r)}
                  </span>
                </div>
                {r.eligible ? (
                  <>
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 mb-1">
                      {t('pathways.eligible')}
                    </span>
                    <div className="text-xs text-gray-600">
                      {t('pathways.mataGred')}: <span className="font-bold">{r.mataGred}</span>/{r.maxMataGred}
                    </div>
                  </>
                ) : (
                  <>
                    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-500 mb-1">
                      {t('pathways.notEligible')}
                    </span>
                    <div className="text-xs text-gray-400">{getReason(r)}</div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add halatuju-web/src/components/PathwayCards.tsx
git commit -m "feat: add PathwayCards component for dashboard"
```

---

### Task 4: Add i18n Keys

**Files:**
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1: Add pathway keys to all 3 language files**

**English (`en.json`)** — add `pathways` section:
```json
"pathways": {
  "title": "Your Pathways",
  "matriculation": "Matriculation (Matrikulasi)",
  "stpm": "Form 6 (STPM)",
  "eligible": "Eligible",
  "notEligible": "Not Eligible",
  "merit": "Merit",
  "mataGred": "Mata Gred",
  "noneEligible": "Based on your current grades, you may not meet the minimum requirements for these pathways. Focus on the courses shown below.",
  "gradeTooLow": "Need at least {minGrade} in {subject}",
  "subjectMissing": "{subject} not entered",
  "notEnoughElectives": "Need more subjects with at least C",
  "notEnoughCredits": "Need credits in {needed} subject groups (have {have})",
  "mataGredTooHigh": "Mata gred {total} exceeds limit of {max}",
  "bmCreditRequired": "Credit in Bahasa Melayu required"
}
```

Also update the existing key:
```json
"pick4Stream": "Enter grades for your 4 stream subjects"
```

**Malay (`ms.json`)** — add `pathways` section:
```json
"pathways": {
  "title": "Laluan Anda",
  "matriculation": "Matrikulasi",
  "stpm": "Tingkatan 6 (STPM)",
  "eligible": "Layak",
  "notEligible": "Tidak Layak",
  "merit": "Merit",
  "mataGred": "Mata Gred",
  "noneEligible": "Berdasarkan keputusan semasa anda, anda mungkin tidak memenuhi syarat minimum laluan ini. Fokus pada kursus yang ditunjukkan di bawah.",
  "gradeTooLow": "Perlukan sekurang-kurangnya {minGrade} dalam {subject}",
  "subjectMissing": "{subject} tidak dimasukkan",
  "notEnoughElectives": "Perlukan lebih banyak subjek dengan sekurang-kurangnya C",
  "notEnoughCredits": "Perlukan kepujian dalam {needed} kumpulan subjek (ada {have})",
  "mataGredTooHigh": "Mata gred {total} melebihi had {max}",
  "bmCreditRequired": "Kepujian Bahasa Melayu diperlukan"
}
```

**Tamil (`ta.json`)** — add `pathways` section:
```json
"pathways": {
  "title": "உங்கள் பாதைகள்",
  "matriculation": "மெட்ரிக்குலேசன்",
  "stpm": "படிவம் 6 (STPM)",
  "eligible": "தகுதியுள்ள",
  "notEligible": "தகுதியற்ற",
  "merit": "மெரிட்",
  "mataGred": "மாட்டா கிரெட்",
  "noneEligible": "உங்கள் தற்போதைய மதிப்பெண்களின் அடிப்படையில், இந்த பாதைகளுக்கான குறைந்தபட்ச தேவைகளை நீங்கள் பூர்த்தி செய்யாமல் இருக்கலாம்.",
  "gradeTooLow": "{subject} இல் குறைந்தபட்சம் {minGrade} தேவை",
  "subjectMissing": "{subject} உள்ளிடப்படவில்லை",
  "notEnoughElectives": "குறைந்தபட்சம் C உடன் மேலும் பாடங்கள் தேவை",
  "notEnoughCredits": "{needed} பாடக் குழுக்களில் கிரெடிட் தேவை ({have} உள்ளது)",
  "mataGredTooHigh": "மாட்டா கிரெட் {total} வரம்பு {max} ஐ மீறுகிறது",
  "bmCreditRequired": "பஹாசா மலாயு கிரெடிட் தேவை"
}
```

**Step 2: Commit**

```bash
git add halatuju-web/src/messages/en.json halatuju-web/src/messages/ms.json halatuju-web/src/messages/ta.json
git commit -m "feat: add i18n keys for pathway cards (EN/BM/TA)"
```

---

### Task 5: Wire Pathways into Dashboard

**Files:**
- Modify: `halatuju-web/src/app/dashboard/page.tsx`

**Context:** Import the pathway engine and `PathwayCards` component. Compute pathway results from localStorage grades when the dashboard loads. Display the cards above the course list.

**Step 1: Add imports**

At the top of `dashboard/page.tsx`, add:
```tsx
import { checkAllPathways } from '@/lib/pathways'
import PathwayCards from '@/components/PathwayCards'
```

**Step 2: Compute pathway results**

Inside `DashboardPage`, after the profile loading `useEffect` (around line 68), add a `useMemo`:

```tsx
import { useMemo } from 'react'  // add to existing import

// Compute pathway eligibility from grades
const pathwayResults = useMemo(() => {
  if (!profile) return []
  const coq = profile.coq_score ?? 0
  return checkAllPathways(profile.grades, coq)
}, [profile])
```

**Step 3: Render PathwayCards**

In the JSX, after the compact dashboard header (after line 310, before the loading state), add:

```tsx
{/* Pathway Cards — Matric & STPM */}
{pathwayResults.length > 0 && !eligibilityLoading && (
  <PathwayCards results={pathwayResults} />
)}
```

**Step 4: Test**

```bash
cd halatuju-web && npm run dev
```

Visit `/dashboard` with Science stream grades entered (e.g. BM=A, BI=B+, MAT=A, SEJ=B, PHY=B+, CHE=B, BIO=C+, AMT=C, CoQ=7):
- Verify Matric Science shows "Eligible" with a merit score
- Verify Matric Engineering shows "Eligible"
- Verify Matric Computer Science shows "Not Eligible" (no Comp Sci grade)
- Verify STPM Sains shows "Eligible" with mata gred sum
- Verify STPM Sains Sosial shows "Eligible" with mata gred sum

**Step 5: Commit**

```bash
git add halatuju-web/src/app/dashboard/page.tsx
git commit -m "feat: show Matriculation and STPM pathway cards on dashboard"
```

---

### Task 6: Build Verification & Deploy

**Files:** None new

**Step 1: Run full frontend build to check for TypeScript errors**

```bash
cd halatuju-web && npm run build
```

Expected: Build succeeds with no errors.

**Step 2: Run backend tests to confirm nothing broke**

```bash
cd halatuju_api && python -m pytest apps/courses/tests/ -v --tb=short -q
```

Expected: 203 pass, 9 fail (pre-existing JWT — unchanged).

**Step 3: Verify GCP config**

```bash
gcloud config get account && gcloud config get project
```

Must show `tamiliam@gmail.com` and `gen-lang-client-0871147736`. If not, fix:
```bash
gcloud config set account tamiliam@gmail.com && gcloud config set project gen-lang-client-0871147736
```

**Step 4: Deploy frontend**

```bash
cd halatuju-web && gcloud run deploy halatuju-web --source . --region asia-southeast1 --project gen-lang-client-0871147736 --allow-unauthenticated
```

**Step 5: Commit any remaining changes**

```bash
git add -A && git status
# Only commit if there are changes
git commit -m "chore: build verification"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Expand grades page to 4 stream subjects | `grades/page.tsx`, i18n |
| 2 | Create pathway engine | `lib/pathways.ts` (new) |
| 3 | Create PathwayCards component | `components/PathwayCards.tsx` (new) |
| 4 | Add i18n keys | `en.json`, `ms.json`, `ta.json` |
| 5 | Wire into dashboard | `dashboard/page.tsx` |
| 6 | Build check & deploy | — |

**No backend changes.** All pathway logic is frontend-only.

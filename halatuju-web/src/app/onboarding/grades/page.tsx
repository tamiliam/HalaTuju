'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import ProgressStepper from '@/components/ProgressStepper'
import { calculateMeritScore } from '@/lib/merit'

const GRADE_OPTIONS = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']

// Section 1: Teras — 4 compulsory subjects
const CORE_SUBJECTS = [
  { id: 'BM' },
  { id: 'BI' },
  { id: 'MAT' },
  { id: 'SEJ' },
]

// Stream definitions — icons are inline SVGs (two-tone: primary-500 + primary-200)
const STREAMS = [
  { id: 'science' },
  { id: 'arts' },
  { id: 'technical' },
]

function StreamIcon({ stream, active }: { stream: string; active: boolean }) {
  const stroke = active ? 'white' : '#3b82f6'
  const fill = active ? 'rgba(255,255,255,0.3)' : '#bfdbfe'
  if (stream === 'science') return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 3h6v6l4 8H5l4-8V3z" fill={fill} />
      <path d="M9 3h6M5 17h14" />
    </svg>
  )
  if (stream === 'arts') return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" fill={fill} />
    </svg>
  )
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" fill={fill} />
    </svg>
  )
}

// Section 2: Aliran — pick best 2 from stream pool
// IDs MUST lowercase to engine keys (serializer fallback) or be in GRADE_KEY_MAP
const STREAM_POOLS: Record<string, { id: string; name: string }[]> = {
  science: [
    { id: 'PHY', name: 'Fizik' },
    { id: 'CHE', name: 'Kimia' },
    { id: 'BIO', name: 'Biologi' },
    { id: 'AMT', name: 'Matematik Tambahan' },
  ],
  arts: [
    { id: 'ECO', name: 'Ekonomi' },
    { id: 'ACC', name: 'Prinsip Perakaunan' },
    { id: 'BUS', name: 'Perniagaan' },
    { id: 'GEO', name: 'Geografi' },
    { id: 'B_TAMIL', name: 'Bahasa Cina/Tamil' },
    { id: 'B_CINA', name: 'Kesusasteraan Cina/Tamil' },
    { id: 'LUKISAN', name: 'Lukisan' },
    { id: 'PSV', name: 'Pendidikan Seni Visual' },
    { id: 'KEUSAHAWANAN', name: 'Keusahawanan' },
  ],
  technical: [
    { id: 'ENG_CIVIL', name: 'Kejuruteraan Awam' },
    { id: 'ENG_MECH', name: 'Kejuruteraan Mekanikal' },
    { id: 'ENG_ELEC', name: 'Kejuruteraan Elektrik' },
    { id: 'ENG_DRAW', name: 'Lukisan Kejuruteraan' },
    { id: 'GKT', name: 'Grafik Komunikasi Teknikal' },
    { id: 'COMP_SCI', name: 'Sains Komputer' },
    { id: 'MULTIMEDIA', name: 'Multimedia' },
    { id: 'REKA_CIPTA', name: 'Reka Cipta' },
  ],
}

// Section 3: Elektif — pick best 2 from everything remaining
const ALL_SUBJECTS = [
  // Science
  { id: 'PHY', name: 'Fizik' },
  { id: 'CHE', name: 'Kimia' },
  { id: 'BIO', name: 'Biologi' },
  { id: 'AMT', name: 'Matematik Tambahan' },
  // Compulsory electives
  { id: 'PI', name: 'Pendidikan Islam' },
  { id: 'PM', name: 'Pendidikan Moral' },
  { id: 'SN', name: 'Sains' },
  { id: 'ADDSCI', name: 'Sains Tambahan' },
  { id: 'PERTANIAN', name: 'Pertanian' },
  { id: 'SRT', name: 'Sains Rumah Tangga' },
  { id: 'SPORTS_SCI', name: 'Sains Sukan' },
  { id: 'MUSIC', name: 'Pendidikan Muzik' },
  // Arts
  { id: 'ECO', name: 'Ekonomi' },
  { id: 'ACC', name: 'Prinsip Perakaunan' },
  { id: 'BUS', name: 'Perniagaan' },
  { id: 'GEO', name: 'Geografi' },
  { id: 'B_TAMIL', name: 'Bahasa Cina/Tamil' },
  { id: 'B_CINA', name: 'Kesusasteraan Cina/Tamil' },
  { id: 'LUKISAN', name: 'Lukisan' },
  { id: 'PSV', name: 'Pendidikan Seni Visual' },
  { id: 'KEUSAHAWANAN', name: 'Keusahawanan' },
  // Technical + IT
  { id: 'ENG_CIVIL', name: 'Kejuruteraan Awam' },
  { id: 'ENG_MECH', name: 'Kejuruteraan Mekanikal' },
  { id: 'ENG_ELEC', name: 'Kejuruteraan Elektrik' },
  { id: 'ENG_DRAW', name: 'Lukisan Kejuruteraan' },
  { id: 'GKT', name: 'Grafik Komunikasi Teknikal' },
  { id: 'COMP_SCI', name: 'Sains Komputer' },
  { id: 'MULTIMEDIA', name: 'Multimedia' },
  { id: 'REKA_CIPTA', name: 'Reka Cipta' },
  // Vocational (MPV)
  { id: 'VOC_CONSTRUCT', name: 'MPV Binaan Bangunan' },
  { id: 'VOC_WELD', name: 'MPV Kimpalan & Fabrikasi' },
  { id: 'VOC_AUTO', name: 'MPV Automotif' },
  { id: 'VOC_ELEC_SERV', name: 'MPV Elektrik & Elektronik' },
  { id: 'VOC_FOOD', name: 'MPV Pemprosesan Makanan' },
  { id: 'VOC_CATERING', name: 'MPV Katering & Penyajian' },
  { id: 'VOC_TAILORING', name: 'MPV Jahitan & Pakaian' },
]

export default function GradesInputPage() {
  const router = useRouter()
  const { t } = useT()

  // Stream selection (merged into this page)
  const [stream, setStream] = useState<string>('science')
  const [grades, setGrades] = useState<Record<string, string>>({})

  // Aliran: 2 dropdown slots (pre-populated from stream)
  const [aliranSubj1, setAliranSubj1] = useState<string>('')
  const [aliranSubj2, setAliranSubj2] = useState<string>('')

  // Elektif: dynamic 0-2 slots
  const [elektifSlots, setElektifSlots] = useState<string[]>([])

  // Load saved data — filter grades to only currently-selected subjects
  useEffect(() => {
    const savedStream = localStorage.getItem('halatuju_stream')
    const activeStream = savedStream || 'science'
    if (savedStream) setStream(savedStream)

    // Load aliran subjects
    let aliran1 = '', aliran2 = ''
    const savedAliran = localStorage.getItem('halatuju_aliran')
    if (savedAliran) {
      const a = JSON.parse(savedAliran)
      aliran1 = a[0] || ''
      aliran2 = a[1] || ''
    } else {
      const pool = STREAM_POOLS[activeStream] || []
      aliran1 = pool[0]?.id || ''
      aliran2 = pool[1]?.id || ''
    }
    setAliranSubj1(aliran1)
    setAliranSubj2(aliran2)

    // Load elective subjects
    let elektif: string[] = []
    const savedElektif = localStorage.getItem('halatuju_elektif')
    if (savedElektif) {
      elektif = JSON.parse(savedElektif).filter(Boolean)
    }
    setElektifSlots(elektif)

    // Load grades — only keep grades for valid (currently selected) subjects
    const savedGrades = localStorage.getItem('halatuju_grades')
    if (savedGrades) {
      const allGrades = JSON.parse(savedGrades)
      const validIds = new Set([
        ...CORE_SUBJECTS.map(s => s.id),
        ...[aliran1, aliran2].filter(Boolean),
        ...elektif,
      ])
      const cleaned: Record<string, string> = {}
      for (const [key, val] of Object.entries(allGrades)) {
        if (validIds.has(key)) cleaned[key] = val as string
      }
      setGrades(cleaned)
    }
  }, [])

  const handleGradeChange = (subjectId: string, grade: string) => {
    setGrades((prev) => ({ ...prev, [subjectId]: grade }))
  }

  const handleGradeClear = (subjectId: string) => {
    setGrades((prev) => {
      const next = { ...prev }
      delete next[subjectId]
      return next
    })
  }

  // Pre-populate stream subjects when stream changes — clear old grades
  const handleStreamChange = (newStream: string) => {
    if (aliranSubj1) handleGradeClear(aliranSubj1)
    if (aliranSubj2) handleGradeClear(aliranSubj2)
    setStream(newStream)
    localStorage.setItem('halatuju_stream', newStream)
    const pool = STREAM_POOLS[newStream] || []
    setAliranSubj1(pool[0]?.id || '')
    setAliranSubj2(pool[1]?.id || '')
  }

  // When switching aliran subject, clear old subject's grade
  const handleAliranSubj1Change = (newId: string) => {
    if (aliranSubj1) handleGradeClear(aliranSubj1)
    setAliranSubj1(newId)
  }
  const handleAliranSubj2Change = (newId: string) => {
    if (aliranSubj2) handleGradeClear(aliranSubj2)
    setAliranSubj2(newId)
  }

  // CoQ score — editable on this page, persisted to profile localStorage
  const [coqInput, setCoqInput] = useState<string>('')
  useEffect(() => {
    const savedProfile = localStorage.getItem('halatuju_profile')
    if (savedProfile) {
      const parsed = JSON.parse(savedProfile)
      if (parsed.coqScore !== undefined && parsed.coqScore > 0) {
        setCoqInput(String(parsed.coqScore))
      }
    }
  }, [])

  const coqScore = coqInput ? parseFloat(coqInput) : 0

  const handleCoqChange = (val: string) => {
    if (val === '' || (parseFloat(val) >= 0 && parseFloat(val) <= 10)) {
      setCoqInput(val)
      // Persist to profile localStorage so dashboard can read it
      const savedProfile = localStorage.getItem('halatuju_profile')
      const profile = savedProfile ? JSON.parse(savedProfile) : {}
      profile.coqScore = val ? parseFloat(val) : 0
      localStorage.setItem('halatuju_profile', JSON.stringify(profile))
    }
  }

  const streamPool = STREAM_POOLS[stream] || []
  const selectedAliranIds = [aliranSubj1, aliranSubj2].filter(Boolean)
  const coreIdsList = CORE_SUBJECTS.map((s) => s.id)

  // Elektif pool = all subjects minus core minus selected aliran
  const elektifPool = useMemo(() => {
    const excluded = new Set([...coreIdsList, ...selectedAliranIds])
    return ALL_SUBJECTS.filter((s) => !excluded.has(s.id)).sort((a, b) =>
      a.name.localeCompare(b.name)
    )
  }, [selectedAliranIds])

  const addElektifSlot = () => {
    if (elektifSlots.length < 2) {
      setElektifSlots((prev) => [...prev, ''])
    }
  }

  const removeElektifSlot = (index: number) => {
    const subjectId = elektifSlots[index]
    setElektifSlots((prev) => prev.filter((_, i) => i !== index))
    if (subjectId) {
      handleGradeClear(subjectId)
    }
  }

  const updateElektifSubject = (index: number, newSubjectId: string) => {
    const oldSubjectId = elektifSlots[index]
    if (oldSubjectId) handleGradeClear(oldSubjectId)
    setElektifSlots((prev) => prev.map((s, i) => (i === index ? newSubjectId : s)))
  }

  // Live merit calculation — UPU formula with categorised grades
  const meritResult = useMemo(() => {
    const coreGrades = CORE_SUBJECTS.map(s => grades[s.id]).filter(Boolean)
    if (coreGrades.length === 0) return null
    const streamGrades = [aliranSubj1, aliranSubj2]
      .filter(Boolean)
      .map(id => grades[id])
      .filter(Boolean)
    const electiveGrades = elektifSlots
      .filter(Boolean)
      .map(id => grades[id])
      .filter(Boolean)
    return calculateMeritScore(coreGrades, streamGrades, electiveGrades, coqScore)
  }, [grades, coqScore, aliranSubj1, aliranSubj2, elektifSlots])

  const coreComplete = CORE_SUBJECTS.every((s) => grades[s.id])

  const handleContinue = () => {
    if (coreComplete) {
      localStorage.setItem('halatuju_grades', JSON.stringify(grades))
      localStorage.setItem(
        'halatuju_aliran',
        JSON.stringify([aliranSubj1, aliranSubj2].filter(Boolean))
      )
      localStorage.setItem(
        'halatuju_elektif',
        JSON.stringify(elektifSlots.filter(Boolean))
      )
      router.push('/onboarding/profile')
    }
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
            {t('onboarding.gradesTitle')}
          </h1>
          <p className="text-gray-600">
            {t('onboarding.gradesSubtitleNew')}
          </p>
        </div>

        {/* Section 1: Select your Stream */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">1</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.selectStream')}</h2>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {STREAMS.map((s) => (
              <button
                key={s.id}
                onClick={() => handleStreamChange(s.id)}
                className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  stream === s.id
                    ? 'bg-primary-500 text-white shadow-md'
                    : 'bg-white text-gray-700 border border-gray-200 shadow-sm hover:shadow-md hover:border-gray-300'
                }`}
              >
                <StreamIcon stream={s.id} active={stream === s.id} />
                {t('onboarding.' + s.id + 'Stream')}
              </button>
            ))}
          </div>
        </div>

        {/* Section 2: Core Subjects — button grid */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">2</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.coreSubjects')}</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.coreSubjectsCount')}</p>
          <div className="space-y-3">
            {CORE_SUBJECTS.map((subject) => (
              <CoreSubjectGrade
                key={subject.id}
                label={t('subjects.' + subject.id)}
                value={grades[subject.id] || ''}
                onChange={(grade) => handleGradeChange(subject.id, grade)}
                onClear={() => handleGradeClear(subject.id)}
              />
            ))}
          </div>
        </div>

        {/* Section 3: Stream Subjects — compact dropdown rows */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">3</span>
            <h2 className="text-lg font-semibold text-gray-900">
              {t('onboarding.streamSubjects')}
            </h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.pickBest2Stream')}</p>
          <div className="space-y-3">
            <CompactSubjectRow
              pool={streamPool}
              excludeIds={aliranSubj2 ? [aliranSubj2] : []}
              selectedId={aliranSubj1}
              onSubjectChange={handleAliranSubj1Change}
              grade={aliranSubj1 ? grades[aliranSubj1] || '' : ''}
              onGradeChange={(grade) => { if (aliranSubj1) handleGradeChange(aliranSubj1, grade) }}
              onRemove={() => { if (aliranSubj1) handleGradeClear(aliranSubj1); setAliranSubj1('') }}
            />
            <CompactSubjectRow
              pool={streamPool}
              excludeIds={aliranSubj1 ? [aliranSubj1] : []}
              selectedId={aliranSubj2}
              onSubjectChange={handleAliranSubj2Change}
              grade={aliranSubj2 ? grades[aliranSubj2] || '' : ''}
              onGradeChange={(grade) => { if (aliranSubj2) handleGradeChange(aliranSubj2, grade) }}
              onRemove={() => { if (aliranSubj2) handleGradeClear(aliranSubj2); setAliranSubj2('') }}
            />
          </div>
        </div>

        {/* Section 4: Elective Subjects — compact dropdown + add button */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">4</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.electiveSubjects')}</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.pickBest2Elective')}</p>
          <div className="space-y-3">
            {elektifSlots.map((subjectId, index) => (
              <CompactSubjectRow
                key={index}
                pool={elektifPool}
                excludeIds={elektifSlots.filter((_, i) => i !== index && elektifSlots[i])}
                selectedId={subjectId}
                onSubjectChange={(id) => updateElektifSubject(index, id)}
                grade={subjectId ? grades[subjectId] || '' : ''}
                onGradeChange={(grade) => { if (subjectId) handleGradeChange(subjectId, grade) }}
                onRemove={() => removeElektifSlot(index)}
              />
            ))}
            {elektifSlots.length < 2 && (
              <button
                onClick={addElektifSlot}
                className="w-full py-3 rounded-xl border-2 border-dashed border-gray-300 text-gray-500 hover:border-primary-400 hover:text-primary-600 hover:shadow-sm transition-all text-sm font-medium"
              >
                + {t('onboarding.addElective')}
              </button>
            )}
          </div>
        </div>

        {/* Section 5: Co-curricular + Total Merit */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">5</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.coqScore')}</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.coqHint')}</p>

          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <div className="flex items-center gap-6">
              {/* CoQ input — left */}
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min="0"
                    max="10"
                    step="0.01"
                    value={coqInput}
                    onChange={(e) => handleCoqChange(e.target.value)}
                    placeholder="0.00"
                    className="w-28 px-3 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none text-center font-medium"
                  />
                  <span className="text-sm text-gray-400">/ 10</span>
                </div>
              </div>

              {/* Total Merit — right */}
              {meritResult && (
                <div className="text-right">
                  <div className="text-xs text-gray-500 mb-1">{t('onboarding.meritTotal')}</div>
                  <div className="flex items-baseline gap-1 justify-end">
                    <span className="text-3xl font-bold text-gray-900">
                      {meritResult.finalMerit.toFixed(2)}
                    </span>
                    <span className="text-sm text-gray-400">/ 100</span>
                  </div>
                </div>
              )}
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
            disabled={!coreComplete}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t('common.continue')}
          </button>
        </div>

        {!coreComplete && (
          <p className="text-center text-sm text-gray-500 mt-4">
            {t('onboarding.enterAllCore')}
          </p>
        )}
      </div>
    </main>
  )
}

/* Core Subject — button grid with checkmark and clear */
function CoreSubjectGrade({
  label,
  value,
  onChange,
  onClear,
}: {
  label: string
  value: string
  onChange: (grade: string) => void
  onClear: () => void
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {value ? (
            <svg className="w-5 h-5 text-green-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : (
            <div className="w-5 h-5 rounded-full border-2 border-gray-300 flex-shrink-0" />
          )}
          <span className="font-medium text-gray-900">{label}</span>
          <span className="text-red-500 text-sm">*</span>
        </div>
        {value && (
          <button onClick={onClear} className="text-gray-400 hover:text-gray-600 p-1" aria-label="Clear">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
      {/* Desktop: 10 cols, Mobile: 5 cols (5+5 split) */}
      <div className="grid grid-cols-5 md:grid-cols-10 gap-1.5">
        {GRADE_OPTIONS.map((grade) => (
          <button
            key={grade}
            onClick={() => onChange(grade)}
            className={`h-9 rounded-lg text-xs font-medium transition-all ${
              value === grade
                ? 'bg-primary-500 text-white shadow-md'
                : 'bg-gray-50 text-gray-700 shadow-sm hover:bg-gray-100 hover:shadow-md border border-gray-100'
            }`}
          >
            {grade}
          </button>
        ))}
      </div>
    </div>
  )
}

/* Compact subject row — dropdown + grade dropdown + remove */
function CompactSubjectRow({
  pool,
  excludeIds,
  selectedId,
  onSubjectChange,
  grade,
  onGradeChange,
  onRemove,
}: {
  pool: { id: string; name: string }[]
  excludeIds: string[]
  selectedId: string
  onSubjectChange: (id: string) => void
  grade: string
  onGradeChange: (grade: string) => void
  onRemove: () => void
}) {
  const { t } = useT()
  const excludeSet = new Set(excludeIds)
  const options = pool.filter((s) => !excludeSet.has(s.id))

  return (
    <div className="flex items-center gap-2 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-3">
      {/* Subject dropdown */}
      <select
        value={selectedId}
        onChange={(e) => onSubjectChange(e.target.value)}
        className="flex-1 min-w-0 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
      >
        <option value="">{t('onboarding.selectSubject')}</option>
        {options.map((s) => (
          <option key={s.id} value={s.id}>{s.name}</option>
        ))}
      </select>

      {/* Grade dropdown — styled as badge when selected */}
      {selectedId && (
        <select
          value={grade}
          onChange={(e) => onGradeChange(e.target.value)}
          className={`w-24 flex-shrink-0 px-3 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
            grade
              ? 'bg-primary-50 border-primary-200 text-primary-700'
              : 'bg-gray-50 border-gray-300 text-gray-500'
          }`}
        >
          <option value="">{t('onboarding.grade')}</option>
          {GRADE_OPTIONS.map((g) => (
            <option key={g} value={g}>{g}</option>
          ))}
        </select>
      )}

      {/* Remove button */}
      <button
        onClick={onRemove}
        className="text-gray-400 hover:text-red-500 p-1 flex-shrink-0"
        aria-label="Remove"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

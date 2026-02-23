'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import ProgressStepper from '@/components/ProgressStepper'

const GRADE_OPTIONS = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']

// Section 1: Teras — 4 compulsory subjects
const CORE_SUBJECTS = [
  { id: 'BM' },
  { id: 'BI' },
  { id: 'MAT' },
  { id: 'SEJ' },
]

// Stream definitions
const STREAMS = [
  { id: 'science', icon: '🔬' },
  { id: 'arts', icon: '📚' },
  { id: 'technical', icon: '🔧' },
]

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
    { id: 'B_CINA', name: 'Bahasa Cina' },
    { id: 'B_TAMIL', name: 'Bahasa Tamil' },
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
  { id: 'B_CINA', name: 'Bahasa Cina' },
  { id: 'B_TAMIL', name: 'Bahasa Tamil' },
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

  // Load saved data
  useEffect(() => {
    const savedStream = localStorage.getItem('halatuju_stream')
    if (savedStream) setStream(savedStream)

    const savedGrades = localStorage.getItem('halatuju_grades')
    if (savedGrades) setGrades(JSON.parse(savedGrades))

    const savedAliran = localStorage.getItem('halatuju_aliran')
    if (savedAliran) {
      const a = JSON.parse(savedAliran)
      if (a[0]) setAliranSubj1(a[0])
      if (a[1]) setAliranSubj2(a[1])
    }

    const savedElektif = localStorage.getItem('halatuju_elektif')
    if (savedElektif) {
      const e = JSON.parse(savedElektif)
      setElektifSlots(e.filter(Boolean))
    }
  }, [])

  // Pre-populate stream subjects when stream changes
  const handleStreamChange = (newStream: string) => {
    setStream(newStream)
    localStorage.setItem('halatuju_stream', newStream)
    const pool = STREAM_POOLS[newStream] || []
    setAliranSubj1(pool[0]?.id || '')
    setAliranSubj2(pool[1]?.id || '')
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

  const updateElektifSubject = (index: number, subjectId: string) => {
    setElektifSlots((prev) => prev.map((s, i) => (i === index ? subjectId : s)))
  }

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

        {/* Stream Selection — compact pills */}
        <div className="mb-8">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            {t('onboarding.selectStream')}
          </label>
          <div className="flex flex-wrap gap-2">
            {STREAMS.map((s) => (
              <button
                key={s.id}
                onClick={() => handleStreamChange(s.id)}
                className={`px-5 py-2.5 rounded-full text-sm font-medium transition-all ${
                  stream === s.id
                    ? 'bg-primary-500 text-white shadow-sm'
                    : 'bg-white text-gray-700 border border-gray-300 hover:border-gray-400'
                }`}
              >
                {s.icon} {t('onboarding.' + s.id + 'Stream')}
              </button>
            ))}
          </div>
        </div>

        {/* Section 1: Core Subjects — button grid */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">1</span>
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

        {/* Section 2: Stream Subjects — compact dropdown rows */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">2</span>
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
              onSubjectChange={setAliranSubj1}
              grade={aliranSubj1 ? grades[aliranSubj1] || '' : ''}
              onGradeChange={(grade) => { if (aliranSubj1) handleGradeChange(aliranSubj1, grade) }}
              onRemove={() => { if (aliranSubj1) handleGradeClear(aliranSubj1); setAliranSubj1('') }}
            />
            <CompactSubjectRow
              pool={streamPool}
              excludeIds={aliranSubj1 ? [aliranSubj1] : []}
              selectedId={aliranSubj2}
              onSubjectChange={setAliranSubj2}
              grade={aliranSubj2 ? grades[aliranSubj2] || '' : ''}
              onGradeChange={(grade) => { if (aliranSubj2) handleGradeChange(aliranSubj2, grade) }}
              onRemove={() => { if (aliranSubj2) handleGradeClear(aliranSubj2); setAliranSubj2('') }}
            />
          </div>
        </div>

        {/* Section 3: Elective Subjects — compact dropdown + add button */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">3</span>
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
                className="w-full py-3 rounded-xl border-2 border-dashed border-gray-300 text-gray-500 hover:border-primary-400 hover:text-primary-600 transition-all text-sm font-medium"
              >
                + {t('onboarding.addElective')}
              </button>
            )}
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
    <div className="bg-white rounded-xl border border-gray-200 p-4">
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
                ? 'bg-primary-500 text-white shadow-sm'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
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
    <div className="flex items-center gap-2 bg-white rounded-xl border border-gray-200 p-3">
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

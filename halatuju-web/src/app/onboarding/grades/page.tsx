'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'

const GRADE_OPTIONS = ['A+', 'A', 'A-', 'B+', 'B', 'C+', 'C', 'D', 'E', 'G']

// Section 1: Teras — 4 compulsory subjects, grade each
const CORE_SUBJECTS = [
  { id: 'BM', name: 'Bahasa Melayu' },
  { id: 'BI', name: 'Bahasa Inggeris' },
  { id: 'MAT', name: 'Matematik' },
  { id: 'SEJ', name: 'Sejarah' },
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
// This is the full pool minus core and minus selected aliran
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

const STREAM_LABELS: Record<string, string> = {
  science: 'Sains',
  arts: 'Sastera',
  technical: 'Teknikal',
}

export default function GradesInputPage() {
  const router = useRouter()
  const [stream, setStream] = useState<string>('science')
  const [grades, setGrades] = useState<Record<string, string>>({})

  // Aliran: 2 dropdown slots
  const [aliranSubj1, setAliranSubj1] = useState<string>('')
  const [aliranSubj2, setAliranSubj2] = useState<string>('')

  // Elektif: 2 dropdown slots
  const [elektifSubj1, setElektifSubj1] = useState<string>('')
  const [elektifSubj2, setElektifSubj2] = useState<string>('')

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
      if (e[0]) setElektifSubj1(e[0])
      if (e[1]) setElektifSubj2(e[1])
    }
  }, [])

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
        JSON.stringify([elektifSubj1, elektifSubj2].filter(Boolean))
      )
      router.push('/onboarding/profile')
    }
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Progress Header */}
      <div className="bg-white border-b">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-icon.png" alt="" width={32} height={32} />
              <span className="font-semibold text-gray-900">HalaTuju</span>
            </Link>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary-500 rounded-full flex items-center justify-center text-white text-sm font-bold">1</div>
              <div className="w-16 h-1 bg-primary-500 rounded" />
              <div className="w-8 h-8 bg-primary-500 rounded-full flex items-center justify-center text-white text-sm font-bold">2</div>
              <div className="w-16 h-1 bg-gray-200 rounded"><div className="w-1/2 h-full bg-primary-500 rounded" /></div>
              <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center text-gray-500 text-sm font-bold">3</div>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-12 max-w-3xl">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            Keputusan SPM Anda
          </h1>
          <p className="text-gray-600">
            Masukkan gred SPM anda untuk semak kelayakan kursus.
          </p>
        </div>

        {/* Section 1: Subjek Teras */}
        <div className="mb-10">
          <h2 className="text-lg font-semibold text-gray-900 mb-1 flex items-center gap-2">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">1</span>
            Subjek Teras
          </h2>
          <p className="text-sm text-gray-500 mb-4 ml-8">4 subjek wajib</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {CORE_SUBJECTS.map((subject) => (
              <GradeSelector
                key={subject.id}
                label={subject.name}
                required
                value={grades[subject.id] || ''}
                onChange={(grade) => handleGradeChange(subject.id, grade)}
              />
            ))}
          </div>
        </div>

        {/* Section 2: Subjek Aliran */}
        <div className="mb-10">
          <h2 className="text-lg font-semibold text-gray-900 mb-1 flex items-center gap-2">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">2</span>
            Subjek Aliran — {STREAM_LABELS[stream] || stream}
          </h2>
          <p className="text-sm text-gray-500 mb-4 ml-8">Pilih 2 subjek terbaik anda</p>
          <div className="space-y-4">
            <SubjectPicker
              label="Subjek Aliran 1"
              pool={streamPool}
              excludeIds={aliranSubj2 ? [aliranSubj2] : []}
              selectedId={aliranSubj1}
              onSubjectChange={setAliranSubj1}
              grade={aliranSubj1 ? grades[aliranSubj1] || '' : ''}
              onGradeChange={(grade) => { if (aliranSubj1) handleGradeChange(aliranSubj1, grade) }}
            />
            <SubjectPicker
              label="Subjek Aliran 2"
              pool={streamPool}
              excludeIds={aliranSubj1 ? [aliranSubj1] : []}
              selectedId={aliranSubj2}
              onSubjectChange={setAliranSubj2}
              grade={aliranSubj2 ? grades[aliranSubj2] || '' : ''}
              onGradeChange={(grade) => { if (aliranSubj2) handleGradeChange(aliranSubj2, grade) }}
            />
          </div>
        </div>

        {/* Section 3: Subjek Elektif */}
        <div className="mb-10">
          <h2 className="text-lg font-semibold text-gray-900 mb-1 flex items-center gap-2">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">3</span>
            Subjek Elektif
          </h2>
          <p className="text-sm text-gray-500 mb-4 ml-8">Pilih 2 subjek lain yang terbaik</p>
          <div className="space-y-4">
            <SubjectPicker
              label="Subjek Elektif 1"
              pool={elektifPool}
              excludeIds={elektifSubj2 ? [elektifSubj2] : []}
              selectedId={elektifSubj1}
              onSubjectChange={setElektifSubj1}
              grade={elektifSubj1 ? grades[elektifSubj1] || '' : ''}
              onGradeChange={(grade) => { if (elektifSubj1) handleGradeChange(elektifSubj1, grade) }}
            />
            <SubjectPicker
              label="Subjek Elektif 2"
              pool={elektifPool}
              excludeIds={elektifSubj1 ? [elektifSubj1] : []}
              selectedId={elektifSubj2}
              onSubjectChange={setElektifSubj2}
              grade={elektifSubj2 ? grades[elektifSubj2] || '' : ''}
              onGradeChange={(grade) => { if (elektifSubj2) handleGradeChange(elektifSubj2, grade) }}
            />
          </div>
        </div>

        {/* Navigation */}
        <div className="flex justify-between">
          <Link href="/onboarding/stream" className="px-6 py-3 text-gray-600 hover:text-gray-900">
            Kembali
          </Link>
          <button
            onClick={handleContinue}
            disabled={!coreComplete}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Teruskan
          </button>
        </div>

        {!coreComplete && (
          <p className="text-center text-sm text-gray-500 mt-4">
            Sila masukkan gred untuk semua subjek teras.
          </p>
        )}
      </div>
    </main>
  )
}

function GradeSelector({
  label,
  required,
  value,
  onChange,
}: {
  label: string
  required?: boolean
  value: string
  onChange: (grade: string) => void
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <div className="flex flex-wrap gap-2">
        {GRADE_OPTIONS.map((grade) => (
          <button
            key={grade}
            onClick={() => onChange(grade)}
            className={`w-10 h-10 rounded-lg text-sm font-medium transition-all ${
              value === grade
                ? 'bg-primary-500 text-white'
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

function SubjectPicker({
  label,
  pool,
  excludeIds,
  selectedId,
  onSubjectChange,
  grade,
  onGradeChange,
}: {
  label: string
  pool: { id: string; name: string }[]
  excludeIds: string[]
  selectedId: string
  onSubjectChange: (id: string) => void
  grade: string
  onGradeChange: (grade: string) => void
}) {
  const excludeSet = new Set(excludeIds)
  const options = pool.filter((s) => !excludeSet.has(s.id))

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className="flex flex-col sm:flex-row sm:items-start gap-3">
        <div className="sm:w-1/2">
          <label className="block text-xs text-gray-500 mb-1">{label}</label>
          <select
            value={selectedId}
            onChange={(e) => onSubjectChange(e.target.value)}
            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
          >
            <option value="">— Pilih subjek —</option>
            {options.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        {selectedId && (
          <div className="sm:w-1/2">
            <label className="block text-xs text-gray-500 mb-1">Gred</label>
            <div className="flex flex-wrap gap-1.5">
              {GRADE_OPTIONS.map((g) => (
                <button
                  key={g}
                  onClick={() => onGradeChange(g)}
                  className={`w-9 h-9 rounded-lg text-xs font-medium transition-all ${
                    grade === g
                      ? 'bg-primary-500 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

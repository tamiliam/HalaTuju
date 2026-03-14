'use client'

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import ProgressStepper from '@/components/ProgressStepper'
import {
  STPM_SUBJECTS,
  STPM_GRADES,
  MUET_BANDS,
  SPM_PREREQ_COMPULSORY,
  SPM_PREREQ_OPTIONAL,
  SPM_GRADE_OPTIONS,
} from '@/lib/subjects'
import { calculateCgpa } from '@/lib/api'

type Stream = 'science' | 'arts'

export default function StpmGradesPage() {
  const router = useRouter()
  const { t } = useT()

  const [stream, setStream] = useState<Stream | null>(null)
  const [stpmGrades, setStpmGrades] = useState<Record<string, string>>({ PA: '' })
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>(['', '', ''])
  const [electiveSubject, setElectiveSubject] = useState('')
  const [showElective, setShowElective] = useState(false)
  const [muetBand, setMuetBand] = useState<number | null>(null)
  const [kokoScore, setKokoScore] = useState<string>('')
  const [spmGrades, setSpmGrades] = useState<Record<string, string>>({})

  useEffect(() => {
    const savedStream = localStorage.getItem('halatuju_stpm_stream')
    if (savedStream === 'science' || savedStream === 'arts') setStream(savedStream)
    const savedStpm = localStorage.getItem('halatuju_stpm_grades')
    if (savedStpm) {
      const parsed = JSON.parse(savedStpm)
      setStpmGrades(prev => ({ ...prev, ...parsed }))
      const subjects = Object.keys(parsed).filter(k => k !== 'PA')
      if (subjects.length >= 3) {
        setSelectedSubjects(subjects.slice(0, 3))
        if (subjects.length > 3) { setElectiveSubject(subjects[3]); setShowElective(true) }
      }
    }
    const savedMuet = localStorage.getItem('halatuju_muet_band')
    if (savedMuet) setMuetBand(parseInt(savedMuet))
    const savedKoko = localStorage.getItem('halatuju_koko_score')
    if (savedKoko) setKokoScore(savedKoko)
    const savedSpm = localStorage.getItem('halatuju_spm_prereq')
    if (savedSpm) setSpmGrades(JSON.parse(savedSpm))
  }, [])

  // Stream-specific subjects for the 3 main slots
  const streamSubjects = useMemo(() => {
    if (!stream) return []
    return STPM_SUBJECTS.filter(
      s => s.stream === stream || s.stream === 'both'
    )
  }, [stream])

  // All non-PA subjects for the elective slot (any stream)
  const allOptionalSubjects = useMemo(() => {
    return STPM_SUBJECTS.filter(s => s.id !== 'PA')
  }, [])

  const handleStreamChange = (newStream: Stream) => {
    setStream(newStream)
    // Clear subject selections when stream changes
    setSelectedSubjects(['', '', ''])
    setElectiveSubject('')
    setStpmGrades({ PA: stpmGrades.PA || '' })
  }

  const handleSubjectChange = (index: number, newId: string) => {
    const oldId = selectedSubjects[index]
    if (oldId) {
      setStpmGrades(prev => {
        const next = { ...prev }
        delete next[oldId]
        return next
      })
    }
    setSelectedSubjects(prev => prev.map((s, i) => i === index ? newId : s))
  }

  const handleElectiveChange = (newId: string) => {
    if (electiveSubject) {
      setStpmGrades(prev => {
        const next = { ...prev }
        delete next[electiveSubject]
        return next
      })
    }
    setElectiveSubject(newId)
  }

  const handleStpmGradeChange = (subjectId: string, grade: string) => {
    setStpmGrades(prev => ({ ...prev, [subjectId]: grade }))
  }

  const handleSpmGradeChange = (subjectId: string, grade: string) => {
    setSpmGrades(prev => ({ ...prev, [subjectId]: grade }))
  }

  const [academicCgpa, setAcademicCgpa] = useState(0)
  const [overallCgpa, setOverallCgpa] = useState(0)

  const koko = parseFloat(kokoScore) || 0

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
      try {
        const result = await calculateCgpa(gradesWithValues, koko)
        setAcademicCgpa(result.academic_cgpa)
        setOverallCgpa(result.cgpa)
      } catch {
        // Silently fail
      }
    }, 400)

    return () => clearTimeout(timer)
  }, [stpmGrades, koko])

  const gradedSubjects = Object.entries(stpmGrades).filter(([, v]) => v !== '')
  const isComplete = stpmGrades.PA !== '' && stpmGrades.PA !== undefined
    && gradedSubjects.length >= 3
    && muetBand !== null
    && stream !== null

  const handleContinue = () => {
    if (!isComplete) return
    const cleanGrades = Object.fromEntries(
      Object.entries(stpmGrades).filter(([, v]) => v !== '')
    )
    localStorage.setItem('halatuju_stpm_stream', stream!)
    localStorage.setItem('halatuju_stpm_grades', JSON.stringify(cleanGrades))
    localStorage.setItem('halatuju_stpm_cgpa', String(overallCgpa))
    localStorage.setItem('halatuju_muet_band', String(muetBand))
    localStorage.setItem('halatuju_koko_score', kokoScore)
    localStorage.setItem('halatuju_spm_prereq', JSON.stringify(spmGrades))
    localStorage.setItem('halatuju_exam_type', 'stpm')
    router.push('/onboarding/profile')
  }

  // All currently selected subject IDs (for filtering dropdowns)
  const allSelected = [...selectedSubjects, electiveSubject].filter(Boolean)

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
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

      <div className="container mx-auto px-6 py-8 max-w-3xl">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            {t('onboarding.stpmGradesTitle')}
          </h1>
          <p className="text-gray-600">
            {t('onboarding.stpmGradesSubtitle')}
          </p>
        </div>

        {/* Section 0: Stream Selection */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">1</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.stpmStream')}</h2>
          </div>
          <div className="flex gap-3">
            {(['science', 'arts'] as Stream[]).map(s => (
              <button
                key={s}
                onClick={() => handleStreamChange(s)}
                className={`flex-1 py-3 px-4 rounded-xl text-sm font-medium transition-all ${
                  stream === s
                    ? 'bg-primary-500 text-white shadow-md'
                    : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50'
                }`}
              >
                {s === 'science' ? t('onboarding.stpmScience') : t('onboarding.stpmArts')}
              </button>
            ))}
          </div>
        </div>

        {/* Section 1: STPM Subjects & Grades */}
        {stream && (
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">2</span>
              <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.stpmSubjects')}</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.stpmSubjectsHint')}</p>

            <div className="space-y-3">
              {/* PA — compulsory */}
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
                  className={`w-20 flex-shrink-0 px-2 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
                    stpmGrades.PA
                      ? 'bg-primary-50 border-primary-200 text-primary-700'
                      : 'bg-gray-50 border-gray-300 text-gray-500'
                  }`}
                >
                  <option value="">{t('onboarding.stpmGrade')}</option>
                  {STPM_GRADES.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>

              {/* 3 stream-specific subject slots */}
              {selectedSubjects.map((subjectId, index) => (
                <div key={`stream-${index}`} className="flex items-center gap-2 bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-3">
                  <select
                    value={subjectId}
                    onChange={(e) => handleSubjectChange(index, e.target.value)}
                    className="flex-1 min-w-0 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                  >
                    <option value="">{t('onboarding.stpmSelectSubject')}</option>
                    {streamSubjects
                      .filter(s => !allSelected.includes(s.id) || s.id === subjectId)
                      .map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                  {subjectId && (
                    <select
                      value={stpmGrades[subjectId] || ''}
                      onChange={(e) => handleStpmGradeChange(subjectId, e.target.value)}
                      className={`w-20 flex-shrink-0 px-2 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
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

              {/* Elective slot — click to add */}
              {showElective ? (
                <div className="flex items-center gap-2 bg-white rounded-xl border border-dashed border-gray-300 hover:shadow-md transition-shadow p-3">
                  <select
                    value={electiveSubject}
                    onChange={(e) => handleElectiveChange(e.target.value)}
                    className="flex-1 min-w-0 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
                  >
                    <option value="">{t('onboarding.stpmElective')}</option>
                    {allOptionalSubjects
                      .filter(s => !allSelected.includes(s.id) || s.id === electiveSubject)
                      .map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                  {electiveSubject && (
                    <select
                      value={stpmGrades[electiveSubject] || ''}
                      onChange={(e) => handleStpmGradeChange(electiveSubject, e.target.value)}
                      className={`w-20 flex-shrink-0 px-2 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
                        stpmGrades[electiveSubject]
                          ? 'bg-primary-50 border-primary-200 text-primary-700'
                          : 'bg-gray-50 border-gray-300 text-gray-500'
                      }`}
                    >
                      <option value="">{t('onboarding.stpmGrade')}</option>
                      {STPM_GRADES.map(g => <option key={g} value={g}>{g}</option>)}
                    </select>
                  )}
                  <button
                    onClick={() => { handleElectiveChange(''); setShowElective(false) }}
                    className="text-gray-400 hover:text-red-500 p-1 flex-shrink-0"
                    aria-label="Remove"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowElective(true)}
                  className="w-full py-3 rounded-xl border-2 border-dashed border-gray-300 text-gray-500 hover:border-primary-400 hover:text-primary-600 hover:shadow-sm transition-all text-sm font-medium"
                >
                  + {t('onboarding.addElective')}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Section 2: MUET + Co-curriculum + CGPA */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">3</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.muetBand')}</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.muetHint')}</p>

          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            {/* MUET band pills */}
            <div className="mb-5">
              <label className="text-sm font-medium text-gray-700 mb-2 block">MUET</label>
              <div className="flex gap-2 flex-wrap">
                {MUET_BANDS.map(band => (
                  <button
                    key={band}
                    onClick={() => setMuetBand(band)}
                    className={`w-10 h-10 rounded-lg text-sm font-medium transition-all ${
                      muetBand === band
                        ? 'bg-primary-500 text-white shadow-md'
                        : 'bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100'
                    }`}
                  >
                    {band}
                  </button>
                ))}
              </div>
            </div>

            {/* Co-curriculum score */}
            <div className="mb-5">
              <label className="text-sm font-medium text-gray-700 mb-2 block">
                {t('onboarding.kokoScore')}
              </label>
              <input
                type="number"
                min="0"
                max="10"
                step="0.01"
                value={kokoScore}
                onChange={(e) => setKokoScore(e.target.value)}
                placeholder="0.00 – 10.00"
                className="w-32 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none"
              />
              <p className="text-xs text-gray-400 mt-1">{t('onboarding.kokoHint')}</p>
            </div>

            {/* CGPA display */}
            {academicCgpa > 0 && (
              <div className="border-t pt-4 flex items-center justify-between">
                <div>
                  <div className="text-xs text-gray-500">{t('onboarding.cgpaLabel')}</div>
                  <div className="text-xs text-gray-400">{t('onboarding.cgpaFormula')}</div>
                </div>
                <div className="text-right">
                  <div className="flex items-baseline gap-1 justify-end">
                    <span className="text-3xl font-bold text-gray-900">{overallCgpa.toFixed(2)}</span>
                    <span className="text-sm text-gray-400">/ 4.00</span>
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{t('onboarding.cgpaAutoCalc')}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Section 3: SPM Prerequisites */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">4</span>
            <h2 className="text-lg font-semibold text-gray-900">{t('onboarding.spmPrerequisites')}</h2>
          </div>
          <p className="text-sm text-gray-500 mb-4 ml-8">{t('onboarding.spmPrereqHint')}</p>

          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            {/* Compulsory */}
            <div className="mb-4">
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{t('onboarding.spmCompulsory')}</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SPM_PREREQ_COMPULSORY.map(subject => (
                  <div key={subject.id} className="flex items-center gap-3">
                    <span className="text-sm font-medium text-gray-700 flex-1">{subject.name}</span>
                    <select
                      value={spmGrades[subject.id] || ''}
                      onChange={(e) => handleSpmGradeChange(subject.id, e.target.value)}
                      className={`w-20 flex-shrink-0 px-2 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
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

            {/* Optional */}
            <div>
              <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{t('onboarding.spmOptional')}</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SPM_PREREQ_OPTIONAL.map(subject => (
                  <div key={subject.id} className="flex items-center gap-3">
                    <span className="text-sm font-medium text-gray-700 flex-1">{subject.name}</span>
                    <select
                      value={spmGrades[subject.id] || ''}
                      onChange={(e) => handleSpmGradeChange(subject.id, e.target.value)}
                      className={`w-20 flex-shrink-0 px-2 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
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

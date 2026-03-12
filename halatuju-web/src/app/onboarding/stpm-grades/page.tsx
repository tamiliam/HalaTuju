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

  const [stpmGrades, setStpmGrades] = useState<Record<string, string>>({ PA: '' })
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>(['', '', '', ''])
  const [muetBand, setMuetBand] = useState<number | null>(null)
  const [spmGrades, setSpmGrades] = useState<Record<string, string>>({})

  useEffect(() => {
    const savedStpm = localStorage.getItem('halatuju_stpm_grades')
    if (savedStpm) {
      const parsed = JSON.parse(savedStpm)
      setStpmGrades(prev => ({ ...prev, ...parsed }))
      const subjects = Object.keys(parsed).filter(k => k !== 'PA')
      const padded = [...subjects, '', '', '', ''].slice(0, 4)
      setSelectedSubjects(padded)
    }
    const savedMuet = localStorage.getItem('halatuju_muet_band')
    if (savedMuet) setMuetBand(parseInt(savedMuet))
    const savedSpm = localStorage.getItem('halatuju_spm_prereq')
    if (savedSpm) setSpmGrades(JSON.parse(savedSpm))
  }, [])

  const optionalSubjects = useMemo(() => {
    return STPM_SUBJECTS.filter(s => s.id !== 'PA')
  }, [])

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

  const handleStpmGradeChange = (subjectId: string, grade: string) => {
    setStpmGrades(prev => ({ ...prev, [subjectId]: grade }))
  }

  const handleSpmGradeChange = (subjectId: string, grade: string) => {
    setSpmGrades(prev => ({ ...prev, [subjectId]: grade }))
  }

  const cgpa = useMemo(() => {
    const gradesWithValues = Object.fromEntries(
      Object.entries(stpmGrades).filter(([_, v]) => v !== '')
    )
    return calculateStpmCgpa(gradesWithValues)
  }, [stpmGrades])

  const gradedSubjects = Object.entries(stpmGrades).filter(([_, v]) => v !== '')
  const isComplete = stpmGrades.PA !== '' && stpmGrades.PA !== undefined
    && gradedSubjects.length >= 3
    && muetBand !== null

  const handleContinue = () => {
    if (!isComplete) return
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

        {/* Section 1: STPM Subjects & Grades */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <span className="w-6 h-6 bg-primary-500 text-white rounded text-xs flex items-center justify-center font-bold">1</span>
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

            {/* Optional subjects — 4 slots */}
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

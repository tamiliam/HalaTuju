'use client'

/**
 * THE SPM RESULTS BLOCK — one component, two results pages (third results route S2b, 2026-10-26).
 *
 * Lifted VERBATIM out of `onboarding/stpm-grades/page.tsx` (its "Section 4", TD-069's rebuild
 * included) so the STPM page and the Matriculation / Asasi / Diploma page (`onboarding/higher-grades`)
 * ask for SPM results the same way, store them under the same keys (`KEY_SPM_PREREQ`,
 * `KEY_SPM_STREAM`, `KEY_SPM_ALIRAN`, `KEY_SPM_ELEKTIF` → the profile's `spm_prereq_grades`,
 * `spm_stream`, `spm_elective_subjects`) and judge it complete by one rule.
 *
 * ⚠ REQUIRED ON BOTH PAGES (owner ruling D4, 2026-10-25): `spmBlockComplete` — the four compulsory
 * SPM subjects graded, the same bar the SPM results page sets (`enterAllCore`). Until it holds,
 * each page keeps Continue disabled. That is the ONLY behaviour the STPM page gained here; what it
 * renders is unchanged (the `step` it passes is the "4" it always showed).
 *
 * The state lives in `useSpmResultsBlock`, so a page keeps owning its Continue: it reads `complete`
 * and calls `save()` when it stores its own results.
 */
import { useEffect, useMemo, useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  SPM_PREREQ_COMPULSORY,
  SPM_PREREQ_STREAM_POOLS,
  SPM_ALL_ELECTIVE_SUBJECTS,
  SPM_GRADE_OPTIONS,
  MAX_SPM_ELECTIVES,
  getSubjectName,
} from '@/lib/subjects'
import { KEY_GRADES, KEY_SPM_PREREQ, KEY_SPM_STREAM, KEY_SPM_ALIRAN, KEY_SPM_ELEKTIF } from '@/lib/storage'

/** D4: the block is complete when the four compulsory SPM subjects carry a grade. */
export function spmBlockComplete(grades: Record<string, string>): boolean {
  return SPM_PREREQ_COMPULSORY.every((s) => !!grades[s.id])
}

export function useSpmResultsBlock() {
  const { locale } = useT()
  const [spmGrades, setSpmGrades] = useState<Record<string, string>>({})
  const [spmStream, setSpmStream] = useState<string>('science')
  const [spmAliranSubjects, setSpmAliranSubjects] = useState<string[]>(['', '', '', ''])
  const [spmElektifSlots, setSpmElektifSlots] = useState<string[]>([])

  useEffect(() => {
    const savedSpm = localStorage.getItem(KEY_SPM_PREREQ)
    const prereq: Record<string, string> = savedSpm ? JSON.parse(savedSpm) : {}
    // S2b review (D4 prefill): a compulsory grade the block lacks is taken from the SPM `grades`
    // already on file (live, 17 STPM profiles hold them there, not here) — the server's
    // `spm_grades_for` reads both — so making the block required never means retyping them.
    // Only the four compulsory subjects, and only to fill a gap: what the block holds wins.
    let spmOnFile: Record<string, string> = {}
    try { spmOnFile = JSON.parse(localStorage.getItem(KEY_GRADES) || '{}') || {} } catch { /* absent */ }
    const filled = { ...prereq }
    for (const { id } of SPM_PREREQ_COMPULSORY) if (!filled[id] && spmOnFile[id]) filled[id] = spmOnFile[id]
    if (savedSpm || Object.keys(filled).length > 0) setSpmGrades(filled)
    const savedSpmStream = localStorage.getItem(KEY_SPM_STREAM)
    if (savedSpmStream) setSpmStream(savedSpmStream)
    const savedElektif = localStorage.getItem(KEY_SPM_ELEKTIF)
    const elektif: string[] = savedElektif ? JSON.parse(savedElektif) : []
    if (savedElektif) setSpmElektifSlots(elektif)
    // TD-069: the server keeps the grades and the elective picks, not the aliran picks — after a
    // login (no saved key) they are exactly what is left: grades minus the core minus electives.
    const savedAliran = localStorage.getItem(KEY_SPM_ALIRAN)
    const core = SPM_PREREQ_COMPULSORY.map(s => s.id)
    const aliran: string[] = savedAliran
      ? JSON.parse(savedAliran)
      : Object.keys(prereq).filter(k => !core.includes(k) && !elektif.includes(k))
    // Pad to 4 slots
    if (aliran.length > 0) setSpmAliranSubjects([...aliran, '', '', '', ''].slice(0, 4))
  }, [])

  const handleSpmGradeChange = (subjectId: string, grade: string) => {
    setSpmGrades(prev => ({ ...prev, [subjectId]: grade }))
  }

  const handleSpmStreamChange = (newStream: string) => {
    // Clear old aliran subject grades
    spmAliranSubjects.filter(Boolean).forEach(id => {
      setSpmGrades(prev => { const next = { ...prev }; delete next[id]; return next })
    })
    setSpmStream(newStream)
    setSpmAliranSubjects(['', '', '', ''])
    setSpmElektifSlots([])
  }

  const handleSpmAliranChange = (index: number, newId: string) => {
    const oldId = spmAliranSubjects[index]
    if (oldId) {
      setSpmGrades(prev => { const next = { ...prev }; delete next[oldId]; return next })
    }
    setSpmAliranSubjects(prev => prev.map((s, i) => i === index ? newId : s))
  }

  const addSpmElektifSlot = () => {
    if (spmElektifSlots.length < MAX_SPM_ELECTIVES) setSpmElektifSlots(prev => [...prev, ''])
  }

  const removeSpmElektifSlot = (index: number) => {
    const id = spmElektifSlots[index]
    if (id) {
      setSpmGrades(prev => { const next = { ...prev }; delete next[id]; return next })
    }
    setSpmElektifSlots(prev => prev.filter((_, i) => i !== index))
  }

  const updateSpmElektifSubject = (index: number, newId: string) => {
    const oldId = spmElektifSlots[index]
    if (oldId) {
      setSpmGrades(prev => { const next = { ...prev }; delete next[oldId]; return next })
    }
    setSpmElektifSlots(prev => prev.map((s, i) => i === index ? newId : s))
  }

  // Computed pools for SPM prereq stream/elective dropdowns.
  // Stream options sorted alphabetically by display name (locale-aware).
  const spmStreamPool = useMemo(() => {
    return [...(SPM_PREREQ_STREAM_POOLS[spmStream] || [])].sort((a, b) =>
      getSubjectName(a.id, locale).localeCompare(getSubjectName(b.id, locale))
    )
  }, [spmStream, locale])

  const spmAllSelectedPrereq = useMemo(() => {
    const coreIds = SPM_PREREQ_COMPULSORY.map(s => s.id)
    return [...coreIds, ...spmAliranSubjects.filter(Boolean), ...spmElektifSlots.filter(Boolean)]
  }, [spmAliranSubjects, spmElektifSlots])

  // Elective pool = every non-core subject minus the core and the aliran picks. The OTHER elective
  // slots are excluded per row below. (Excluding every elective pick here also removed each row's
  // own pick from its own dropdown, so a chosen elective showed as unselected — TD-069.)
  const spmElektifPool = useMemo(() => {
    const coreIds = SPM_PREREQ_COMPULSORY.map(s => s.id)
    const taken = [...coreIds, ...spmAliranSubjects.filter(Boolean)]
    return SPM_ALL_ELECTIVE_SUBJECTS.filter(s => !taken.includes(s.id))
  }, [spmAliranSubjects])

  /** Store the block under the shared keys (the profile sync reads them). */
  const save = () => {
    localStorage.setItem(KEY_SPM_PREREQ, JSON.stringify(spmGrades))
    localStorage.setItem(KEY_SPM_STREAM, spmStream)
    localStorage.setItem(KEY_SPM_ALIRAN, JSON.stringify(spmAliranSubjects.filter(Boolean)))
    localStorage.setItem(KEY_SPM_ELEKTIF, JSON.stringify(spmElektifSlots.filter(Boolean)))
  }

  return {
    spmGrades, spmStream, spmAliranSubjects, spmElektifSlots, spmStreamPool, spmAllSelectedPrereq,
    spmElektifPool, handleSpmGradeChange, handleSpmStreamChange, handleSpmAliranChange,
    addSpmElektifSlot, removeSpmElektifSlot, updateSpmElektifSubject, save,
    complete: spmBlockComplete(spmGrades),
  }
}

export type SpmResultsBlockState = ReturnType<typeof useSpmResultsBlock>

/** The block itself. `step` is the section number the page shows beside its heading. */
export default function SpmResultsBlock({ block, step }: { block: SpmResultsBlockState; step: number }) {
  const { t, locale } = useT()
  const {
    spmGrades, spmStream, spmAliranSubjects, spmElektifSlots, spmStreamPool, spmAllSelectedPrereq,
    spmElektifPool, handleSpmGradeChange, handleSpmStreamChange, handleSpmAliranChange,
    addSpmElektifSlot, removeSpmElektifSlot, updateSpmElektifSubject,
  } = block

  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-6 h-6 bg-brand-fill text-brand-fill-ink rounded text-xs flex items-center justify-center font-bold">{step}</span>
        <h2 className="text-lg font-semibold text-ground-900">{t('onboarding.spmPrerequisites')}</h2>
      </div>
      <p className="text-sm text-ground-500 mb-4 ml-8">{t('onboarding.spmPrereqHint')}</p>

      <div className="bg-ground-0 rounded-2xl border border-ground-200 shadow-sm p-5">
        {/* A) SPM Stream pills */}
        <div className="mb-4">
          <div className="text-xs font-semibold text-ground-500 uppercase tracking-wide mb-2">{t('onboarding.spmStream')}</div>
          <div className="flex gap-2">
            {([
              { id: 'science', key: 'spmSains' },
              { id: 'arts', key: 'spmSastera' },
              { id: 'technical', key: 'spmTeknikal' },
            ] as const).map(s => (
              <button
                key={s.id}
                onClick={() => handleSpmStreamChange(s.id)}
                className={`flex-1 py-2 px-2 rounded-lg text-xs font-medium transition-all ${
                  spmStream === s.id
                    ? 'bg-brand-fill text-brand-fill-ink shadow-sm'
                    : 'bg-ground-0 text-ground-600 border border-ground-200 hover:bg-ground-50'
                }`}
              >
                {t(`onboarding.${s.key}`)}
              </button>
            ))}
          </div>
        </div>

        {/* B) Core subjects — 2-col grid */}
        <div className="mb-4">
          <div className="text-xs font-semibold text-ground-500 uppercase tracking-wide mb-2">{t('onboarding.spmCompulsory')}</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {SPM_PREREQ_COMPULSORY.map(subject => (
              <div key={subject.id} className="flex items-center gap-3">
                <span className="text-sm font-medium text-ground-700 flex-1">{subject.name}</span>
                <select
                  value={spmGrades[subject.id] || ''}
                  onChange={(e) => handleSpmGradeChange(subject.id, e.target.value)}
                  className={`w-20 flex-shrink-0 px-2 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
                    spmGrades[subject.id]
                      ? 'bg-primary-50 border-primary-200 text-primary-700'
                      : 'bg-ground-50 border-ground-300 text-ground-500'
                  }`}
                >
                  <option value="">{t('onboarding.grade')}</option>
                  {SPM_GRADE_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>

        {/* C) Stream subjects — 4 dropdown rows */}
        <div className="mb-4">
          <div className="text-xs font-semibold text-ground-500 uppercase tracking-wide mb-2">
            {t('onboarding.spmStreamHint')}
          </div>
          <div className="space-y-2">
            {spmAliranSubjects.map((subjectId, index) => (
              <div key={`aliran-${index}`} className="flex items-center gap-2">
                <select
                  value={subjectId}
                  onChange={(e) => handleSpmAliranChange(index, e.target.value)}
                  className="flex-1 min-w-0 px-3 py-2 border border-ground-300 rounded-lg text-sm bg-ground-0 focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
                >
                  <option value="">{t('onboarding.selectSubject')}</option>
                  {spmStreamPool
                    .filter(s => !spmAllSelectedPrereq.includes(s.id) || s.id === subjectId)
                    .map(s => (
                      <option key={s.id} value={s.id}>{getSubjectName(s.id, locale)}</option>
                    ))}
                </select>
                {subjectId && (
                  <select
                    value={spmGrades[subjectId] || ''}
                    onChange={(e) => handleSpmGradeChange(subjectId, e.target.value)}
                    className={`w-20 flex-shrink-0 px-2 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
                      spmGrades[subjectId]
                        ? 'bg-primary-50 border-primary-200 text-primary-700'
                        : 'bg-ground-50 border-ground-300 text-ground-500'
                    }`}
                  >
                    <option value="">{t('onboarding.grade')}</option>
                    {SPM_GRADE_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                )}
                <button
                  onClick={() => handleSpmAliranChange(index, '')}
                  className="text-ground-400 hover:text-critical-600 p-1 flex-shrink-0"
                  aria-label={t('common.remove')}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* D) Electives — 0 to MAX_SPM_ELECTIVES slots + add button */}
        <div>
          <div className="text-xs font-semibold text-ground-500 uppercase tracking-wide mb-2">{t('onboarding.spmOptional')}</div>
          <div className="space-y-2">
            {spmElektifSlots.map((subjectId, index) => (
              <div key={`elektif-${index}`} className="flex items-center gap-2">
                <select
                  value={subjectId}
                  onChange={(e) => updateSpmElektifSubject(index, e.target.value)}
                  className="flex-1 min-w-0 px-3 py-2 border border-ground-300 rounded-lg text-sm bg-ground-0 focus:border-brand-shape focus:ring-1 focus:ring-brand-shape outline-none"
                >
                  <option value="">{t('onboarding.selectSubject')}</option>
                  {spmElektifPool
                    .filter(s => !spmElektifSlots.includes(s.id) || s.id === subjectId)
                    .map(s => (
                      <option key={s.id} value={s.id}>{getSubjectName(s.id, locale)}</option>
                    ))}
                </select>
                {subjectId && (
                  <select
                    value={spmGrades[subjectId] || ''}
                    onChange={(e) => handleSpmGradeChange(subjectId, e.target.value)}
                    className={`w-20 flex-shrink-0 px-2 py-2 rounded-lg text-sm font-medium border outline-none transition-all ${
                      spmGrades[subjectId]
                        ? 'bg-primary-50 border-primary-200 text-primary-700'
                        : 'bg-ground-50 border-ground-300 text-ground-500'
                    }`}
                  >
                    <option value="">{t('onboarding.grade')}</option>
                    {SPM_GRADE_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}
                  </select>
                )}
                <button
                  onClick={() => removeSpmElektifSlot(index)}
                  className="text-ground-400 hover:text-critical-600 p-1 flex-shrink-0"
                  aria-label={t('common.remove')}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
            {spmElektifSlots.length < MAX_SPM_ELECTIVES && (
              <button
                onClick={addSpmElektifSlot}
                className="w-full py-2.5 rounded-lg border-2 border-dashed border-ground-300 text-ground-500 hover:border-primary-400 hover:text-primary-600 text-sm transition-all"
              >
                {t('onboarding.spmAddElective')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

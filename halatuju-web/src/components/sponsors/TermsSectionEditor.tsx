'use client'

import { useState } from 'react'
import { LangTabs, btnGhost, inputCls, type CLocale } from '@/components/contracts/shared'
import { Toggle } from '@/components/sources/shared'
import {
  blankSection, moveSection, quizComplete, renumber, setQuizFlag,
} from '@/lib/sponsorTerms'
import type { SponsorTermsSection } from '@/lib/admin-api'

/**
 * The section list, with each section's quiz checkpoint edited inline beneath it.
 *
 * Inline rather than on its own tab, deliberately: a checkpoint only makes sense next to the words
 * it tests, and the contract module's separate Quiz tab makes you hold the clause in your head
 * while writing the question about it.
 *
 * Sections are FLAT — no indent, no outline numbering. A thirteen-section document does not need
 * a tree, and dropping it removes the whole hierarchy apparatus the contract editor carries.
 */
export default function TermsSectionEditor({
  sections, onChange, disabled, onGenerate, generating, t,
}: {
  sections: SponsorTermsSection[]
  onChange: (next: SponsorTermsSection[]) => void
  disabled: boolean
  onGenerate: (order: number) => void
  generating: number | null
  t: (k: string, p?: Record<string, string | number>) => string
}) {
  const [lang, setLang] = useState<CLocale>('en')
  const [open, setOpen] = useState<number | null>(null)

  const patch = (i: number, changes: Partial<SponsorTermsSection>) =>
    onChange(sections.map((s, idx) => (idx === i ? { ...s, ...changes } : s)))

  const patchQuiz = (i: number, changes: Record<string, unknown>) => {
    const key = `quiz_${lang}` as 'quiz_en' | 'quiz_ms' | 'quiz_ta'
    patch(i, { [key]: { ...sections[i][key], ...changes } } as Partial<SponsorTermsSection>)
  }

  const setOption = (i: number, oi: number, value: string) => {
    const key = `quiz_${lang}` as 'quiz_en' | 'quiz_ms' | 'quiz_ta'
    const opts = [...(sections[i][key].options || ['', '', ''])]
    opts[oi] = value
    patchQuiz(i, { options: opts })
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-gray-500">{t('admin.sponsors.terms.sectionsHint')}</p>
        <LangTabs value={lang} onChange={setLang} />
      </div>

      {sections.length === 0 && (
        <p className="text-sm text-gray-500 py-6 text-center">{t('admin.sponsors.terms.noSections')}</p>
      )}

      {sections.map((s, i) => {
        const quiz = s[`quiz_${lang}` as 'quiz_en'] || {}
        const expanded = open === s.order
        return (
          <div key={s.order} className="border border-gray-200 rounded-xl bg-white">
            <div className="flex items-start gap-3 p-3">
              <span className="text-xs font-mono text-gray-400 mt-2.5 w-6 text-right">{s.order}</span>
              <div className="flex-1 flex flex-col gap-2">
                <input
                  className={inputCls} disabled={disabled}
                  placeholder={t('admin.sponsors.terms.headingPh')}
                  value={s[`heading_${lang}` as 'heading_en']}
                  onChange={(e) => patch(i, { [`heading_${lang}`]: e.target.value } as Partial<SponsorTermsSection>)}
                />
                <textarea
                  className={`${inputCls} font-mono text-xs`} rows={4} disabled={disabled}
                  placeholder={t('admin.sponsors.terms.bodyPh')}
                  value={s[`body_${lang}` as 'body_en']}
                  onChange={(e) => patch(i, { [`body_${lang}`]: e.target.value } as Partial<SponsorTermsSection>)}
                />
                <div className="flex flex-wrap items-center gap-3 text-xs">
                  <span className="flex items-center gap-2">
                    <Toggle on={s.is_quiz_candidate} disabled={disabled}
                      label={t('admin.sponsors.terms.quizToggle')}
                      onClick={() => onChange(sections.map((x, idx) =>
                        (idx === i ? setQuizFlag(x, !x.is_quiz_candidate) : x)))} />
                    <span className="text-gray-600">{t('admin.sponsors.terms.quizToggle')}</span>
                  </span>
                  {s.is_quiz_candidate && (
                    <>
                      <button type="button" className="text-blue-600 hover:underline"
                        onClick={() => setOpen(expanded ? null : s.order)}>
                        {expanded ? t('admin.sponsors.terms.hideQuiz') : t('admin.sponsors.terms.editQuiz')}
                      </button>
                      <span className={quizComplete(s.quiz_en)
                        ? 'text-green-700' : 'text-amber-700 font-medium'}>
                        {quizComplete(s.quiz_en)
                          ? t('admin.sponsors.terms.quizReady')
                          : t('admin.sponsors.terms.quizIncomplete')}
                      </span>
                    </>
                  )}
                  <span className="ml-auto flex gap-1">
                    <button type="button" className={btnGhost} disabled={disabled || i === 0}
                      onClick={() => onChange(moveSection(sections, i, -1))}
                      aria-label={t('admin.sponsors.terms.moveUp')}>↑</button>
                    <button type="button" className={btnGhost}
                      disabled={disabled || i === sections.length - 1}
                      onClick={() => onChange(moveSection(sections, i, 1))}
                      aria-label={t('admin.sponsors.terms.moveDown')}>↓</button>
                    <button type="button" className={btnGhost} disabled={disabled}
                      onClick={() => onChange(renumber(sections.filter((_x, idx) => idx !== i)))}
                      aria-label={t('admin.sponsors.terms.removeSection')}>×</button>
                  </span>
                </div>
              </div>
            </div>

            {s.is_quiz_candidate && expanded && (
              <div className="border-t border-gray-100 bg-gray-50/60 p-3 pl-12 flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                    {t('admin.sponsors.terms.checkpoint')}
                  </span>
                  <button type="button" className={btnGhost} disabled={disabled || generating !== null}
                    onClick={() => onGenerate(s.order)}>
                    {generating === s.order
                      ? t('admin.sponsors.terms.generating')
                      : t('admin.sponsors.terms.generate')}
                  </button>
                </div>
                <input className={inputCls} disabled={disabled}
                  placeholder={t('admin.sponsors.terms.tagPh')} value={quiz.tag || ''}
                  onChange={(e) => patchQuiz(i, { tag: e.target.value })} />
                <input className={inputCls} disabled={disabled}
                  placeholder={t('admin.sponsors.terms.plainPh')} value={quiz.plain || ''}
                  onChange={(e) => patchQuiz(i, { plain: e.target.value })} />
                <input className={inputCls} disabled={disabled}
                  placeholder={t('admin.sponsors.terms.questionPh')} value={quiz.question || ''}
                  onChange={(e) => patchQuiz(i, { question: e.target.value })} />
                {[0, 1, 2].map((oi) => (
                  <label key={oi} className="flex items-center gap-2">
                    <input type="radio" name={`correct-${s.order}-${lang}`} disabled={disabled}
                      checked={quiz.correct === oi}
                      onChange={() => patchQuiz(i, { correct: oi })}
                      aria-label={t('admin.sponsors.terms.markCorrect', { n: oi + 1 })} />
                    <input className={inputCls} disabled={disabled}
                      placeholder={t('admin.sponsors.terms.optionPh', { n: oi + 1 })}
                      value={(quiz.options || [])[oi] || ''}
                      onChange={(e) => setOption(i, oi, e.target.value)} />
                  </label>
                ))}
                <textarea className={inputCls} rows={2} disabled={disabled}
                  placeholder={t('admin.sponsors.terms.whyPh')} value={quiz.why || ''}
                  onChange={(e) => patchQuiz(i, { why: e.target.value })} />
                <p className="text-[11px] text-gray-500">{t('admin.sponsors.terms.quizHint')}</p>
                {s.quiz_generated_model && (
                  <p className="text-[11px] text-gray-400">
                    {t('admin.sponsors.terms.draftedBy', { model: s.quiz_generated_model })}
                  </p>
                )}
              </div>
            )}
          </div>
        )
      })}

      <button type="button" className={btnGhost} disabled={disabled}
        onClick={() => onChange([...sections, blankSection(sections.length + 1)])}>
        {t('admin.sponsors.terms.addSection')}
      </button>
    </div>
  )
}

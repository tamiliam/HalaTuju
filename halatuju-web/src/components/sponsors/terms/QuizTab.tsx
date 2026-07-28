'use client'

import { useState } from 'react'
import { LangTabs, btnGhost, btnPrimary, inputCls, type CLocale } from '@/components/contracts/shared'
import type { SponsorTermsSection } from '@/lib/admin-api'

/**
 * Quiz — one card per section marked as a checkpoint on the Clauses tab.
 *
 * Cards are labelled by the section's NUMBER and heading, so you can see which words each question
 * is testing without switching tabs. A section that is not a checkpoint simply does not appear
 * here; turning one on is a Clauses decision.
 */
export default function QuizTab({ sections, onSections, disabled, onSave, onGenerate, generating, busy, dirty, t }: {
  sections: SponsorTermsSection[]
  onSections: (next: SponsorTermsSection[]) => void
  disabled: boolean
  onSave: () => void
  onGenerate: (order: number) => void
  generating: number | null
  busy: boolean
  dirty: boolean
  t: (k: string, p?: Record<string, string>) => string
}) {
  const [lang, setLang] = useState<CLocale>('en')
  const candidates = sections.filter((s) => s.is_quiz_candidate)

  const key = `quiz_${lang}` as 'quiz_en' | 'quiz_ms' | 'quiz_ta'

  const patchQuiz = (order: number, changes: Record<string, unknown>) =>
    onSections(sections.map((s) => (s.order === order
      ? { ...s, [key]: { ...s[key], ...changes } }
      : s)))

  const setOption = (order: number, oi: number, value: string) => {
    const section = sections.find((s) => s.order === order)
    const opts = [...(section?.[key].options || ['', '', ''])]
    opts[oi] = value
    patchQuiz(order, { options: opts })
  }

  if (candidates.length === 0) {
    return <p className="text-sm text-gray-500 py-8 text-center">{t('admin.sponsors.terms.quizNone')}</p>
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-gray-500">{t('admin.sponsors.terms.quizIntro')}</p>
        <LangTabs value={lang} onChange={setLang} />
      </div>

      {candidates.map((s) => {
        const quiz = s[key] || {}
        return (
          <div key={s.order} className="border border-gray-200 rounded-xl bg-white p-4 flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-gray-800">
                <span className="font-mono text-xs text-gray-400 mr-2">{s.order}</span>
                {s.heading_en || '—'}
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
              onChange={(e) => patchQuiz(s.order, { tag: e.target.value })} />
            <input className={inputCls} disabled={disabled}
              placeholder={t('admin.sponsors.terms.plainPh')} value={quiz.plain || ''}
              onChange={(e) => patchQuiz(s.order, { plain: e.target.value })} />
            <input className={inputCls} disabled={disabled}
              placeholder={t('admin.sponsors.terms.questionPh')} value={quiz.question || ''}
              onChange={(e) => patchQuiz(s.order, { question: e.target.value })} />

            {[0, 1, 2].map((oi) => (
              <label key={oi} className="flex items-center gap-2">
                <input type="radio" name={`correct-${s.order}-${lang}`} disabled={disabled}
                  checked={quiz.correct === oi}
                  onChange={() => patchQuiz(s.order, { correct: oi })}
                  aria-label={t('admin.sponsors.terms.markCorrect', { n: String(oi + 1) })} />
                <input className={inputCls} disabled={disabled}
                  placeholder={t('admin.sponsors.terms.optionPh', { n: String(oi + 1) })}
                  value={(quiz.options || [])[oi] || ''}
                  onChange={(e) => setOption(s.order, oi, e.target.value)} />
              </label>
            ))}

            <textarea className={inputCls} rows={2} disabled={disabled}
              placeholder={t('admin.sponsors.terms.whyPh')} value={quiz.why || ''}
              onChange={(e) => patchQuiz(s.order, { why: e.target.value })} />
            <p className="text-[11px] text-gray-500">{t('admin.sponsors.terms.quizHint')}</p>
            {s.quiz_generated_model && (
              <p className="text-[11px] text-gray-400">
                {t('admin.sponsors.terms.draftedBy', { model: s.quiz_generated_model })}
              </p>
            )}
          </div>
        )
      })}

      {!disabled && (
        <button type="button" className={`${btnPrimary} self-start`} disabled={busy || !dirty}
          onClick={onSave}>
          {busy ? t('admin.sources.saving') : t('admin.sources.save')}
        </button>
      )}
    </div>
  )
}

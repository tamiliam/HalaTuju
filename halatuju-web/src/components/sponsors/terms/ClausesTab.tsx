'use client'

import { useState } from 'react'
import { LangTabs, btnGhost, btnPrimary, inputCls, type CLocale } from '@/components/contracts/shared'
import { Toggle } from '@/components/sources/shared'
import { blankSection, moveSection, quizComplete, renumber, setQuizFlag } from '@/lib/sponsorTerms'
import CheckpointEditor from './CheckpointEditor'
import type { SponsorQuizPayload, SponsorTermsDetail, SponsorTermsSection } from '@/lib/admin-api'

/**
 * Clauses — the title, the opening, and the flat section list.
 *
 * The title and intro live HERE rather than in a Config tab, because the editor has no Config tab
 * (owner: Clauses / Quiz / Preview / Deploy) and they are the document's own opening lines.
 *
 * Sections are FLAT. There is no indent, no outline numbering and no sub-clause: the number shown
 * is the order itself.
 *
 * The checkpoint is written HERE, directly under the clause it tests (owner, 2026-07-28), and in
 * the shape a sponsor will read it — see `CheckpointEditor`. The Quiz tab is where you then TAKE
 * the quiz rather than fill in a second form.
 */
export default function ClausesTab({
  terms, sections, onTerms, onSections, disabled, onSave, onGenerate, generating, busy, dirty, t,
}: {
  terms: SponsorTermsDetail
  sections: SponsorTermsSection[]
  onTerms: (next: SponsorTermsDetail) => void
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
  const [open, setOpen] = useState<number | null>(null)

  const patch = (i: number, changes: Partial<SponsorTermsSection>) =>
    onSections(sections.map((s, idx) => (idx === i ? { ...s, ...changes } : s)))

  const quizKey = `quiz_${lang}` as 'quiz_en' | 'quiz_ms' | 'quiz_ta'

  const patchQuiz = (i: number, changes: Partial<SponsorQuizPayload>) =>
    patch(i, { [quizKey]: { ...sections[i][quizKey], ...changes } } as Partial<SponsorTermsSection>)

  const setOption = (i: number, oi: number, value: string) => {
    const opts = [...(sections[i][quizKey].options || ['', '', ''])]
    opts[oi] = value
    patchQuiz(i, { options: opts })
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-gray-500">{t('admin.sponsors.terms.clausesIntro')}</p>
        <LangTabs value={lang} onChange={setLang} />
      </div>

      <input className={inputCls} disabled={disabled}
        placeholder={t('admin.sponsors.terms.titlePh')}
        value={terms[`title_${lang}` as 'title_en']}
        onChange={(e) => onTerms({ ...terms, [`title_${lang}`]: e.target.value })} />
      <textarea className={inputCls} rows={2} disabled={disabled}
        placeholder={t('admin.sponsors.terms.introPh')}
        value={terms[`intro_${lang}` as 'intro_en']}
        onChange={(e) => onTerms({ ...terms, [`intro_${lang}`]: e.target.value })} />

      <p className="text-xs text-gray-500">{t('admin.sponsors.terms.sectionsHint')}</p>

      {sections.length === 0 && (
        <p className="text-sm text-gray-500 py-6 text-center">{t('admin.sponsors.terms.noSections')}</p>
      )}

      {sections.map((s, i) => (
        <div key={s.order} className="border border-gray-200 rounded-xl bg-white overflow-hidden">
        <div className="p-3 flex items-start gap-3">
          <span className="text-xs font-mono text-gray-400 mt-2.5 w-6 text-right">{s.order}</span>
          <div className="flex-1 flex flex-col gap-2">
            <input className={inputCls} disabled={disabled}
              placeholder={t('admin.sponsors.terms.headingPh')}
              value={s[`heading_${lang}` as 'heading_en']}
              onChange={(e) => patch(i, { [`heading_${lang}`]: e.target.value } as Partial<SponsorTermsSection>)} />
            <textarea className={`${inputCls} font-mono text-xs`} rows={4} disabled={disabled}
              placeholder={t('admin.sponsors.terms.bodyPh')}
              value={s[`body_${lang}` as 'body_en']}
              onChange={(e) => patch(i, { [`body_${lang}`]: e.target.value } as Partial<SponsorTermsSection>)} />
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <span className="flex items-center gap-2">
                <Toggle on={s.is_quiz_candidate} disabled={disabled}
                  label={t('admin.sponsors.terms.quizToggle')}
                  onClick={() => onSections(sections.map((x, idx) =>
                    (idx === i ? setQuizFlag(x, !x.is_quiz_candidate) : x)))} />
                <span className="text-gray-600">{t('admin.sponsors.terms.quizToggle')}</span>
              </span>
              {s.is_quiz_candidate && (
                <>
                  <button type="button" className="text-blue-600 hover:underline"
                    onClick={() => setOpen(open === s.order ? null : s.order)}>
                    {open === s.order
                      ? t('admin.sponsors.terms.hideQuiz')
                      : t('admin.sponsors.terms.editQuiz')}
                  </button>
                  <span className={quizComplete(s.quiz_en) ? 'text-green-700' : 'text-amber-700 font-medium'}>
                    {quizComplete(s.quiz_en)
                      ? t('admin.sponsors.terms.quizReady')
                      : t('admin.sponsors.terms.quizIncomplete')}
                  </span>
                </>
              )}
              <span className="ml-auto flex gap-1">
                <button type="button" className={btnGhost} disabled={disabled || i === 0}
                  onClick={() => onSections(moveSection(sections, i, -1))}
                  aria-label={t('admin.sponsors.terms.moveUp')}>↑</button>
                <button type="button" className={btnGhost} disabled={disabled || i === sections.length - 1}
                  onClick={() => onSections(moveSection(sections, i, 1))}
                  aria-label={t('admin.sponsors.terms.moveDown')}>↓</button>
                <button type="button" className={btnGhost} disabled={disabled}
                  onClick={() => onSections(renumber(sections.filter((_x, idx) => idx !== i)))}
                  aria-label={t('admin.sponsors.terms.removeSection')}>×</button>
              </span>
            </div>
          </div>
        </div>
        {s.is_quiz_candidate && open === s.order && (
          <CheckpointEditor
            section={s} lang={lang} disabled={disabled}
            generating={generating === s.order}
            onGenerate={() => onGenerate(s.order)}
            onPatch={(changes) => patchQuiz(i, changes)}
            onSetOption={(oi, value) => setOption(i, oi, value)}
            t={t} />
        )}
        </div>
      ))}

      {!disabled && (
        <div className="flex gap-2">
          <button type="button" className={btnGhost}
            onClick={() => onSections([...sections, blankSection(sections.length + 1)])}>
            {t('admin.sponsors.terms.addSection')}
          </button>
          <button type="button" className={btnPrimary} disabled={busy || !dirty} onClick={onSave}>
            {busy ? t('admin.sources.saving') : t('admin.sources.save')}
          </button>
        </div>
      )}
    </div>
  )
}

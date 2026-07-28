'use client'

import { btnGhost } from '@/components/contracts/shared'
import type { SponsorQuizPayload, SponsorTermsSection } from '@/lib/admin-api'

/**
 * The checkpoint, edited in the shape a sponsor will read it.
 *
 * The problem this solves (owner, 2026-07-28): six identical input boxes told you nothing about
 * which field was the label, which was the question, and which was the feedback shown after
 * answering. Every field here is typed in the STYLE it will be rendered in — the tag small and
 * uppercase, the question large and bold, the options as answer rows, the explanation in the
 * green feedback panel — so the editor doubles as a preview of one card.
 *
 * Inputs are borderless until focused. That is the whole trick: at rest it reads as the sponsor's
 * card, and a focus ring appears the moment you go to change something.
 */
const FIELD = 'w-full bg-transparent border border-transparent rounded-md px-2 py-1 -mx-2 ' +
  'hover:border-gray-200 focus:border-blue-400 focus:bg-white focus:outline-none ' +
  'disabled:hover:border-transparent'

export default function CheckpointEditor({
  section, lang, disabled, onPatch, onSetOption, onGenerate, generating, t,
}: {
  section: SponsorTermsSection
  lang: 'en' | 'ms' | 'ta'
  disabled: boolean
  onPatch: (changes: Partial<SponsorQuizPayload>) => void
  onSetOption: (index: number, value: string) => void
  onGenerate: () => void
  generating: boolean
  t: (k: string, p?: Record<string, string>) => string
}) {
  const quiz: SponsorQuizPayload = section[`quiz_${lang}` as 'quiz_en'] || {}

  return (
    <div className="border-t border-gray-100 bg-gray-50/60 px-4 py-4 flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-400">
          {t('admin.sponsors.terms.checkpoint')}
        </span>
        <button type="button" className={btnGhost} disabled={disabled || generating}
          onClick={onGenerate}>
          {generating ? t('admin.sponsors.terms.generating') : t('admin.sponsors.terms.generate')}
        </button>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl p-4 flex flex-col gap-2">
        {/* the small uppercase label above the question */}
        <input
          className={`${FIELD} text-[11px] font-bold uppercase tracking-[0.1em] text-gray-500`}
          disabled={disabled} value={quiz.tag || ''}
          placeholder={t('admin.sponsors.terms.tagPh')}
          onChange={(e) => onPatch({ tag: e.target.value })} />

        {/* the plain-language restatement, muted */}
        <textarea
          className={`${FIELD} text-sm text-gray-500 resize-none`} rows={2}
          disabled={disabled} value={quiz.plain || ''}
          placeholder={t('admin.sponsors.terms.plainPh')}
          onChange={(e) => onPatch({ plain: e.target.value })} />

        {/* the question itself — the biggest thing on the card */}
        <textarea
          className={`${FIELD} text-base font-semibold text-gray-900 resize-none`} rows={2}
          disabled={disabled} value={quiz.question || ''}
          placeholder={t('admin.sponsors.terms.questionPh')}
          onChange={(e) => onPatch({ question: e.target.value })} />

        {/* answer rows, the marked one tinted the way a correct answer will be */}
        <div className="flex flex-col gap-1.5 mt-1">
          {[0, 1, 2].map((oi) => {
            const isCorrect = quiz.correct === oi
            return (
              <label key={oi}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors ${
                  isCorrect ? 'border-green-300 bg-green-50' : 'border-gray-200 bg-gray-50/60'}`}>
                <input type="radio" name={`ck-${section.order}-${lang}`} disabled={disabled}
                  checked={isCorrect} onChange={() => onPatch({ correct: oi })}
                  aria-label={t('admin.sponsors.terms.markCorrect', { n: String(oi + 1) })} />
                <input
                  className={`${FIELD} text-sm ${isCorrect ? 'text-green-800 font-medium' : 'text-gray-700'}`}
                  disabled={disabled} value={(quiz.options || [])[oi] || ''}
                  placeholder={t('admin.sponsors.terms.optionPh', { n: String(oi + 1) })}
                  onChange={(e) => onSetOption(oi, e.target.value)} />
              </label>
            )
          })}
        </div>

        {/* what they read after answering — shown in the feedback panel's own colours */}
        <div className="mt-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2">
          <p className="text-[11px] font-bold text-green-800 mb-0.5">
            {t('admin.sponsors.terms.afterAnswer')}
          </p>
          <textarea
            className={`${FIELD} text-sm text-green-900 resize-none`} rows={2}
            disabled={disabled} value={quiz.why || ''}
            placeholder={t('admin.sponsors.terms.whyPh')}
            onChange={(e) => onPatch({ why: e.target.value })} />
        </div>
      </div>

      <p className="text-[11px] text-gray-500 mt-1">{t('admin.sponsors.terms.quizHint')}</p>
      {section.quiz_generated_model && (
        <p className="text-[11px] text-gray-400">
          {t('admin.sponsors.terms.draftedBy', { model: section.quiz_generated_model })}
        </p>
      )}
    </div>
  )
}

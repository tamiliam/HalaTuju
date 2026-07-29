'use client'

import { useMemo, useState } from 'react'
import { LangTabs, btnGhost, btnPrimary, type CLocale } from '@/components/contracts/shared'
import { quizComplete } from '@/lib/sponsorTerms'
import type { SponsorQuizPayload, SponsorTermsSection } from '@/lib/admin-api'

/**
 * The Quiz tab: take the quiz as a sponsor would, rather than fill in a second form.
 *
 * Owner, 2026-07-28: *"We cannot see how it would look and behave in practice."* Editing happens
 * inline under each clause now; this is where you find out whether the thing you wrote actually
 * works — including the behaviour that only exists at runtime, where a wrong answer explains itself
 * and lets you try again without penalty.
 *
 * It runs off the sections currently ON SCREEN, not off the server, so you can rehearse an edit
 * before saving it. The same shape ships to sponsors in T3.
 */
export default function QuizRehearsal({ sections, t }: {
  sections: SponsorTermsSection[]
  t: (k: string, p?: Record<string, string>) => string
}) {
  const [lang, setLang] = useState<CLocale>('en')
  const [i, setI] = useState(0)
  const [picked, setPicked] = useState<number[]>([])
  const [answered, setAnswered] = useState(false)

  // A checkpoint only counts if a sponsor could actually answer it — the same rule the server's
  // Q2 applies, so the rehearsal never shows a card that could not ship.
  const checkpoints = useMemo(() => sections
    .filter((s) => s.is_quiz_candidate)
    .map((s) => {
      const own = s[`quiz_${lang}` as 'quiz_en'] as SponsorQuizPayload
      const payload = quizComplete(own) ? own : s.quiz_en          // per-item English fallback
      return { order: s.order, heading: s.heading_en, payload }
    })
    .filter((c) => quizComplete(c.payload)), [sections, lang])

  const reset = () => { setI(0); setPicked([]); setAnswered(false) }

  if (checkpoints.length === 0) {
    return <p className="text-sm text-ground-500 py-8 text-center">{t('admin.sponsors.terms.quizNone')}</p>
  }

  const done = i >= checkpoints.length
  const current = checkpoints[Math.min(i, checkpoints.length - 1)]
  const quiz = current.payload

  const choose = (k: number) => {
    if (answered) return
    if (k === quiz.correct) {
      setAnswered(true)
    } else if (!picked.includes(k)) {
      setPicked([...picked, k])          // wrong: mark it, explain, let them go again
    }
  }

  return (
    <div className="flex flex-col gap-4 max-w-2xl">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-ground-500">{t('admin.sponsors.terms.rehearseIntro')}</p>
        <LangTabs value={lang} onChange={(l) => { setLang(l); reset() }} />
      </div>

      <div className="bg-ground-0 border border-ground-200 rounded-xl overflow-hidden">
        <div className="flex gap-1 px-4 pt-4">
          {checkpoints.map((c, k) => (
            <span key={c.order} aria-hidden
              className={`flex-1 h-1 rounded ${
                k < i ? 'bg-positive-600' : k === i ? 'bg-info-600' : 'bg-ground-200'}`} />
          ))}
        </div>

        {done ? (
          <div className="p-8 text-center">
            <p className="font-semibold text-ground-900">
              {t('admin.sponsors.terms.rehearseDone', { n: String(checkpoints.length) })}
            </p>
            <p className="text-sm text-ground-500 mt-2">{t('admin.sponsors.terms.rehearseDoneBody')}</p>
          </div>
        ) : (
          <div className="p-5 flex flex-col gap-3">
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-ground-400">
              {quiz.tag}
            </p>
            <p className="text-sm text-ground-500">{quiz.plain}</p>
            <p className="text-base font-semibold text-ground-900">{quiz.question}</p>

            <div className="flex flex-col gap-2">
              {(quiz.options || []).map((o, k) => {
                const isRight = answered && k === quiz.correct
                const isWrong = picked.includes(k)
                return (
                  <button key={k} type="button" onClick={() => choose(k)}
                    disabled={answered || isWrong}
                    className={`text-left text-sm rounded-lg border px-3 py-2.5 transition-colors ${
                      isRight ? 'border-positive-500 bg-positive-50 text-positive-800 font-medium'
                        : isWrong ? 'border-critical-300 bg-critical-50 text-critical-700'
                          : 'border-ground-200 hover:border-info-400 hover:bg-info-50/50'}`}>
                    {o}
                  </button>
                )
              })}
            </div>

            {(answered || picked.length > 0) && (
              <div className={`rounded-lg border px-3 py-2.5 text-sm ${
                answered ? 'border-positive-300 bg-positive-50 text-positive-800'
                  : 'border-critical-300 bg-critical-50 text-critical-700'}`}>
                <p className="font-semibold mb-0.5">
                  {answered
                    ? t('admin.sponsors.terms.rehearseRight')
                    : t('admin.sponsors.terms.rehearseWrong')}
                </p>
                {quiz.why}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-between gap-3 border-t border-ground-100 bg-ground-50 px-4 py-3">
          <span className="text-xs text-ground-500 tabular-nums">
            {done
              ? t('admin.sponsors.terms.rehearseComplete')
              : t('admin.sponsors.terms.rehearseProgress', {
                n: String(i + 1), total: String(checkpoints.length), sec: String(current.order),
              })}
          </span>
          <span className="flex gap-2">
            <button type="button" className={btnGhost} onClick={reset}>
              {t('admin.sponsors.terms.rehearseRestart')}
            </button>
            <button type="button" className={btnPrimary} disabled={!answered || done}
              onClick={() => { setI(i + 1); setPicked([]); setAnswered(false) }}>
              {i === checkpoints.length - 1
                ? t('admin.sponsors.terms.rehearseFinish')
                : t('admin.sponsors.terms.rehearseNext')}
            </button>
          </span>
        </div>
      </div>
    </div>
  )
}

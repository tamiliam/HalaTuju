'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { checkpointsFor, quizUiFor, CHECKPOINT_COUNT } from '@/lib/awardComprehension'

/**
 * The "Understand" step of /scholarship/award — a gamified comprehension quiz.
 *
 * Ported from the owner-approved prototype: the student works through 8 multiple-choice
 * checkpoints, one at a time, each mirroring a clause of the bursary agreement. A wrong
 * answer is NEVER penalised — they re-read the plain-language box and try again. When all
 * 8 are passed, `onComplete()` fires (the page advances to "Read & sign" and records the
 * pass). Content + copy live in lib/awardComprehension.ts (en/ms/ta).
 */
export default function AwardComprehensionQuiz({ onComplete }: { onComplete: () => void }) {
  const { locale } = useT()
  const ui = quizUiFor(locale)
  const checkpoints = checkpointsFor(locale)

  // 'intro' = the congratulations + "what happens now" card; then one card per checkpoint.
  const [phase, setPhase] = useState<'intro' | 'learn'>('intro')
  const [i, setI] = useState(0)
  // null = unanswered; 'correct' / 'wrong' after a pick. 'wrong' auto-clears so they retry.
  const [status, setStatus] = useState<'idle' | 'correct' | 'wrong'>('idle')
  const [picked, setPicked] = useState<number | null>(null)

  if (phase === 'intro') {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-4xl" aria-hidden>🎉</div>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">{ui.introTitle}</h1>
        <p className="mt-2 text-gray-600">{ui.introBody}</p>
        <div className="mt-4 rounded-xl bg-blue-50 p-4 text-sm text-gray-800">
          <div className="font-semibold">{ui.whatHappens}</div>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li>{ui.step1(CHECKPOINT_COUNT)}</li>
            <li>{ui.step2}</li>
            <li>{ui.step3}</li>
          </ul>
        </div>
        <button
          type="button"
          onClick={() => { setPhase('learn'); setI(0); setStatus('idle'); setPicked(null); window.scrollTo(0, 0) }}
          className="mt-6 w-full rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600"
        >
          {ui.begin}
        </button>
        <p className="mt-5 text-center text-xs text-gray-400">{ui.heldNote}</p>
      </div>
    )
  }

  const cp = checkpoints[i]
  const isLast = i >= CHECKPOINT_COUNT - 1

  function choose(idx: number) {
    if (status === 'correct') return
    setPicked(idx)
    if (cp.options[idx].correct) {
      setStatus('correct')
    } else {
      setStatus('wrong')
      // No penalty: clear the wrong state after a beat so they can try again.
      window.setTimeout(() => { setStatus('idle'); setPicked(null) }, 750)
    }
  }

  function advance() {
    if (isLast) { onComplete(); return }
    setI((n) => n + 1); setStatus('idle'); setPicked(null); window.scrollTo(0, 0)
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between text-sm text-gray-500">
        <span>{ui.understandHeading}</span>
        <span>{ui.ofCount(i + 1, CHECKPOINT_COUNT)}</span>
      </div>

      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-xs font-semibold uppercase tracking-wider text-blue-600">{cp.tag}</div>
        <div className="mt-2 rounded-xl bg-blue-50 p-4 text-sm text-gray-800">
          <span className="font-semibold">{ui.whatThisMeans}</span>{cp.plain}
        </div>
        <h2 className="mt-5 text-lg font-bold text-gray-900">{cp.question}</h2>

        <div className="mt-2 space-y-2">
          {cp.options.map((o, idx) => {
            const chosen = picked === idx
            const tone = status === 'correct' && chosen ? 'border-green-600 bg-green-50'
              : status === 'wrong' && chosen ? 'border-red-600 bg-red-50'
              : 'border-gray-300 bg-white hover:border-blue-300 hover:bg-slate-50'
            return (
              <button
                key={idx}
                type="button"
                disabled={status === 'correct'}
                onClick={() => choose(idx)}
                className={`block w-full rounded-xl border px-4 py-3 text-left text-sm text-gray-800 transition-colors ${tone}`}
              >
                {o.text}
              </button>
            )
          })}
        </div>

        {status === 'correct' && (
          <div className="mt-4 rounded-xl bg-green-50 p-3 text-sm text-green-800">
            <span className="font-semibold">✓ </span>{cp.why}
          </div>
        )}
        {status === 'wrong' && (
          <div className="mt-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{ui.notQuite}</div>
        )}

        {status === 'correct' && (
          <button
            type="button"
            onClick={advance}
            className="mt-5 w-full rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600"
          >
            {isLast ? ui.finish : ui.next}
          </button>
        )}
      </div>
      <p className="mt-5 text-center text-xs text-gray-400">{ui.footnote}</p>
    </div>
  )
}

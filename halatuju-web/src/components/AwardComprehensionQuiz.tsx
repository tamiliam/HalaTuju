'use client'

import { useCallback, useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { quizUiFor } from '@/lib/awardComprehension'
import {
  getComprehensionQuiz, recordComprehensionPass,
  type ComprehensionCheckpoint,
} from '@/lib/api'

/**
 * The "Understand" step of /scholarship/award — a gamified comprehension quiz.
 *
 * The checkpoints are fetched from the API (served from the org's active contract
 * template, en fallback when a locale isn't translated). The student works through them
 * one at a time; a wrong answer is NEVER penalised. On the final pass we POST with the
 * template_version we were quizzed on; a redeploy mid-quiz → 409 `version_changed` →
 * we re-fetch and the student re-takes. Only a successful pass fires `onComplete()`.
 * The UI chrome (intro/buttons/footnote) still lives in lib/awardComprehension.ts.
 */
export default function AwardComprehensionQuiz({
  onComplete, token,
}: { onComplete: () => void; token?: string }) {
  const { locale } = useT()
  const ui = quizUiFor(locale)

  const [load, setLoad] = useState<'loading' | 'error' | 'ready'>('loading')
  const [version, setVersion] = useState('')
  const [checkpoints, setCheckpoints] = useState<ComprehensionCheckpoint[]>([])
  const [retakeNote, setRetakeNote] = useState(false)

  const [phase, setPhase] = useState<'intro' | 'learn'>('intro')
  const [i, setI] = useState(0)
  const [status, setStatus] = useState<'idle' | 'correct' | 'wrong'>('idle')
  const [picked, setPicked] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const fetchQuiz = useCallback(async () => {
    setLoad('loading')
    try {
      const data = await getComprehensionQuiz(locale, token ? { token } : undefined)
      setVersion(data.template_version)
      setCheckpoints(data.checkpoints || [])
      setLoad((data.checkpoints || []).length ? 'ready' : 'error')
    } catch {
      setLoad('error')
    }
  }, [locale, token])

  useEffect(() => { fetchQuiz() }, [fetchQuiz])

  if (load === 'loading') {
    return <div className="rounded-2xl border bg-white p-6 text-center text-sm text-gray-500 shadow-sm">{ui.loading}</div>
  }
  if (load === 'error') {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <p className="text-sm text-gray-700">{ui.loadError}</p>
        <button type="button" onClick={fetchQuiz}
          className="mt-4 rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-600">
          {ui.retry}
        </button>
      </div>
    )
  }

  const count = checkpoints.length

  if (phase === 'intro') {
    return (
      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        {retakeNote && (
          <div className="mb-4 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{ui.versionChanged}</div>
        )}
        <div className="text-4xl" aria-hidden>🎉</div>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">{ui.introTitle}</h1>
        <p className="mt-2 text-gray-600">{ui.introBody}</p>
        <div className="mt-4 rounded-xl bg-blue-50 p-4 text-sm text-gray-800">
          <div className="font-semibold">{ui.whatHappens}</div>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li>{ui.step1(count)}</li>
            <li>{ui.step2}</li>
            <li>{ui.step3}</li>
          </ul>
        </div>
        <button
          type="button"
          onClick={() => { setPhase('learn'); setI(0); setStatus('idle'); setPicked(null); setRetakeNote(false); window.scrollTo(0, 0) }}
          className="mt-6 w-full rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600"
        >
          {ui.begin}
        </button>
        <p className="mt-5 text-center text-xs text-gray-400">{ui.heldNote}</p>
      </div>
    )
  }

  const cp = checkpoints[i]
  const isLast = i >= count - 1

  function choose(idx: number) {
    if (status === 'correct') return
    setPicked(idx)
    if (idx === cp.correct) {
      setStatus('correct')
    } else {
      setStatus('wrong')
      window.setTimeout(() => { setStatus('idle'); setPicked(null) }, 750)
    }
  }

  async function advance() {
    if (!isLast) {
      setI((n) => n + 1); setStatus('idle'); setPicked(null); window.scrollTo(0, 0)
      return
    }
    // Final checkpoint: record the pass, pinned to the version we were quizzed on.
    setSubmitting(true)
    try {
      await recordComprehensionPass(version, token ? { token } : undefined)
      onComplete()
    } catch (err) {
      if ((err as { code?: string })?.code === 'version_changed') {
        // The agreement was redeployed mid-quiz → re-fetch and re-take.
        setRetakeNote(true); setPhase('intro'); setI(0); setStatus('idle'); setPicked(null)
        window.scrollTo(0, 0)
        await fetchQuiz()
      } else {
        // Best-effort (matches the prior behaviour): let them proceed; a missed stamp
        // surfaces later as `comprehension_stale` at signing and they re-take then.
        onComplete()
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <div className="mb-3 flex items-center justify-between text-sm text-gray-500">
        <span>{ui.understandHeading}</span>
        <span>{ui.ofCount(i + 1, count)}</span>
      </div>

      <div className="rounded-2xl border bg-white p-6 shadow-sm">
        <div className="text-xs font-semibold uppercase tracking-wider text-blue-600">{cp.tag}</div>
        <div className="mt-2 rounded-xl bg-blue-50 p-4 text-sm text-gray-800">
          <span className="font-semibold">{ui.whatThisMeans}</span>{cp.plain}
        </div>
        <h2 className="mt-5 text-lg font-bold text-gray-900">{cp.question}</h2>

        <div className="mt-2 space-y-2">
          {cp.options.map((text, idx) => {
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
                {text}
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
            disabled={submitting}
            className="mt-5 w-full rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
          >
            {isLast ? ui.finish : ui.next}
          </button>
        )}
      </div>
      <p className="mt-5 text-center text-xs text-gray-400">{ui.footnote}</p>
    </div>
  )
}

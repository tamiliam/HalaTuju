'use client'

import { useEffect, useState } from 'react'
import { getDocumentHelp, type ApplicantDocument } from '@/lib/api'
import { shouldShowCoach, fallbackKeyFor, helpSignal, readHelpCache, writeHelpCache } from '@/lib/documentHelp'

// "Cikgu Gopal" — a warm helper note shown beneath a document's amber/grey chip.
// Proactive (fires when there's a soft problem), never a chat box. Reacts to the
// already-decided verdict; degrades to pre-written i18n copy when the AI is off.
export default function DocumentHelpCoach({
  doc,
  token,
  t,
  lang,
}: {
  doc: ApplicantDocument
  token: string | null
  t: (key: string) => string
  lang: string
}) {
  const show = shouldShowCoach(doc)
  const [status, setStatus] = useState<'loading' | 'ai' | 'fallback' | 'none'>('loading')
  const [message, setMessage] = useState('')
  const [verdict, setVerdict] = useState<string | undefined>(undefined)

  // Cache key: the per-language verdict signal. Only a (re-)upload changes the signal,
  // so a plain page reload reuses the stored advice — Gopal sticks, never re-pops.
  const cacheSignal = `${helpSignal(doc)}|${lang}`

  useEffect(() => {
    if (!show || !token) return
    // Advice STICKS: if we already have advice for this exact signal, reuse it — no
    // re-fetch, no re-pop on a plain reload. Gopal re-fires only after a real upload.
    const cached = readHelpCache(doc.id, cacheSignal)
    if (cached) {
      setVerdict(cached.verdict)
      setMessage(cached.message)
      setStatus(cached.source)
      return
    }
    let cancelled = false
    setStatus('loading')
    getDocumentHelp(doc.id, lang, { token })
      .then((r) => {
        if (cancelled) return
        const next =
          r.source === 'ai' && r.message
            ? { source: 'ai' as const, message: r.message, verdict: r.verdict }
            : r.source === 'none'
              ? { source: 'none' as const, message: '', verdict: r.verdict }
              : { source: 'fallback' as const, message: '', verdict: r.verdict }
        setVerdict(next.verdict)
        setMessage(next.message)
        setStatus(next.source)
        writeHelpCache(doc.id, cacheSignal, next)
      })
      .catch(() => {
        if (!cancelled) setStatus('fallback')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show, token, doc.id, lang, cacheSignal])

  if (!show || status === 'none') return null

  const body =
    status === 'ai' ? message : t(fallbackKeyFor(verdict))

  return (
    <div className="mt-2 flex gap-2.5 rounded-xl bg-primary-50 ring-1 ring-primary-100 p-3">
      {/* Friendly mentor icon — distinct from the amber warning above. */}
      <div
        aria-hidden
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-600 text-white"
      >
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 14l9-5-9-5-9 5 9 5z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 14v6m-5-9v4a5 5 0 0010 0v-4" />
        </svg>
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-700">
          {t('scholarship.docs.help.coachLabel')}
        </p>
        {status === 'loading' ? (
          <div className="mt-1.5 space-y-1.5" aria-hidden>
            <div className="h-2.5 w-48 max-w-full animate-pulse rounded bg-primary-100" />
            <div className="h-2.5 w-32 max-w-full animate-pulse rounded bg-primary-100" />
          </div>
        ) : (
          <p className="mt-0.5 text-sm leading-relaxed text-primary-900/90 whitespace-pre-line">{body}</p>
        )}
      </div>
    </div>
  )
}

'use client'

import { useEffect, useState } from 'react'
import { getIncomeHelp, type ApplicantDocument } from '@/lib/api'
import {
  fallbackKeyFor,
  clusterDocsFor,
  clusterHelpSignal,
  clusterCacheKey,
  readHelpCacheRaw,
  writeHelpCacheRaw,
} from '@/lib/documentHelp'
import { CoachCard } from './DocumentHelpCoach'

// The SINGLE "Cikgu Gopal" for one earner's whole income cluster — anchored at the foot of
// the cluster, not on any one file. It reads the cluster as a whole (IC + STR / payslip +
// relationship doc) and speaks once, even before the IC is uploaded. The per-document
// coaches inside the cluster are suppressed so there is exactly one voice per earner.
export default function IncomeClusterCoach({
  member,
  route,
  docs,
  token,
  t,
  lang,
}: {
  member: string
  route: string
  docs: ApplicantDocument[]
  token: string | null
  t: (key: string) => string
  lang: string
}) {
  const clusterDocs = clusterDocsFor(docs, member, route)
  // Nothing uploaded for this earner yet → nothing to coach (no fetch).
  const show = clusterDocs.length > 0
  const [status, setStatus] = useState<'loading' | 'ai' | 'fallback' | 'none'>('loading')
  const [message, setMessage] = useState('')
  const [verdict, setVerdict] = useState<string | undefined>(undefined)

  // Cache key: member + a signal over the cluster's docs + language. Re-fires only when
  // a cluster document actually changes (upload / re-run); a plain reload reuses the cache.
  const signal = `${clusterHelpSignal(clusterDocs)}|${lang}`
  const cacheKey = clusterCacheKey(member, signal)

  useEffect(() => {
    if (!show || !token) return
    const cached = readHelpCacheRaw(cacheKey)
    if (cached) {
      setVerdict(cached.verdict)
      setMessage(cached.message)
      setStatus(cached.source)
      return
    }
    let cancelled = false
    setStatus('loading')
    getIncomeHelp(member, lang, { token })
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
        writeHelpCacheRaw(cacheKey, next)
      })
      .catch(() => {
        if (!cancelled) setStatus('fallback')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show, token, member, lang, cacheKey])

  if (!show || status === 'none') return null

  const body = status === 'ai' ? message : t(fallbackKeyFor(verdict))
  return <CoachCard t={t} loading={status === 'loading'} body={body} />
}

'use client'

import { useEffect, useState } from 'react'
import { resolveCachedResults, type CachedResults } from '@/lib/resultsCache'

const NOTHING: CachedResults = { view: 'none' }

/**
 * The results this browser holds, re-read whenever `hydrationSignal` changes.
 *
 * ⚠ **THE SIGNAL IS THE WHOLE POINT — pass AuthProvider's `profile`.** The cache is written by
 * AuthProvider's caching effect, which cannot run until `getProfile` has come back over the
 * network. A page that reads the cache only on mount therefore reads it strictly BEFORE it can be
 * populated, and on the first view after any sign-in concludes there is nothing there. That is how
 * a student who had onboarded was shown *No profile found* (org request #11, 2026-08-13).
 *
 * `ready` is false only until the first read completes, so callers can show a loading state rather
 * than a wrong answer. Re-reads after that keep `ready` true — the screen must not flash back to
 * loading when the profile lands.
 *
 * ⚠ Safe to re-run ONLY because these screens display results and never edit them. If a caller
 * ever lets somebody type into state derived from this, re-reading would clobber their input.
 */
export function useCachedResults(hydrationSignal: unknown): { results: CachedResults; ready: boolean } {
  const [results, setResults] = useState<CachedResults>(NOTHING)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    setResults(resolveCachedResults(localStorage))
    setReady(true)
  }, [hydrationSignal])

  return { results, ready }
}

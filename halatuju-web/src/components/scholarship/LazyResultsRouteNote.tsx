'use client'

/**
 * Step 3's results notes (TD-773), fetched only when one is drawn (see `ResultsRouteNote`).
 *
 * ⚠ NOTHING HERE IS IN THE APPLY PAGE'S FIRST-LOAD JS: /scholarship/apply sits close to its budget, so
 * this wrapper rides the `LazyApplyNotice` chunk and the notes and their words
 * (`documentsTab.resultsNote.*`, the Documents slice) ride a second one. Only the decision
 * (`lib/resultsRouteNote.ts`) is eager, and it is a few lines.
 *
 * The import is owned here, not by `next/dynamic` (the `LazyApplyNotice` reason): a failed chunk
 * says so in place instead of throwing the page away. Nothing is drawn until the chunk AND the
 * slice of the language on screen are in, so a Malay or Tamil reader never sees English first.
 */
import { useEffect, useState } from 'react'

import { useT } from '@/lib/i18n'

import type { ResultsNoteKind } from './ResultsRouteNote'   // a type only: erased, pulls no chunk

type Note = typeof import('./ResultsRouteNote')['default']

export default function LazyResultsRouteNote({ kind }: { kind: ResultsNoteKind }) {
  const { t, locale } = useT()
  const [Loaded, setLoaded] = useState<Note | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import(/* webpackChunkName: 'rn' */ './ResultsRouteNote')
      .then(async (m) => { await m.wordsReady(locale); if (live) setLoaded(() => m.default) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [locale])

  if (failed) {
    return (
      <p role="alert" className="mt-4 rounded-lg border border-caution-200 bg-caution-50 px-4 py-3 text-sm text-caution-800">
        {t('verifyEmail.networkError')}
      </p>
    )
  }
  return Loaded ? <Loaded kind={kind} /> : null
}

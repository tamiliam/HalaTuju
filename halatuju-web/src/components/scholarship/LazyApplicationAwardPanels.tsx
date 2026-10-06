'use client'

/**
 * The award and bursary-agreement panels, fetched only for the student they are drawn for.
 *
 * WHY (TD-352, 2026-10-06): `/scholarship/application` sat 0.18 kB under its 274 kB first-load
 * budget, and the one sentence the owner asked for ("while this application is in process …")
 * needed room. Both panels draw nothing unless the student holds an award offer the flag lets her
 * see, or a signed agreement — a small minority — yet their code rode in every visit's first load.
 * The budget is never raised; the weight is paid for here.
 *
 * ⚠ THE CHUNK IS ASKED FOR ONLY WHEN A PANEL WOULD DRAW (`shows`, the panels' own two guards), so
 * a student with no award never fetches it. The page still asks for the award and the agreement
 * itself, exactly as before.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — the `LazyInterviewBookingPanel` reason: a
 * failed chunk says so in place instead of throwing the whole page away. Nothing is drawn while
 * the chunk is in the air. The specifier is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState } from 'react'

import { useT } from '@/lib/i18n'
import type { AwardPanelsProps } from './ApplicationAwardPanels'

type Panels = typeof import('./ApplicationAwardPanels')['default']

/** Would either panel draw? (The award panel needs an offer the flag shows; the agreement panel a
 *  signed PDF.) Asked BEFORE the chunk is fetched. */
export function showsAwardPanels(p: Pick<AwardPanelsProps, 'award' | 'acceptanceEnabled' | 'bursary'>) {
  return !!(p.award && p.acceptanceEnabled) || !!p.bursary?.pdf_url
}

export default function LazyApplicationAwardPanels(props: AwardPanelsProps) {
  const { t } = useT()
  const shows = showsAwardPanels(props)
  const [Loaded, setLoaded] = useState<Panels | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!shows) return
    let live = true
    import('./ApplicationAwardPanels')
      .then((m) => { if (live) setLoaded(() => m.default) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [shows])

  if (!shows) return null
  if (failed) {
    return (
      <p role="alert" className="mb-6 rounded-lg border border-caution-200 bg-caution-50 px-4 py-3 text-sm text-caution-800">
        {t('verifyEmail.networkError')}
      </p>
    )
  }
  return Loaded ? <Loaded {...props} /> : null
}

'use client'

/**
 * The income-route switch, fetched only when the Action Centre would draw it.
 *
 * WHY (TD-352, 2026-10-06): `/scholarship/application` sat 0.18 kB under its 274 kB first-load
 * budget and the owner's one sentence ("while this application is in process …") needed room. The
 * switch is drawn only for a submitted student with an OPEN income task — a minority of visits —
 * yet its code rode in every visit's first load. The budget is never raised; the weight is paid
 * for here.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic` — the `LazyInterviewBookingPanel` reason: a
 * failed chunk says so in place instead of throwing the whole page away. Nothing is drawn while
 * the chunk is in the air (a moment; the switch opens collapsed, as a quiet link). The specifier
 * is a LITERAL so the bundler emits a real chunk.
 */
import { useEffect, useState, type ComponentProps } from 'react'

import { useT } from '@/lib/i18n'

type Switch = typeof import('./IncomeRouteSwitch')['default']

export default function LazyIncomeRouteSwitch(props: ComponentProps<Switch>) {
  const { t } = useT()
  const [Loaded, setLoaded] = useState<Switch | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('./IncomeRouteSwitch')
      .then((m) => { if (live) setLoaded(() => m.default) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [])

  if (failed) {
    return (
      <p role="alert" className="rounded-lg border border-caution-200 bg-caution-50 px-4 py-3 text-sm text-caution-800">
        {t('verifyEmail.networkError')}
      </p>
    )
  }
  return Loaded ? <Loaded {...props} /> : null
}

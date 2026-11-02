'use client'

/**
 * Her Growth tab (development modules), fetched as its own chunk the first time it is opened (student maintenance S10) — the
 * `LazyBursaryNews` arrangement: `/scholarship/bursary` stays within its first-load budget, and a student
 * who never opens the tab downloads none of it. A failed chunk says so in one line.
 */
import { useEffect, useState, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

type Props = { token: string | null; onCount?: (n: number) => void }

export default function LazyBursaryGrowth(props: Props) {
  const { t } = useT()
  const [Tab, setTab] = useState<ComponentType<Props> | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let live = true
    import('@/components/bursary/tabScreens')   // shared with Surveys: no new chunk-map entry (S10)
      .then((m) => { if (live) setTab(() => m.BursaryGrowth) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [])
  if (Tab) return <Tab {...props} />
  if (failed) return <p className="text-sm text-critical-600" role="alert">{t('bursaryTabs.growth.loadFailed')}</p>
  return null
}

'use client'

/**
 * The student's Mentoring tab, fetched as its own chunk the first time it is opened (student maintenance S7b):
 * `/scholarship/bursary` stays within its first-load budget, and a student without the tab downloads
 * none of it. The import is owned here, not by `next/dynamic` (which re-throws a failed chunk load —
 * the `LazySource` arrangement). A failed chunk says so in one line.
 */
import { useEffect, useState, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

type Props = { token: string | null }

export default function LazyBursaryMentoring(props: Props) {
  const { t } = useT()
  const [Tab, setTab] = useState<ComponentType<Props> | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let live = true
    import('@/components/bursary/BursaryMentoring')
      .then((m) => { if (live) setTab(() => m.default) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [])
  if (Tab) return <Tab {...props} />
  if (failed) return <p className="text-sm text-critical-600" role="alert">{t('bursaryTabs.mentoring.loadFailed')}</p>
  return null
}

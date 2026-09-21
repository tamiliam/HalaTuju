'use client'

/**
 * The interview booking panel, fetched when the page needs it instead of riding in the page's
 * first-load JS for every student.
 *
 * WHY (audit follow-up, 2026-09-21): the panel renders NOTHING for most students — no interview
 * schedule, or a funded case — yet its code and `lib/interviewTime` were a static import of
 * `/scholarship/application`, the one student route sitting exactly on its first-load budget.
 * The language-switch bug fixes added about half a kilobyte of required code to every route and
 * tipped this one 1 kB over. The budget is never raised; the weight is paid for here.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic`. `next/dynamic` RE-THROWS a failed load
 * (its `loading` prop never sees the error), which would hand a student holding a tab across a
 * deploy a whole-page error where a booking panel should be. Owning `import()` lets a failure
 * say so, in place, and leave the rest of the page working.
 *
 * ⚠ NOTHING IS DRAWN WHILE THE CHUNK IS IN THE AIR, and that is identical to before: the panel
 * itself returns null until its own schedule fetch lands, so the first paint never showed it.
 *
 * The specifier is a LITERAL so the bundler emits a real chunk (same technique as lib/messages).
 */
import { useEffect, useState, type ComponentType } from 'react'
import { useT } from '@/lib/i18n'

type PanelProps = { applicationId: number; token: string | null }

export default function LazyInterviewBookingPanel(props: PanelProps) {
  const { t } = useT()
  const [Panel, setPanel] = useState<ComponentType<PanelProps> | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('@/components/scholarship/InterviewBookingPanel')
      .then(m => { if (live) setPanel(() => m.default) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [])

  if (failed) {
    return (
      <p role="alert" className="mb-4 rounded-lg border border-caution-200 bg-caution-50 px-4 py-3 text-sm text-caution-800">
        {t('verifyEmail.networkError')}
      </p>
    )
  }
  return Panel ? <Panel {...props} /> : null
}

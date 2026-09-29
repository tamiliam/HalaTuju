'use client'

/**
 * The Action Centre's two POST-AWARD cards (bank details, Vircle eWallet), fetched when a task
 * needs one instead of riding in the first-load JS of every applicant.
 *
 * WHY (TD-306 follow-up, 2026-09-30): the deploy gate refused 4583a83d because
 * `/scholarship/application` printed 276 kB against its 275 kB budget. Only an AWARDED student
 * ever holds a `bank_details_missing` or `vircle_setup_pending` task, so these cards — and the
 * phone helpers, country list and Vircle account rule they bring — are the weight most students
 * never render. The budget is never raised; the weight is paid for here.
 *
 * ⚠ THE IMPORT IS OWNED HERE, NOT BY `next/dynamic`, exactly as LazyInterviewBookingPanel does:
 * `next/dynamic` RE-THROWS a failed load, which would hand a funded student holding a tab across
 * a deploy a whole-page error where one card should be. Owning `import()` lets a failure say so
 * in place, and leaves the rest of the Action Centre working.
 *
 * ⚠ NOTHING IS DRAWN WHILE THE CHUNK IS IN THE AIR. The Action Centre itself draws nothing until
 * its task fetch lands, so this adds one more short wait after that, with no dead button in it.
 *
 * The specifier is a LITERAL so the bundler emits a real chunk (same technique as lib/messages).
 */
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import type { ResolutionItem } from '@/lib/api'

type Common = { item: ResolutionItem; token: string | null; onResolved: () => void }
type Props = ({ kind: 'bank' } & Common) | ({ kind: 'vircle'; contactPhone: string } & Common)
type Tasks = typeof import('@/components/scholarship/PostAwardTasks')

export default function LazyPostAwardTask(props: Props) {
  const { t } = useT()
  const [tasks, setTasks] = useState<Tasks | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    import('@/components/scholarship/PostAwardTasks')
      .then(m => { if (live) setTasks(m) })
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
  if (!tasks) return null
  if (props.kind === 'bank') {
    return <tasks.BankDetailsTask item={props.item} token={props.token} onResolved={props.onResolved} />
  }
  return (
    <tasks.VircleTask
      item={props.item} token={props.token}
      contactPhone={props.contactPhone} onResolved={props.onResolved}
    />
  )
}

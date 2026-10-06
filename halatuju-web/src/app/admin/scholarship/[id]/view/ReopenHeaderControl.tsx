'use client'

/**
 * The Decision card's header control for a super: Reopen a recorded decision — or, while a
 * decline's email is still embargoed, the existing "cancel the pending decline" in its place,
 * because the api refuses that reopen (`decline_pending`, TD-349). The rule is
 * `decisionReopenOffer`; this only draws it.
 */
import { decisionReopenOffer, isDeclinePending } from '@/lib/decisionReopenOffer'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import type { T } from './shared'

export function ReopenHeaderControl({
  app, t, busy, decisionLocked, isSuper, hidden, onReopen, onCancelDecline,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  decisionLocked: boolean
  isSuper: boolean
  hidden: boolean
  onReopen: () => void
  onCancelDecline: () => void
}) {
  const offer = decisionReopenOffer({ decisionLocked, isSuper, declinePending: isDeclinePending(app) })
  if (offer === 'cancelPendingDecline') {
    return (
      <button onClick={onCancelDecline} disabled={busy === 'cooloff'}
        className="rounded-lg border border-caution-300 px-2.5 py-1 text-xs text-caution-800 hover:bg-caution-100 disabled:opacity-50">
        {busy === 'cooloff' ? '…' : t('admin.scholarship.cooloff.cancelDecline')}
      </button>
    )
  }
  if (offer !== 'reopen' || hidden) return null
  return (
    <button onClick={onReopen}
      className="rounded-lg border border-ground-300 px-2.5 py-1 text-xs text-ground-600 hover:bg-ground-100">
      {t('admin.scholarship.recordVerdict.reopen')}
    </button>
  )
}

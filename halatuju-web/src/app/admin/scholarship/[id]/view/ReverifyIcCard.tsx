'use client'

/**
 * TD-378 (audit sprint A2.8a) — "Re-verify IC" on an AWAITING-QC case whose IC lock a super released
 * on an intake with a "Born in" rule. QC accept refuses that case (`birth_state_ic_unlocked`), and
 * before this card the only cockpit route was QC reopen → the reviewer's Recommend, which emailed her
 * "returned for revision" and counted a false correction against her.
 *
 * The button calls the SAME verify-accept the reviewer's Recommend calls (no new endpoint, no verdict
 * re-record): it re-locks the IC and runs the duplicate-verified-IC check, and the case stays at
 * AWAITING QC. The presser becomes the IC's verifier, so the QC separation rule then asks someone
 * else (or a super) to do the QC — the same as calling the endpoint through the API.
 */
import { useState } from 'react'
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import { verifyAcceptApplication } from '@/lib/admin-api'

import type { T } from './shared'

/** Shown only at AWAITING QC, to a QC holder, on a ruled intake whose IC is not locked. */
export function needsIcReverify(app: AdminScholarshipDetail, canQc: boolean): boolean {
  return app.status === 'interviewed' && canQc && app.birth_state?.meets_rule != null && !app.nric_verified
}

export function ReverifyIcCard({ app, t, token, busy, canQc, onDone }: {
  app: AdminScholarshipDetail
  t: T
  token: string | null
  busy: string
  canQc: boolean
  onDone: (app: AdminScholarshipDetail) => void
}) {
  const [working, setWorking] = useState(false)
  const [error, setError] = useState('')
  if (!needsIcReverify(app, canQc)) return null
  const reverify = async () => {
    if (!token) return
    setWorking(true); setError('')
    try {
      onDone(await verifyAcceptApplication(app.id, {}, { token }))
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.scholarship.acceptError'))
    } finally { setWorking(false) }
  }
  return (
    <div data-testid="reverify-ic" className="border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-caution-200 md:bg-caution-50 md:p-5 space-y-2">
      <p className="text-sm font-medium text-caution-900">{t('admin.scholarship.qcDecision.reverifyTitle')}</p>
      <p className="text-xs text-caution-800">{t('admin.scholarship.qcDecision.reverifyHint')}</p>
      {error && <p role="alert" className="text-xs text-critical-700">{error}</p>}
      <button onClick={reverify} disabled={!!busy || working}
        className="rounded-lg border border-caution-600 bg-ground-0 px-4 py-2.5 text-sm font-medium text-caution-700 hover:bg-caution-50 disabled:opacity-50 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center">
        {working ? t('common.loading') : t('admin.scholarship.qcDecision.reverifyButton')}
      </button>
    </div>
  )
}

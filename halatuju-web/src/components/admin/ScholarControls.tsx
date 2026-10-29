'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  closeApplication, setMaintenanceSubstate,
  type ClosureReason, type MaintenanceSubstate, type ScholarFile,
} from '@/lib/admin-api'

const SUBSTATES: readonly MaintenanceSubstate[] = ['on_track', 'probation', 'on_hold', 'ready_to_close']

/** Refusal codes the two doors answer, each with its own sentence (the rest read generically). */
const KNOWN_ERRORS = [
  'hold_needs_payments', 'not_in_maintenance', 'changed_meanwhile', 'bad_substate',
  'sponsorship_open', 'decline_pending', 'not_closeable', 'bad_reason', 'reason_not_allowed',
]

/**
 * The scholar file's maintenance controls (student maintenance S3) — the sub-state and Close, MOVED
 * here from the cockpit's `PostAwardPanels` (which now carries a summary and a link).
 *
 * ⚠ AN OFFER, NEVER THE GATE: what is drawn follows the server's `controls` (who may write, who holds
 * payments rights, which closure reasons fit), and `AdminMaintenanceSubstateView` /
 * `AdminCloseApplicationView` judge every request again. A refusal is shown in words
 * (`admin.scholars.control.error.*`), never as a bare code — TD-419's untranslated
 * `hold_needs_payments` is gone with the move.
 * ⚠ A HOLD STOPS MONEY, so the hold buttons are drawn only for a payments-rights holder; anyone else
 * sees why. An awarded case still holding the sponsor's offer CANNOT be closed (`sponsorship_open`,
 * TD-366) — the file says so instead of offering a button that always refuses (S1 review L4).
 */
export default function ScholarControls({ file, token, onChanged }: {
  file: ScholarFile
  token: string | null
  onChanged: () => void
}) {
  const { t } = useT()
  const c = file.controls
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [reason, setReason] = useState<ClosureReason | ''>('')
  const [confirm, setConfirm] = useState(false)
  if (!c || file.status === 'closed') return null

  const say = (e: unknown, fallback: string) => {
    const code = (e as { code?: string })?.code || ''
    setError(KNOWN_ERRORS.includes(code) ? t(`admin.scholars.control.error.${code}`) : t(fallback))
  }
  const holdMove = (s: MaintenanceSubstate) => s === 'on_hold' || file.maintenance_substate === 'on_hold'

  async function move(s: MaintenanceSubstate) {
    if (!token) return
    setBusy(s); setError('')
    try { await setMaintenanceSubstate(file.id, s, { token }); onChanged() }
    catch (e) { say(e, 'admin.scholars.control.error.generic') }
    finally { setBusy('') }
  }

  async function close() {
    if (!token || !reason) return
    setBusy('close'); setError('')
    try { await closeApplication(file.id, reason, { token }); setConfirm(false); onChanged() }
    catch (e) { say(e, 'admin.closure.error.generic') }
    finally { setBusy('') }
  }

  const offered = SUBSTATES.filter((s) => s !== file.maintenance_substate)
  return (
    <section aria-label={t('admin.scholars.control.title')} data-testid="scholar-controls"
      className="mt-4 space-y-3 border-t border-ground-100 pt-4">
      {c.can_set_substate && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-ground-600">{t('admin.scholars.control.substate')}</p>
          <div className="flex flex-wrap gap-1.5">
            {offered.map((s) => (holdMove(s) && !c.can_hold) ? null : (
              <button key={s} type="button" onClick={() => move(s)} disabled={!!busy}
                className="rounded-lg border border-ground-300 px-3 py-1 text-xs font-medium text-ground-700 hover:bg-ground-100 disabled:opacity-50">
                {t(`admin.maintenance.action.${s}`)}
              </button>
            ))}
          </div>
          {!c.can_hold && (
            <p className="mt-1.5 text-[11px] text-ground-500" data-testid="hold-needs-payments">
              {t('admin.scholars.control.holdNeedsPayments')}
            </p>
          )}
          {file.maintenance_substate === 'on_hold' && (
            <p className="mt-1.5 text-[11px] text-critical-600">{t('admin.scholars.control.onHoldHint')}</p>
          )}
        </div>
      )}

      {c.close_refusal && (
        <p className="rounded-lg border border-caution-200 bg-caution-50 p-3 text-xs text-caution-800"
          data-testid="close-refusal">
          {t(`admin.scholars.control.refusal.${c.close_refusal}`)}
        </p>
      )}

      {c.close_reasons.length > 0 && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-[11px] font-medium text-ground-600">
            {t('admin.closure.reasonLabel')}
            <select value={reason} onChange={(e) => setReason(e.target.value as ClosureReason | '')}
              className="mt-1 block rounded-lg border px-3 py-1.5 text-sm">
              <option value="">{t('admin.closure.reasonUnset')}</option>
              {c.close_reasons.map((r) => (
                <option key={r} value={r}>{t(`admin.closure.reason.${r}`)}</option>
              ))}
            </select>
          </label>
          {!confirm ? (
            <button type="button" onClick={() => setConfirm(true)} disabled={!!busy || !reason}
              className="rounded-lg border border-critical-300 px-4 py-1.5 text-sm font-medium text-critical-700 hover:bg-critical-50 disabled:opacity-50">
              {t('admin.scholars.control.closeFile')}
            </button>
          ) : (
            <span className="flex flex-wrap items-center gap-2 rounded-lg border border-critical-300 bg-critical-50 p-2"
              data-testid="close-confirm">
              <span className="text-sm font-medium text-critical-800">{t('admin.scholarship.orgReject.confirmTitle')}</span>
              <button type="button" onClick={() => setConfirm(false)} disabled={busy === 'close'}
                className="rounded-lg border px-3 py-1 text-sm text-ground-600 hover:bg-ground-50">
                {t('admin.scholarship.orgReject.back')}
              </button>
              <button type="button" onClick={close} disabled={busy === 'close'}
                className="rounded-lg bg-critical-fill px-3 py-1 text-sm font-medium text-critical-fill-ink hover:bg-critical-700 disabled:opacity-50">
                {busy === 'close' ? t('common.loading') : t('admin.scholars.control.closeFile')}
              </button>
            </span>
          )}
        </div>
      )}

      {error && <p className="text-xs text-critical-700" role="alert">{error}</p>}
    </section>
  )
}

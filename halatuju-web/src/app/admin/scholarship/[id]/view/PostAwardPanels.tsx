'use client'

/**
 * THE POST-AWARD PANELS, full width below the cockpit grid — the Conditional Bursary Award
 * Agreement's four signatures, the disbursement (tranche) ledger with its maintenance
 * sub-state, and the manual closure of a funded student's file.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import type { Dispatch, SetStateAction } from 'react'
import {
  isFunded,
  disbursementTone,
  actionsFor,
  totalReleased,
} from '@/lib/disbursement'
import { formatDate } from '@/lib/formatDate'
import type {
  AdminScholarshipDetail,
  AdminDisbursement,
  DisbursementAction,
  MaintenanceSubstate,
  ClosureReason,
} from '@/lib/admin-api'
import type { BursaryAgreement } from '@/lib/api'

import type { T } from './shared'

export function PostAwardPanels({
  app, t, busy, isSuper, canWrite,
  bursary, bursaryMsg, doCountersignBursary, doWitnessBursary,
  disbAmount, setDisbAmount, disbLabel, setDisbLabel, disbMsg,
  doScheduleTranche, doDisbursementAction, doSetSubstate,
  closeReason, setCloseReason, closeMsg, doClose,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  isSuper: boolean
  canWrite: boolean
  bursary: BursaryAgreement | null
  bursaryMsg: string
  doCountersignBursary: () => void
  doWitnessBursary: () => void
  disbAmount: string
  setDisbAmount: Dispatch<SetStateAction<string>>
  disbLabel: string
  setDisbLabel: Dispatch<SetStateAction<string>>
  disbMsg: string
  doScheduleTranche: () => void
  doDisbursementAction: (disbursementId: number, action: DisbursementAction) => void
  doSetSubstate: (substate: MaintenanceSubstate) => void
  closeReason: ClosureReason | ''
  setCloseReason: Dispatch<SetStateAction<ClosureReason | ''>>
  closeMsg: string
  doClose: () => void
}) {
  return (<>

      {/* ── Conditional Bursary Award Agreement (flag-gated; dark by default) ──
          Shown once the award has been accepted (the student + guarantor have
          signed in-session). The Foundation countersignature + the partner-org
          witness are recorded here. The admin detail GET doesn't carry the
          agreement, so the four states resolve from the action responses. */}
      {app.bursary_agreement_enabled && (app.status === 'awarded' || app.status === 'active' || app.status === 'maintenance') && (() => {
        // TD-144 FIXED: all four states come from the REAL loaded agreement (seeded from the
        // detail GET, refreshed by the action responses) — no optimistic default. No agreement
        // yet (awarded but the student hasn't signed) → every tick is correctly "–".
        const hasAgreement = !!bursary
        const studentDone = !!bursary?.student_signed_at
        const guarantorDone = !!bursary?.guarantor_signed_at
        const foundationDone = !!bursary?.foundation_signed_at
        const witnessDone = !!bursary?.witness_signed_at
        const stateRow = (label: string, done: boolean) => (
          <div className="flex items-center justify-between rounded-lg border border-ground-200 px-3 py-2">
            <span className="text-sm text-ground-700">{label}</span>
            <span className={done ? 'text-positive-700' : 'text-ground-300'} aria-hidden>
              {done ? '✓' : '–'}
            </span>
          </div>
        )
        return (
          <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold tracking-tight text-ground-900">
                {t('admin.scholarship.bursary.title')}
              </h2>
              {bursary?.status && (
                <span className="rounded-full border border-ground-200 px-2.5 py-0.5 text-xs font-medium text-ground-600">
                  {bursary.status}
                </span>
              )}
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {stateRow(t('admin.scholarship.bursary.student'), studentDone)}
              {stateRow(t('admin.scholarship.bursary.guarantor'), guarantorDone)}
              {stateRow(t('admin.scholarship.bursary.foundation'), foundationDone)}
              {stateRow(t('admin.scholarship.bursary.witness'), witnessDone)}
            </div>
            {!hasAgreement && (
              <p className="text-xs text-ground-500">{t('admin.scholarship.bursary.awaitingSignature')}</p>
            )}
            {bursaryMsg && <p className="text-xs text-caution-700">{bursaryMsg}</p>}
            <div className="flex flex-wrap items-center gap-2">
              {isSuper && (
                <button
                  type="button"
                  onClick={doCountersignBursary}
                  disabled={busy === 'bursary' || !hasAgreement || foundationDone}
                  className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm font-medium text-ground-700 hover:bg-ground-100 disabled:opacity-50"
                >
                  {t('admin.scholarship.bursary.countersign')}
                </button>
              )}
              <button
                type="button"
                onClick={doWitnessBursary}
                disabled={busy === 'bursary' || !hasAgreement || witnessDone}
                className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm font-medium text-ground-700 hover:bg-ground-100 disabled:opacity-50"
              >
                {t('admin.scholarship.bursary.witnessAction')}
              </button>
              {bursary?.pdf_url && (
                <a
                  href={bursary.pdf_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm font-medium text-ground-700 hover:bg-ground-100"
                >
                  {t('admin.scholarship.bursary.download')}
                </a>
              )}
            </div>
            <p className="text-xs text-ground-400">{t('admin.scholarship.bursary.note')}</p>
          </div>
        )
      })()}

      {/* ── Post-award S4: disbursement (tranche) ledger ──
          Money OUT to the student, paid in tranches. Shown once the student is funded
          (active / maintenance). Marking the FIRST tranche disbursed flips the
          application active → maintenance. Mock ledger — real toyyibPay is deferred (TD-075). */}
      {isFunded(app.status) && (() => {
        const rows = app.disbursements ?? []
        const released = totalReleased(rows)
        return (
          <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold tracking-tight text-ground-900">
                {t('admin.disbursement.title')}
              </h2>
              {released > 0 && (
                <span className="rounded-full border border-positive-200 bg-positive-50 px-2.5 py-0.5 text-xs font-medium text-positive-700">
                  {t('admin.disbursement.totalReleased')} RM{released.toLocaleString()}
                </span>
              )}
            </div>
            <p className="text-xs text-ground-400">{t('admin.disbursement.note')}</p>

            {/* S5: maintenance sub-state — only once funded into the recurring loop. */}
            {app.status === 'maintenance' && (
              <div className="rounded-lg border border-ground-100 bg-ground-50/60 p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-ground-600">{t('admin.maintenance.title')}</span>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    app.maintenance_substate === 'on_track' ? 'bg-positive-100 text-positive-700'
                    : app.maintenance_substate === 'probation' ? 'bg-caution-100 text-caution-700'
                    : app.maintenance_substate === 'on_hold' ? 'bg-critical-100 text-critical-700'
                    : 'bg-info-100 text-info-700'}`}>
                    {t(`admin.maintenance.substate.${app.maintenance_substate}`)}
                  </span>
                </div>
                {canWrite && (
                  <div className="flex flex-wrap gap-1.5">
                    {(['on_track', 'probation', 'on_hold', 'ready_to_close'] as const)
                      .filter((s) => s !== app.maintenance_substate)
                      .map((s) => (
                        <button key={s} type="button"
                          onClick={() => doSetSubstate(s)}
                          disabled={busy === 'disbursement'}
                          className="rounded-lg border border-ground-300 px-3 py-1 text-xs font-medium text-ground-700 hover:bg-ground-100 disabled:opacity-50">
                          {t(`admin.maintenance.action.${s}`)}
                        </button>
                      ))}
                  </div>
                )}
                {app.maintenance_substate === 'on_hold' && (
                  <p className="text-[11px] text-critical-600">{t('admin.maintenance.onHoldHint')}</p>
                )}
              </div>
            )}

            {rows.length === 0 ? (
              <p className="text-sm text-ground-400">{t('admin.disbursement.empty')}</p>
            ) : (
              <div className="space-y-2">
                {rows.map((d: AdminDisbursement) => {
                  const tone = disbursementTone(d.status)
                  const toneClass = tone === 'green' ? 'bg-positive-100 text-positive-700'
                    : tone === 'amber' ? 'bg-caution-100 text-caution-700'
                    : tone === 'red' ? 'bg-critical-100 text-critical-700'
                    : tone === 'grey' ? 'bg-ground-100 text-ground-600'
                    : 'bg-info-100 text-info-700'
                  return (
                    <div key={d.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-ground-100 p-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-ground-700">
                          {d.label || `${t('admin.disbursement.tranche')} ${d.sequence}`}
                        </span>
                        <span className="text-sm font-semibold text-ground-900">RM{Math.round(Number(d.amount)).toLocaleString()}</span>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${toneClass}`}>
                          {t(`admin.disbursement.status.${d.status}`)}
                        </span>
                      </div>
                      {canWrite && (
                        <div className="flex flex-wrap gap-1.5">
                          {actionsFor(d.status).map((action) => (
                            <button key={action} type="button"
                              onClick={() => doDisbursementAction(d.id, action)}
                              disabled={busy === 'disbursement'}
                              className="rounded-lg border border-ground-300 px-3 py-1 text-xs font-medium text-ground-700 hover:bg-ground-100 disabled:opacity-50">
                              {t(`admin.disbursement.action.${action}`)}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}

            {canWrite && (
              <div className="flex flex-wrap items-end gap-2 border-t pt-3">
                <div>
                  <label className="block text-[11px] font-medium text-ground-600 mb-1">{t('admin.disbursement.amountLabel')}</label>
                  <input type="number" min={1} step={50} value={disbAmount}
                    onChange={(e) => setDisbAmount(e.target.value)}
                    placeholder="500"
                    className="w-28 rounded-lg border px-3 py-1.5 text-sm" />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-ground-600 mb-1">{t('admin.disbursement.labelLabel')}</label>
                  <input type="text" value={disbLabel} maxLength={100}
                    onChange={(e) => setDisbLabel(e.target.value)}
                    placeholder={t('admin.disbursement.labelPlaceholder')}
                    className="w-40 rounded-lg border px-3 py-1.5 text-sm" />
                </div>
                <button type="button" onClick={doScheduleTranche}
                  disabled={busy === 'disbursement'}
                  className="rounded-lg bg-brand-fill px-4 py-1.5 text-sm font-medium text-brand-fill-ink disabled:opacity-50">
                  {t('admin.disbursement.schedule')}
                </button>
              </div>
            )}
            {disbMsg && <p className="text-xs text-caution-700">{disbMsg}</p>}
          </div>
        )
      })()}

      {/* ── Post-award S6: manual closure ──
          Close a funded student's file with a reason. Terminal. Shows the closed summary
          once closed (the graduation thank-you relay stays open after closure). */}
      {(app.status === 'active' || app.status === 'maintenance' || app.status === 'closed') && (
        <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">
            {t('admin.closure.title')}
          </h2>
          {app.status === 'closed' ? (
            <div className="space-y-1">
              <p className="flex items-center gap-1.5 text-sm text-ground-700">
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  app.closure_reason === 'graduated' || app.closure_reason === 'completed'
                    ? 'bg-positive-100 text-positive-700' : 'bg-ground-200 text-ground-600'}`}>
                  {t(`admin.closure.reason.${app.closure_reason}`)}
                </span>
              </p>
              <p className="text-xs text-ground-500">
                {t('admin.closure.closedBy')} {app.closed_by || '—'}
                {app.closed_at ? ` · ${formatDate(app.closed_at)}` : ''}
              </p>
            </div>
          ) : canWrite ? (
            <>
              <p className="text-xs text-ground-500">{t('admin.closure.note')}</p>
              {/* Offboarding checklist — informational guidance before closing. */}
              <ul className="list-disc ml-5 text-xs text-ground-500 space-y-0.5">
                {(['finalDisbursement', 'thankYou', 'records'] as const).map((k) => (
                  <li key={k}>{t(`admin.closure.checklist.${k}`)}</li>
                ))}
              </ul>
              <div className="flex flex-wrap items-end gap-2">
                <div>
                  <label className="block text-[11px] font-medium text-ground-600 mb-1">{t('admin.closure.reasonLabel')}</label>
                  <select value={closeReason}
                    onChange={(e) => setCloseReason(e.target.value as ClosureReason | '')}
                    className="rounded-lg border px-3 py-1.5 text-sm">
                    <option value="">{t('admin.closure.reasonUnset')}</option>
                    {(['graduated', 'completed', 'withdrawn', 'lapsed', 'terminated'] as const).map((r) => (
                      <option key={r} value={r}>{t(`admin.closure.reason.${r}`)}</option>
                    ))}
                  </select>
                </div>
                <button type="button" onClick={doClose}
                  disabled={busy === 'close' || !closeReason}
                  className="rounded-lg border border-critical-300 px-4 py-1.5 text-sm font-medium text-critical-700 hover:bg-critical-50 disabled:opacity-50">
                  {busy === 'close' ? t('common.loading') : t('admin.closure.close')}
                </button>
              </div>
              {closeMsg && <p className="text-xs text-caution-700">{closeMsg}</p>}
            </>
          ) : null}
        </div>
      )}

  </>)
}

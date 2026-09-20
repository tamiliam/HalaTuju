'use client'

/**
 * THE ORG-ADMIN REJECT — a three-step wizard (idle -> reason -> confirm), because unlike every
 * other decline this one is IMMEDIATE and IRREVERSIBLE — and, below it, the record of one once
 * made, which is the whole audit surface for that action.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import type { Dispatch, SetStateAction } from 'react'
import { canOrgReject } from '@/lib/officerCockpit'
import { formatDate } from '@/lib/formatDate'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import type { T, AdminRole } from './shared'

export function OrgRejectPanel({
  app, t, busy, isSuper, role,
  rejectStep, setRejectStep, rejectComments, setRejectComments, rejectErr,
  closeReject, doOrgReject,
}: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  isSuper: boolean
  role: AdminRole
  rejectStep: 'idle' | 'form' | 'confirm'
  setRejectStep: Dispatch<SetStateAction<'idle' | 'form' | 'confirm'>>
  rejectComments: string
  setRejectComments: Dispatch<SetStateAction<string>>
  rejectErr: string
  closeReject: () => void
  doOrgReject: () => void
}) {
  return (<>

      {/* ── Reject this student (org-admin) — takes the Assign card's slot at 'shortlisted'.
            Owner 2026-07-21: "rejection is a super feature; the org admin is the super of the
            organisation". Nothing is lost by the swap — a reviewer CANNOT be assigned at
            'shortlisted' anyway (services.is_assignable), so that box was inert here.

            KEEP IN SYNC with the server (lessons.md 2026-07-16 — the offer-set and the accept-set
            are one unit of change): role must match AdminOrgRejectView's super/org_admin guard,
            and the status must match services.ORG_REJECT_FROM. Rendering it anywhere else just
            produces a button that 403s or 400s. ─── */}
      {canOrgReject({ isSuper, role: role?.role, status: app.status }) && (
        <div className="rounded-2xl border border-critical-200 bg-ground-0 p-5 shadow-sm space-y-3">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">
            {t('admin.scholarship.orgReject.title')}
          </h2>

          {rejectStep === 'idle' && (
            <>
              <p className="text-xs text-ground-500">{t('admin.scholarship.orgReject.hint')}</p>
              <button type="button" onClick={() => setRejectStep('form')} disabled={!!busy}
                className="w-full rounded-lg border border-critical-300 px-3 py-2 text-sm font-medium
                           text-critical-700 hover:bg-critical-50 disabled:opacity-50">
                {t('admin.scholarship.orgReject.start')}
              </button>
            </>
          )}

          {rejectStep === 'form' && (
            <>
              <label htmlFor="org-reject-why" className="block text-sm font-medium text-ground-700">
                {t('admin.scholarship.orgReject.whyLabel')}
              </label>
              <textarea
                id="org-reject-why" rows={4} value={rejectComments} autoFocus
                onChange={(e) => setRejectComments(e.target.value)}
                placeholder={t('admin.scholarship.orgReject.whyPlaceholder')}
                className="w-full rounded-lg border px-3 py-2 text-sm"
              />
              <p className="text-xs text-ground-500">{t('admin.scholarship.orgReject.whyHint')}</p>
              <div className="flex gap-2">
                <button type="button" onClick={closeReject}
                  className="flex-1 rounded-lg border px-3 py-2 text-sm text-ground-600 hover:bg-ground-50">
                  {t('admin.scholarship.orgReject.cancel')}
                </button>
                {/* Mandatory reason enforced here AND at the endpoint (400 comments_required). */}
                <button type="button" onClick={() => setRejectStep('confirm')}
                  disabled={!rejectComments.trim()}
                  className="flex-1 rounded-lg bg-critical-fill px-3 py-2 text-sm font-medium text-critical-fill-ink
                             hover:bg-critical-700 disabled:opacity-40">
                  {t('admin.scholarship.orgReject.submit')}
                </button>
              </div>
            </>
          )}

          {rejectStep === 'confirm' && (
            <>
              <div className="rounded-lg border border-critical-300 bg-critical-50 p-3">
                <p className="text-sm font-medium text-critical-800">
                  {t('admin.scholarship.orgReject.confirmTitle')}
                </p>
                <p className="mt-1 text-xs text-critical-700">
                  {t('admin.scholarship.orgReject.confirmBody')}
                </p>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => setRejectStep('form')} disabled={!!busy}
                  className="flex-1 rounded-lg border px-3 py-2 text-sm text-ground-600 hover:bg-ground-50">
                  {t('admin.scholarship.orgReject.back')}
                </button>
                <button type="button" onClick={doOrgReject} disabled={!!busy}
                  className="flex-1 rounded-lg bg-critical-fill px-3 py-2 text-sm font-medium text-critical-fill-ink
                             hover:bg-critical-700 disabled:opacity-50">
                  {busy === 'orgReject' ? t('admin.scholarship.orgReject.running')
                    : t('admin.scholarship.orgReject.confirmYes')}
                </button>
              </div>
            </>
          )}

          {rejectErr && <p className="text-sm text-critical-600">{rejectErr}</p>}
        </div>
      )}

      {/* The record of an org-admin reject, once made. The reason lives ONLY here (it is never
          emailed), so this is the whole audit surface for an irreversible action. */}
      {app.status === 'rejected' && app.rejection_category === 'incomplete' && app.rejection_comments && (
        <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">
            {t('admin.scholarship.orgReject.recordTitle')}
          </h2>
          <p className="whitespace-pre-wrap text-sm text-ground-700">{app.rejection_comments}</p>
          <p className="text-xs text-ground-400">
            {app.rejected_by_name || app.rejected_by || '—'}
            {app.rejected_at ? ` · ${formatDate(app.rejected_at)}` : ''}
          </p>
        </div>
      )}

  </>)
}

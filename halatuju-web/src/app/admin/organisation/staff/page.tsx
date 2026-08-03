'use client'

import { useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { byCategory } from '@/lib/adminStaff'
import { outstanding } from '@/lib/invitations'
import {
  MessageBanner, PageHeader, StaffTable, inputCls, useStaffAdmin,
} from '@/components/admin/StaffAdmin'
import OutstandingInvitations from '@/components/admin/OutstandingInvitations'

type StaffRole = 'reviewer' | 'admin' | 'qc' | 'finance'
const STAFF_ROLES: StaffRole[] = ['reviewer', 'admin', 'qc', 'finance']

/**
 * Organisation → **Invitations**. Who was asked to join, and who is here now.
 *
 * Renamed from "Staff" on 2026-08-03: reviewers moved to their own page in request #10, and what
 * was left is the asking. The page leads with the invitations still waiting for an answer — the
 * question the old screen structurally could not answer, because an invitation was not a record
 * and every row read "Active" whether somebody had worked here a year or never once signed in.
 *
 * Below that, the people, in the owner's two categories: REVIEWERS (reviewer, qc) and ADMINS
 * (admin, org_admin, finance). Same category, different permissions — the permissions stay where
 * they live; `adminStaff.categoryOf` is presentation only.
 *
 * ⚠ PLATFORM roles never appear here: the super, and the platform-level **Referral Partner**
 * (`partner`), which is the HalaTuju course selector's relationship and NOT the organisation-level
 * Source Partner. See docs/decisions.md, 2026-08-03.
 *
 * Only super + org_admin may invite or revoke; Admin-General and Finance see it read-only
 * (role matrix, 2026-07-15 / 2026-07-23).
 */
export default function OrganisationStaffPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = effectiveRole(role)
  const canManage = r === 'super' || r === 'org_admin'
  const mayView = canAccess('/admin/organisation/staff', r)

  const { admins, message, busy, busyId, invite, resend, toggle, soleOrgAdmin } =
    useStaffAdmin(token)

  const [sRole, setSRole] = useState<StaffRole>('reviewer')
  const [sName, setSName] = useState('')
  const [sEmail, setSEmail] = useState('')
  // ⚠ Somebody with an unanswered invitation belongs to the WORKLIST, not to the roster — they
  // appear once, at the top, until they arrive. Listing them in both would put the same person on
  // screen twice and quietly inflate "Reviewers (13)" with people who have never signed in.
  const waiting = outstanding(admins)
  const waitingIds = new Set(waiting.map((a) => a.id))
  const groups = byCategory(admins.filter((a) => !waitingIds.has(a.id)))

  if (role && !mayView) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    // No org field — the backend forces the owning org (org_admin → own org; super → org #1).
    if (await invite({ email: sEmail, name: sName, role: sRole })) { setSName(''); setSEmail('') }
  }

  return (
    <div className="max-w-4xl">
      <PageHeader title={t('admin.invitations.title')} subtitle={t('admin.invitations.subtitle')} />
      <MessageBanner message={message} />

      {canManage && (
        <form onSubmit={submit} className="mb-6 space-y-4 rounded-xl border bg-white p-6 shadow-sm">
          <div>
            <p className="mb-2 text-sm font-semibold text-gray-900">{t('admin.inviteAs')}</p>
            <div className="grid max-w-md grid-cols-2 gap-2 sm:grid-cols-4">
              {STAFF_ROLES.map((rl) => (
                <button key={rl} type="button" onClick={() => setSRole(rl)}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                    sRole === rl ? 'border-primary-600 bg-primary-600 text-white'
                                 : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}`}>
                  {t(`admin.administration.staffRole.${rl}`)}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <input className={inputCls} placeholder={t('admin.name')} value={sName}
              onChange={(e) => setSName(e.target.value)} required />
            <input className={inputCls} type="email" placeholder={t('admin.emailLabel')} value={sEmail}
              onChange={(e) => setSEmail(e.target.value)} required />
          </div>
          <button type="submit" disabled={busy}
            className="rounded-lg bg-primary-600 px-6 py-2.5 font-medium text-white hover:bg-primary-700 disabled:opacity-50">
            {t('admin.sendInvite')}
          </button>
        </form>
      )}

      {/* The worklist first. It is the question the old screen could not answer. */}
      <h2 className="mb-2 text-sm font-semibold text-gray-900">
        {t('admin.invitations.outstandingHeading')}
      </h2>
      <OutstandingInvitations
        rows={waiting}
        canAct={canManage}
        busyId={busyId}
        onResend={canManage ? resend : undefined}
      />

      {/* Then the people, in the owner's two categories. */}
      {(['reviewers', 'admins'] as const).map((cat) => {
        const rows = groups[cat]
        if (rows.length === 0) return null
        return (
          <div key={cat} className="mt-8">
            <h2 className="mb-2 text-sm font-semibold text-gray-900">
              {t(`admin.invitations.category.${cat}`)}{' '}
              <span className="font-normal text-gray-400">({rows.length})</span>
            </h2>
            <StaffTable
              rows={rows}
              canAct={canManage}
              busyId={busyId}
              onResend={canManage ? resend : undefined}
              onToggle={canManage ? toggle : undefined}
              soleOrgAdmin={soleOrgAdmin}
            />
          </div>
        )
      })}
      {!canManage && (
        <p className="mt-3 text-sm text-gray-500">{t('admin.administration.viewOnlyNote')}</p>
      )}
    </div>
  )
}

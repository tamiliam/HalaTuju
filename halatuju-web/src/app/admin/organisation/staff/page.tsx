'use client'

import { useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { programmeStaff } from '@/lib/adminStaff'
import {
  MessageBanner, PageHeader, StaffTable, inputCls, useStaffAdmin,
} from '@/components/admin/StaffAdmin'

type StaffRole = 'reviewer' | 'admin' | 'qc' | 'finance'
const STAFF_ROLES: StaffRole[] = ['reviewer', 'admin', 'qc', 'finance']

/**
 * Organisation → Staff. Who can act inside this organisation, and what each may do.
 *
 * The table shows PROGRAMME roles only (`lib/adminStaff.programmeStaff`): the platform super
 * and referral partners belong to the platform world and never appear inside an organisation's
 * staff list. Only super + org_admin may invite or revoke; Admin-General and Finance see the
 * same table read-only (role matrix, 2026-07-15 / 2026-07-23).
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

  if (role && !mayView) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    // No org field — the backend forces the owning org (org_admin → own org; super → org #1).
    if (await invite({ email: sEmail, name: sName, role: sRole })) { setSName(''); setSEmail('') }
  }

  return (
    <div className="max-w-4xl">
      <PageHeader title={t('admin.nav.staff')} subtitle={t('admin.orgPage.staffSub')} />
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

      <StaffTable
        rows={programmeStaff(admins)}
        canAct={canManage}
        busyId={busyId}
        onResend={canManage ? resend : undefined}
        onToggle={canManage ? toggle : undefined}
        soleOrgAdmin={soleOrgAdmin}
      />
      {!canManage && (
        <p className="mt-3 text-sm text-gray-500">{t('admin.administration.viewOnlyNote')}</p>
      )}
    </div>
  )
}

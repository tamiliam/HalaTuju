'use client'

import { useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { tenantAdmins } from '@/lib/adminStaff'
import {
  MessageBanner, PageHeader, StaffTable, inputCls, useStaffAdmin,
} from '@/components/admin/StaffAdmin'

/**
 * Platform → Organisations. The tenants HalaTuju runs, and the org_admin who leads each.
 *
 * Super only, and deliberately so: creating a tenant and appointing its org_admin are withheld
 * from every organisation role (role matrix, "withheld from ALL organisation roles"). Inviting
 * an `org_admin` with a new organisation is what brings a tenant into existence.
 */
export default function OrganisationsPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const mayView = canAccess('/admin/organisations', effectiveRole(role))

  const { admins, message, busy, busyId, invite, resend, toggle, soleOrgAdmin } =
    useStaffAdmin(token)

  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [adminName, setAdminName] = useState('')
  const [adminEmail, setAdminEmail] = useState('')

  if (role && !mayView) return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const ok = await invite({
      email: adminEmail, name: adminName, role: 'org_admin',
      new_org_name: name, new_org_code: code,
    })
    if (ok) { setName(''); setCode(''); setAdminName(''); setAdminEmail('') }
  }

  return (
    <div className="max-w-4xl">
      <PageHeader title={t('admin.nav.organisations')} subtitle={t('admin.organisations.sub')} />
      <MessageBanner message={message} />

      <form onSubmit={submit} className="mb-6 space-y-4 rounded-xl border bg-white p-6 shadow-sm">
        <p className="text-sm text-gray-500">{t('admin.administration.addTenantHelp')}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <input className={inputCls} placeholder={t('admin.administration.tenantName')} value={name}
            onChange={(e) => setName(e.target.value)} required />
          <input className={inputCls} placeholder={t('admin.urlCode')} value={code} required
            onChange={(e) => setCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} />
          <input className={inputCls} placeholder={t('admin.administration.tenantAdminName')} value={adminName}
            onChange={(e) => setAdminName(e.target.value)} required />
          <input className={inputCls} type="email" placeholder={t('admin.administration.tenantAdminEmail')}
            value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} required />
        </div>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-primary-600 px-6 py-2.5 font-medium text-white hover:bg-primary-700 disabled:opacity-50">
          {t('admin.administration.createTenant')}
        </button>
      </form>

      <StaffTable rows={tenantAdmins(admins)} showOrg busyId={busyId}
        onResend={resend} onToggle={toggle} soleOrgAdmin={soleOrgAdmin} />
    </div>
  )
}

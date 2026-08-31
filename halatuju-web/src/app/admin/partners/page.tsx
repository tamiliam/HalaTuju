'use client'

import { useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { referralPartners } from '@/lib/adminStaff'
import {
  MessageBanner, PageHeader, StaffTable, inputCls, useStaffAdmin,
} from '@/components/admin/StaffAdmin'

/**
 * Platform → Referral partners. The roadshow / referral organisations that send students to the
 * course selector, and their representatives.
 *
 * A PLATFORM concept, not an organisation one — a referral org is an attribution relationship,
 * never an access scope (`docs/build-for-tenancy-conventions.md`). That is why this sits beside
 * Organisations rather than inside one, and why a `partner` login reaches the course-selector
 * pages and nothing of any tenant's.
 */
export default function ReferralPartnersPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const mayView = canAccess('/admin/partners', effectiveRole(role))

  const { admins, orgs, message, busy, busyId, invite, resend, toggle } =
    useStaffAdmin(token, true)

  const [mode, setMode] = useState<'existing' | 'new'>('existing')
  const [orgId, setOrgId] = useState<number | ''>('')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [newName, setNewName] = useState('')
  const [newCode, setNewCode] = useState('')

  if (role && !mayView) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const data: Parameters<typeof invite>[0] = { email, name, role: 'partner' }
    if (mode === 'existing' && orgId) data.org_id = Number(orgId)
    else if (mode === 'new') { data.new_org_name = newName; data.new_org_code = newCode }
    if (await invite(data)) {
      setName(''); setEmail(''); setOrgId(''); setNewName(''); setNewCode('')
    }
  }

  return (
    <div className="max-w-4xl">
      <PageHeader title={t('admin.nav.referralPartners')} subtitle={t('admin.partners.sub')} />
      <MessageBanner message={message} />

      <form onSubmit={submit} className="mb-6 space-y-4 rounded-xl border bg-ground-0 p-6 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-2">
          <input className={inputCls} placeholder={t('admin.name')} value={name}
            onChange={(e) => setName(e.target.value)} required />
          <input className={inputCls} type="email" placeholder={t('admin.emailLabel')} value={email}
            onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" checked={mode === 'existing'} onChange={() => setMode('existing')} />
            {t('admin.existing')}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" checked={mode === 'new'} onChange={() => setMode('new')} />
            {t('admin.newOrganisation')}
          </label>
        </div>
        {mode === 'existing' ? (
          <select className={inputCls} value={orgId}
            onChange={(e) => setOrgId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">{t('admin.selectOrg')}</option>
            {orgs.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.code})</option>)}
          </select>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            <input className={inputCls} placeholder={t('admin.orgName')} value={newName}
              onChange={(e) => setNewName(e.target.value)} />
            <input className={inputCls} placeholder={t('admin.urlCode')} value={newCode}
              onChange={(e) => setNewCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} />
          </div>
        )}
        <button type="submit" disabled={busy}
          className="rounded-lg bg-primary-600 px-6 py-2.5 font-medium text-white hover:bg-primary-700 disabled:opacity-50">
          {t('admin.sendInvite')}
        </button>
      </form>

      <StaffTable rows={referralPartners(admins)} showOrg busyId={busyId}
        onResend={resend} onToggle={toggle} />
    </div>
  )
}

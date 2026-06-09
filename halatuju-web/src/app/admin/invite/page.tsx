'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { getOrgs, inviteAdmin, getAdmins, revokeAdmin, type OrgItem, type AdminItem } from '@/lib/admin-api'
import { useT } from '@/lib/i18n'

type InviteRole = 'admin' | 'partner' | 'reviewer'
const INVITE_ROLES: InviteRole[] = ['admin', 'partner', 'reviewer']

export default function AdminInvitePage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const [orgs, setOrgs] = useState<OrgItem[]>([])
  const [orgMode, setOrgMode] = useState<'existing' | 'new'>('existing')
  const [selectedOrgId, setSelectedOrgId] = useState<number | ''>('')
  const [newOrgName, setNewOrgName] = useState('')
  const [newOrgCode, setNewOrgCode] = useState('')
  const [contactPerson, setContactPerson] = useState('')
  const [orgPhone, setOrgPhone] = useState('')
  const [adminName, setAdminName] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [adminRole, setAdminRole] = useState<InviteRole>('reviewer')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [admins, setAdmins] = useState<AdminItem[]>([])
  const [revoking, setRevoking] = useState<number | null>(null)

  const loadAdmins = () => {
    if (token) getAdmins({ token }).then((data) => setAdmins(data.admins)).catch(() => {})
  }

  useEffect(() => {
    if (token) {
      getOrgs({ token }).then((data) => setOrgs(data.orgs)).catch(() => {})
      loadAdmins()
    }
  }, [token])

  // Only a super admin can invite (admin is read-only for now).
  if (!role?.is_super_admin) {
    return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const needsOrg = adminRole === 'partner'   // organisation applies only to a partner

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)
    try {
      const data: Parameters<typeof inviteAdmin>[0] = { email: adminEmail, name: adminName, role: adminRole }
      if (needsOrg) {
        if (orgMode === 'existing' && selectedOrgId) {
          data.org_id = Number(selectedOrgId)
        } else if (orgMode === 'new' && newOrgName && newOrgCode) {
          data.new_org_name = newOrgName
          data.new_org_code = newOrgCode
          data.contact_person = contactPerson
          data.org_phone = orgPhone
        }
      }
      const result = await inviteAdmin(data, { token: token! })
      setMessage({ type: 'success', text: result.message })
      setAdminName(''); setAdminEmail('')
      setSelectedOrgId(''); setNewOrgName(''); setNewOrgCode(''); setContactPerson(''); setOrgPhone('')
      if (token) {
        getOrgs({ token }).then((d) => setOrgs(d.orgs)).catch(() => {})
        loadAdmins()
      }
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : t('apiErrors.inviteEmailFailed') })
    }
    setLoading(false)
  }

  const inputCls = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
  const roleBadge = (rl: string) =>
    rl === 'super' ? 'bg-purple-100 text-purple-700'
    : rl === 'admin' ? 'bg-indigo-100 text-indigo-700'
    : rl === 'partner' ? 'bg-teal-100 text-teal-700'
    : rl === 'reviewer' ? 'bg-blue-100 text-blue-700'
    : 'bg-gray-100 text-gray-600'

  const canSubmit = !loading && !!adminName.trim() && !!adminEmail.trim() && (!needsOrg ||
    (orgMode === 'existing' ? !!selectedOrgId : (!!newOrgName.trim() && !!newOrgCode.trim())))

  return (
    <div className="max-w-4xl">
      {/* Title follows the chosen role: Invite an Admin / a Partner / a Reviewer */}
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t(`admin.inviteHeading.${adminRole}`)}</h1>

      {message && (
        <div className={`rounded-lg p-4 mb-6 ${message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-600'}`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-xl border shadow-sm p-6 space-y-6">
        {/* 1) Role first */}
        <div>
          <p className="text-sm font-semibold text-gray-900 mb-2">{t('admin.inviteAs')}</p>
          <div className="grid grid-cols-3 gap-2 max-w-md">
            {INVITE_ROLES.map((rl) => (
              <button key={rl} type="button" onClick={() => setAdminRole(rl)}
                className={`px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                  adminRole === rl ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}>
                {t(`admin.role.${rl}`)}
              </button>
            ))}
          </div>
          <div className="mt-3 flex items-start gap-2 rounded-lg bg-blue-50 border border-blue-100 px-3 py-2 text-sm text-blue-800">
            <span aria-hidden>ℹ️</span>{t(`admin.roleDesc.${adminRole}`)}
          </div>
        </div>

        {/* 2) Name + email (2-up on desktop) */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm text-gray-600 mb-1">{t('admin.name')}</label>
            <input type="text" value={adminName} onChange={(e) => setAdminName(e.target.value)}
              placeholder={t('admin.adminName')} className={inputCls} required />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">{t('admin.emailLabel')}</label>
            <input type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)}
              placeholder={t('admin.adminEmail')} className={inputCls} required />
          </div>
        </div>

        {/* 3) Organisation — Partner only */}
        {needsOrg && (
          <fieldset className="space-y-3 border-t pt-5">
            <legend className="text-sm font-semibold text-gray-900">{t('admin.organisation')}</legend>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" checked={orgMode === 'existing'} onChange={() => setOrgMode('existing')} />
                {t('admin.existing')}
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" checked={orgMode === 'new'} onChange={() => setOrgMode('new')} />
                {t('admin.newOrganisation')}
              </label>
            </div>
            {orgMode === 'existing' ? (
              <select value={selectedOrgId} onChange={(e) => setSelectedOrgId(e.target.value ? Number(e.target.value) : '')} className={inputCls}>
                <option value="">{t('admin.selectOrg')}</option>
                {orgs.map((org) => <option key={org.id} value={org.id}>{org.name} ({org.code})</option>)}
              </select>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                <input type="text" value={newOrgName} onChange={(e) => setNewOrgName(e.target.value)} placeholder={t('admin.orgName')} className={inputCls} />
                <input type="text" value={newOrgCode} onChange={(e) => setNewOrgCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} placeholder={t('admin.urlCode')} className={inputCls} />
                <input type="text" value={contactPerson} onChange={(e) => setContactPerson(e.target.value)} placeholder={t('admin.contactPerson')} className={inputCls} />
                <input type="text" value={orgPhone} onChange={(e) => setOrgPhone(e.target.value)} placeholder={t('admin.phonePlaceholder')} className={inputCls} />
              </div>
            )}
          </fieldset>
        )}

        <button type="submit" disabled={!canSubmit}
          className="w-full sm:w-auto px-8 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50">
          {loading ? t('admin.sendingInvite') : t('admin.sendInvite')}
        </button>
      </form>

      {/* Team members */}
      <div className="mt-10">
        <h2 className="text-xl font-bold text-gray-900 mb-4">{t('admin.adminList')}</h2>
        <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.nameHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.emailHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.orgHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.roleHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.statusHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.actionHeader')}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {admins.map((a) => (
                <tr key={a.id}>
                  <td className="px-4 py-3">{a.name}</td>
                  <td className="px-4 py-3 text-gray-500">{a.email}</td>
                  <td className="px-4 py-3">{a.org_name || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${roleBadge(a.role)}`}>{t(`admin.role.${a.role}`)}</span>
                  </td>
                  <td className="px-4 py-3">
                    {a.is_active
                      ? <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">{t('admin.active')}</span>
                      : <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-600">{t('admin.revoked')}</span>}
                  </td>
                  <td className="px-4 py-3">
                    {!a.is_super_admin && (
                      <button disabled={revoking === a.id}
                        onClick={async () => {
                          setRevoking(a.id)
                          try {
                            await revokeAdmin(a.id, a.is_active ? 'revoke' : 'restore', { token: token! })
                            loadAdmins()
                          } catch (err) {
                            setMessage({ type: 'error', text: err instanceof Error ? err.message : t('admin.actionFailed') })
                          }
                          setRevoking(null)
                        }}
                        className={`text-xs font-medium ${a.is_active ? 'text-red-600 hover:text-red-800' : 'text-blue-600 hover:text-blue-800'} disabled:opacity-50`}>
                        {a.is_active ? t('admin.revoke') : t('admin.restore')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {admins.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-6 text-center text-gray-400">{t('admin.noAdmins')}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

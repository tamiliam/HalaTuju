'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { getOrgs, inviteAdmin, getAdmins, revokeAdmin, type OrgItem, type AdminItem } from '@/lib/admin-api'
import { useT } from '@/lib/i18n'

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
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [admins, setAdmins] = useState<AdminItem[]>([])
  const [revoking, setRevoking] = useState<number | null>(null)

  const loadAdmins = () => {
    if (token) {
      getAdmins({ token }).then((data) => setAdmins(data.admins)).catch(() => {})
    }
  }

  useEffect(() => {
    if (token) {
      getOrgs({ token }).then((data) => setOrgs(data.orgs)).catch(() => {})
      loadAdmins()
    }
  }, [token])

  if (!role?.is_super_admin) {
    return <p className="text-red-600">{t('apiErrors.superAdminRequired')}</p>
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage(null)

    try {
      const data: Parameters<typeof inviteAdmin>[0] = {
        email: adminEmail,
        name: adminName,
      }
      if (orgMode === 'existing' && selectedOrgId) {
        data.org_id = Number(selectedOrgId)
      } else if (orgMode === 'new' && newOrgName && newOrgCode) {
        data.new_org_name = newOrgName
        data.new_org_code = newOrgCode
        data.contact_person = contactPerson
        data.org_phone = orgPhone
      }

      const result = await inviteAdmin(data, { token: token! })
      setMessage({ type: 'success', text: result.message })

      // Reset form
      setAdminName('')
      setAdminEmail('')
      setSelectedOrgId('')
      setNewOrgName('')
      setNewOrgCode('')
      setContactPerson('')
      setOrgPhone('')

      // Refresh org list and admin list
      if (token) {
        getOrgs({ token }).then((data) => setOrgs(data.orgs)).catch(() => {})
        loadAdmins()
      }
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : t('apiErrors.inviteEmailFailed') })
    }

    setLoading(false)
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('admin.inviteTitle')}</h1>

      {message && (
        <div className={`rounded-lg p-4 mb-6 ${message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-600'}`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Organisation */}
        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold text-gray-900">{t('admin.organisation')}</legend>
          <div className="flex gap-4">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={orgMode === 'existing'}
                onChange={() => setOrgMode('existing')}
              />
              <span className="text-sm">{t('admin.existing')}</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={orgMode === 'new'}
                onChange={() => setOrgMode('new')}
              />
              <span className="text-sm">{t('admin.newOrganisation')}</span>
            </label>
          </div>

          {orgMode === 'existing' ? (
            <select
              value={selectedOrgId}
              onChange={(e) => setSelectedOrgId(e.target.value ? Number(e.target.value) : '')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="">{t('admin.selectOrg')}</option>
              {orgs.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name} ({org.code})
                </option>
              ))}
            </select>
          ) : (
            <div className="space-y-3">
              <input
                type="text"
                value={newOrgName}
                onChange={(e) => setNewOrgName(e.target.value)}
                placeholder={t('admin.orgName')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                required={orgMode === 'new'}
              />
              <input
                type="text"
                value={newOrgCode}
                onChange={(e) => setNewOrgCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                placeholder={t('admin.urlCode')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                required={orgMode === 'new'}
              />
              <input
                type="text"
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                placeholder={t('admin.contactPerson')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
              <input
                type="text"
                value={orgPhone}
                onChange={(e) => setOrgPhone(e.target.value)}
                placeholder={t('admin.phonePlaceholder')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          )}
        </fieldset>

        {/* Admin details */}
        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold text-gray-900">{t('admin.adminDetails')}</legend>
          <input
            type="text"
            value={adminName}
            onChange={(e) => setAdminName(e.target.value)}
            placeholder={t('admin.adminName')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            required
          />
          <input
            type="email"
            value={adminEmail}
            onChange={(e) => setAdminEmail(e.target.value)}
            placeholder={t('admin.adminEmail')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            required
          />
        </fieldset>

        <button
          type="submit"
          disabled={loading || !adminName || !adminEmail}
          className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {loading ? t('admin.sendingInvite') : t('admin.sendInvite')}
        </button>
      </form>

      {/* Admin list */}
      <div className="mt-10">
        <h2 className="text-xl font-bold text-gray-900 mb-4">{t('admin.adminList')}</h2>
        <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.nameHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.emailHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.orgHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.statusHeader')}</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">{t('admin.actionHeader')}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {admins.map((a) => (
                <tr key={a.id}>
                  <td className="px-4 py-3">{a.name}</td>
                  <td className="px-4 py-3 text-gray-500">{a.email}</td>
                  <td className="px-4 py-3">{a.org_name || t('admin.superAdmin')}</td>
                  <td className="px-4 py-3">
                    {a.is_active ? (
                      <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">{t('admin.active')}</span>
                    ) : (
                      <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-600">{t('admin.revoked')}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {!a.is_super_admin && (
                      <button
                        disabled={revoking === a.id}
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
                        className={`text-xs font-medium ${a.is_active ? 'text-red-600 hover:text-red-800' : 'text-blue-600 hover:text-blue-800'} disabled:opacity-50`}
                      >
                        {a.is_active ? t('admin.revoke') : t('admin.restore')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {admins.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-gray-400">{t('admin.noAdmins')}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

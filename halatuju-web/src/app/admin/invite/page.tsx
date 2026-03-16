'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { getOrgs, inviteAdmin, type OrgItem } from '@/lib/admin-api'

export default function AdminInvitePage() {
  const { token, role } = useAdminAuth()
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

  useEffect(() => {
    if (token) {
      getOrgs({ token }).then((data) => setOrgs(data.orgs)).catch(() => {})
    }
  }, [token])

  if (!role?.is_super_admin) {
    return <p className="text-red-600">Super admin access required.</p>
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

      // Refresh org list
      if (token) {
        getOrgs({ token }).then((data) => setOrgs(data.orgs)).catch(() => {})
      }
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to send invite' })
    }

    setLoading(false)
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Invite Partner Admin</h1>

      {message && (
        <div className={`rounded-lg p-4 mb-6 ${message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-600'}`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Organisation */}
        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold text-gray-900">Organisation</legend>
          <div className="flex gap-4">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={orgMode === 'existing'}
                onChange={() => setOrgMode('existing')}
              />
              <span className="text-sm">Existing</span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                checked={orgMode === 'new'}
                onChange={() => setOrgMode('new')}
              />
              <span className="text-sm">New Organisation</span>
            </label>
          </div>

          {orgMode === 'existing' ? (
            <select
              value={selectedOrgId}
              onChange={(e) => setSelectedOrgId(e.target.value ? Number(e.target.value) : '')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="">Select organisation...</option>
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
                placeholder="Organisation name"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                required={orgMode === 'new'}
              />
              <input
                type="text"
                value={newOrgCode}
                onChange={(e) => setNewOrgCode(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                placeholder="URL code (e.g. cumig)"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                required={orgMode === 'new'}
              />
              <input
                type="text"
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                placeholder="Contact person (optional)"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
              <input
                type="text"
                value={orgPhone}
                onChange={(e) => setOrgPhone(e.target.value)}
                placeholder="Phone (optional)"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          )}
        </fieldset>

        {/* Admin details */}
        <fieldset className="space-y-3">
          <legend className="text-sm font-semibold text-gray-900">Admin Details</legend>
          <input
            type="text"
            value={adminName}
            onChange={(e) => setAdminName(e.target.value)}
            placeholder="Admin name"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            required
          />
          <input
            type="email"
            value={adminEmail}
            onChange={(e) => setAdminEmail(e.target.value)}
            placeholder="Admin email"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg"
            required
          />
        </fieldset>

        <button
          type="submit"
          disabled={loading || !adminName || !adminEmail}
          className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {loading ? 'Sending invite...' : 'Send Invite'}
        </button>
      </form>
    </div>
  )
}

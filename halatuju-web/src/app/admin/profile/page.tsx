'use client'

import { useState, useEffect } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { getAdminProfile, updateAdminProfile, type AdminProfile } from '@/lib/admin-api'
import { useT } from '@/lib/i18n'

export default function AdminProfilePage() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [profile, setProfile] = useState<AdminProfile | null>(null)
  const [name, setName] = useState('')
  const [contactPerson, setContactPerson] = useState('')
  const [orgPhone, setOrgPhone] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (!token) return
    getAdminProfile({ token }).then((data) => {
      setProfile(data)
      setName(data.name)
      setContactPerson(data.org_contact_person || '')
      setOrgPhone(data.org_phone || '')
    }).catch(() => {})
  }, [token])

  if (!profile) {
    return <div className="mt-8 text-center text-gray-500">{t('common.loading')}</div>
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      const data: Record<string, string> = { name }
      if (profile.org_name) {
        data.org_contact_person = contactPerson
        data.org_phone = orgPhone
      }
      await updateAdminProfile(data, { token: token! })
      setMessage({ type: 'success', text: t('admin.profileUpdated') })
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : t('admin.profileUpdateFailed') })
    }
    setSaving(false)
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">{t('admin.profileTitle')}</h1>

      {message && (
        <div className={`rounded-lg p-4 mb-6 ${message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-600'}`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white rounded-lg p-6 shadow-sm border space-y-4">
          <h2 className="font-semibold">{t('admin.yourInfo')}</h2>
          <div>
            <label className="block text-sm text-gray-600 mb-1">{t('admin.name')}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">{t('admin.emailLabel')}</label>
            <p className="text-sm text-gray-800 px-3 py-2 bg-gray-50 rounded-lg">{profile.email}</p>
          </div>
        </div>

        {profile.org_name && (
          <div className="bg-white rounded-lg p-6 shadow-sm border space-y-4">
            <h2 className="font-semibold">{t('admin.orgInfo', { org: profile.org_name })}</h2>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t('admin.contactPersonLabel')}</label>
              <input
                type="text"
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t('admin.orgPhone')}</label>
              <input
                type="text"
                value={orgPhone}
                onChange={(e) => setOrgPhone(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={saving || !name}
          className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
        >
          {saving ? t('admin.saving') : t('common.save')}
        </button>
      </form>
    </div>
  )
}

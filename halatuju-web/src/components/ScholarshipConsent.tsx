'use client'

import { useState, useEffect } from 'react'
import { useT } from '@/lib/i18n'
import { getConsentStatus, recordConsent, type ConsentStatus } from '@/lib/api'

export default function ScholarshipConsent({
  token,
  locale,
}: {
  token: string | null
  locale: string
}) {
  const { t } = useT()
  const [status, setStatus] = useState<ConsentStatus | null>(null)
  const [checked, setChecked] = useState(false)
  const [guardianName, setGuardianName] = useState('')
  const [guardianRel, setGuardianRel] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    getConsentStatus({ token }).then(setStatus).catch(() => { /* ignore */ })
  }, [token])

  const isMinor = !!status?.is_minor
  const hasActive = !!status?.consents?.some((c) => c.is_active)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setSaving(true)
    setError(null)
    try {
      await recordConsent({
        locale,
        granted_by: isMinor ? 'guardian' : 'self',
        guardian_name: isMinor ? guardianName : '',
        guardian_relationship: isMinor ? guardianRel : '',
      }, { token })
      setStatus(await getConsentStatus({ token }))
    } catch {
      setError(t('scholarship.consent.error'))
    } finally {
      setSaving(false)
    }
  }

  if (hasActive) {
    return <p className="text-green-700 text-sm">{t('scholarship.consent.given')}</p>
  }

  const guardianIncomplete = isMinor && (!guardianName.trim() || !guardianRel.trim())

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="bg-gray-50 border rounded-lg p-3 text-sm text-gray-700 max-h-40 overflow-y-auto">
        <p className="text-xs font-medium text-amber-700 mb-1">{t('scholarship.consent.draftNotice')}</p>
        {t('scholarship.consent.text')}
      </div>
      {isMinor && (
        <>
          <p className="text-sm text-gray-700">{t('scholarship.consent.guardianNotice')}</p>
          <input
            className="input" placeholder={t('scholarship.consent.guardianName')}
            value={guardianName} onChange={(e) => setGuardianName(e.target.value)}
          />
          <input
            className="input" placeholder={t('scholarship.consent.guardianRelationship')}
            value={guardianRel} onChange={(e) => setGuardianRel(e.target.value)}
          />
        </>
      )}
      <label className="flex items-start gap-2 text-sm text-gray-700">
        <input type="checkbox" className="mt-1" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
        {isMinor ? t('scholarship.consent.agreeGuardian') : t('scholarship.consent.agree')}
      </label>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <button
        type="submit"
        disabled={saving || !checked || guardianIncomplete}
        className="btn-primary disabled:opacity-50"
      >
        {saving ? t('scholarship.consent.saving') : t('scholarship.consent.submit')}
      </button>
    </form>
  )
}

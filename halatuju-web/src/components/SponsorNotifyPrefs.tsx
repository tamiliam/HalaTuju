'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { patchSponsorNotifications } from '@/lib/api'

/** F3: the sponsor's email cadence (realtime | weekly | off). Saves then refreshes the account. */
export default function SponsorNotifyPrefs() {
  const { t } = useT()
  const { token, account, refreshAccount } = useSponsorAuth()
  const [saving, setSaving] = useState(false)

  const change = async (freq: 'realtime' | 'weekly' | 'off') => {
    if (!token || saving || account?.notify_frequency === freq) return
    setSaving(true)
    try {
      await patchSponsorNotifications(freq, { token })
      await refreshAccount()
    } catch {
      /* keep the current preference on failure */
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="text-left">
      <p className="text-sm font-medium text-gray-700">{t('sponsorPortal.notify.title')}</p>
      <p className="text-xs text-gray-500 mt-0.5">{t('sponsorPortal.notify.intro')}</p>
      <div className="mt-2 space-y-2">
        {(['realtime', 'weekly', 'off'] as const).map((f) => {
          const selected = (account?.notify_frequency || 'weekly') === f
          return (
            <button
              key={f} type="button" disabled={saving} onClick={() => change(f)}
              className={`w-full text-left rounded-lg border px-3 py-2 transition-colors disabled:opacity-60 ${
                selected ? 'border-blue-600 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'
              }`}
            >
              <span className={`text-sm font-medium ${selected ? 'text-blue-800' : 'text-gray-800'}`}>
                {t(`sponsorPortal.notify.${f}`)}
              </span>
              <span className="block text-xs text-gray-500">{t(`sponsorPortal.notify.${f}Desc`)}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

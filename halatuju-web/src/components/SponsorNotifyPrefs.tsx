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
      <p className="text-sm font-medium text-ground-700">{t('sponsorPortal.notify.title')}</p>
      <p className="text-xs text-ground-500 mt-0.5">{t('sponsorPortal.notify.intro')}</p>
      <div className="mt-2 space-y-2">
        {(['realtime', 'weekly', 'off'] as const).map((f) => {
          const selected = (account?.notify_frequency || 'weekly') === f
          return (
            <button
              key={f} type="button" disabled={saving} onClick={() => change(f)}
              className={`w-full text-left rounded-lg border px-3 py-2 transition-colors disabled:opacity-60 ${
                // BRAND — this is the SELECTED state of a control the reader is choosing between,
                // not a piece of information about it. Selection is the product acknowledging an
                // action, so a tenant's colour should be what acknowledges it.
                selected ? 'border-primary-600 bg-primary-50' : 'border-ground-200 hover:bg-ground-50'
              }`}
            >
              <span className={`text-sm font-medium ${selected ? 'text-primary-800' : 'text-ground-800'}`}>
                {t(`sponsorPortal.notify.${f}`)}
              </span>
              <span className="block text-xs text-ground-500">{t(`sponsorPortal.notify.${f}Desc`)}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { registerSponsor } from '@/lib/api'
import { SPONSOR_SOURCES, formatMyMobile, isValidMyMobile } from '@/lib/sponsorAuth'
import { KEY_SPONSOR_PENDING, KEY_SPONSOR_REF } from '@/lib/storage'

const inputCls =
  'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'

/**
 * The "complete your details" form shown to a signed-in sponsor whose account is
 * unregistered or incomplete (e.g. arrived via Google). Self-contained: owns its
 * form state, one-time prefill from the stash/session, and the register submit.
 */
export default function SponsorDetailsForm() {
  const { t } = useT()
  const { token, account, session, refreshAccount } = useSponsorAuth()

  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [source, setSource] = useState('')
  const [consent, setConsent] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const prefilled = useRef(false)

  // One-time pre-fill from the sign-up stash / Google metadata / existing account.
  useEffect(() => {
    if (prefilled.current) return
    let stash: { name?: string; phone?: string; source?: string } = {}
    try {
      const raw = sessionStorage.getItem(KEY_SPONSOR_PENDING)
      if (raw) stash = JSON.parse(raw)
    } catch { /* ignore malformed stash */ }
    const metaName =
      (session?.user?.user_metadata?.full_name as string) ||
      (session?.user?.user_metadata?.name as string) ||
      ''
    setName(account?.name || stash.name || metaName || '')
    setPhone(formatMyMobile(account?.phone || stash.phone || ''))
    setSource(account?.source || stash.source || '')
    prefilled.current = true
  }, [account, session])

  const phoneInvalid = phone.length > 0 && !isValidMyMobile(phone)
  const canSubmit = !!name.trim() && isValidMyMobile(phone) && !!source && consent && !submitting

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit || !token) return
    setSubmitting(true)
    setError('')
    try {
      let ref = ''
      try { ref = sessionStorage.getItem(KEY_SPONSOR_REF) || '' } catch { /* ignore */ }
      await registerSponsor(
        { name: name.trim(), phone: `+60 ${phone}`, source, consent: true, ...(ref ? { ref } : {}) },
        { token },
      )
      try { sessionStorage.removeItem(KEY_SPONSOR_PENDING); sessionStorage.removeItem(KEY_SPONSOR_REF) } catch { /* ignore */ }
      await refreshAccount()
    } catch {
      setError(t('sponsorAuth.registerFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <h1 className="text-xl font-bold text-gray-900">{t('sponsorPortal.completeTitle')}</h1>
      <p className="text-sm text-gray-600 mt-1">{t('sponsorPortal.completeBody')}</p>
      <form onSubmit={handleSubmit} className="mt-5 space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('sponsorAuth.fullName')} <span className="text-red-500">*</span>
          </label>
          <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('sponsorAuth.phone')} <span className="text-red-500">*</span>
          </label>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-sm text-gray-600 whitespace-nowrap">🇲🇾 +60</span>
            <input inputMode="tel" value={phone} onChange={(e) => setPhone(formatMyMobile(e.target.value))} placeholder="12-345 6789" className={inputCls} />
          </div>
          {phoneInvalid && <p className="text-xs text-red-600 mt-1">{t('sponsorAuth.mobileInvalid')}</p>}
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {t('sponsorAuth.source')} <span className="text-red-500">*</span>
          </label>
          <select value={source} onChange={(e) => setSource(e.target.value)} className={inputCls}>
            <option value="">{t('sponsorAuth.sourcePlaceholder')}</option>
            {SPONSOR_SOURCES.map((s) => <option key={s} value={s}>{t(`sponsorAuth.sourceOption.${s}`)}</option>)}
          </select>
        </div>
        <label className="flex items-start gap-2 text-sm text-gray-600">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-1" />
          <span>{t('sponsorAuth.consent')}{' '}
            <Link href="/privacy" className="text-blue-600 hover:underline">{t('sponsorAuth.privacyNotice')}</Link>.
          </span>
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={!canSubmit}
          className="w-full bg-blue-600 text-white font-semibold py-3 rounded-xl hover:bg-blue-700 transition-colors disabled:opacity-50">
          {submitting ? t('sponsorAuth.submitting') : t('sponsorAuth.submitDetails')}
        </button>
      </form>
    </>
  )
}

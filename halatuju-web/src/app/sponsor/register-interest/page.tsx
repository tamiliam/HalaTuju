'use client'

import { useState } from 'react'
import Link from 'next/link'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { submitSponsorInterest } from '@/lib/api'
import { useT } from '@/lib/i18n'

export default function SponsorRegisterInterestPage() {
  const { t } = useT()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [organisation, setOrganisation] = useState('')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState(false)

  const canSubmit = name.trim() && /\S+@\S+\.\S+/.test(email) && !submitting

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    setError(false)
    try {
      await submitSponsorInterest({ name: name.trim(), email: email.trim(), organisation, message })
      setDone(true)
    } catch {
      setError(true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <AppHeader />
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border p-8">
          {done ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-700 text-xl">✓</div>
              <h1 className="text-xl font-bold text-gray-900 mt-3">{t('sponsorInterest.doneTitle')}</h1>
              <p className="text-sm text-gray-600 mt-1">{t('sponsorInterest.doneBody')}</p>
              <Link href="/" className="inline-block mt-5 text-sm font-semibold text-primary-600 hover:underline">
                {t('sponsorInterest.backHome')}
              </Link>
            </div>
          ) : (
            <>
              <h1 className="text-xl font-bold text-gray-900">{t('sponsorInterest.title')}</h1>
              <p className="text-sm text-gray-600 mt-1">{t('sponsorInterest.intro')}</p>
              <form onSubmit={handleSubmit} className="mt-5 space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorInterest.name')} *</label>
                  <input value={name} onChange={(e) => setName(e.target.value)} className="input w-full" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorInterest.email')} *</label>
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="input w-full" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorInterest.organisation')}</label>
                  <input value={organisation} onChange={(e) => setOrganisation(e.target.value)} className="input w-full" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('sponsorInterest.message')}</label>
                  <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3}
                    placeholder={t('sponsorInterest.messagePlaceholder')} className="input w-full" />
                </div>
                {error && <p className="text-sm text-red-600">{t('sponsorInterest.error')}</p>}
                <button type="submit" disabled={!canSubmit}
                  className="w-full bg-primary-500 text-white font-semibold py-3 rounded-xl hover:bg-primary-600 transition-colors disabled:opacity-50">
                  {submitting ? t('sponsorInterest.submitting') : t('sponsorInterest.submit')}
                </button>
              </form>
            </>
          )}
        </div>
      </main>
      <AppFooter />
    </div>
  )
}

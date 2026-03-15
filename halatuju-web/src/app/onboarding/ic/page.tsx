'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'
import { syncProfile } from '@/lib/api'
import { useT } from '@/lib/i18n'
import IcInput from '@/components/IcInput'
import { validateIc } from '@/lib/ic-utils'

export default function IcOnboardingPage() {
  const router = useRouter()
  const { t } = useT()
  const { token, session } = useAuth()
  const [ic, setIc] = useState('')
  const [icValid, setIcValid] = useState(false)
  const [name, setName] = useState(
    session?.user?.user_metadata?.full_name ||
    session?.user?.user_metadata?.name ||
    ''
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const validationErr = validateIc(ic)
    if (validationErr) {
      setError(validationErr)
      return
    }
    if (!token) {
      setError('Not signed in. Please go back and sign in again.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      await syncProfile(
        { nric: ic, ...(name.trim() && { name: name.trim() }) },
        { token }
      )
      router.replace('/onboarding/exam-type')
    } catch {
      setError('Failed to save. Please try again.')
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#f8fafc]">
      {/* Header */}
      <div className="bg-white border-b border-gray-100">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-icon.png" alt="HalaTuju" width={90} height={40} />
            </Link>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 py-8 max-w-md">
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
          <h1 className="text-xl font-bold text-gray-900 text-center mb-2">
            {t('authGate.icTitle') || 'Verify Your Identity'}
          </h1>
          <p className="text-gray-600 text-center text-sm mb-6">
            {t('authGate.icSubtitle')}
          </p>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <IcInput
              value={ic}
              onChange={setIc}
              onValidChange={setIcValid}
              label={t('authGate.icLabel')}
            />

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('authGate.nameLabel')}
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('authGate.namePlaceholder')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={!icValid || loading}
              className="btn-primary w-full disabled:opacity-50"
            >
              {loading ? '...' : t('common.continue')}
            </button>

            <p className="text-xs text-gray-400 text-center">
              {t('authGate.icPrivacy')}
            </p>
          </form>
        </div>
      </div>
    </main>
  )
}

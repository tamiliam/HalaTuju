'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useT } from '@/lib/i18n'

function VerifyEmailContent() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')
  const { t } = useT()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [email, setEmail] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setErrorMsg(t('verifyEmail.noToken'))
      return
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || ''
    fetch(`${apiUrl}/api/v1/profile/verify-email/${token}/`)
      .then(res => res.json().then(data => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (ok) {
          setStatus('success')
          setEmail(data.email)
        } else {
          setStatus('error')
          setErrorMsg(data.error || t('verifyEmail.verificationFailed'))
        }
      })
      .catch(() => {
        setStatus('error')
        setErrorMsg(t('verifyEmail.networkError'))
      })
  }, [token, t])

  return (
    <main className="min-h-screen bg-[#f8fafc] flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8 max-w-md w-full text-center">
        {status === 'loading' && (
          <p className="text-gray-600">{t('verifyEmail.loading')}</p>
        )}
        {status === 'success' && (
          <>
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-gray-900 mb-2">{t('verifyEmail.successTitle')}</h1>
            <p className="text-sm text-gray-600 mb-4">{t('verifyEmail.successMsg', { email })}</p>
            <Link href="/profile" className="text-primary-600 text-sm font-medium hover:underline">
              {t('verifyEmail.goToProfile')}
            </Link>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-lg font-semibold text-gray-900 mb-2">{t('verifyEmail.failedTitle')}</h1>
            <p className="text-sm text-gray-600 mb-4">{errorMsg}</p>
            <Link href="/profile" className="text-primary-600 text-sm font-medium hover:underline">
              {t('verifyEmail.goToProfile')}
            </Link>
          </>
        )}
      </div>
    </main>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-[#f8fafc] flex items-center justify-center p-4">
        <p className="text-gray-600">Loading...</p>
      </main>
    }>
      <VerifyEmailContent />
    </Suspense>
  )
}

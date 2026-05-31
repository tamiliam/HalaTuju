'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useParams, useRouter } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import { useT } from '@/lib/i18n'
import { useSponsorAuth } from '@/lib/sponsor-auth-context'
import { sponsorSignOut } from '@/lib/sponsor-supabase'
import { getSponsorPoolDetail, type SponsorPoolDetail } from '@/lib/api'

export default function SponsorPoolDetailPage() {
  const { t } = useT()
  const router = useRouter()
  const params = useParams()
  const id = Number(params?.id)
  const { isLoading, isSignedIn, token } = useSponsorAuth()

  const [detail, setDetail] = useState<SponsorPoolDetail | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    if (isLoading || !isSignedIn || !token || !id) return
    let cancelled = false
    getSponsorPoolDetail(id, { token })
      .then((d) => { if (!cancelled) setDetail(d) })
      .catch(() => { if (!cancelled) setUnavailable(true) })
    return () => { cancelled = true }
  }, [isLoading, isSignedIn, token, id])

  const handleSignOut = async () => {
    await sponsorSignOut()
    router.replace('/sponsor/login')
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <header className="bg-white border-b">
        <div className="container mx-auto px-6 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Image src="/logo-icon.png" alt="HalaTuju" width={100} height={36} />
            <span className="text-sm font-semibold text-blue-600">{t('sponsorAuth.badge')}</span>
          </Link>
          {isSignedIn && (
            <button onClick={handleSignOut} className="text-sm text-red-600 hover:text-red-800">{t('header.logout')}</button>
          )}
        </div>
      </header>

      <main className="flex-1 container mx-auto px-6 py-8 max-w-2xl">
        <Link href="/sponsor" className="text-sm text-blue-600 hover:underline">← {t('sponsorPool.back')}</Link>

        {!isSignedIn && !isLoading ? (
          <p className="text-center text-gray-500 mt-12">
            <Link href="/sponsor/login" className="text-blue-600 hover:underline">{t('sponsorAuth.signIn')}</Link>
          </p>
        ) : unavailable ? (
          <p className="text-center text-gray-500 mt-12">{t('sponsorPool.notAvailable')}</p>
        ) : detail === null ? (
          <p className="text-center text-gray-500 mt-12">{t('common.loading')}</p>
        ) : (
          <div className="mt-4">
            {/* Summary card — non-identifying */}
            <div className="bg-white rounded-2xl border p-6">
              <div className="flex items-center justify-between">
                <h1 className="text-xl font-bold text-gray-900">{detail.ref}</h1>
                {detail.state && <span className="text-sm text-gray-500">{detail.state}</span>}
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                {detail.field && (
                  <div><dt className="text-gray-500">{t('sponsorPool.fieldLabel')}</dt><dd className="text-gray-900">{detail.field}</dd></div>
                )}
                {detail.academic && (
                  <div><dt className="text-gray-500">{t('sponsorPool.academicLabel')}</dt><dd className="text-gray-900">{detail.academic}</dd></div>
                )}
                {detail.funding_categories.length > 0 && (
                  <div><dt className="text-gray-500">{t('sponsorPool.fundingLabel')}</dt><dd className="text-gray-900">{detail.funding_categories.join(' · ')}</dd></div>
                )}
                {detail.programme_months != null && (
                  <div><dt className="text-gray-500">{t('sponsorPool.durationLabel')}</dt><dd className="text-gray-900">{detail.programme_months} {t('sponsorPool.months')}</dd></div>
                )}
              </dl>
            </div>

            {/* Generated anonymous profile */}
            {detail.anon_profile && (
              <div className="bg-white rounded-2xl border p-6 mt-4">
                <div className="text-sm text-gray-800 leading-relaxed [&_h1]:text-base [&_h1]:font-bold [&_h2]:font-semibold [&_h2]:mt-3 [&_p]:mt-2 [&_ul]:list-disc [&_ul]:pl-5">
                  <ReactMarkdown>{detail.anon_profile}</ReactMarkdown>
                </div>
              </div>
            )}

            <div className="mt-4 rounded-lg bg-blue-50 border border-blue-100 px-4 py-2.5 text-xs text-blue-800">
              {t('sponsorPool.anonymityNote')}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

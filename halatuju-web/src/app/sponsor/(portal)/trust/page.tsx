'use client'

import '@/lib/messagesSponsor'   // TD-416: this page's sponsor* words (their own slice)
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { useSponsorPortal } from '@/lib/sponsor-portal-context'
import { LazyTrustView } from './LazyTrustView'

/**
 * Trust & Transparency hub (R5). The page holds the loading state; the five sections (Who we are,
 * Governance, Our volunteers, Sources & uses of funds, Independent assurance) are `TrustView.tsx`,
 * fetched as their own chunk (`LazyTrustView`, which says so in place if it cannot load) once the shared context's `trust` has loaded.
 */
export default function TrustPage() {
  const { t } = useT()
  const { trust } = useSponsorPortal()

  if (!trust) {
    return (
      <div className="max-w-3xl">
        <Link href="/sponsor" className="inline-flex min-h-11 items-center text-sm text-primary-600 hover:underline">← {t('sponsorPortal.trust.back')}</Link>
        <p className="text-center text-ground-500 mt-12">{t('common.loading')}</p>
      </div>
    )
  }

  return <LazyTrustView trust={trust} />
}

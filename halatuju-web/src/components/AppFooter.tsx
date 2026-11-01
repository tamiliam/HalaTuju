'use client'

import BrandLogo from '@/components/BrandLogo'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/lib/auth-context'
import { hasGrades } from '@/lib/storage'

/**
 * Every footer link is a 44 px row (Mobile M3; they were 18-20 px). So the footer does not grow
 * much, a phone sets the three link lists in TWO columns (the brand spans both) and the lists lose
 * their 8 px gaps — each row is now its own 44 px. A long Tamil label wraps inside its row.
 */
const LINK = 'inline-flex min-h-11 min-w-11 items-center text-left text-sm text-ground-600 hover:text-ground-900'

export default function AppFooter() {
  const { t } = useT()
  const router = useRouter()
  const { isAuthenticated, showAuthGate } = useAuth()

  return (
    <footer className="bg-ground-50 border-t border-ground-200">
      <div className="container mx-auto px-4 py-10 sm:px-6 md:py-12">
        <div className="grid grid-cols-2 gap-x-6 gap-y-8 md:grid-cols-5 md:gap-8">
          {/* Brand */}
          <div className="col-span-2">
            <BrandLogo width={120} height={40} />
            <p className="mt-3 text-sm text-ground-500 max-w-xs">
              {t('footer.tagline')}
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="text-sm font-semibold text-ground-900 uppercase tracking-wider mb-1">
              {t('footer.quickLinks')}
            </h3>
            <ul>
              <li>
                <Link href="/dashboard" className={LINK}>
                  {t('common.dashboard')}
                </Link>
              </li>
              <li>
                <Link href="/onboarding/exam-type" className={LINK}>
                  {t('footer.startHere')}
                </Link>
              </li>
              <li>
                {isAuthenticated ? (
                  <Link href="/saved" className={LINK}>
                    {t('common.saved')}
                  </Link>
                ) : (
                  <button
                    onClick={() => hasGrades() ? showAuthGate('save') : router.push('/onboarding/exam-type')}
                    className={LINK}
                  >
                    {t('common.saved')}
                  </button>
                )}
              </li>
            </ul>
          </div>

          {/* BrightPath Bursary — the assistance programme entry points */}
          <div>
            <h3 className="text-sm font-semibold text-ground-900 uppercase tracking-wider mb-1">
              {t('footer.b40Heading')}
            </h3>
            <ul>
              <li>
                <Link href="/scholarship" className={LINK}>
                  {t('footer.applyAssistance')}
                </Link>
              </li>
              <li>
                <Link href="/sponsor" className={LINK}>
                  {t('footer.becomeSponsor')}
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h3 className="text-sm font-semibold text-ground-900 uppercase tracking-wider mb-1">
              {t('footer.legal')}
            </h3>
            <ul>
              <li>
                <Link href="/about" className={LINK}>
                  {t('common.about')}
                </Link>
              </li>
              <li>
                <Link href="/privacy" className={LINK}>
                  {t('common.privacy')}
                </Link>
              </li>
              <li>
                <Link href="/terms" className={LINK}>
                  {t('common.terms')}
                </Link>
              </li>
              <li>
                <Link href="/cookies" className={LINK}>
                  {t('common.cookies')}
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-ground-200 mt-8 pt-4 flex flex-col sm:flex-row justify-between items-center gap-2 sm:gap-4">
          <p className="text-sm text-ground-400">
            &copy; {t('common.copyright')}
          </p>
          <div className="flex items-center gap-4">
            <Link href="/contact" className="inline-flex min-h-11 min-w-11 items-center text-sm text-ground-500 hover:text-ground-900">
              {t('common.contact')}
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}

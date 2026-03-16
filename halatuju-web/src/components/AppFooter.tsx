'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { useAuth } from '@/lib/auth-context'
import { hasGrades } from '@/lib/storage'

export default function AppFooter() {
  const { t } = useT()
  const router = useRouter()
  const { isAuthenticated, showAuthGate } = useAuth()

  return (
    <footer className="bg-gray-50 border-t border-gray-200">
      <div className="container mx-auto px-6 py-12">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="sm:col-span-2">
            <Image src="/logo-icon.png" alt="HalaTuju" width={120} height={40} />
            <p className="mt-3 text-sm text-gray-500 max-w-xs">
              {t('footer.tagline')}
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">
              {t('footer.quickLinks')}
            </h3>
            <ul className="space-y-2">
              <li>
                <Link href="/dashboard" className="text-sm text-gray-600 hover:text-gray-900">
                  {t('common.dashboard')}
                </Link>
              </li>
              <li>
                <Link href="/onboarding/exam-type" className="text-sm text-gray-600 hover:text-gray-900">
                  {t('footer.startHere')}
                </Link>
              </li>
              <li>
                {isAuthenticated ? (
                  <Link href="/saved" className="text-sm text-gray-600 hover:text-gray-900">
                    {t('common.saved')}
                  </Link>
                ) : (
                  <button
                    onClick={() => hasGrades() ? showAuthGate('save') : router.push('/onboarding/exam-type')}
                    className="text-sm text-gray-600 hover:text-gray-900"
                  >
                    {t('common.saved')}
                  </button>
                )}
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wider mb-3">
              {t('footer.legal')}
            </h3>
            <ul className="space-y-2">
              <li>
                <Link href="/about" className="text-sm text-gray-600 hover:text-gray-900">
                  {t('common.about')}
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="text-sm text-gray-600 hover:text-gray-900">
                  {t('common.privacy')}
                </Link>
              </li>
              <li>
                <Link href="/terms" className="text-sm text-gray-600 hover:text-gray-900">
                  {t('common.terms')}
                </Link>
              </li>
              <li>
                <Link href="/cookies" className="text-sm text-gray-600 hover:text-gray-900">
                  {t('common.cookies')}
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-gray-200 mt-8 pt-6 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-sm text-gray-400">
            &copy; {t('common.copyright')}
          </p>
          <div className="flex items-center gap-4">
            <Link href="/contact" className="text-sm text-gray-500 hover:text-gray-900">
              {t('common.contact')}
            </Link>
            <Link href="/admin" className="text-sm text-gray-400 hover:text-gray-600">
              Admin
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}

'use client'

import Link from 'next/link'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useAuth } from '@/lib/auth-context'
import { useT } from '@/lib/i18n'

export default function GetStartedPage() {
  const { t } = useT()
  const { showAuthGate } = useAuth()

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <AppHeader />
      <main className="flex-1 flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border p-8">
          <h1 className="text-xl font-bold text-gray-900">{t('getStarted.title')}</h1>
          <p className="text-sm text-gray-600 mt-1">{t('getStarted.tagline')}</p>

          <button
            onClick={() => showAuthGate('profile')}
            className="mt-6 w-full bg-primary-500 text-white font-semibold py-3 rounded-xl hover:bg-primary-600 transition-colors"
          >
            {t('getStarted.student')}
          </button>

          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-xs text-gray-400">{t('getStarted.or')}</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          <Link
            href="/sponsor/register-interest"
            className="block w-full text-center border border-primary-300 text-primary-700 font-semibold py-3 rounded-xl hover:bg-primary-50 transition-colors"
          >
            {t('getStarted.sponsor')}
          </Link>

          <div className="border-t mt-6 pt-4 flex items-center justify-between">
            <span className="text-sm text-gray-600">{t('getStarted.haveAccount')}</span>
            <button
              onClick={() => showAuthGate('profile')}
              className="text-sm font-semibold text-primary-600 border border-gray-200 rounded-lg px-4 py-1.5 hover:bg-gray-50"
            >
              {t('header.login.label')}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-3">{t('getStarted.partnerNote')}</p>
        </div>
      </main>
      <AppFooter />
    </div>
  )
}

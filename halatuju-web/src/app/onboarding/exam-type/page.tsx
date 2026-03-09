'use client'

import { useRouter } from 'next/navigation'
import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import ProgressStepper from '@/components/ProgressStepper'

export default function ExamTypePage() {
  const router = useRouter()
  const { t } = useT()

  const handleSelectSPM = () => {
    localStorage.setItem('halatuju_exam_type', 'spm')
    router.push('/onboarding/grades')
  }

  return (
    <main className="min-h-screen bg-[#f8fafc]">
      {/* Header */}
      <div className="bg-white border-b border-gray-100">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <Image src="/logo-icon.png" alt="HalaTuju" width={60} height={32} />
            </Link>
            <ProgressStepper currentStep={1} />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-6 py-16 max-w-2xl">
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            {t('onboarding.examTypeTitle')}
          </h1>
          <p className="text-gray-500 text-lg">
            {t('onboarding.examTypeSubtitle')}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
          {/* SPM Card */}
          <button
            onClick={handleSelectSPM}
            className="group relative overflow-hidden p-8 rounded-xl bg-white border-2 border-primary-100 shadow-sm hover:border-primary-500 hover:shadow-lg transition-all duration-200 text-left"
          >
            {/* Decorative gradient corner */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-primary-50 to-transparent rounded-bl-[80px] group-hover:from-primary-100 transition-colors" />
            <div className="relative">
              <div className="w-14 h-14 mb-5 rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-md shadow-primary-500/20">
                <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-1">SPM</h3>
              <p className="text-gray-500 text-sm mb-4">{t('onboarding.spmDesc')}</p>
              <span className="inline-flex items-center gap-1.5 text-primary-500 text-sm font-medium group-hover:gap-2.5 transition-all">
                Get started
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                </svg>
              </span>
            </div>
          </button>

          {/* STPM Card — Coming Soon */}
          <div className="relative overflow-hidden p-8 rounded-xl bg-white border-2 border-gray-100 shadow-sm text-left opacity-60 cursor-not-allowed">
            {/* Decorative gradient corner */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-gray-50 to-transparent rounded-bl-[80px]" />
            <div className="relative">
              <div className="flex items-center justify-between mb-5">
                <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-gray-300 to-gray-400 flex items-center justify-center">
                  <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25" />
                  </svg>
                </div>
                <span className="px-3 py-1 bg-gray-100 text-gray-500 text-xs font-medium rounded-full">
                  {t('onboarding.comingSoon')}
                </span>
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-1">STPM</h3>
              <p className="text-gray-500 text-sm mb-4">{t('onboarding.stpmDesc')}</p>
              <span className="inline-flex items-center gap-1.5 text-gray-400 text-sm font-medium">
                Coming soon
              </span>
            </div>
          </div>
        </div>

        <div className="flex justify-start">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-gray-500 hover:text-gray-900 text-sm font-medium transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
            </svg>
            {t('common.back')}
          </Link>
        </div>
      </div>
    </main>
  )
}

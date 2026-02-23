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
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Header */}
      <div className="bg-white border-b">
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
      <div className="container mx-auto px-6 py-12 max-w-2xl">
        <div className="text-center mb-10">
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            {t('onboarding.examTypeTitle')}
          </h1>
          <p className="text-gray-600">
            {t('onboarding.examTypeSubtitle')}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
          {/* SPM Card */}
          <button
            onClick={handleSelectSPM}
            className="p-8 rounded-2xl border-2 border-gray-200 bg-white hover:border-primary-500 hover:bg-primary-50 transition-all text-center group"
          >
            <div className="text-5xl mb-4">📝</div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">SPM</h3>
            <p className="text-gray-500">{t('onboarding.spmDesc')}</p>
          </button>

          {/* STPM Card — Coming Soon */}
          <div className="relative p-8 rounded-2xl border-2 border-gray-200 bg-gray-50 text-center opacity-60 cursor-not-allowed">
            <span className="absolute top-3 right-3 px-2.5 py-0.5 bg-gray-200 text-gray-600 text-xs font-medium rounded-full">
              {t('onboarding.comingSoon')}
            </span>
            <div className="text-5xl mb-4">📚</div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">STPM</h3>
            <p className="text-gray-500">{t('onboarding.stpmDesc')}</p>
          </div>
        </div>

        <div className="flex justify-start">
          <Link
            href="/"
            className="px-6 py-3 text-gray-600 hover:text-gray-900"
          >
            {t('common.back')}
          </Link>
        </div>
      </div>
    </main>
  )
}

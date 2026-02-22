'use client'

import Image from 'next/image'
import Link from 'next/link'
import { useT } from '@/lib/i18n'
import LanguageSelector from '@/components/LanguageSelector'

export default function LandingPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Navigation */}
      <nav className="container mx-auto px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Image src="/logo-icon.png" alt="HalaTuju" width={75} height={40} />
        </div>
        <div className="flex items-center gap-4">
          <LanguageSelector />
          <Link href="/about" className="text-gray-600 hover:text-gray-900">
            {t('common.about')}
          </Link>
          <Link href="/login" className="btn-primary">
            {t('common.getStarted')}
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-6 py-20 text-center">
        <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
          {t('landing.heroTitle')}
        </h1>
        <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto">
          {t('landing.heroSubtitle')}
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/onboarding/stream" className="btn-primary text-lg px-8 py-4">
            {t('landing.startJourney')}
          </Link>
          <Link href="/about" className="btn-secondary text-lg px-8 py-4">
            {t('common.learnMore')}
          </Link>
        </div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
          {t('landing.howItWorks')}
        </h2>
        <div className="grid md:grid-cols-3 gap-8">
          <FeatureCard
            step="1"
            title={t('landing.step1Title')}
            description={t('landing.step1Desc')}
          />
          <FeatureCard
            step="2"
            title={t('landing.step2Title')}
            description={t('landing.step2Desc')}
          />
          <FeatureCard
            step="3"
            title={t('landing.step3Title')}
            description={t('landing.step3Desc')}
          />
        </div>
      </section>

      {/* Stats Section */}
      <section className="bg-primary-500 py-16">
        <div className="container mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-8 text-center text-white">
            <StatCard number="310" label={t('landing.courses')} />
            <StatCard number="212" label={t('landing.institutions')} />
            <StatCard number="3" label={t('landing.languages')} />
            <StatCard number="100%" label={t('landing.free')} />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-6 py-20 text-center">
        <h2 className="text-3xl font-bold text-gray-900 mb-6">
          {t('landing.readyTitle')}
        </h2>
        <p className="text-lg text-gray-600 mb-8 max-w-xl mx-auto">
          {t('landing.readySubtitle')}
        </p>
        <Link href="/onboarding/stream" className="btn-primary text-lg px-8 py-4">
          {t('landing.getStartedFree')}
        </Link>
      </section>

      {/* Footer */}
      <footer className="bg-gray-50 py-12">
        <div className="container mx-auto px-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <div className="flex items-center gap-2">
              <Image src="/logo-icon.png" alt="HalaTuju" width={60} height={32} />
            </div>
            <div className="flex gap-6 text-sm text-gray-600">
              <Link href="/about">{t('common.about')}</Link>
              <Link href="/privacy">{t('common.privacy')}</Link>
              <Link href="/terms">{t('common.terms')}</Link>
            </div>
            <p className="text-sm text-gray-500">
              {t('common.copyright')}
            </p>
          </div>
        </div>
      </footer>
    </main>
  )
}

function FeatureCard({
  step,
  title,
  description,
}: {
  step: string
  title: string
  description: string
}) {
  return (
    <div className="card text-center">
      <div className="w-12 h-12 bg-primary-100 text-primary-500 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
        {step}
      </div>
      <h3 className="text-xl font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}

function StatCard({ number, label }: { number: string; label: string }) {
  return (
    <div>
      <div className="text-4xl font-bold mb-2">{number}</div>
      <div className="text-primary-100">{label}</div>
    </div>
  )
}

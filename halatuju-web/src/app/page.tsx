'use client'

import Link from 'next/link'
import { useT } from '@/lib/i18n'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'

export default function LandingPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gradient-to-b from-primary-50 to-ground-0">
      {/* The ONE student header (Mobile M2). Home used to draw its own bar, which wrapped onto three
          rows on a phone (TD-310's fix); `navLayout.test.ts` pins that Home uses this one. About is
          in the footer. */}
      <AppHeader />

      {/* Hero Section */}
      <section className="container mx-auto px-6 py-20 text-center">
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold text-ground-900 mb-6">
          {t('landing.heroTitle')}
        </h1>
        <p className="text-xl text-ground-600 mb-10 max-w-2xl mx-auto">
          {t('landing.heroSubtitle')}
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/onboarding/exam-type" className="btn-primary text-lg px-8 py-4">
            {t('landing.startJourney')}
          </Link>
          <Link href="/about" className="btn-secondary text-lg px-8 py-4">
            {t('common.learnMore')}
          </Link>
        </div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-6 py-20">
        <h2 className="text-3xl font-bold text-center text-ground-900 mb-12">
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
      {/* A2: the brand band carries `text-white` on its CHILD grid, so it is a TEXT pair and takes
          `-600` like every other filled control. The codemod could not see it — it matches within
          one class string, and CSS composes this one across two elements. */}
      <section className="bg-brand-fill py-16">
        <div className="container mx-auto px-6">
          {/* The ink pairs with `bg-brand-fill` on the SECTION above, not with anything here — the
              same parent/child split A2 found on this band, now on the role tokens. */}
          <div className="grid md:grid-cols-4 gap-8 text-center text-brand-fill-ink">
            <StatCard number="1,300+" label={t('landing.courses')} />
            <StatCard number="800+" label={t('landing.institutions')} />
            <StatCard number="3" label={t('landing.languages')} />
            <StatCard number="100%" label={t('landing.free')} />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-6 py-20 text-center">
        <h2 className="text-3xl font-bold text-ground-900 mb-6">
          {t('landing.readyTitle')}
        </h2>
        <p className="text-lg text-ground-600 mb-8 max-w-xl mx-auto">
          {t('landing.readySubtitle')}
        </p>
        {/* inline-block (TD-311): a bare inline link wrapped a long Tamil label across lines with
            its padding and fill broken at each line end, so the words ran over the button edge. */}
        <Link href="/onboarding/exam-type" className="btn-primary inline-block max-w-full text-lg px-8 py-4">
          {t('landing.getStartedFree')}
        </Link>
      </section>

      <AppFooter />
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
      <div className="w-12 h-12 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
        {step}
      </div>
      <h3 className="text-xl font-semibold text-ground-900 mb-2">{title}</h3>
      <p className="text-ground-600">{description}</p>
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

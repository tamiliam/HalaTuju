'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function AboutPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-6">
          <h1 className="text-2xl font-bold text-gray-900">{t('common.about')}</h1>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">The Problem We&apos;re Solving</h2>
            <p className="text-gray-600">
              Every year, thousands of Malaysian Indian students leave SPM and enrol in expensive private colleges — often taking on heavy student loans for qualifications that don&apos;t always match what&apos;s available for free or at heavily subsidised rates in the public system.
            </p>
            <p className="text-gray-600">
              In 2024, over 137,000 places were available across polytechnics, community colleges, TVET institutions, and public universities — not including UiTM. These are government-funded, industry-recognised programmes. But too many students and families never find them, because the information is scattered and hard to navigate.
            </p>
            <p className="text-gray-700 font-medium">HalaTuju exists to fix that.</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">What It Does</h2>
            <p className="text-gray-600">
              Enter your SPM results, and our eligibility engine checks them against the entry requirements of over 800 courses across Malaysia&apos;s public institutions. We help you find the programmes you&apos;re actually eligible for — matched to your grades, your interests, and your goals.
            </p>
            <p className="text-gray-700 font-medium">No sign-ups. No fees. No catch.</p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">Who&apos;s Behind This</h2>
            <p className="text-gray-600">
              HalaTuju is built under Project Lentera, a community-driven initiative focused on improving access to public tertiary education for Malaysian students.
            </p>
            <p className="text-gray-600">
              This is a volunteer effort — no single person owns it. Teachers, counsellors, parents, alumni, and community organisations all play a part. We believe every student deserves to make an informed choice, not a default one driven by lack of information.
            </p>
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">How You Can Help</h2>
            <div className="space-y-3">
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-700"><span className="font-semibold">Parents:</span> Use HalaTuju with your child after SPM results. The options may surprise you.</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-700"><span className="font-semibold">Teachers and counsellors:</span> Share it with your students. Five minutes could save a family years of debt.</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-700"><span className="font-semibold">Everyone else:</span> Spread the word. The more families who know about public options, the fewer who choose private ones simply because they didn&apos;t know better.</p>
              </div>
            </div>
            <p className="text-gray-600">
              HalaTuju is a growing platform — we&apos;re continuously adding courses and improving recommendations. If you have feedback or want to contribute, we want to hear from you.
            </p>
          </section>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}

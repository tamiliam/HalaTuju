'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'
import { useBranding } from '@/lib/branding-context'

export default function TermsPage() {
  const { t } = useT()
  const b = useBranding()

  return (
    <main className="min-h-screen bg-ground-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-ground-0 rounded-xl border border-ground-200 p-6 space-y-4">
          <h1 className="text-2xl font-bold text-ground-900 mb-2">{t('common.terms')}</h1>
          <p className="text-sm text-ground-500">Last updated: June 2026</p>

          <h2 className="text-lg font-semibold text-ground-900">Acceptance of Terms</h2>
          <p className="text-ground-600">
            By using HalaTuju, you agree to these terms of service. HalaTuju is
            provided free of charge as a public service tool for Malaysian students
            exploring SPM and STPM course options.
          </p>

          <h2 className="text-lg font-semibold text-ground-900">Account and IC Number</h2>
          <p className="text-ground-600">
            To access personalised features, you must create an account and provide
            your IC number (NRIC). You are responsible for providing accurate
            information. Misrepresenting your identity or IC number may result in
            incorrect recommendations and account suspension.
          </p>

          <h2 className="text-lg font-semibold text-ground-900">Recommendations Disclaimer</h2>
          <p className="text-ground-600">
            Course recommendations are generated based on publicly available entry
            requirements from over 1,300 courses across 800+ institutions. HalaTuju
            does not guarantee admission to any course or institution. Always verify
            requirements directly with the institution before applying.
          </p>

          <h2 className="text-lg font-semibold text-ground-900">Limitation of Liability</h2>
          <p className="text-ground-600">
            HalaTuju is provided &ldquo;as is&rdquo; without warranty of any kind.
            We are not liable for any decisions made based on the recommendations
            provided by this tool.
          </p>

          <h2 className="text-lg font-semibold text-ground-900">Scope</h2>
          <p className="text-ground-600">
            HalaTuju provides a free course-matching tool and operates the B40
            {' '}{b.programmeName.en} Programme. Using either means you accept these terms.
          </p>

          <h2 className="text-lg font-semibold text-ground-900">The {b.programmeName.en} Programme</h2>
          <p className="text-ground-600">
            Applying does <strong>not</strong> guarantee assistance &mdash; places are
            limited and subject to eligibility checks and a human review. Assistance is a
            gift, not a loan; there is nothing to repay. Funds (where a sponsor supports a
            student) are administered by the programme&rsquo;s non-profit partner and are
            never paid directly to a student. <em>(Partnership being finalised.)</em>
          </p>

          <h2 className="text-lg font-semibold text-ground-900">Sponsors</h2>
          <p className="text-ground-600">
            Sponsor contributions support students through the programme&rsquo;s
            administering non-profit; they are not a direct transfer to a student and are
            not a commercial transaction. A contribution is a <strong>gift</strong> &mdash; nothing
            is repaid, and it cannot be withdrawn once given. A sponsor <strong>nominates</strong> a
            student from those we have vetted, and the programme makes the award; we follow a
            sponsor&rsquo;s choice wherever we can, and credit returns to their balance for another
            student where we cannot. We are <strong>not</strong> an approved institution for tax
            deduction, so we cannot issue a tax-deductible receipt.
          </p>

          <h2 className="text-lg font-semibold text-ground-900">Minors</h2>
          <p className="text-ground-600">
            If you are under 18, you may use the course tool, but a parent or guardian
            must give consent before you apply for assistance or before your profile is
            shared with any sponsor.
          </p>

          <h2 className="text-lg font-semibold text-ground-900">Accuracy &amp; honesty</h2>
          <p className="text-ground-600">
            You are responsible for the accuracy of what you submit; misrepresenting your
            identity, grades, or income may result in disqualification or account
            suspension.
          </p>

          <h2 className="text-lg font-semibold text-ground-900">Changes to Terms</h2>
          <p className="text-ground-600">
            We may update these terms from time to time. Continued use of HalaTuju
            constitutes acceptance of any changes.
          </p>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}

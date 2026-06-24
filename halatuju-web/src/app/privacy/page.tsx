'use client'

import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

export default function PrivacyPage() {
  const { t } = useT()

  return (
    <main className="min-h-screen bg-gray-50">
      <AppHeader />

      <div className="container mx-auto px-6 py-8 max-w-2xl">
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('common.privacy')}</h1>
          <p className="text-sm text-gray-500">Last updated: June 2026</p>

          <p className="text-gray-600">
            HalaTuju provides two things: a free <strong>course-matching tool</strong> for
            SPM/STPM students, and the <strong>BrightPath Bursary Programme</strong>, which
            connects verified low-income students with sponsors who support their public
            tertiary studies. This policy covers both.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Data we collect</h2>
          <ul className="list-disc pl-6 text-gray-600 space-y-1">
            <li><em>Course tool:</em> your IC number (NRIC, stored securely and shown only masked, e.g. ****-**-1234), SPM/STPM grades, optional profile details (name, gender, nationality, state, contact details, family background), optional quiz answers, and your sign-in identifier (phone number or Google account).</li>
            <li><em>BrightPath Bursary Programme (only if you apply):</em> household and family income details, and <strong>documents you upload</strong> to verify your application &mdash; your IC, results slip, university/college offer letter, a parent/guardian IC, and proof of household income or aid (e.g. an STR letter, EPF statement, payslip, or utility bill).</li>
          </ul>

          <h2 className="text-lg font-semibold text-gray-900">How we use and process your data</h2>
          <ul className="list-disc pl-6 text-gray-600 space-y-1">
            <li>To generate course recommendations and to assess and administer assistance applications.</li>
            <li><strong>Automated processing:</strong> to help us read and check your documents, we use automated text-recognition and AI services (Google Cloud Vision and Google Gemini) to extract text from uploaded documents and to prepare an anonymised profile for sponsors. We also use an automated rule to check eligibility against the published criteria. <strong>These are decision-support tools &mdash; a person reviews your application before any decision</strong>, and you can ask us to review any automated outcome.</li>
            <li>To send you relevant follow-up emails (e.g. assistance opportunities, important changes). You can unsubscribe at any time.</li>
          </ul>

          <h2 className="text-lg font-semibold text-gray-900">Who we share it with</h2>
          <ul className="list-disc pl-6 text-gray-600 space-y-1">
            <li><strong>Service providers that process data on our behalf:</strong> Supabase (secure database hosting, Singapore region) and Google (the text-recognition and AI services above). They process your data only to provide these services to us.</li>
            <li><strong>The administering trust foundation</strong> &mdash; for applicants accepted into the BrightPath Bursary Programme, to administer the support. <em>(Currently being established.)</em></li>
            <li><strong>Sponsors</strong> &mdash; only an <strong>anonymised profile</strong> (e.g. field of study, region, academic band), and only <strong>after you give explicit consent</strong> (for applicants under 18, a parent or guardian must consent). Sponsors <strong>never</strong> see your name, IC, address, phone, email, photo, or your parents&rsquo; details.</li>
            <li>We <strong>do not</strong> sell your data or share it for unrelated third-party marketing.</li>
          </ul>

          <h2 className="text-lg font-semibold text-gray-900">Keeping and deleting your data</h2>
          <p className="text-gray-600">
            We keep your data while your account is active and for as long as needed to
            administer the programme and meet legal obligations. You may request deletion
            of your account and data at any time. Certain limited data is purged
            automatically &mdash; for example, the contact details of an unconverted
            sponsor-referral invite are removed after 60 days.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Your rights</h2>
          <p className="text-gray-600">
            You may access, correct, or delete your data, and withdraw consent (including
            a sponsor-sharing consent) at any time. Use the{' '}
            <a href="/contact" className="text-primary-500 hover:underline">contact form</a>{' '}
            (there&rsquo;s a &ldquo;Data Deletion Request&rdquo; option).
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Security</h2>
          <p className="text-gray-600">
            Your data is stored on Supabase (Singapore region) with row-level security;
            sensitive data, including your IC, is encrypted at rest and in transit.
          </p>

          <h2 className="text-lg font-semibold text-gray-900">Minors</h2>
          <p className="text-gray-600">
            Many of our users are school-leavers. If you are under 18, a parent or
            guardian must consent before your profile is shared with any sponsor.
          </p>

          <p className="text-sm text-gray-500 italic pt-2">
            Questions about your data? Use our{' '}
            <a href="/contact" className="text-primary-500 hover:underline">contact form</a>.
          </p>
        </div>
      </div>

      <AppFooter />
    </main>
  )
}

'use client'

import Link from 'next/link'
import { useT } from '@/lib/i18n'
import type { StudentAward, BursaryAgreement } from '@/lib/api'
import { isFundedStatus } from '@/lib/scholarship'

/**
 * The award offer and the signed bursary agreement on `/scholarship/application` — the two
 * panels moved here from the page whole (TD-352, 2026-10-06) so they load on demand
 * (`LazyApplicationAwardPanels`). The page still asks for the award and the agreement exactly as
 * before; the lazy boundary fetches this only when one of them would draw something, which only a student holding
 * an award offer (or a signed agreement) ever does. Every other visitor used to download this
 * code to draw nothing.
 */
export interface AwardPanelsProps {
  award: StudentAward | null
  acceptanceEnabled: boolean
  bursary: BursaryAgreement | null
  status: string
  onboardedAt: string | null | undefined
}

export default function ApplicationAwardPanels(
  { award, acceptanceEnabled, bursary, status, onboardedAt }: AwardPanelsProps,
) {
  const { t } = useT()

  return <>{awardPanel()}{bursaryPanel()}</>

  // "Next: accept your award / complete onboarding" — shown only when the
  // student has an award offer. An un-accepted offer (status 'offered') points
  // to the award page; an accepted-but-not-yet-onboarded award points to
  // onboarding. Once onboarded (onboarded_at set) the panel disappears.
  function awardPanel() {
    // Embargoed for now: the accept→onboarding flow isn't tested end-to-end, so we
    // keep the panel hidden until AWARD_ACCEPTANCE_ENABLED is turned on (no deploy).
    if (!award || !acceptanceEnabled) return null

    // Bursary flow: once the student has SIGNED (a bursary agreement exists) but the
    // agreement isn't yet fully executed — the application only reaches a funded state
    // (active/maintenance) when the Foundation has counter-signed — we do NOT route them
    // to the portal yet. "We do not land them in the portal until everyone has signed."
    const signedAgreement = !!bursary
    const fullyExecuted = isFundedStatus(status)
    if (signedAgreement && !fullyExecuted) {
      return (
        <div className="mb-6 rounded-2xl border border-info-200 bg-info-50 p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <span className="shrink-0 text-info-600" aria-hidden>✅</span>
            <div className="flex-1">
              <h2 className="font-semibold text-ground-900">{t('scholarship.application.awardPanel.awaitingTitle')}</h2>
              <p className="mt-1 text-sm text-ground-700">{t('scholarship.application.awardPanel.awaitingBody')}</p>
            </div>
          </div>
        </div>
      )
    }

    const accepted = award.status !== 'offered'   // active / sponsored / etc.
    if (accepted && onboardedAt) return null
    const href = accepted ? '/scholarship/onboarding' : '/scholarship/award'
    const cta = accepted
      ? t('scholarship.application.awardPanel.onboardingCta')
      : t('scholarship.application.awardPanel.acceptCta')
    const body = accepted
      ? t('scholarship.application.awardPanel.onboardingBody')
      : t('scholarship.application.awardPanel.acceptBody')
    return (
      <div className="mb-6 rounded-2xl border border-info-200 bg-info-50 p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="shrink-0 text-info-600" aria-hidden>🎉</span>
          <div className="flex-1">
            <h2 className="font-semibold text-ground-900">{t('scholarship.application.awardPanel.title')}</h2>
            <p className="mt-1 text-sm text-ground-700">{body}</p>
            <Link href={href} className="btn-primary mt-3 inline-block">{cta}</Link>
          </div>
        </div>
      </div>
    )
  }

  // "Your bursary agreement" — a minimal panel with a PDF download, shown only once
  // the student has signed (getBursaryAgreement returned an agreement). Flag-gated:
  // null while the feature is off or unsigned. No donor identity anywhere.
  function bursaryPanel() {
    if (!bursary || !bursary.pdf_url) return null
    return (
      <div className="mb-6 rounded-2xl border border-positive-200 bg-positive-50 p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="shrink-0 text-positive-700" aria-hidden>📄</span>
          <div className="flex-1">
            <h2 className="font-semibold text-ground-900">{t('scholarship.application.bursaryPanel.title')}</h2>
            <p className="mt-1 text-sm text-ground-700">{t('scholarship.application.bursaryPanel.body')}</p>
            <a
              href={bursary.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary mt-3 inline-block"
            >
              {t('scholarship.application.bursaryPanel.download')}
            </a>
          </div>
        </div>
      </div>
    )
  }
}

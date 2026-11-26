'use client'

/**
 * "Switch to SPM results?" — shown on /onboarding/exam-type when a student the SERVER says holds
 * STPM / Matriculation / Asasi / Diploma results taps SPM (pre-U sprint, 2026-11-26). Saying yes
 * only RECORDS the choice (`lib/resultsSwitch`): nothing is removed until they save their SPM grades.
 * When an application of theirs uses those results (`held_results_locked`: open, closed or awarded;
 * a rejected, withdrawn or expired one does not), the server would refuse the clear, so the dialog
 * says so up front and offers only Back.
 */
import { Fragment, useRef } from 'react'
import { useT } from '@/lib/i18n'
import Sheet from '@/components/Sheet'
import { heldResultsSummary } from '@/lib/resultsSwitch'

type HeldProfile = {
  results_held?: string | null
  stpm_cgpa?: number | null
  higher_cgpa?: number | null
  held_results_locked?: boolean
}

/** Renders a message whose `<b>…</b>` spans are bold (the odd parts after a split). */
function withBold(text: string) {
  return text.split(/<\/?b>/).map((part, i) => (i % 2 ? <b key={i}>{part}</b> : <Fragment key={i}>{part}</Fragment>))
}

export default function SpmSwitchDialog({ profile, onBack, onConfirm }: {
  profile: HeldProfile
  onBack: () => void
  onConfirm: () => void
}) {
  const { t } = useT()
  const backRef = useRef<HTMLButtonElement>(null)
  const { route, summary } = heldResultsSummary(profile, (k) => t(`onboarding.higherKind.${k}`))
  const locked = !!profile.held_results_locked
  const footer = (
    <div className="flex gap-3">
      <button ref={backRef} type="button" onClick={onBack}
        className="flex-1 min-h-11 px-4 py-2.5 border border-ground-300 rounded-lg text-sm font-medium text-ground-700 hover:bg-ground-50">
        {t('common.back')}
      </button>
      {!locked && (
        <button type="button" onClick={onConfirm}
          className="flex-1 min-h-11 px-4 py-2.5 bg-brand-fill text-brand-fill-ink rounded-lg text-sm font-medium hover:bg-brand-fill-hover">
          {t('onboarding.switchSpmConfirm')}
        </button>
      )}
    </div>
  )
  return (
    <Sheet open onClose={onBack} title={t('onboarding.switchSpmTitle')} footer={footer} size="md"
      initialFocus={backRef} testId="spm-switch">
      <p className="rounded-lg bg-caution-50 border border-caution-200 p-3 text-sm text-ground-800 mb-3">
        {withBold(t('onboarding.switchSpmHeld', { route, summary }))}
      </p>
      {locked ? (
        <p className="text-sm text-ground-700">{t('onboarding.switchSpmLocked', { route })}</p>
      ) : (
        <>
          <p className="text-sm text-ground-700 mb-2">{t('onboarding.switchSpmRemove', { route })}</p>
          <p className="text-sm text-ground-500">{t('onboarding.switchSpmNothing')}</p>
        </>
      )}
    </Sheet>
  )
}

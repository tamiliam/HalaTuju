'use client'

import { useT } from '@/lib/i18n'

interface ProgressStepperProps {
  currentStep: number
  totalSteps?: number
}

/**
 * "Step 2 of 3" with the bars UNDER the words (Mobile M2, Stitch M2c2).
 *
 * ⚠ STACKED, NOT SIDE BY SIDE. Words and bars in one row needed 268 px in Malay ("Langkah 2
 * daripada 3" + three 32 px bars), so beside the logo on a 390 px phone the row squeezed the LOGO to
 * 74 px wide (44 px at 360). Stacked, the indicator is only as wide as its words — 152 px in Malay,
 * the longest — and the bars (3 × 24 px) sit under them, right-aligned.
 */
export default function ProgressStepper({ currentStep, totalSteps = 3 }: ProgressStepperProps) {
  const { t } = useT()

  return (
    <div className="flex flex-col items-end gap-1.5">
      <span className="text-sm font-medium text-ground-500 whitespace-nowrap">
        {t('onboarding.step')} {currentStep} {t('onboarding.of')} {totalSteps}
      </span>
      <div className="flex items-center gap-1" aria-hidden>
        {Array.from({ length: totalSteps }, (_, i) => (
          <div
            key={i}
            className={`h-1 w-6 rounded-full transition-all ${
              i < currentStep ? 'bg-brand-shape' : 'bg-ground-200'
            }`}
          />
        ))}
      </div>
    </div>
  )
}

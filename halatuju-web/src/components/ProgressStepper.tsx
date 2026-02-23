'use client'

import { useT } from '@/lib/i18n'

interface ProgressStepperProps {
  currentStep: number
  totalSteps?: number
}

export default function ProgressStepper({ currentStep, totalSteps = 3 }: ProgressStepperProps) {
  const { t } = useT()

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm font-medium text-gray-500 whitespace-nowrap">
        {t('onboarding.step')} {currentStep} {t('onboarding.of')} {totalSteps}
      </span>
      <div className="flex items-center gap-1">
        {Array.from({ length: totalSteps }, (_, i) => (
          <div
            key={i}
            className={`h-1.5 w-8 rounded-full transition-all ${
              i < currentStep ? 'bg-primary-500' : 'bg-gray-200'
            }`}
          />
        ))}
      </div>
    </div>
  )
}

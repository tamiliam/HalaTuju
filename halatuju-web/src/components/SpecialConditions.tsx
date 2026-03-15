'use client'

import { useT } from '@/lib/i18n'

interface SpecialConditionsProps {
  reqInterview?: boolean
  noColorblind?: boolean
  reqMedicalFitness?: boolean
}

export default function SpecialConditions({ reqInterview, noColorblind, reqMedicalFitness }: SpecialConditionsProps) {
  const { t } = useT()

  const hasAny = reqInterview || noColorblind || reqMedicalFitness
  if (!hasAny) return null

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2 mb-3">
        <svg className="w-[18px] h-[18px] text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.832c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        {t('common.specialConditions')}
      </h2>
      <div className="space-y-2">
        {reqInterview && (
          <div className="flex items-center gap-2 text-sm text-amber-700">
            <span className="w-2 h-2 bg-amber-500 rounded-full flex-shrink-0" />
            {t('common.interviewRequired')}
          </div>
        )}
        {noColorblind && (
          <div className="flex items-center gap-2 text-sm text-red-700">
            <span className="w-2 h-2 bg-red-500 rounded-full flex-shrink-0" />
            {t('common.noColorblind')}
          </div>
        )}
        {reqMedicalFitness && (
          <div className="flex items-center gap-2 text-sm text-orange-700">
            <span className="w-2 h-2 bg-orange-500 rounded-full flex-shrink-0" />
            {t('common.medicalFitness')}
          </div>
        )}
      </div>
    </section>
  )
}

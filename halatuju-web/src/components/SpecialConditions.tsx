'use client'

import { useT } from '@/lib/i18n'

interface SpecialConditionsProps {
  reqInterview?: boolean
  noColorblind?: boolean
  reqMedicalFitness?: boolean
  reqMale?: boolean
  reqFemale?: boolean
  single?: boolean
  noDisability?: boolean
}

export default function SpecialConditions({
  reqInterview,
  noColorblind,
  reqMedicalFitness,
  reqMale,
  reqFemale,
  single,
  noDisability,
}: SpecialConditionsProps) {
  const { t } = useT()

  const hasAny = reqInterview || noColorblind || reqMedicalFitness || reqMale || reqFemale || single || noDisability
  if (!hasAny) return null

  return (
    <section className="bg-ground-0 rounded-xl border border-ground-200 p-6">
      <h2 className="text-base font-semibold text-ground-900 flex items-center gap-2 mb-3">
        <svg className="w-[18px] h-[18px] text-caution-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.832c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        {t('common.specialConditions')}
      </h2>
      {/* A CATEGORY PALETTE, on the `category-N` family (Layer 1 F2c, owner decision 2026-08-31).
          Seven entry conditions, seven swatches, so they can be told apart in a list. They are NOT
          signals: "female applicants only" is a REQUIREMENT, not a warning, and "medical fitness
          required" is not an error — which is why a tone would have been wrong here, not merely
          ugly. The warning triangle in the heading above IS a genuine caution and stays a tone.
          ✅ Fixed here: `noColorblind` and `noDisability` were both red, so two of the seven were
          already indistinguishable. ⛔ Seven conditions, seven DIFFERENT numbers. Never a tone. */}
      <div className="space-y-2">
        {reqMale && (
          <div className="flex items-center gap-2 text-sm text-category-5-ink">
            <span className="w-2 h-2 bg-category-5-dot rounded-full flex-shrink-0" />
            {t('common.maleOnly')}
          </div>
        )}
        {reqFemale && (
          <div className="flex items-center gap-2 text-sm text-category-4-ink">
            <span className="w-2 h-2 bg-category-4-dot rounded-full flex-shrink-0" />
            {t('common.femaleOnly')}
          </div>
        )}
        {single && (
          <div className="flex items-center gap-2 text-sm text-category-1-ink">
            <span className="w-2 h-2 bg-category-1-dot rounded-full flex-shrink-0" />
            {t('common.unmarriedOnly')}
          </div>
        )}
        {reqInterview && (
          <div className="flex items-center gap-2 text-sm text-category-3-ink">
            <span className="w-2 h-2 bg-category-3-dot rounded-full flex-shrink-0" />
            {t('common.interviewRequired')}
          </div>
        )}
        {noColorblind && (
          <div className="flex items-center gap-2 text-sm text-category-2-ink">
            <span className="w-2 h-2 bg-category-2-dot rounded-full flex-shrink-0" />
            {t('common.noColorblind')}
          </div>
        )}
        {noDisability && (
          <div className="flex items-center gap-2 text-sm text-category-8-ink">
            <span className="w-2 h-2 bg-category-8-dot rounded-full flex-shrink-0" />
            {t('common.noDisability')}
          </div>
        )}
        {reqMedicalFitness && (
          <div className="flex items-center gap-2 text-sm text-category-6-ink">
            <span className="w-2 h-2 bg-category-6-dot rounded-full flex-shrink-0" />
            {t('common.medicalFitness')}
          </div>
        )}
        {/* END CONDITION MARKERS */}
      </div>
    </section>
  )
}

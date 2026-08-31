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
        <svg className="w-[18px] h-[18px] text-caution-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.832c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        {t('common.specialConditions')}
      </h2>
      {/* ⚠ A CATEGORY PALETTE — DELIBERATELY NOT ON THE THEME TOKENS (Layer 1 F2b, 2026-08-31).
          Seven entry conditions, each with its own dot colour so they can be told apart in a list.
          They are not signals: "female applicants only" is a REQUIREMENT, not a warning, and
          "medical fitness required" is not an error. Renaming by family would put three of the
          seven onto `critical`/`caution`/`info` — reading as alarm — while pink, purple and orange
          stayed literal, leaving the set half-converted and incoherent. The warning triangle in
          the heading above IS a genuine caution signal and DID convert.
          Known gap: these do not follow dark mode. Awaiting the owner's decision on a fifth
          CATEGORICAL family. ⛔ Do not "finish the migration" over this block. */}
      <div className="space-y-2">
        {reqMale && (
          <div className="flex items-center gap-2 text-sm text-blue-700">
            <span className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0" />
            {t('common.maleOnly')}
          </div>
        )}
        {reqFemale && (
          <div className="flex items-center gap-2 text-sm text-pink-700">
            <span className="w-2 h-2 bg-pink-500 rounded-full flex-shrink-0" />
            {t('common.femaleOnly')}
          </div>
        )}
        {single && (
          <div className="flex items-center gap-2 text-sm text-purple-700">
            <span className="w-2 h-2 bg-purple-500 rounded-full flex-shrink-0" />
            {t('common.unmarriedOnly')}
          </div>
        )}
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
        {noDisability && (
          <div className="flex items-center gap-2 text-sm text-red-700">
            <span className="w-2 h-2 bg-red-500 rounded-full flex-shrink-0" />
            {t('common.noDisability')}
          </div>
        )}
        {reqMedicalFitness && (
          <div className="flex items-center gap-2 text-sm text-orange-700">
            <span className="w-2 h-2 bg-orange-500 rounded-full flex-shrink-0" />
            {t('common.medicalFitness')}
          </div>
        )}
        {/* END CONDITION MARKERS */}
      </div>
    </section>
  )
}

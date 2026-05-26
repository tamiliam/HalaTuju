'use client'

import { useT } from '@/lib/i18n'
import type { EligiblePathway } from '@/lib/scholarship'

/**
 * Single-select pathway dropdown for the B40 apply form's "decided" branch.
 * Lists only the pathways the student is eligible for (computed live from the
 * eligibility engine), each showing its eligible-programme count — e.g.
 * "Polytechnic — 85 eligible". A dropdown (not chips) keeps single-select
 * unambiguous: the student commits to exactly one pathway. Labels are trilingual.
 *
 * Loading and empty states are handled here so the parent stays declarative:
 * while options load it shows a disabled placeholder; if the student has no
 * eligible pathways (e.g. results not yet entered) it explains why.
 */
export default function PathwaySelect({
  pathways,
  value,
  onChange,
  loading = false,
}: {
  pathways: EligiblePathway[]
  value: string
  onChange: (key: string) => void
  loading?: boolean
}) {
  const { t } = useT()

  if (loading) {
    return (
      <select className="input text-gray-400" disabled>
        <option>{t('scholarship.apply.plan.loading')}</option>
      </select>
    )
  }

  if (pathways.length === 0) {
    return (
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-gray-600">
        {t('scholarship.apply.plan.noPathways')}
      </p>
    )
  }

  return (
    <select
      className="input"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{t('scholarship.apply.plan.pathwayPlaceholder')}</option>
      {pathways.map((p) => (
        <option key={p.key} value={p.key}>
          {t(`scholarship.apply.plan.pathway.${p.key}`)} — {t('scholarship.apply.plan.eligibleCount', { count: String(p.count) })}
        </option>
      ))}
    </select>
  )
}

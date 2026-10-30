'use client'

import { useT } from '@/lib/i18n'

/**
 * Single-select pathway dropdown for the scholarship "My Plans" offer branch. Since 2026-10-30
 * (owner rulings) it lists EVERY pathway in `PATHWAY_ORDER` — no "N eligible" counts — and only
 * the pathways with an eligible course while the student has "Eligible only" switched on. A
 * dropdown (not chips) keeps single-select unambiguous. Labels are trilingual.
 *
 * Loading and empty states are handled here so the parent stays declarative: while "Eligible
 * only" loads it shows a disabled placeholder; when the switch leaves nothing it says so.
 */
export default function PathwaySelect({
  pathways,
  value,
  onChange,
  loading = false,
  label,
}: {
  pathways: readonly string[]
  value: string
  onChange: (key: string) => void
  loading?: boolean
  label: string
}) {
  const { t } = useT()

  if (loading) {
    return (
      <select className="input text-ground-placeholder" disabled aria-label={label}>
        <option>{t('scholarship.apply.plan.loading')}</option>
      </select>
    )
  }

  if (pathways.length === 0) {
    return (
      <p className="rounded-xl border border-caution-200 bg-caution-50 p-3 text-sm text-ground-600">
        {t('scholarship.apply.plan.noPathways')}
      </p>
    )
  }

  return (
    <select className="input" value={value} aria-label={label} onChange={(e) => onChange(e.target.value)}>
      <option value="">{t('scholarship.apply.plan.pathwayPlaceholder')}</option>
      {pathways.map((key) => (
        <option key={key} value={key}>{t(`scholarship.apply.plan.pathway.${key}`)}</option>
      ))}
    </select>
  )
}

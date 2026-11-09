'use client'

import { useT } from '@/lib/i18n'
import { roleBadgeClass } from '@/lib/roleBadge'

/**
 * The Team tables' chips — "Admin", "Reviewer", "Mentor", "Admin (lead)" — in ONE place, so the tables'
 * "Also in" column (`TeamTables.AlsoIn`) and a person's page (Sprint T3, D9: the chips under the name,
 * never a role word) cannot drift apart. Fed by the served `tables` / `lead`.
 */

// The role palette's own swatches (`lib/roleBadge`, ONE copy), so a table reads the colour its role does.
export const CHIP: Record<string, string> = {
  admins: roleBadgeClass('admin'),
  reviewers: roleBadgeClass('reviewer'),
  mentors: 'bg-positive-50 text-positive-700',
}

/** The chips for `tables`, leaving out `except` (the table the reader is looking at). Nothing when empty. */
export default function TableChips({ tables, lead, except, testId = 'table-chips' }: {
  tables?: readonly string[]
  lead?: boolean
  except?: string
  testId?: string
}) {
  const { t } = useT()
  const shown = (tables ?? []).filter((x) => x !== except)
  if (shown.length === 0) return null
  return (
    <span className="inline-flex flex-wrap gap-1" data-testid={testId}>
      {shown.map((x) => (
        <span key={x} className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${CHIP[x] ?? 'bg-ground-100'}`}>
          {x === 'admins' && lead ? t('admin.team.chip.lead') : t(`admin.team.chip.${x}`)}
        </span>
      ))}
    </span>
  )
}

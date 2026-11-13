'use client'

import Link from 'next/link'
import { useT } from '@/lib/i18n'
import { roleBadgeClass } from '@/lib/roleBadge'
import { teamChipLabel } from '@/lib/teamSort'

/**
 * The Team tables' chips — "Admin", "Reviewer", "Mentor", "Admin (lead)" — in ONE place, so the tables'
 * "Also in" column (`TeamTables.AlsoIn`) and a person's page (Sprint T3, D9: the chips under the name,
 * never a role word) cannot drift apart. Fed by the served `tables` / `lead`.
 *
 * Sprint M2a (U4): on a person page each chip may LINK to that group's page (`hrefs`, from
 * `lib/teamPaths.chipLinks`); the page's own group (`current`) is plain text with `aria-current="page"`.
 * A linked chip keeps the pill, inside a 44 px tap area on a phone (the mobile standard's floor).
 */

// The role palette's own swatches (`lib/roleBadge`, ONE copy), so a table reads the colour its role does.
export const CHIP: Record<string, string> = {
  admins: roleBadgeClass('admin'),
  reviewers: roleBadgeClass('reviewer'),
  mentors: 'bg-positive-50 text-positive-700',
}

/** The chips for `tables`, leaving out `except` (the table the reader is looking at). Nothing when empty. */
export default function TableChips({ tables, lead, except, testId = 'table-chips', hrefs, current }: {
  tables?: readonly string[]
  lead?: boolean
  except?: string
  testId?: string
  /** A group's page to link its chip to (the person page's other groups the viewer may open). */
  hrefs?: Partial<Record<string, string>>
  /** The group of the page the reader is on: plain, `aria-current="page"`. */
  current?: string
}) {
  const { t } = useT()
  const shown = (tables ?? []).filter((x) => x !== except)
  if (shown.length === 0) return null
  return (
    <span className="inline-flex flex-wrap items-center gap-1" data-testid={testId}>
      {shown.map((x) => {
        const pill = `rounded-full px-2 py-0.5 text-[11px] font-medium ${CHIP[x] ?? 'bg-ground-100'}`
        const label = teamChipLabel(x, lead, t)
        const href = x === current ? undefined : hrefs?.[x]
        return href ? (
          <Link key={x} href={href} data-testid={`chip-link-${x}`}
            className="rounded-full hover:underline focus-visible:outline-2 max-md:inline-flex max-md:min-h-11 max-md:min-w-11 max-md:items-center max-md:justify-center">
            <span className={pill}>{label}</span>
          </Link>
        ) : (
          <span key={x} className={pill} aria-current={x === current ? 'page' : undefined}>{label}</span>
        )
      })}
    </span>
  )
}

'use client'

/** THE OPENED DOCUMENT'S "CHECKS" PANEL — each chip with its state, plus the full read and upload time.
 *  A shell in Sprint 1: the family sprints add the reason and the side-by-side values. */
import { useT } from '@/lib/i18n'
import { formatReadTime, type ChipPillWord, type DocChipData } from '@/lib/docChips'
import { DocChip, DocPill } from '@/components/DocChip'

export interface DocChecks {
  chips: DocChipData[]
  pill: ChipPillWord
  /** null = never read; undefined = an old payload (say nothing). */
  readAt?: string | null
  uploadedAt?: string | null
}

export default function DocChecksPanel({ checks }: { checks: DocChecks }) {
  const { t, locale } = useT()
  const p = 'admin.scholarship.docsDrawer.'
  const read = formatReadTime(checks.readAt, { full: true, locale })
  const up = formatReadTime(checks.uploadedAt, { full: true, locale })
  return (
    <aside className="w-full shrink-0 overflow-auto border-t border-ground-100 bg-ground-0 p-4 max-md:max-h-[40dvh] md:w-72 md:border-l md:border-t-0"
      data-checks-panel aria-label={t(`${p}checks.title`)}>
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-widest text-ground-400">{t(`${p}checks.title`)}</h3>
        <DocPill pill={checks.pill}>{t(`${p}pill.${checks.pill}`)}</DocPill>
      </div>
      <p className="text-xs text-ground-500">
        {read ? t(`${p}checks.readAt`, { datetime: read }) : checks.readAt === null ? t(`${p}readAtNone`) : null}
      </p>
      {up && <p className="mb-3 text-xs text-ground-500">{t(`${p}checks.uploadedAt`, { datetime: up })}</p>}
      {checks.chips.length === 0 ? (
        <p className="mt-3 text-xs text-ground-400">{t(`${p}checks.empty`)}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {checks.chips.map((c, i) => (
            <li key={`${c.key}-${i}`} className="rounded-lg border border-ground-100 px-2.5 py-2" data-check={c.state}>
              <DocChip state={c.state}>
                {c.kind === 'year'
                  ? t(`${p}${c.key}`, { year: String(c.value ?? '') })
                  : t(`${p}fact.${c.key}`)}
              </DocChip>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}

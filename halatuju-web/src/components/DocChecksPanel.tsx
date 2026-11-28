'use client'

/** THE OPENED DOCUMENT'S "CHECKS" PANEL — each chip with its state and reason, plus the full read and upload time.
 *  A water or electricity bill also shows what the bill says beside what the application says (chip Sprint 2):
 *  the only place a name or an address appears. */
import { useT } from '@/lib/i18n'
import { formatReadTime, STATE_COLOURS, type ChipPillWord, type DocChipData } from '@/lib/docChips'
import type { BillChecks } from '@/lib/billChecks'
import { DocChip, DocPill } from '@/components/DocChip'
import { REASON_WORDS, chipText } from '@/app/admin/scholarship/[id]/view/docChipRow'

export interface DocChecks {
  chips: DocChipData[]
  pill: ChipPillWord
  /** null = never read; undefined = an old payload (say nothing). */
  readAt?: string | null
  uploadedAt?: string | null
  /** A bill only: the bill read beside the application. */
  bill?: BillChecks
}

const P = 'admin.scholarship.docsDrawer.'

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="text-xs">
      <dt className="text-ground-400">{label}</dt>
      <dd className="text-ground-700 break-words">{children}</dd>
    </div>
  )
}

function BillBlock({ bill, chips }: { bill: BillChecks; chips: DocChipData[] }) {
  const { t } = useT()
  const dateState = chips.find((c) => c.key === 'date')?.state
  const none = t(`${P}checks.bill.none`)
  const reasonableWord = bill.reasonable ? t(`${P}checks.bill.reasonableValue.${bill.reasonable}`) : none
  return (
    <div className="mt-4 space-y-3 border-t border-ground-100 pt-3" data-bill-checks>
      <dl className="space-y-1.5">
        <Row label={t(`${P}checks.bill.holder`)}>{bill.holder || none}</Row>
        <Row label={t(`${P}checks.bill.appNames`)}>{bill.appNames.length ? bill.appNames.join(' · ') : none}</Row>
      </dl>
      <dl className="space-y-1.5">
        <Row label={t(`${P}checks.bill.billAddress`)}>{bill.billAddress || none}</Row>
        <Row label={t(`${P}checks.bill.appAddress`)}>{bill.appAddress || none}</Row>
      </dl>
      <dl className="space-y-1.5">
        <Row label={t(`${P}checks.bill.billDate`)}>
          <span className={dateState ? STATE_COLOURS[dateState].text : ''}>{bill.billMonth || none}</span>
        </Row>
        <Row label={t(`${P}checks.bill.dateRule`)}>{t(`${P}checks.bill.dateRuleText`)}</Row>
      </dl>
      <dl className="space-y-1.5">
        <Row label={t(`${P}billValue.amount`)}>{bill.amount || none}</Row>
        <Row label={t(`${P}billValue.period`)}>{bill.period || none}</Row>
        <Row label={t(`${P}fact.reasonable`)}>{reasonableWord}</Row>
        <Row label={t(`${P}fact.outstanding`)}>{bill.arrears || (bill.amount ? t(`${P}billValue.none`) : none)}</Row>
      </dl>
      {bill.nameNote === 'unrelated' && (
        <p className="text-xs text-critical-600">{t(`${P}utilityNote.unrelated`, { name: bill.holder })}</p>
      )}
      {(bill.reasonableDetail === 'water_only' || bill.reasonableDetail === 'electricity_only') && (
        <p className="text-xs text-ground-400">{t(`${P}utilityNote.${bill.reasonableDetail}`)}</p>
      )}
    </div>
  )
}

export default function DocChecksPanel({ checks }: { checks: DocChecks }) {
  const { t, locale } = useT()
  const p = P
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
          {checks.chips.map((c, i) => {
            const word = (c.state === 'amber' || c.state === 'red') ? REASON_WORDS[`${c.key}.${c.reason}`] : undefined
            return (
              <li key={`${c.key}-${i}`} className="rounded-lg border border-ground-100 px-2.5 py-2" data-check={c.state}>
                <DocChip state={c.state} plain={c.kind === 'plain'}>{chipText(c, t)}</DocChip>
                {word && <p className={`mt-1 text-[11.5px] leading-snug ${STATE_COLOURS[c.state].line}`} data-check-reason>{t(word)}</p>}
              </li>
            )
          })}
        </ul>
      )}
      {checks.bill && <BillBlock bill={checks.bill} chips={checks.chips} />}
    </aside>
  )
}

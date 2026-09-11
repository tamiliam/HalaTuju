'use client'

/**
 * One shop per row: what it was counted as, how that was decided, the money — and the correction.
 *
 * ⚠⚠ **THE SPENDING SCREEN DRAWS THIS LIST TWICE** — every shop under **Shops**, and the ones with
 * money we could not place under **Unsorted**. It is a component rather than a copy for the reason
 * `StaffAdmin` learned the hard way (docs/lessons.md, People actions 2026-09-09): a rule copied
 * into a second rendering is a rule that will be fixed in one of them. Every conditional about a
 * shop row — the pill, the held-back line, which control corrects it — lives here, once.
 *
 * ⚠ **THE CATEGORY CONTROL IS A NATIVE `<select>` AND MUST STAY ONE.** `TableFrame` establishes two
 * clipping contexts (rounded corners, and the horizontal scroller), so a hand-rolled absolute
 * dropdown inside a cell is sliced off at the table's edge — that really happened on the Intake
 * years badge (2026-09-08) and the owner reported it as a panel that opens and cannot be seen. A
 * native select's list is drawn by the browser outside the document, so nothing can clip it.
 *
 * ⚠ **THE ROW IS A SHOP, NOT A PAYMENT.** You fix a shop once and every payment at it follows; a
 * per-payment screen would ask the same question forty times for one stall.
 *
 * ⚠ Each instance keeps its OWN sort and page. The two tabs are different lists, and a reader
 * ordering the unsorted shops by "last seen" has not asked anything about the full list.
 */
import TableFrame from '@/components/admin/TableFrame'
import SortHeader from '@/components/admin/SortHeader'
import { Pagination } from '@/components/Pagination'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { PAGE_SIZE_OPTIONS, nextSort } from '@/lib/tableView'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import {
  MERCHANT_DEFAULT_SORT, MERCHANT_SORT_LABEL, merchantFirstDir, sortMerchants,
  type MerchantSortKey,
} from '@/lib/spendingTable'
import type { SpendingMerchantRow } from '@/lib/admin-api'

/** Thousands grouping by hand, so server and browser render identically (no locale drift).
 *  ⚠ The value arrives as a STRING and is never parsed to a Number and back — this is money. */
export const rm = (v: string) => {
  const [whole, cents = '00'] = String(v).split('.')
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`
}

/** The pill under "How we decided". Only `owner` — your own answer — carries the accent. */
export function decidedPill(decidedBy: string) {
  return decidedBy === 'owner'
    ? 'bg-info-100 text-info-700'
    : 'bg-ground-100 text-ground-600'
}

export default function SpendingShops({
  rows, categories, onCorrect, saving, loading, emptyKey, labelKey, testId,
}: {
  rows: SpendingMerchantRow[]
  categories: { code: string; label: string }[]
  onCorrect: (merchant: string, category: string) => void
  /** The merchant currently being saved, or ''. Its control is disabled while it saves. */
  saving: string
  loading: boolean
  /** What to say when there is nothing — the two tabs mean different things by empty. */
  emptyKey: string
  /** The scrolling region's accessible name. ⚠ Must resolve — `pageWidth.test.ts` checks it. */
  labelKey: string
  testId: string
}) {
  const { t } = useT()
  const { sort, setSort } = useSort<MerchantSortKey>(MERCHANT_DEFAULT_SORT)
  const labels: Record<string, string> = {}
  categories.forEach((c) => { labels[c.code] = c.label })

  // Sort the WHOLE list, then take a page of the sorted result. The other order sorts one page at
  // a time and shuffles rows between pages.
  const paged = usePagedRows(sortMerchants(rows, sort.key, sort.dir, labels))
  const onSort = (col: MerchantSortKey) => setSort(nextSort(sort, col, merchantFirstDir(col)))

  /** The correction control. Drawn twice (card + row), so it is written once. */
  const categoryBox = (m: SpendingMerchantRow, className: string) => (
    <select
      aria-label={`${t('admin.spending.col.countedAs')} — ${m.merchant}`}
      className={className}
      value={m.category || 'unsorted'}
      disabled={saving === m.merchant}
      onChange={(e) => onCorrect(m.merchant, e.target.value)}
    >
      {categories.map((c) => (
        <option key={c.code} value={c.code}>{c.label}</option>
      ))}
    </select>
  )

  const heldBack = (m: SpendingMerchantRow, className: string) => (
    m.held_back > 0
      ? <p className={className}>{t('admin.spending.heldBack', { count: String(m.held_back) })}</p>
      : null
  )

  const empty = !loading && rows.length === 0

  return (
    <>
      {/* ── PHONE: one card per shop (the console standard, owner 2026-09-08). A six-column table
          dragged sideways is safe but wrong-shaped for the screen people actually check things
          on. The SHOP and its category lead, because this list is scanned for what to correct. ── */}
      <div className="space-y-2.5 md:hidden" data-testid={`${testId}-cards`}>
        {paged.rows.map((m) => (
          <div key={m.merchant} className="rounded-xl border border-ground-200 bg-ground-0 p-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-semibold text-ground-900">{m.merchant}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${decidedPill(m.decided_by)}`}>
                {t(`admin.spending.by.${m.decided_by || 'none'}`)}
              </span>
            </div>
            <div className="mt-2">
              {categoryBox(m, 'w-full rounded-md border border-ground-200 bg-ground-0 px-2 py-1.5 text-sm text-ground-700')}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ground-600">
              <span className="tabular-nums">RM{rm(m.total)}</span>
              <span>{t('admin.spending.col.visits')}{' '}
                <span className="tabular-nums">{m.visits}</span></span>
              {m.last_seen && <span>{formatDate(m.last_seen)}</span>}
            </div>
            {heldBack(m, 'mt-1 text-[11px] text-ground-500')}
          </div>
        ))}
        {empty && <p className="py-6 text-center text-sm text-ground-400">{t(emptyKey)}</p>}
      </div>

      <TableFrame className="hidden md:block" minWidth={760} label={t(labelKey)}>
        <table className="w-full text-sm">
          <thead className="bg-ground-50 border-b">
            <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
              <SortHeader col="shop" label={t(MERCHANT_SORT_LABEL.shop)} sort={sort} onSort={onSort} />
              <SortHeader col="countedAs" label={t(MERCHANT_SORT_LABEL.countedAs)} sort={sort} onSort={onSort} />
              <SortHeader col="decidedBy" label={t(MERCHANT_SORT_LABEL.decidedBy)} sort={sort} onSort={onSort} />
              <SortHeader col="visits" label={t(MERCHANT_SORT_LABEL.visits)} sort={sort} onSort={onSort} align="right" />
              <SortHeader col="total" label={t(MERCHANT_SORT_LABEL.total)} sort={sort} onSort={onSort} align="right" />
              <SortHeader col="lastSeen" label={t(MERCHANT_SORT_LABEL.lastSeen)} sort={sort} onSort={onSort} />
            </tr>
          </thead>
          <tbody className="divide-y divide-ground-100">
            {paged.rows.map((m) => (
              <tr key={m.merchant} className="hover:bg-info-50/40">
                <td className="px-4 py-3 font-medium text-ground-900">
                  {m.merchant}
                  {heldBack(m, 'mt-0.5 block text-[11px] font-normal text-ground-500')}
                </td>
                <td className="px-4 py-3">
                  {/* ⚠ NATIVE select — see the file header. Do not replace with a custom panel. */}
                  {categoryBox(m, 'rounded-md border border-ground-200 bg-ground-0 px-2 py-1 text-sm text-ground-700')}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${decidedPill(m.decided_by)}`}>
                    {t(`admin.spending.by.${m.decided_by || 'none'}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-ground-700">{m.visits}</td>
                <td className="px-4 py-3 text-right font-medium tabular-nums text-ground-900">
                  RM{rm(m.total)}
                </td>
                <td className="px-4 py-3 text-ground-500">
                  {m.last_seen ? formatDate(m.last_seen) : '—'}
                </td>
              </tr>
            ))}
            {empty && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-ground-400">
                {t(emptyKey)}
              </td></tr>
            )}
          </tbody>
        </table>
      </TableFrame>

      {/* ⚠ The footer is OUTSIDE the frame because the phone cards need it too — the frame is the
          desktop rendering only. `paged.visible` is false on a short list, which is what stops the
          page-size selector appearing above four rows. */}
      {paged.visible && (
        <div className="mt-3">
          <Pagination
            page={paged.page} totalPages={paged.totalPages} pageSize={paged.pageSize}
            onPageChange={paged.setPage}
            pageSizeOptions={PAGE_SIZE_OPTIONS} onPageSizeChange={paged.setPageSize}
          />
        </div>
      )}
    </>
  )
}

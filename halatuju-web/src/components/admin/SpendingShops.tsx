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
 * ⚠ **"CHECKED – STILL UNKNOWN" IS A UI-ONLY OPTION** (request #28 follow-up). A native select
 * fires no change when you choose the value it already shows, so a shop the sorter left
 * `unsorted` (every row on the Unsorted tab) could never be marked as checked by choosing
 * "Not yet sorted". The extra option carries a sentinel value that is NEVER sent: `onChange` maps
 * it to `unsorted`, which the server stores with `decided_by='owner'`. A shop already checked
 * shows the sentinel and is not offered plain "Not yet sorted" — the two would mean the same.
 *
 * ⚠ **THE FLAG (request #28 follow-up) OPENS A MODAL, NEVER A POPOVER IN THE TABLE.** For the same
 * clipping reason, the flag dialog is drawn ONCE, outside `TableFrame`, `fixed` over the page
 * (`LazyMerchantFlagDialog`). A flag is THIS organisation's question about a shop — it changes no
 * category and no total, and the server never sends another organisation's.
 *
 * ⚠ **THE ROW IS A SHOP, NOT A PAYMENT.** You fix a shop once and every payment at it follows; a
 * per-payment screen would ask the same question forty times for one stall.
 *
 * ⚠ Each instance keeps its OWN sort and page. The two tabs are different lists, and a reader
 * ordering the unsorted shops by "last seen" has not asked anything about the full list.
 */
import TableFrame from '@/components/admin/TableFrame'
import LazyMerchantFlagDialog from '@/components/admin/LazyMerchantFlagDialog'
import SortHeader from '@/components/admin/SortHeader'
import { Pagination } from '@/components/Pagination'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { PAGE_SIZE_OPTIONS, nextSort } from '@/lib/tableView'
import { usePagedRows, useSort } from '@/lib/usePagedRows'
import { useState } from 'react'
import {
  MERCHANT_DEFAULT_SORT, MERCHANT_SORT_LABEL, filterMerchants, merchantAverage, merchantFirstDir,
  sortMerchants, type MerchantSortKey,
} from '@/lib/spendingTable'
import type { SpendingMerchantRow } from '@/lib/admin-api'

/** The checked-but-unsorted option's value. ⚠ Never reaches the server — see the file header. */
const CHECKED = 'unsorted:checked'

/** The rungs a shop's category can come from, in the order the filter offers them. `none` is the
 *  blank — a real state (the sorter has not reached this shop), not an absence. */
const DECIDED_BY_OPTIONS = ['owner', 'rule', 'inferred', 'ai', 'duitnow', 'none'] as const

/** Thousands grouping by hand, so server and browser render identically (no locale drift).
 *  ⚠ The value arrives as a STRING and is never parsed to a Number and back — this is money. */
export const rm = (v: string) => {
  const [whole, cents = '00'] = String(v).split('.')
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`
}

/** Average per transaction, in the same `RM` form as Total; a dash when there are no visits. */
const avg = (m: SpendingMerchantRow) => {
  const a = merchantAverage(m)
  return a === null ? '—' : `RM${rm(a)}`
}

/** The pill under "How we decided". Only `owner` — your own answer — carries the accent. */
export function decidedPill(decidedBy: string) {
  return decidedBy === 'owner'
    ? 'bg-info-100 text-info-700'
    : 'bg-ground-100 text-ground-600'
}

/** A small flag: outlined, or FILLED when this organisation has the shop flagged. */
const FlagGlyph = ({ on }: { on: boolean }) => (
  <svg aria-hidden="true" focusable="false" width={16} height={16} viewBox="0 0 24 24"
    fill={on ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth={1.75}
    strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 21V4M5 4h12l-2.5 4L17 12H5" />
  </svg>
)

export default function SpendingShops({
  rows, categories, onCorrect, saving, loading, emptyKey, labelKey, testId, flagGift, onFlagChanged,
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
  /** The gift the rows on screen belong to — a flag change names it, as a correction does. */
  flagGift: string | undefined
  /** A flag was opened, noted or cleared: re-read the list. */
  onFlagChanged: () => void
}) {
  const { t } = useT()
  const { sort, setSort } = useSort<MerchantSortKey>(MERCHANT_DEFAULT_SORT)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [decidedBy, setDecidedBy] = useState('')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  /** The shop whose flag dialog is open, or ''. */
  const [flagFor, setFlagFor] = useState('')
  const labels: Record<string, string> = {}
  categories.forEach((c) => { labels[c.code] = c.label })

  // ⚠ FILTER, then SORT, then PAGE. Any other order is a defect with a plausible-looking screen:
  // sorting a page shuffles rows between pages, and paging before filtering shows a first page
  // with holes in it. `page.test.tsx` pins the sort/page half of this.
  const shown = filterMerchants(rows, { query, category, decidedBy, flaggedOnly })
  const paged = usePagedRows(sortMerchants(shown, sort.key, sort.dir, labels))
  const onSort = (col: MerchantSortKey) => setSort(nextSort(sort, col, merchantFirstDir(col)))
  const filtered = shown.length !== rows.length

  /** The correction control. Drawn twice (card + row), so it is written once. */
  const categoryBox = (m: SpendingMerchantRow, className: string) => {
    const unsorted = (m.category || 'unsorted') === 'unsorted'
    const checked = unsorted && m.decided_by === 'owner'
    return (
      <select
        aria-label={`${t('admin.spending.col.countedAs')} — ${m.merchant}`}
        className={className}
        value={checked ? CHECKED : m.category || 'unsorted'}
        disabled={saving === m.merchant}
        onChange={(e) => onCorrect(m.merchant, e.target.value === CHECKED ? 'unsorted' : e.target.value)}
      >
        {categories.flatMap((c) => (c.code === 'unsorted' && unsorted
          ? [
              ...(checked ? [] : [<option key={c.code} value={c.code}>{c.label}</option>]),
              <option key={CHECKED} value={CHECKED}>{t('admin.spending.checked')}</option>,
            ]
          : [<option key={c.code} value={c.code}>{c.label}</option>]))}
      </select>
    )
  }

  /** The flag button. Drawn twice (card + row). Its name says the shop, and whether it is flagged. */
  const flagButton = (m: SpendingMerchantRow) => (
    <button
      type="button"
      aria-haspopup="dialog"
      aria-label={`${t('admin.spending.flag.col')} — ${m.merchant}${m.flagged ? ` (${t('admin.spending.flag.opened')})` : ''}`}
      onClick={() => setFlagFor(m.merchant)}
      className={`rounded p-1 ${m.flagged ? 'text-caution-700' : 'text-ground-400 hover:text-ground-700'}`}
    >
      <FlagGlyph on={m.flagged} />
    </button>
  )

  const heldBack = (m: SpendingMerchantRow, className: string) => (
    m.held_back > 0
      ? <p className={className}>{t('admin.spending.heldBack', { count: String(m.held_back) })}</p>
      : null
  )

  // ⚠ TWO DIFFERENT EMPTIES, AND SAYING THE WRONG ONE IS A LIE. "No spending recorded" on a list
  // that is merely filtered down to nothing tells a reader their data is missing. The filtered
  // case says so, and offers the way back.
  const empty = !loading && paged.rows.length === 0
  const emptyMessage = empty && filtered ? t('admin.spending.noMatch') : t(emptyKey)

  const clear = () => { setQuery(''); setCategory(''); setDecidedBy(''); setFlaggedOnly(false) }

  const controls = (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('admin.spending.searchShops')}
        aria-label={t('admin.spending.searchShops')}
        className="min-w-0 flex-1 rounded-md border border-ground-200 bg-ground-0 px-3 py-1.5 text-sm text-ground-800 placeholder:text-ground-placeholder sm:max-w-xs"
      />
      <select
        aria-label={t('admin.spending.filter.categoryLabel')}
        value={category}
        onChange={(e) => setCategory(e.target.value)}
        className="rounded-md border border-ground-200 bg-ground-0 px-2 py-1.5 text-sm text-ground-700"
      >
        <option value="">{t('admin.spending.filter.allCategories')}</option>
        {categories.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
      </select>
      <select
        aria-label={t('admin.spending.filter.decidedByLabel')}
        value={decidedBy}
        onChange={(e) => setDecidedBy(e.target.value)}
        className="rounded-md border border-ground-200 bg-ground-0 px-2 py-1.5 text-sm text-ground-700"
      >
        <option value="">{t('admin.spending.filter.anyDecidedBy')}</option>
        {DECIDED_BY_OPTIONS.map((d) => (
          <option key={d} value={d}>{t(`admin.spending.by.${d}`)}</option>
        ))}
      </select>
      <label className="flex items-center gap-1.5 text-sm text-ground-700">
        <input type="checkbox" checked={flaggedOnly}
          onChange={(e) => setFlaggedOnly(e.target.checked)} />
        {t('admin.spending.flag.only')}
      </label>
      {filtered && (
        <button type="button" onClick={clear}
          className="text-xs font-medium text-primary-600 hover:underline">
          {t('admin.spending.filter.clear')}
        </button>
      )}
      {/* ⚠ The count of what is SHOWING, beside the controls that changed it — deliberately not
          on the tab, where the number must keep meaning "how many are there in total". */}
      {filtered && (
        <span className="text-xs text-ground-500" data-testid={`${testId}-showing`}>
          {t('admin.spending.filter.showing', {
            shown: String(shown.length), total: String(rows.length),
          })}
        </span>
      )}
    </div>
  )

  return (
    <>
      {controls}
      {/* ── PHONE: one card per shop (the console standard, owner 2026-09-08). A six-column table
          dragged sideways is safe but wrong-shaped for the screen people actually check things
          on. The SHOP and its category lead, because this list is scanned for what to correct. ── */}
      <div className="space-y-2.5 md:hidden" data-testid={`${testId}-cards`}>
        {paged.rows.map((m) => (
          <div key={m.merchant} className="rounded-xl border border-ground-200 bg-ground-0 p-3">
            <div className="flex items-start justify-between gap-3">
              <span className="text-sm font-semibold text-ground-900">{m.merchant}</span>
              <span className="flex shrink-0 items-center gap-1">
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${decidedPill(m.decided_by)}`}>
                  {t(`admin.spending.by.${m.decided_by || 'none'}`)}
                </span>
                {flagButton(m)}
              </span>
            </div>
            <div className="mt-2">
              {categoryBox(m, 'w-full rounded-md border border-ground-200 bg-ground-0 px-2 py-1.5 text-sm text-ground-700')}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ground-600">
              <span className="tabular-nums">RM{rm(m.total)}</span>
              <span>{t('admin.spending.col.visits')}{' '}
                <span>{m.visits}</span></span>
              <span>{t('admin.spending.col.average')}{' '}
                <span>{avg(m)}</span></span>
              {m.last_seen && <span>{formatDate(m.last_seen)}</span>}
            </div>
            {heldBack(m, 'mt-1 text-[11px] text-ground-500')}
          </div>
        ))}
        {empty && <p className="py-6 text-center text-sm text-ground-400">{emptyMessage}</p>}
      </div>

      <TableFrame className="hidden md:block" minWidth={840} label={t(labelKey)}>
        <table className="w-full text-sm">
          <thead className="bg-ground-50 border-b">
            <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
              <SortHeader col="shop" label={t(MERCHANT_SORT_LABEL.shop)} sort={sort} onSort={onSort} />
              <SortHeader col="countedAs" label={t(MERCHANT_SORT_LABEL.countedAs)} sort={sort} onSort={onSort} />
              <SortHeader col="decidedBy" label={t(MERCHANT_SORT_LABEL.decidedBy)} sort={sort} onSort={onSort} />
              <SortHeader col="visits" label={t(MERCHANT_SORT_LABEL.visits)} sort={sort} onSort={onSort} align="right" />
              <SortHeader col="total" label={t(MERCHANT_SORT_LABEL.total)} sort={sort} onSort={onSort} align="right" />
              <SortHeader col="average" label={t(MERCHANT_SORT_LABEL.average)} sort={sort} onSort={onSort} align="right" />
              <SortHeader col="lastSeen" label={t(MERCHANT_SORT_LABEL.lastSeen)} sort={sort} onSort={onSort} />
              <SortHeader col="decidedAt" label={t(MERCHANT_SORT_LABEL.decidedAt)} sort={sort} onSort={onSort} />
              <th className="w-12 px-2 py-3 font-semibold">{t('admin.spending.flag.col')}</th>
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
                <td className="px-4 py-3 text-right tabular-nums text-ground-700">{avg(m)}</td>
                <td className="px-4 py-3 text-ground-500">
                  {m.last_seen ? formatDate(m.last_seen) : '—'}
                </td>
                <td className="px-4 py-3 text-ground-500">
                  {m.decided_at ? formatDate(m.decided_at.slice(0, 10)) : '—'}
                </td>
                <td className="px-2 py-3">{flagButton(m)}</td>
              </tr>
            ))}
            {empty && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-ground-400">
                {emptyMessage}
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

      {/* ⚠ ONCE, OUTSIDE THE FRAME — `TableFrame` clips; a modal drawn here cannot be. */}
      {flagFor && (
        <LazyMerchantFlagDialog
          merchant={flagFor} programme={flagGift}
          onClose={() => setFlagFor('')} onChanged={onFlagChanged}
        />
      )}
    </>
  )
}

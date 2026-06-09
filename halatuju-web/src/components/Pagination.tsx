'use client'

/**
 * Reusable pagination control for partner-admin tables.
 *
 * Stateless: it renders from the props it's given and reports intent back via
 * callbacks. Pair it with server-side pagination — the parent owns `page` /
 * `pageSize` state, fetches the matching page, and passes `total` / `totalPages`
 * from the API response. Designed to be dropped onto any admin table.
 *
 * Footer layout mirrors the MySkills admin tables: a "Show [n] per page ·
 * Page X of Y · [Page][Go]" cluster on the left and First / Previous / Next /
 * Last controls on the right; a compact "‹ Page X of Y ›" on mobile.
 */
import { useState } from 'react'
import { useT } from '@/lib/i18n'

interface PaginationProps {
  page: number
  totalPages: number
  /** Kept for call-site compatibility; the footer now shows "Page X of Y". */
  total?: number
  pageSize: number
  onPageChange: (page: number) => void
  /** Optional page-size selector. Provide both to show it. */
  pageSizeOptions?: number[]
  onPageSizeChange?: (size: number) => void
  /** Retained for call-site compatibility; no longer rendered. */
  rangeKey?: string
}

const NAV_BTN =
  'text-sm py-1.5 rounded-lg border border-primary-500 text-primary-500 bg-white font-medium ' +
  'hover:bg-primary-50 transition-colors disabled:opacity-30 disabled:cursor-not-allowed'

export function Pagination({
  page,
  totalPages,
  pageSize,
  onPageChange,
  pageSizeOptions,
  onPageSizeChange,
}: PaginationProps) {
  const { t } = useT()
  const [jumpValue, setJumpValue] = useState('')

  const showPageSize = pageSizeOptions && onPageSizeChange
  if (totalPages <= 1 && !showPageSize) return null

  function handleJump(e: React.FormEvent) {
    e.preventDefault()
    const target = parseInt(jumpValue, 10)
    if (target >= 1 && target <= totalPages) {
      onPageChange(target)
      setJumpValue('')
    }
  }

  const pageOf = t('admin.pageOf', { page: String(page), total: String(totalPages) })

  return (
    <div className="w-full mt-4 pt-4 border-t border-gray-100">
      {/* Mobile: compact inline ‹ Page X of Y › */}
      <div className="flex sm:hidden items-center justify-center gap-3">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed p-1 transition-colors"
          aria-label={t('admin.previous')}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
          </svg>
        </button>
        <p className="text-sm text-gray-500">{pageOf}</p>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="text-gray-500 hover:text-gray-700 disabled:opacity-30 disabled:cursor-not-allowed p-1 transition-colors"
          aria-label={t('admin.next')}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
          </svg>
        </button>
      </div>

      {/* Desktop: full controls */}
      <div className="hidden sm:flex items-center justify-between">
        <div className="flex items-center gap-4">
          {showPageSize && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">{t('admin.show')}</span>
              <select
                value={pageSize}
                onChange={(e) => onPageSizeChange!(Number(e.target.value))}
                className="text-xs border border-gray-200 rounded px-1.5 py-1 text-gray-600 bg-white"
                aria-label={t('admin.show')}
              >
                {pageSizeOptions!.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
              <span className="text-xs text-gray-400">{t('admin.perPageSuffix')}</span>
            </div>
          )}
          <p className="text-sm text-gray-500 whitespace-nowrap">{pageOf}</p>
          {totalPages > 5 && (
            <form onSubmit={handleJump} className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={totalPages}
                value={jumpValue}
                onChange={(e) => setJumpValue(e.target.value)}
                placeholder={t('admin.pageJump')}
                aria-label={t('admin.pageJump')}
                className="w-16 text-xs border border-gray-200 rounded px-2 py-1 text-gray-600 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <button type="submit" className="text-sm py-1 px-2.5 rounded-lg border border-primary-500 text-primary-500 bg-white font-medium hover:bg-primary-50 transition-colors">
                {t('admin.go')}
              </button>
            </form>
          )}
        </div>
        <div className="flex gap-1.5">
          <button onClick={() => onPageChange(1)} disabled={page <= 1} className={`${NAV_BTN} px-2.5`}>
            {t('admin.first')}
          </button>
          <button onClick={() => onPageChange(page - 1)} disabled={page <= 1} className={`${NAV_BTN} px-3`}>
            {t('admin.previous')}
          </button>
          <button onClick={() => onPageChange(page + 1)} disabled={page >= totalPages} className={`${NAV_BTN} px-3`}>
            {t('admin.next')}
          </button>
          <button onClick={() => onPageChange(totalPages)} disabled={page >= totalPages} className={`${NAV_BTN} px-2.5`}>
            {t('admin.last')}
          </button>
        </div>
      </div>
    </div>
  )
}

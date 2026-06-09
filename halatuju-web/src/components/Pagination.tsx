'use client'

/**
 * Reusable pagination control for partner-admin tables.
 *
 * Stateless: it renders from the props it's given and reports intent back via
 * callbacks. Pair it with server-side pagination — the parent owns `page` /
 * `pageSize` state, fetches the matching page, and passes `total` / `totalPages`
 * from the API response. Designed to be dropped onto any admin table.
 */
import { useT } from '@/lib/i18n'
import { pageWindow } from '@/lib/pagination'

interface PaginationProps {
  page: number
  totalPages: number
  total: number
  pageSize: number
  onPageChange: (page: number) => void
  /** Optional page-size selector. Provide both to show it. */
  pageSizeOptions?: number[]
  onPageSizeChange?: (size: number) => void
}

export function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
  pageSizeOptions,
  onPageSizeChange,
}: PaginationProps) {
  const { t } = useT()
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 mt-4 text-sm text-gray-500">
      <div className="flex items-center gap-3">
        <span>
          {t('admin.showingRange', { start: String(start), end: String(end), total: String(total) })}
        </span>
        {pageSizeOptions && onPageSizeChange && (
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="border border-gray-200 rounded-lg px-2 py-1 text-sm bg-white text-gray-600"
            aria-label={t('admin.perPage', { n: String(pageSize) })}
          >
            {pageSizeOptions.map((o) => (
              <option key={o} value={o}>
                {t('admin.perPage', { n: String(o) })}
              </option>
            ))}
          </select>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-2.5 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            &lsaquo;
          </button>
          {pageWindow(page, totalPages).map((p, i) =>
            p === 'gap' ? (
              <span key={`gap-${i}`} className="w-8 h-8 flex items-center justify-center text-gray-400">
                &hellip;
              </span>
            ) : (
              <button
                key={p}
                onClick={() => onPageChange(p)}
                aria-current={p === page ? 'page' : undefined}
                className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                  p === page ? 'bg-blue-600 text-white' : 'hover:bg-gray-50 border border-gray-200'
                }`}
              >
                {p}
              </button>
            ),
          )}
          <button
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="px-2.5 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            &rsaquo;
          </button>
        </div>
      )}
    </div>
  )
}

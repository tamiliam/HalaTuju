'use client'

/**
 * Page state for a client-side table (2026-07-28).
 *
 * Four tables needed the same three pieces of state and the same two corrections, so they live
 * here once rather than four times:
 *
 *   * the page **resets to 1** when the row count changes — otherwise filtering the sponsors list
 *     down to "pending" while on page 3 shows an empty table, and
 *   * the page is **clamped** on read, so it can never point past the end.
 */
import { useEffect, useState } from 'react'
import {
  DEFAULT_PAGE_SIZE, pageOf, shouldPaginate, totalPages, type SortDir,
} from './tableView'

export interface PagedRows<T> {
  /** Just this page's rows — what the table body renders. */
  rows: T[]
  page: number
  setPage: (p: number) => void
  pageSize: number
  setPageSize: (n: number) => void
  totalPages: number
  /** False → render no footer at all (the Pagination component would show its size selector). */
  visible: boolean
}

export function usePagedRows<T>(all: T[], initialPageSize = DEFAULT_PAGE_SIZE): PagedRows<T> {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(initialPageSize)

  // A shorter list must not leave the viewer stranded on a page that no longer exists.
  useEffect(() => { setPage(1) }, [all.length, pageSize])

  const pages = totalPages(all.length, pageSize)
  return {
    rows: pageOf(all, page, pageSize),
    page: Math.min(page, pages),
    setPage,
    pageSize,
    setPageSize,
    totalPages: pages,
    visible: shouldPaginate(all.length, pageSize),
  }
}

/** Sort state for a table whose columns are keyed by a string union. */
export function useSort<K extends string>(initial: { key: K; dir: SortDir }) {
  const [sort, setSort] = useState(initial)
  return { sort, setSort }
}

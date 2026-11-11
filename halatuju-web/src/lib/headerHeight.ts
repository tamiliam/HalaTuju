'use client'

import { useEffect } from 'react'

/**
 * The student header's height as the CSS variable `--header-height` on <html> (TD-457; the `--bottom-bar`
 * pattern, `bottomBarInset.ts`). Its height includes the notch's safe area and its border, so a row that
 * sticks under it (the saved compare's course names) uses `var(--header-height, <fallback>)`.
 *
 * ⚠ THE ROW'S OWNER MEASURES THE HEADER, not the header itself: `AppHeader` rides every student route's
 * shared chunk, and a page that needs no number should not carry the code. The header is found by its
 * `data-app-header` mark. Removed on unmount.
 */
export function useHeaderHeight(): void {
  useEffect(() => {
    const el = document.querySelector<HTMLElement>('[data-app-header]')
    if (!el) return
    const root = document.documentElement
    const set = () => root.style.setProperty('--header-height', `${el.offsetHeight}px`)
    set()
    const o = typeof ResizeObserver == 'function' ? new ResizeObserver(set) : null
    o?.observe(el)
    return () => { o?.disconnect(); root.style.removeProperty('--header-height') }
  }, [])
}

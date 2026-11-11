'use client'

import { useEffect, type RefObject } from 'react'

/**
 * The student header tells the page how tall it is (TD-457), as the CSS variable `--header-height` on
 * <html> (the `--bottom-bar` pattern, `bottomBarInset.ts`). Its height includes the notch's safe area
 * and its border, so a row that sticks under it (the saved compare's course names) uses
 * `var(--header-height, <fallback>)` and never hides under it or floats below it. Removed on unmount.
 */
export function useHeaderHeight(ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const root = document.documentElement
    const set = () => root.style.setProperty('--header-height', `${el.offsetHeight}px`)
    set()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(set) : null
    observer?.observe(el)
    window.addEventListener('resize', set)
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', set)
      root.style.removeProperty('--header-height')
    }
  }, [ref])
}

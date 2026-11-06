'use client'

import { useEffect, type RefObject } from 'react'

/**
 * A phone's sticky bottom bar tells the page how tall it is (Mobile M3), as the CSS variable
 * `--bottom-bar` on <html>, so the toast (`components/Toast.tsx`) rises above it instead of
 * covering the button the student just pressed. A bar hidden from `md` (`md:hidden`) measures 0,
 * so on a desktop the toast keeps its place. The variable is removed when the bar unmounts.
 *
 * One bar at a time: the course pages' Save bar and the saved page's compare bar never share a page.
 */
export function useBottomBarInset(ref: RefObject<HTMLElement | null>, shown = true): void {
  // `shown`: a bar that mounts LATER than its owner (the compare bar, on the first tick) re-measures.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const root = document.documentElement
    const set = () => root.style.setProperty('--bottom-bar', `${el.offsetHeight}px`)
    set()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(set) : null
    observer?.observe(el)
    window.addEventListener('resize', set)
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', set)
      root.style.removeProperty('--bottom-bar')
    }
  }, [ref, shown])
}

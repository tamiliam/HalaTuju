'use client'

import { useEffect, useState } from 'react'

/**
 * "A phone" in the console is BELOW md BY WIDTH — one line for every phone rule (Mobile M6b review): the same
 * width as Tailwind's `max-md:` and `DocViewer`'s `PHONE_QUERY` (pinned equal by `phoneWidth.test.ts`).
 */
export const PHONE_WIDTH_QUERY = '(max-width: 767.98px)'

/**
 * True while the window is below md. False on the server, before mount, and in a browser without matchMedia (a
 * desktop) — so the first paint is the desktop markup and a phone swaps after mount. Use it only where TWO copies
 * of a control in the DOM would be wrong (a chooser and the tab bar it replaces); a pure look stays in CSS.
 */
export function usePhoneWidth(): boolean {
  const [phone, setPhone] = useState(false)
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const mq = window.matchMedia(PHONE_WIDTH_QUERY)
    const update = () => setPhone(mq.matches)
    update()
    mq.addEventListener?.('change', update)
    return () => mq.removeEventListener?.('change', update)
  }, [])
  return phone
}

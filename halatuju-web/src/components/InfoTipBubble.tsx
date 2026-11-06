'use client'

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'

/** Gap kept between the bubble and either edge of the screen, in px. */
const EDGE = 8

/**
 * The open half of `InfoTip`: the bubble itself, how it stays on screen, and how it closes. Loaded
 * the first time any InfoTip opens (see InfoTip.tsx for why it is a separate chunk).
 *
 * ⚠ IT STAYS ON SCREEN. The bubble is 256 px wide and centred on an 18 px trigger, so a trigger near
 * either edge pushed it off the screen. On mount it is measured and slid back inside an 8 px margin;
 * the caret is moved back by the same amount, so it still points at the `i`.
 *
 * ⚠ IT CLOSES on a tap or click anywhere outside the InfoTip, and on Escape (`onClose`).
 */
export default function InfoTipBubble({ text, root, onClose }: {
  text: string
  root: RefObject<HTMLElement | null>
  onClose: () => void
}) {
  const [shift, setShift] = useState(0)
  const bubble = useRef<HTMLSpanElement>(null)

  // Measured once, unshifted, as it mounts: a bubble is re-mounted for every opening.
  useLayoutEffect(() => {
    const r = bubble.current?.getBoundingClientRect()
    if (!r) return
    const vw = document.documentElement.clientWidth
    setShift(r.left < EDGE ? EDGE - r.left : r.right > vw - EDGE ? vw - EDGE - r.right : 0)
  }, [])

  useEffect(() => {
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) onClose() }
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [root, onClose])

  return (
    <span
      ref={bubble} role="tooltip" style={{ marginLeft: shift }}
      className="absolute left-1/2 top-7 z-30 w-64 -translate-x-1/2 rounded-xl border border-primary-100 bg-ground-0 px-3.5 py-3 text-left text-xs font-normal leading-relaxed text-ground-600 shadow-xl"
    >
      {/* caret pointing up at the i button — moved back by the shift, so it stays on it */}
      <span style={{ left: `calc(50% - ${shift}px)` }}
        className="absolute -top-1.5 h-3 w-3 -translate-x-1/2 rotate-45 border-l border-t border-primary-100 bg-ground-0" />
      <span className="relative flex gap-2">
        <svg className="mt-0.5 h-4 w-4 shrink-0 text-primary-600" fill="none" stroke="currentColor" strokeWidth={1.7} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.5 17h5M10 20.5h4M12 3a6 6 0 00-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0012 3z" />
        </svg>
        <span>{text}</span>
      </span>
    </span>
  )
}

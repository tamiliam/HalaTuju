'use client'

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { createPortal } from 'react-dom'

/** Gap kept between the bubble and either edge of the screen, in px. */
const EDGE = 8
/** Gap between the bottom of the trigger and the top of the bubble, in px (the old `top-7` on an 18 px `i`). */
const GAP = 10

type Pos = { left: number; top: number; caret: number }

/**
 * The open half of `InfoTip`: the bubble itself, how it stays on screen, and how it closes. Loaded
 * the first time any InfoTip opens (see InfoTip.tsx for why it is a separate chunk).
 *
 * ⚠ IT IS A PORTAL ON `document.body`, `position: fixed` (team-membership small change, 2026-11-10).
 * It used to be `absolute` inside the trigger, so a table frame (`TableFrame`'s `overflow-hidden` card
 * and `overflow-x-auto` scroller) cut it off: the greyed Delete's reason near the right edge of
 * Team → Reviewers showed only its top line. `Menu` escaped the same clip the same way. The cost is
 * that the bubble no longer follows the trigger by itself, so `place()` measures the trigger and puts
 * the bubble under it, again on every scroll (any ancestor: capture) and resize.
 *
 * ⚠ IT STAYS ON SCREEN. The bubble is 256 px wide and centred on the trigger, so a trigger near either
 * edge would push it off the screen. It is slid back inside an 8 px margin; the caret is placed at the
 * trigger's centre, so it still points at the `i`.
 *
 * ⚠ IT CLOSES on a tap or click anywhere outside the InfoTip, and on Escape (`onClose`). "Outside"
 * means outside BOTH the trigger's `root` and the bubble: the bubble is no longer inside `root` in the
 * page, so a tap on its own text must not count as a tap elsewhere.
 */
export default function InfoTipBubble({ text, root, onClose }: {
  text: string
  root: RefObject<HTMLElement | null>
  onClose: () => void
}) {
  const [pos, setPos] = useState<Pos | null>(null)
  const bubble = useRef<HTMLSpanElement>(null)

  const place = useCallback(() => {
    const r = root.current?.getBoundingClientRect()
    const width = bubble.current?.offsetWidth
    if (!r || width === undefined) return
    // clientWidth, not innerWidth: a fixed box is laid out against the viewport without the scrollbar.
    const vw = document.documentElement.clientWidth || window.innerWidth
    const centre = r.left + r.width / 2
    const left = Math.round(Math.max(EDGE, Math.min(centre - width / 2, vw - EDGE - width)))
    const next = { left, top: Math.round(r.bottom + GAP), caret: Math.round(centre - left) }
    setPos((p) => (p && p.left === next.left && p.top === next.top && p.caret === next.caret ? p : next))
  }, [root])

  // Placed before paint (a bubble is re-mounted for every opening), then kept with its trigger.
  useLayoutEffect(() => {
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [place])

  useEffect(() => {
    const outside = (e: Event) => {
      const target = e.target as Node
      if (!root.current?.contains(target) && !bubble.current?.contains(target)) onClose()
    }
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [root, onClose])

  return createPortal(
    <span
      ref={bubble} role="tooltip"
      style={{ left: pos?.left ?? 0, top: pos?.top ?? 0, visibility: pos ? undefined : 'hidden' }}
      // z-[60]: above a Sheet or dialog (z-50) the trigger may sit in, now that it is no longer inside it.
      className="fixed z-[60] w-64 rounded-xl border border-primary-100 bg-ground-0 px-3.5 py-3 text-left text-xs font-normal leading-relaxed text-ground-600 shadow-xl"
    >
      {/* caret pointing up at the trigger's centre, wherever the bubble was slid to */}
      <span style={{ left: pos?.caret ?? 0 }}
        className="absolute -top-1.5 h-3 w-3 -translate-x-1/2 rotate-45 border-l border-t border-primary-100 bg-ground-0" />
      <span className="relative flex gap-2">
        <svg className="mt-0.5 h-4 w-4 shrink-0 text-primary-600" fill="none" stroke="currentColor" strokeWidth={1.7} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.5 17h5M10 20.5h4M12 3a6 6 0 00-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0012 3z" />
        </svg>
        <span>{text}</span>
      </span>
    </span>,
    document.body,
  )
}

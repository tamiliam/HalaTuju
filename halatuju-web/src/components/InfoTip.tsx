'use client'

import { useEffect, useLayoutEffect, useRef, useState, type PointerEvent, type ReactNode } from 'react'

/** Gap kept between the bubble and either edge of the screen, in px. */
const EDGE = 8

/**
 * A friendly `i` help bubble. Tap/click opens a small popover that works on both mobile and
 * desktop. Used across the B40 apply form to explain fields. Styled on-brand (primary tint, white
 * card, caret + helper icon) rather than the old flat grey/dark tooltip.
 *
 * ⚠ HOW IT OPENS, AND WHY (Mobile M1a). It used to open on `mouseenter` and TOGGLE on click. On an
 * iPhone a tap fires `mouseenter` THEN `click`, so the first opened it and the second shut it at once
 * — the help never appeared. Now there are two separate reasons to show it:
 *   - `hovered`: a real MOUSE is over it (`pointerType === 'mouse'` — a finger is never a hover);
 *   - `pinned`:  it was clicked or tapped, and stays open until tapped again, a tap lands anywhere
 *                else, Escape is pressed, or keyboard focus moves on.
 *
 * ⚠ IT STAYS ON SCREEN. The bubble is 256 px wide and centred on an 18 px trigger, so a trigger near
 * either edge pushed it off the screen. On open it is measured and slid back inside an 8 px margin;
 * the caret stays pointing at the `i`. ⚠ THE TAP TARGET IS 44 PX, THE LOOK IS STILL 18 PX: the
 * button carries 13 px of padding cancelled by -13 px margins, so the line it sits in does not move.
 * Any small mark can use the same behaviour (`mark` + `markSize`) — `VerifiedTick` does.
 */
export default function InfoTip({ text, defaultOpen = false, mark, markSize = 18, hoverOpens = true }: {
  text: string
  defaultOpen?: boolean
  /** What the reader SEES as the trigger. Default: the `i` circle. `VerifiedTick` passes its seal. */
  mark?: ReactNode
  /** The mark's size in px — the padding that makes the tap target 44 px is worked out from it. */
  markSize?: number
  /** False where the mark already has a native desktop tooltip, so hovering does not show two. */
  hoverOpens?: boolean
}) {
  // 44 px to a thumb: pad the mark out to 44, and cancel the padding with negative margins so the
  // line it sits in does not move. The 4 px left gap is what the old `ml-1` gave.
  const pad = Math.max(0, (44 - markSize) / 2)
  const [pinned, setPinned] = useState(defaultOpen)
  const [hovered, setHovered] = useState(false)
  const [shift, setShift] = useState(0)
  // The shift in force, read to undo itself when measuring — a ref, so it is never a reason to
  // re-measure (that would chase its own tail).
  const shiftRef = useRef(0)
  const rootRef = useRef<HTMLSpanElement>(null)
  const bubbleRef = useRef<HTMLSpanElement>(null)
  const open = pinned || hovered

  // Slide the bubble back inside the screen: measure where it WOULD sit unshifted, then shift once.
  useLayoutEffect(() => {
    let next = 0
    if (open && bubbleRef.current) {
      const r = bubbleRef.current.getBoundingClientRect()
      const left = r.left - shiftRef.current
      const right = r.right - shiftRef.current
      const vw = document.documentElement.clientWidth
      next = left < EDGE ? EDGE - left : right > vw - EDGE ? vw - EDGE - right : 0
    }
    shiftRef.current = next
    setShift(next)
  }, [open])

  // A pinned bubble closes on a tap elsewhere and on Escape.
  useEffect(() => {
    if (!pinned) return
    const outside = (e: Event) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setPinned(false)
    }
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') { setPinned(false); setHovered(false) } }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [pinned])

  const onMouse = (on: boolean) => (e: PointerEvent) => { if (hoverOpens && e.pointerType === 'mouse') setHovered(on) }

  return (
    // No native `title` — that produced a second, drab browser tooltip on hover.
    <span ref={rootRef} className="relative inline-flex align-middle"
      onPointerEnter={onMouse(true)} onPointerLeave={onMouse(false)}>
      <button
        type="button" aria-label={text} aria-expanded={open}
        onClick={() => setPinned((v) => !v)} onBlur={() => setPinned(false)}
        className="group inline-flex" style={{ padding: pad, margin: `-${pad}px -${pad}px -${pad}px ${4 - pad}px` }}
      >
        {mark ?? (
          <span className="inline-flex h-[18px] w-[18px] items-center justify-center rounded-full bg-primary-100 text-[11px] font-bold leading-none text-primary-700 ring-1 ring-inset ring-primary-200 transition-colors group-hover:bg-primary-200 group-hover:text-primary-800">
            i
          </span>
        )}
      </button>
      {open && (
        <span
          ref={bubbleRef} role="tooltip" style={{ marginLeft: shift }}
          className="absolute left-1/2 top-7 z-30 w-64 max-w-[calc(100vw-1rem)] -translate-x-1/2 rounded-xl border border-primary-100 bg-ground-0 px-3.5 py-3 text-left text-xs font-normal leading-relaxed text-ground-600 shadow-xl"
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
      )}
    </span>
  )
}

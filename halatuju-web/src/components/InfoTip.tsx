'use client'

import { useCallback, useEffect, useRef, useState, type PointerEvent } from 'react'

type Bubble = typeof import('./InfoTipBubble').default

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
 * ⚠ THE TAP TARGET IS 44 PX, THE LOOK IS STILL 18 PX: the button carries 13 px of padding cancelled
 * by -13 px margins, so the line it sits in does not move.
 *
 * ⚠ THE BUBBLE IS ITS OWN CHUNK (`InfoTipBubble`), fetched the first time any InfoTip opens. The
 * on-screen clamp and the close-on-outside/Escape logic it gained in M1a would otherwise ride in the
 * first-load JS of every student form, and `/scholarship/application` sits 0.3 kB under its line. The
 * import is owned here (not `next/dynamic`, which re-throws a failed load as a page error — the
 * LazyPostAwardTask lesson): if the chunk cannot load, the `i` simply stays shut, and its text is
 * still its accessible name. The first opening waits for one small file; every later one is instant.
 */
export default function InfoTip({ text, defaultOpen = false }: { text: string; defaultOpen?: boolean }) {
  const [pinned, setPinned] = useState(defaultOpen)
  const [hovered, setHovered] = useState(false)
  const [Bubble, setBubble] = useState<Bubble | null>(null)
  const root = useRef<HTMLSpanElement>(null)
  const open = pinned || hovered

  useEffect(() => {
    if (!open || Bubble) return
    let live = true
    import('./InfoTipBubble').then((m) => { if (live) setBubble(() => m.default) }).catch(() => {})
    return () => { live = false }
  }, [open, Bubble])

  const close = useCallback(() => setPinned(false), [])
  const onMouse = (on: boolean) => (e: PointerEvent) => { if (e.pointerType === 'mouse') setHovered(on) }

  return (
    // No native `title` — that produced a second, drab browser tooltip on hover.
    <span ref={root} className="relative inline-flex align-middle"
      onPointerEnter={onMouse(true)} onPointerLeave={onMouse(false)}>
      <button
        type="button" aria-label={text} aria-expanded={open}
        onClick={() => setPinned((v) => !v)}
        // Close on blur only when focus moves to ANOTHER control outside this tip. Chrome focuses a
        // tapped button, so a tap on the bubble's text blurred it to <body> and shut the bubble the
        // student was reading (M1 close review); taps elsewhere are the bubble's outside-tap listener.
        onBlur={(e) => { const to = e.relatedTarget as Node | null; if (to && !root.current?.contains(to)) close() }}
        className="group -my-[13px] -mr-[13px] ml-[-9px] inline-flex p-[13px]"
      >
        <span className="inline-flex h-[18px] w-[18px] items-center justify-center rounded-full bg-primary-100 text-[11px] font-bold leading-none text-primary-700 ring-1 ring-inset ring-primary-200 transition-colors group-hover:bg-primary-200 group-hover:text-primary-800">
          i
        </span>
      </button>
      {open && Bubble && <Bubble text={text} root={root} onClose={close} />}
    </span>
  )
}

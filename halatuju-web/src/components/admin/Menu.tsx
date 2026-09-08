'use client'

import {
  useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

/**
 * The console's one dropdown primitive — used by the help menu, the account menu and the
 * notification bell. Written once so the keyboard and accessibility behaviour is identical in
 * all three rather than approximated three times.
 *
 * No dependency: the project has no Radix or headless-ui and this sprint adds none. What a
 * menu actually owes the user is small and testable — close on Escape, close on a click
 * outside, move through items with the arrow keys, and put focus back where it came from.
 *
 * `MenuItem` is defined at module scope, NOT inside the component. A sub-component redeclared
 * on every render is a new type each time, so React unmounts and remounts the subtree and any
 * focused input loses focus mid-keystroke — the bug that hit the Administration invite form
 * (see the hoist comment in admin/administration/page.tsx).
 *
 * ⚠ THE PANEL IS A PORTAL ON `document.body`, AND THAT IS THE WHOLE POINT (owner, 2026-09-08:
 * *"Clicking the close opens something, but it is hidden"*). It used to be `absolute` inside the
 * trigger's own box, so ANY ancestor with `overflow-hidden` clipped it — and the intake-round
 * table has exactly that, on the wrapper that rounds its corners. The menu opened correctly,
 * rendered correctly, and was sliced off at the table's edge.
 *
 * Fixing the one table would have left the trap armed for the next caller: a menu inside a card,
 * a modal, any rounded panel. Escaping the clip at the PRIMITIVE means no future caller has to
 * know. The cost is that the panel no longer inherits the trigger's position, so it is measured
 * and placed — see `place()`, which also flips it above the trigger when the space below is short.
 */

export function MenuItem({ icon, children, sub, onClick, href, danger, disabled, reason }: {
  icon?: ReactNode
  children: ReactNode
  sub?: string
  onClick?: () => void
  href?: string
  danger?: boolean
  /**
   * Asleep, and SHOWN rather than hidden.
   *
   * ⚠ THE OWNER RULED THIS ON 2026-09-07, ABOUT DELETE: *"I feel it should be prevented at the
   * button stage, and not wait until typed to check."* They were afraid to press Delete on the live
   * flagship, and that fear was the finding — a destructive control you cannot tell is safe to press
   * is one people avoid, so they cannot tidy up either. Hiding it explains nothing; asleep with the
   * reason explains everything. When such a control moves INTO a menu the reason has to move with
   * it, or the ruling is quietly undone by the relocation.
   */
  disabled?: boolean
  /** Why it is asleep. Rendered under the item — a `title` needs a hover a touch screen cannot give. */
  reason?: string
}) {
  const cls = `flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors
    ${danger
      ? 'text-critical-600 hover:bg-critical-50'
      : 'text-ground-700 hover:bg-primary-50 hover:text-primary-800'}`
  const inner = (
    <>
      {icon && <span aria-hidden className="shrink-0 text-base leading-none">{icon}</span>}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {sub && <span className="shrink-0 text-xs text-ground-400">{sub}</span>}
    </>
  )
  if (disabled) {
    return (
      // ⚠ `stopPropagation` IS LOAD-BEARING. The panel closes on its own click, so without this
      // pressing an asleep item would shut the menu — taking the reason off the screen at the exact
      // moment the reader went looking for it.
      <span
        role="menuitem" aria-disabled="true" data-menuitem data-menuitem-disabled
        onClick={(e) => e.stopPropagation()}
        className="block cursor-not-allowed rounded-lg px-3 py-2"
      >
        <span className="flex w-full items-center gap-2.5 text-left text-sm text-ground-400">
          {inner}
        </span>
        {reason && <span className="mt-0.5 block text-xs text-ground-500">{reason}</span>}
      </span>
    )
  }
  if (href) {
    return <a role="menuitem" href={href} className={cls} data-menuitem>{inner}</a>
  }
  return (
    <button type="button" role="menuitem" onClick={onClick} className={cls} data-menuitem>
      {inner}
    </button>
  )
}

/** A labelled divider inside a menu. */
export function MenuHeading({ children }: { children: ReactNode }) {
  return (
    <p className="px-3 pb-1 pt-2 text-[10px] font-bold uppercase tracking-wider text-ground-400">
      {children}
    </p>
  )
}

export function MenuSeparator() {
  return <div className="my-1 h-px bg-ground-100" role="separator" />
}

/** Where the panel sits, in viewport pixels. Two of the four edges are set, never all four. */
type Pos = { top?: number; bottom?: number; left?: number; right?: number }

/** The gap between the trigger and the panel — the old `mt-1.5`, now a number we can add up. */
const GAP = 6

const samePos = (a: Pos | null, b: Pos) =>
  !!a && a.top === b.top && a.bottom === b.bottom && a.left === b.left && a.right === b.right

export function Menu({ label, trigger, children, align = 'right', width = 'w-60' }: {
  /** Accessible name for the trigger — every trigger here is an icon, so this is not optional. */
  label: string
  trigger: ReactNode
  children: ReactNode
  align?: 'left' | 'right'
  width?: string
}) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<Pos | null>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const id = useId()

  /**
   * Put the panel under (or over) the trigger, in viewport coordinates.
   *
   * Called once before paint — when the panel's height is not yet known, so it assumes "below" —
   * and again on the next frame, when the height IS known and it can flip. Both passes go through
   * `samePos`, so a scroll that does not actually move the menu costs no render.
   */
  const place = useCallback(() => {
    const r = triggerRef.current?.getBoundingClientRect()
    if (!r) return
    // ⚠ clientWidth/clientHeight, NOT innerWidth/innerHeight. A `fixed` box is laid out against
    // the viewport WITHOUT the scrollbar, while innerWidth counts it — anchoring a right-aligned
    // menu to innerWidth would leave every topbar menu a scrollbar's width out of true.
    const vw = document.documentElement.clientWidth || window.innerWidth
    const vh = document.documentElement.clientHeight || window.innerHeight
    const height = panel.current?.offsetHeight ?? 0
    const below = vh - r.bottom
    // Flip above ONLY when it does not fit below and genuinely fits better above. A fixed panel
    // running off the bottom cannot be scrolled to — it is simply gone.
    const flip = height > 0 && below < height + GAP && r.top > below
    const next: Pos = flip
      ? { bottom: Math.round(vh - r.top + GAP) }
      : { top: Math.round(r.bottom + GAP) }
    if (align === 'right') next.right = Math.round(Math.max(0, vw - r.right))
    else next.left = Math.round(Math.max(0, r.left))
    setPos((prev) => (samePos(prev, next) ? prev : next))
  }, [align])

  // Measure before paint, then again once the panel has a height. Keep up with scrolling and
  // resizing — `true` catches scroll on any ancestor, not only the window.
  useLayoutEffect(() => {
    if (!open) { setPos(null); return }
    place()
    const frame = requestAnimationFrame(place)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open, place])

  // Close on a click anywhere outside, and on Escape. Escape also returns focus to the trigger:
  // a keyboard user who dismisses a menu should not be dumped at the top of the document.
  useEffect(() => {
    if (!open) return
    const onPointer = (e: MouseEvent) => {
      const target = e.target as Node
      // ⚠ THE PANEL IS NO LONGER INSIDE `wrap` — it is a portal. Testing only `wrap` would make
      // every menu close on the mousedown of its own item, BEFORE the click ever fired.
      if (wrap.current?.contains(target) || panel.current?.contains(target)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const items = () =>
    Array.from(panel.current?.querySelectorAll<HTMLElement>('[data-menuitem]') ?? [])

  const move = (delta: number) => {
    const list = items()
    if (!list.length) return
    const at = list.indexOf(document.activeElement as HTMLElement)
    // From the trigger (at === -1) Down lands on the first item and Up on the last.
    const next = at === -1
      ? (delta > 0 ? 0 : list.length - 1)
      : (at + delta + list.length) % list.length
    list[next]?.focus()
  }

  return (
    <div ref={wrap} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault()
            setOpen(true)
            // Wait for the panel to exist before reaching into it.
            setTimeout(() => move(e.key === 'ArrowDown' ? 1 : -1), 0)
          }
        }}
        className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-ground-500 transition-colors hover:bg-primary-50 hover:text-primary-700 aria-expanded:bg-primary-50 aria-expanded:text-primary-700"
      >
        {trigger}
      </button>

      {open && typeof document !== 'undefined' && createPortal(
        <div
          ref={panel}
          id={id}
          role="menu"
          aria-label={label}
          data-menu-panel
          style={pos ?? { top: 0, left: 0 }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
            if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
          }}
          onClick={() => setOpen(false)}
          // z-50 so it clears the sticky save bar and the topbar. `fixed`, because the panel no
          // longer lives beside its trigger — `place()` supplies the coordinates.
          className={`fixed z-50 ${width} rounded-xl border border-ground-200 bg-ground-0 p-1.5 shadow-lg`}
        >
          {children}
        </div>,
        document.body,
      )}
    </div>
  )
}

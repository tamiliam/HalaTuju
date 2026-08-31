'use client'

import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

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
 */

export function MenuItem({ icon, children, sub, onClick, href, danger }: {
  icon?: ReactNode
  children: ReactNode
  sub?: string
  onClick?: () => void
  href?: string
  danger?: boolean
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

export function Menu({ label, trigger, children, align = 'right', width = 'w-60' }: {
  /** Accessible name for the trigger — every trigger here is an icon, so this is not optional. */
  label: string
  trigger: ReactNode
  children: ReactNode
  align?: 'left' | 'right'
  width?: string
}) {
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const id = useId()

  // Close on a click anywhere outside, and on Escape. Escape also returns focus to the trigger:
  // a keyboard user who dismisses a menu should not be dumped at the top of the document.
  useEffect(() => {
    if (!open) return
    const onPointer = (e: MouseEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false)
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

      {open && (
        <div
          ref={panel}
          id={id}
          role="menu"
          aria-label={label}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
            if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
          }}
          onClick={() => setOpen(false)}
          className={`absolute z-40 mt-1.5 ${width} rounded-xl border border-ground-200 bg-ground-0 p-1.5 shadow-lg
            ${align === 'right' ? 'right-0' : 'left-0'}`}
        >
          {children}
        </div>
      )}
    </div>
  )
}

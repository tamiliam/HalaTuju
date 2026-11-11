'use client'

import {
  useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode,
  type RefObject,
} from 'react'
import { createPortal } from 'react-dom'
import { useT } from '@/lib/i18n'

/**
 * THE shared overlay (Mobile M1b, mobile-standard.md rule 5). Every dialog, confirm and form-in-a-
 * box uses this; nothing else in the product writes `fixed inset-0` (the static guard counts them).
 *
 * WHY ONE. Eighteen hand-rolled overlays each re-decided max height, inner scroll, the close
 * target, the safe area and the keyboard — and several decided wrong: on an iPhone the action
 * buttons sat behind the keyboard or below the screen with no way to scroll to them.
 *
 * WHAT IT IS
 *   - Phone (below `md`): a BOTTOM SHEET — full width, rounded top, a grab bar, at most 90 % of
 *     the visible height. The title row and the footer stay put; only the body scrolls, and the page
 *     behind does not. The footer pads itself clear of the home bar (`env(safe-area-inset-bottom)`).
 *     When the keyboard opens, the sheet rises above it (`visualViewport`) and the focused field is
 *     scrolled into view, so what you are typing into is never hidden.
 *   - Desktop (`md` and up): a centred dialog, as the console's modals have always looked.
 *
 * ACCESSIBILITY: `role="dialog"`, `aria-modal`, named by its title (and described by
 * `description`); focus moves in on open (`initialFocus`, else the first field or button in the body,
 * else the panel), Tab is kept inside, and focus returns to whatever opened it; Escape closes.
 *
 * CLOSING: Escape, the backdrop, the 44 px × in the title row — all call `onClose`. Two ways to stop
 * that: `busy` (an action is in flight — nothing closes), and `dismissible={false}` for flows that
 * must not vanish by accident (consent, sign-in, a guardian's details half typed): then there is no
 * ×, the backdrop does nothing and Escape does nothing — the footer's own buttons are the only way out.
 *
 * ⚠ IT IS PORTALLED TO `document.body`, so no ancestor's `overflow-hidden` or `transform` can clip
 * or mis-place it (docs/lessons.md, the round-menu clipping). The other side of that coin: the
 * BODY scrolls (`overflow-y-auto`), so a dropdown positioned `absolute` inside it is clipped at the
 * body's edge — use the portalled `admin/Menu` for a menu inside a sheet, never a hand-rolled one.
 */

const WIDTH = { sm: 'md:max-w-sm', md: 'md:max-w-md', lg: 'md:max-w-lg', xl: 'md:max-w-2xl' } as const

/** Every focusable thing, in DOM order — what Tab cycles through. */
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), '
  + 'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Open sheets, newest last: only the top one answers Escape and Tab. */
const stack: string[] = []
/** How many sheets hold the page still; the page scrolls again when the last one closes. */
let locks = 0
let saved: { html: string; body: string } | null = null

function lockScroll(): () => void {
  if (locks++ === 0) {
    saved = { html: document.documentElement.style.overflow, body: document.body.style.overflow }
    document.documentElement.style.overflow = 'hidden'
    document.body.style.overflow = 'hidden'
  }
  return () => {
    if (--locks === 0 && saved) {
      document.documentElement.style.overflow = saved.html
      document.body.style.overflow = saved.body
      saved = null
    }
  }
}

export interface SheetProps {
  open: boolean
  onClose: () => void
  /** Names the dialog (`aria-labelledby`) and heads it. */
  title: ReactNode
  /** A line under the title, read out with it (`aria-describedby`). */
  description?: ReactNode
  /** The title in the critical colour — a destructive confirm. */
  tone?: 'default' | 'critical'
  children: ReactNode
  /** Actions, pinned under the body. Buttons go here, never at the end of a long body. */
  footer?: ReactNode
  /** When set, body and footer are one `<form>`: Enter submits, a `type="submit"` button in the
   *  footer works, and the browser's own `required` checks run. */
  onSubmit?: (e: FormEvent<HTMLFormElement>) => void
  /** Desktop width. Phones always get the full width. */
  size?: keyof typeof WIDTH
  /** false for flows that must not vanish by accident — see CLOSING above. */
  dismissible?: boolean
  /** An action is in flight: nothing closes the sheet until it is false again. */
  busy?: boolean
  /** What to focus on open, when the first field is not the right place. */
  initialFocus?: RefObject<HTMLElement | null>
  /** The dialog's accessible name when it must say more than the visible title (it then replaces
   *  `aria-labelledby`): e.g. "Flag — <shop>" over a title that shows only the shop. */
  label?: string
  /** `alertdialog` for a confirm that interrupts to ask something with consequences. */
  role?: 'dialog' | 'alertdialog'
  /** Extra classes on the panel. The sheet is portalled to <body>, so it does NOT inherit its
   *  page's wrapper classes — a page set in another face (e.g. `font-plex`) passes it here. */
  className?: string
  testId?: string
}

export default function Sheet(props: SheetProps) {
  // Mounted only while open, so every open is a fresh focus/lock/listener cycle.
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  if (!props.open || !mounted) return null
  return createPortal(<SheetPanel {...props} />, document.body)
}

function SheetPanel({
  onClose, title, description, tone = 'default', children, footer, onSubmit, size = 'md',
  dismissible = true, busy = false, initialFocus, label, role = 'dialog', className = '', testId,
}: SheetProps) {
  const { t } = useT()
  const id = useId()
  const panel = useRef<HTMLDivElement>(null)
  const body = useRef<HTMLDivElement>(null)
  const foot = useRef<HTMLDivElement>(null)
  // Read once, at opening: a parent re-render must never move focus back to the first field.
  const initial = useRef(initialFocus)
  // The keyboard: how much of the layout viewport it covers, and how tall the visible part is.
  const [keyboard, setKeyboard] = useState(0)
  const [visible, setVisible] = useState<number | null>(null)
  const canClose = dismissible && !busy
  const close = useCallback(() => { if (canClose) onClose() }, [canClose, onClose])

  // Focus in on open, back out on close; the page stays still underneath.
  useLayoutEffect(() => {
    const before = document.activeElement as HTMLElement | null
    const first = initial.current?.current
      ?? body.current?.querySelector<HTMLElement>(FOCUSABLE)
      ?? foot.current?.querySelector<HTMLElement>(FOCUSABLE)
      ?? panel.current
    first?.focus({ preventScroll: true })
    const unlock = lockScroll()
    stack.push(id)
    return () => {
      unlock()
      stack.splice(stack.indexOf(id), 1)
      if (before && document.contains(before)) before.focus({ preventScroll: true })
    }
  }, [id])

  // Escape closes; Tab stays inside. Only the top sheet listens.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== id) return
      if (e.key === 'Escape') { e.stopPropagation(); close(); return }
      if (e.key !== 'Tab' || !panel.current) return
      // Everything focusable, in DOM order. ⚠ Not filtered by visibility: a sheet's content shows
      // all its controls, and a hidden one would only make Tab pause once on it, never escape.
      const items = Array.from(panel.current.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (items.length === 0) { e.preventDefault(); panel.current.focus(); return }
      const firstEl = items[0]
      const lastEl = items[items.length - 1]
      const active = document.activeElement
      if (e.shiftKey && (active === firstEl || !panel.current.contains(active))) {
        e.preventDefault(); lastEl.focus()
      } else if (!e.shiftKey && (active === lastEl || !panel.current.contains(active))) {
        e.preventDefault(); firstEl.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [id, close])

  // The on-screen keyboard. iOS does not shrink the layout viewport for it, so a bottom sheet
  // would sit BEHIND it; `visualViewport` says how much is covered and the sheet rises by that.
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const measure = () => {
      setKeyboard(Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop)))
      setVisible(Math.round(vv.height))
    }
    measure()
    vv.addEventListener('resize', measure)
    vv.addEventListener('scroll', measure)
    return () => {
      vv.removeEventListener('resize', measure)
      vv.removeEventListener('scroll', measure)
    }
  }, [])

  // A field that gains focus is brought into view once the keyboard has finished rising.
  const onFocusIn = (e: { target: EventTarget }) => {
    const el = e.target as HTMLElement
    if (!/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) return
    window.setTimeout(() => el.scrollIntoView?.({ block: 'nearest' }), 300)
  }

  const inner = (
    <>
      <div ref={body} onFocus={onFocusIn}
        className={`min-h-0 flex-1 overflow-y-auto overscroll-contain sheet-pad-x pt-4 ${
          footer ? 'pb-4' : 'pb-[max(1rem,env(safe-area-inset-bottom))]'}`}>
        {children}
      </div>
      {footer && (
        <div ref={foot}
          className="flex flex-wrap items-center justify-end gap-3 border-t border-ground-100 sheet-pad-x pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:pb-4">
          {footer}
        </div>
      )}
    </>
  )
  const BODY = 'flex min-h-0 flex-1 flex-col'
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center md:items-center md:p-4"
      style={{ paddingBottom: keyboard || undefined }} data-testid={testId}>
      <div className="absolute inset-0 bg-black/40" aria-hidden onClick={close} data-sheet-backdrop="" />
      <div ref={panel} role={role} aria-modal="true"
        aria-label={label} aria-labelledby={label ? undefined : `${id}-title`}
        aria-describedby={description ? `${id}-desc` : undefined} tabIndex={-1}
        // Pixels, not `dvh`: a browser without `dvh` (Safari < 15.4, Chrome < 108) drops a whole
        // `min(90dvh, …)` value AND the class, and the panel then has no height limit at all — a
        // long sheet runs off the top, title and × out of reach (M1 close review). `visualViewport`
        // (Safari 13+, Chrome 61+) is measured at mount, so this applies from the first frame.
        style={{ maxHeight: visible ? `${Math.round(Math.min(visible * 0.9, visible - 8))}px` : undefined }}
        className={`relative flex max-h-[90dvh] w-full flex-col rounded-t-2xl bg-ground-0 shadow-xl outline-none md:rounded-2xl ${WIDTH[size]} ${className}`}>
        {/* Grab bar: a phone's cue that this is a sheet. Decorative — closing is the × or the backdrop. */}
        <div className="flex justify-center pt-2 md:hidden" aria-hidden>
          <span className="h-1.5 w-10 rounded-full bg-ground-300" />
        </div>
        <div className="flex items-start gap-3 border-b border-ground-100 sheet-pad-x pb-3 pt-2 md:pt-4">
          <div className="min-w-0 flex-1 pt-2">
            <h2 id={`${id}-title`}
              className={`text-lg font-semibold break-words ${tone === 'critical' ? 'text-critical-700' : 'text-ground-900'}`}>
              {title}
            </h2>
            {description && <p id={`${id}-desc`} className="mt-1 text-sm text-ground-600">{description}</p>}
          </div>
          {dismissible && (
            <button type="button" onClick={close} disabled={busy} aria-label={t('common.dismiss')}
              className="-mr-2 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-ground-500 hover:bg-ground-50 hover:text-ground-900 disabled:opacity-50">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
        {onSubmit
          ? <form className={BODY} onSubmit={onSubmit}>{inner}</form>
          : <div className={BODY}>{inner}</div>}
      </div>
    </div>
  )
}

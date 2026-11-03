'use client'

/**
 * "‹ Back to <tab>" and "‹ Previous · 2 of 7 · Next ›" on a request's detail page (Requests
 * list R1, 2026-11-03). Reads what the list left in `lib/listNav`; the walk is the PAGE the
 * reader came from, greyed at its ends. ← / → move too — but never while the reader is typing or
 * picking, with a modifier held, or with a dialog open (`arrowKeysIgnored`).
 *
 * Arrived by a direct link (or from a list that no longer holds this id), there is no list to walk:
 * it shows the plain "Back to requests" it always did.
 *
 * Its own file because the detail page sits on its oversize ledger with two lines of room.
 */
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useRef } from 'react'
import { useT } from '@/lib/i18n'
import { REQUESTS_LIST_NAV, arrowKeysIgnored, useListNav } from '@/lib/listNav'

const LINK = 'inline-flex min-h-11 items-center text-sm text-primary-600 hover:text-primary-800'
const STEP = 'inline-flex min-h-11 items-center px-2 text-sm font-medium text-primary-600 '
  + 'hover:text-primary-800 disabled:cursor-not-allowed disabled:text-ground-300'

/** The step button pressed last, across the remount a new request's page may cause. */
let pressedStep: 'prev' | 'next' | null = null

export default function RequestListNav({ id }: { id: number }) {
  const { t } = useT()
  const router = useRouter()
  const nav = useListNav(REQUESTS_LIST_NAV, id)
  const prevRef = useRef<HTMLButtonElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const go = (which: 'prev' | 'next', to: number | null) => {
    if (to === null) return
    pressedStep = which
    router.push(`/admin/requests/${to}`)
  }

  // ⚠ A control that disables itself on its own press drops focus to <body> (or keeps it on a
  // dead button, depending on the browser) — and the next request's page may mount a NEW copy of
  // this component, which is why the pressed step is held outside it. Focus returns to the step
  // that was pressed; when that one is now greyed (Next onto the last request), to the other one.
  useEffect(() => {
    if (!nav || !pressedStep) return
    const want = pressedStep === 'next' ? nav.nextId : nav.prevId
    const same = pressedStep === 'next' ? nextRef.current : prevRef.current
    const other = pressedStep === 'next' ? prevRef.current : nextRef.current
    pressedStep = null
    ;(want !== null ? same : other)?.focus()
  }, [nav])

  const navRef = useRef(nav)
  navRef.current = nav
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const at = navRef.current
      if (!at || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') || arrowKeysIgnored(e)) return
      const to = e.key === 'ArrowLeft' ? at.prevId : at.nextId
      if (to === null) return
      e.preventDefault()
      router.push(`/admin/requests/${to}`)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [router])

  if (!nav) {
    return <Link href="/admin/requests" className={LINK}>← {t('admin.requests.detail.back')}</Link>
  }
  return (
    <nav aria-label={t('admin.requests.detail.listNav')}
      className="flex flex-wrap items-center justify-between gap-x-4">
      <Link href={nav.backHref} data-list-nav="back" className={LINK}>
        ‹ {t('admin.requests.detail.backTo', { tab: t(nav.labelKey) })}
      </Link>
      <div className="flex items-center gap-1">
        <button ref={prevRef} type="button" data-list-nav="prev" className={STEP}
          disabled={nav.prevId === null} onClick={() => go('prev', nav.prevId)}>
          ‹ {t('admin.previous')}
        </button>
        <span className="text-sm text-ground-500" data-list-nav="position">
          {t('admin.requests.detail.position', { n: String(nav.index + 1), m: String(nav.total) })}
        </span>
        <button ref={nextRef} type="button" data-list-nav="next" className={STEP}
          disabled={nav.nextId === null} onClick={() => go('next', nav.nextId)}>
          {t('admin.next')} ›
        </button>
      </div>
    </nav>
  )
}

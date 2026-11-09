/**
 * The ONE Previous / Next behaviour for a detail page that sits in a list (audit A3.3, TD-477):
 * the step buttons' focus, and the ← / → keys. `RequestListNav` and the Applications cockpit's
 * header both use it, so the two lists can never step differently. Moved whole out of
 * `RequestListNav`; nothing about it changed.
 *
 * The position itself comes from `useListNav` (`@/lib/listNav`); this adds the doing.
 */
import { useRouter } from 'next/navigation'
import { useEffect, useRef } from 'react'
import { arrowKeysIgnored, type ListNavPosition } from '@/lib/listNav'

/** The step button pressed last, across the remount a new record's page may cause. */
let pressedStep: 'prev' | 'next' | null = null

export function useListSteps(nav: ListNavPosition | null, hrefFor: (id: number) => string) {
  const router = useRouter()
  const prevRef = useRef<HTMLButtonElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const go = (which: 'prev' | 'next', to: number | null) => {
    if (to === null) return
    pressedStep = which
    router.push(hrefFor(to))
  }

  // ⚠ A control that disables itself on its own press drops focus to <body> (or keeps it on a
  // dead button, depending on the browser) — and the next record's page may mount a NEW copy of
  // this component, which is why the pressed step is held outside it. Focus returns to the step
  // that was pressed; when that one is now greyed (Next onto the last record), to the other one.
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
  const hrefRef = useRef(hrefFor)
  hrefRef.current = hrefFor
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const at = navRef.current
      if (!at || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') || arrowKeysIgnored(e)) return
      const to = e.key === 'ArrowLeft' ? at.prevId : at.nextId
      if (to === null) return
      e.preventDefault()
      router.push(hrefRef.current(to))
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [router])

  return { prevRef, nextRef, go }
}

'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { getNewNoteCount, type NewNoteCount } from '@/lib/admin-api'

const NONE: NewNoteCount = { from_reviewer: 0, from_org_admin: 0 }

/** A route change asks again at most once a minute (#73 review): the count is a hint, not a live feed. */
export const NEW_NOTE_THROTTLE_MS = 60_000

/** `focus` and `visibilitychange` within this many ms of each other are one return to the tab: one ask. */
export const RETURN_COALESCE_MS = 1_000

/** Fired by the notes card after a notes GET or POST succeeds: the server has just cleared that case's mark,
 *  so the bell asks again at once instead of waiting out the minute (#73 re-check M2). */
export const NOTES_READ_EVENT = 'halatuju:notes-read'

export function announceNotesRead(): void {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(NOTES_READ_EVENT))
}

/**
 * Request #73: the bell's new-note numbers (`GET .../staff-notifications/count/`), for the shell.
 *
 * Asked on sign-in, then on a route change only when the last ask is a minute old, and again at once whenever
 * the window regains focus or the tab becomes visible (someone coming back expects a fresh bell) or the notes
 * card says a case was just read (`NOTES_READ_EVENT`). Each ask is numbered, so an older answer never
 * overwrites a newer one. Pass a null token for anyone who is never on a case's notes: nothing is asked and
 * the count is zero. A refusal is swallowed, and `Promise.resolve().then` keeps a missing function (a test's
 * factory mock of admin-api) from throwing.
 */
export function useNewNoteCount(token: string | null | undefined, pathname: string): NewNoteCount {
  const [count, setCount] = useState<NewNoteCount>(NONE)
  const asked = useRef(0)
  const current = useRef(token)
  const seq = useRef(0)

  const load = useCallback((force: boolean) => {
    const asking = current.current
    if (!asking) return
    const now = Date.now()
    if (!force && asked.current && now - asked.current < NEW_NOTE_THROTTLE_MS) return
    asked.current = now
    const mine = ++seq.current
    Promise.resolve().then(() => getNewNoteCount({ token: asking }))
      .then((d) => { if (d && current.current === asking && seq.current === mine) setCount(d) })
      .catch(() => { /* a hint; never block the shell on it */ })
  }, [])

  useEffect(() => {
    current.current = token
    asked.current = 0
    seq.current += 1
    if (!token) setCount(NONE)
  }, [token])

  useEffect(() => { load(false) }, [token, pathname, load])

  useEffect(() => {
    const now = () => load(true)
    // Coming back to a tab fires `focus` AND `visibilitychange` together: one ask, not two (re-check 2 L-E).
    let back = 0
    const onBack = () => {
      const at = Date.now()
      if (at - back < RETURN_COALESCE_MS) return
      back = at
      load(true)
    }
    const onVisible = () => { if (document.visibilityState === 'visible') onBack() }
    window.addEventListener('focus', onBack)
    window.addEventListener(NOTES_READ_EVENT, now)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.removeEventListener('focus', onBack)
      window.removeEventListener(NOTES_READ_EVENT, now)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [load])

  return count
}

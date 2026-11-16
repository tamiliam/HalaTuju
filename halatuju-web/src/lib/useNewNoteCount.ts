'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

import { getNewNoteCount, type NewNoteCount } from '@/lib/admin-api'

const NONE: NewNoteCount = { from_reviewer: 0, from_org_admin: 0 }

/** A route change asks again at most once a minute (#73 review): the count is a hint, not a live feed. */
export const NEW_NOTE_THROTTLE_MS = 60_000

/**
 * Request #73: the bell's new-note numbers (`GET .../staff-notifications/count/`), for the shell.
 *
 * Asked on sign-in, then on a route change only when the last ask is a minute old, and again whenever the
 * window regains focus (someone coming back to the tab expects a fresh bell). Pass a null token for anyone
 * who is never on a case's notes: nothing is asked and the count is zero. A refusal is swallowed, and
 * `Promise.resolve().then` keeps a missing function (a test's factory mock of admin-api) from throwing.
 */
export function useNewNoteCount(token: string | null | undefined, pathname: string): NewNoteCount {
  const [count, setCount] = useState<NewNoteCount>(NONE)
  const asked = useRef(0)
  const current = useRef(token)

  const load = useCallback((force: boolean) => {
    const asking = current.current
    if (!asking) return
    const now = Date.now()
    if (!force && asked.current && now - asked.current < NEW_NOTE_THROTTLE_MS) return
    asked.current = now
    Promise.resolve().then(() => getNewNoteCount({ token: asking }))
      .then((d) => { if (d && current.current === asking) setCount(d) })
      .catch(() => { /* a hint; never block the shell on it */ })
  }, [])

  useEffect(() => {
    current.current = token
    asked.current = 0
    if (!token) setCount(NONE)
  }, [token])

  useEffect(() => { load(false) }, [token, pathname, load])

  useEffect(() => {
    const onFocus = () => load(true)
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [load])

  return count
}

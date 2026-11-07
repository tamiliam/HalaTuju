'use client'

/**
 * TD-460(b) (audit A1.12, review L1-L3) — THE INCOME WIZARD'S FAILED SAVES, REMEMBERED BY FIELD.
 *
 * A save that does not reach the server is kept here, field by field, with the exact value it
 * tried to send. The alert stays until EVERY failed field has been saved, and its "Try again"
 * re-sends those exact values — it never repeats a tap, because repeating a toggle un-ticks it.
 * A later save of the SAME field (a newer value) speaks for that field; a save of a DIFFERENT
 * field never clears it. Only the newest save of a field counts, so an older answer's late
 * failure cannot bring back a value the student has since replaced.
 */
import { useRef, useState } from 'react'

type Patch = Record<string, unknown>
export type SaveTicket = { n: number; patch: Patch }

/** The question answers (pills and toggles); their alert sits under the questions. Typed income
 *  (`income_declared`) has its own alert, under the members' income cards it was typed in. */
export const ANSWER_FIELDS = ['income_route', 'income_earner', 'income_working_members']

export function useFailedSaves() {
  const [failed, setFailed] = useState<Patch>({})
  const seq = useRef(0)
  const latest = useRef<Record<string, number>>({})

  const begin = (patch: Patch): SaveTicket => {
    const n = ++seq.current
    for (const k of Object.keys(patch)) latest.current[k] = n
    return { n, patch }
  }

  const settle = (ticket: SaveTicket, ok: boolean) => {
    const mine = Object.keys(ticket.patch).filter((k) => latest.current[k] === ticket.n)
    if (!mine.length) return
    setFailed((f) => {
      const next = { ...f }
      for (const k of mine) {
        if (ok) delete next[k]
        else next[k] = ticket.patch[k]
      }
      return next
    })
  }

  return { failed, begin, settle }
}

/** The alert for the failed fields among `fields`, drawn beside the answers it is about. */
export function SaveFailedAlert({ failed, fields, onRetry, iq }: {
  failed: Patch
  fields: string[]
  onRetry: (patch: Patch) => void
  iq: (k: string) => string
}) {
  const mine = Object.fromEntries(Object.entries(failed).filter(([k]) => fields.includes(k)))
  if (!Object.keys(mine).length) return null
  return (
    <div role="alert" className="flex flex-wrap items-center gap-2 text-sm text-critical-600">
      <span>{iq('notSaved')}</span>
      <button type="button" onClick={() => onRetry(mine)}
        className="min-h-11 px-4 py-2 rounded-full border border-critical-600 text-critical-600 hover:bg-critical-50">
        {iq('tryAgain')}
      </button>
    </div>
  )
}

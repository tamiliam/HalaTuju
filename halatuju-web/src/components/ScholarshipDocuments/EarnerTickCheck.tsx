'use client'

/**
 * Request #84 (2026-11-25): ASK BEFORE SAVING a "working" tick the family details disagree with.
 *
 * The who-is-working toggles saved every tap. A student once ticked all five members while the
 * family details said the mother was unemployed and listed no guardian or siblings, and every one
 * of them then owed an IC and proof of income. Now a tick the family details disagree with is held:
 * a short, non-blocking question names the person and what the details say, and the student
 * confirms (saved as before) or leaves it unticked. Nothing is ever unticked for the student.
 *
 * WHERE IT HOLDS (both places the ticks are edited): the income step (`IncomeWizard`, before
 * submission) and, once submitted, the Action Centre's "change how you prove income" panel
 * (`IncomeRouteSwitch`, drawn while an income task is open; it starts from a fresh choice). The
 * standing note shows under the toggles in both, for the ticks on screen. A submitted student's
 * already-saved ticks get no student-side note; the officer's case page warns on every open case
 * with a saved disagreeing tick (`earner_tick_warnings`, computed live).
 *
 * ⚠ SERVED, NEVER DERIVED: whether a tick disagrees is `earner_tick_conflicts` on the student's
 * payload (`family.earner_tick_conflicts`, the one rule). The browser only looks a member up.
 */
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import type { EarnerTickConflicts, WorkingMemberRole } from '@/lib/api/application'

const W = 'scholarship.docs.income.wizard'
const PROF = 'scholarship.nextSteps.story.cardA.prof'

/** The sentence for one member: what the family details say against the tick. */
function said(t: (key: string) => string, m: WorkingMemberRole, conflicts: EarnerTickConflicts, key: 'ask' | 'note') {
  const c = conflicts[m]
  if (!c) return ''
  const who = t(`${W}.member.${m}`)
  const status = c.kind === 'not_working' && c.occupation ? t(`${PROF}.${c.occupation}`) : ''
  return t(`${W}.earnerCheck.${key}${c.kind === 'not_working' ? 'NotWorking' : 'NotListed'}`)
    .replace('{who}', who).replace('{status}', status)
}

/** The standing note for each ticked member the served conflicts disagree with (nothing when none). */
function EarnerTickNotes({ conflicts, members, t }: {
  conflicts: EarnerTickConflicts | null | undefined
  members: readonly string[]
  t: (key: string) => string
}) {
  const served = conflicts || {}
  const standing = members.filter((m): m is WorkingMemberRole => !!served[m as WorkingMemberRole])
  if (standing.length === 0) return null
  return (
    <>
      {standing.map((m) => (
        <p key={m} className="rounded-lg bg-caution-50 px-3 py-2 text-sm text-caution-800" data-testid={`earner-tick-note-${m}`}>
          {said(t, m, served, 'note')}
        </p>
      ))}
    </>
  )
}

export function useEarnerTickCheck({ conflicts, members, saveMembers, t, route }: {
  conflicts: EarnerTickConflicts | null | undefined
  members: WorkingMemberRole[]
  saveMembers: (next: WorkingMemberRole[]) => void
  t: (key: string) => string
  /** The income route on screen: a change drops an open question (STR and back never revives it). */
  route?: string
}): { toggle: (m: WorkingMemberRole, opener?: HTMLElement | null) => void; node: ReactNode; open: boolean } {
  const [pending, setPending] = useState<WorkingMemberRole | null>(null)
  const served = conflicts || {}
  // A question whose member no longer disagrees (the served answer changed) is dropped, never drawn empty.
  const asking = pending && served[pending] ? pending : null
  const ids = useId()
  const cancelRef = useRef<HTMLButtonElement>(null)
  const openerRef = useRef<HTMLElement | null>(null)
  const wasAsking = useRef(false)

  useEffect(() => { if (pending && !asking) setPending(null) }, [pending, asking])
  useEffect(() => { setPending(null) }, [route])
  // Focus: into the question on open, on "No" (review round 2: Enter twice must never confirm unread;
  // "Yes" is the answer that makes proof owed); back to the toggle that opened it on close.
  useEffect(() => {
    if (asking) {
      cancelRef.current?.focus()
    } else if (wasAsking.current && openerRef.current?.isConnected) {
      openerRef.current.focus()
    }
    wasAsking.current = !!asking
  }, [asking])

  const toggle = (m: WorkingMemberRole, opener?: HTMLElement | null) => {
    if (members.includes(m)) {
      saveMembers(members.filter((x) => x !== m))
    } else if (served[m]) {
      openerRef.current = opener ?? (typeof document !== 'undefined' ? (document.activeElement as HTMLElement | null) : null)
      setPending(m)            // hold the tick: ask first
      return
    } else {
      saveMembers([...members, m])
    }
    setPending(null)
  }

  const notes = <EarnerTickNotes conflicts={served} members={members} t={t} />
  const node = (asking || members.some((m) => served[m])) ? (
    <div className="mt-3 space-y-2" data-testid="earner-tick-check">
      {asking && (
        <div role="alertdialog" aria-labelledby={`${ids}-ask`} aria-describedby={`${ids}-check`}
          onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); setPending(null) } }}   // Escape = No
          className="rounded-lg border border-caution-200 bg-caution-50 p-3 text-sm text-caution-800">
          <p id={`${ids}-ask`} className="font-medium">{said(t, asking, served, 'ask')}</p>
          <p id={`${ids}-check`} className="mt-1">{t(`${W}.earnerCheck.askCheck`)}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" onClick={() => { saveMembers([...members, asking]); setPending(null) }}
              className="min-h-11 rounded-full border border-primary-600 bg-brand-fill px-4 py-2 text-sm text-brand-fill-ink">
              {t(`${W}.earnerCheck.confirm`)}
            </button>
            <button type="button" ref={cancelRef} onClick={() => setPending(null)}
              className="min-h-11 rounded-full border border-ground-300 px-4 py-2 text-sm text-ground-700">
              {t(`${W}.earnerCheck.cancel`)}
            </button>
          </div>
        </div>
      )}
      {notes}
    </div>
  ) : null

  // `open`: a question is waiting — the route switch holds its Confirm so the held member is not silently left out.
  return { toggle, node, open: !!asking }
}

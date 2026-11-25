'use client'

/**
 * Request #84 (2026-11-25): ASK BEFORE SAVING a "working" tick the family details disagree with.
 *
 * The income step's who-is-working toggles saved every tap. A student once ticked all five members
 * while the family details said the mother was unemployed and listed no guardian or siblings, and
 * every one of them then owed an IC and proof of income. Now a tick the family details disagree
 * with is held: a short, non-blocking question names the person and what the details say, and the
 * student confirms (saved as before) or leaves it unticked. A tick already saved that disagrees
 * keeps a standing note, so open cases see it too. Nothing is ever unticked for the student.
 *
 * ⚠ SERVED, NEVER DERIVED: whether a tick disagrees is `earner_tick_conflicts` on the student's
 * payload (`family.earner_tick_conflicts`, the one rule). The browser only looks a member up.
 */
import { useState, type ReactNode } from 'react'
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

export function useEarnerTickCheck({ conflicts, members, saveMembers, t }: {
  conflicts: EarnerTickConflicts | null | undefined
  members: WorkingMemberRole[]
  saveMembers: (next: WorkingMemberRole[]) => void
  t: (key: string) => string
}): { toggle: (m: WorkingMemberRole) => void; node: ReactNode } {
  const [pending, setPending] = useState<WorkingMemberRole | null>(null)
  const served = conflicts || {}

  const toggle = (m: WorkingMemberRole) => {
    if (members.includes(m)) {
      saveMembers(members.filter((x) => x !== m))
    } else if (served[m]) {
      setPending(m)            // hold the tick: ask first
      return
    } else {
      saveMembers([...members, m])
    }
    setPending(null)
  }

  const standing = members.filter((m) => served[m])
  const node = (pending || standing.length > 0) ? (
    <div className="mt-3 space-y-2" data-testid="earner-tick-check">
      {pending && (
        <div role="alertdialog" aria-labelledby="earner-tick-ask"
          className="rounded-lg border border-caution-200 bg-caution-50 p-3 text-sm text-caution-800">
          <p id="earner-tick-ask" className="font-medium">{said(t, pending, served, 'ask')}</p>
          <p className="mt-1">{t(`${W}.earnerCheck.askCheck`)}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" onClick={() => { saveMembers([...members, pending]); setPending(null) }}
              className="min-h-11 rounded-full border border-primary-600 bg-brand-fill px-4 py-2 text-sm text-brand-fill-ink">
              {t(`${W}.earnerCheck.confirm`)}
            </button>
            <button type="button" onClick={() => setPending(null)}
              className="min-h-11 rounded-full border border-ground-300 px-4 py-2 text-sm text-ground-700">
              {t(`${W}.earnerCheck.cancel`)}
            </button>
          </div>
        </div>
      )}
      {standing.map((m) => (
        <p key={m} className="rounded-lg bg-caution-50 px-3 py-2 text-sm text-caution-800" data-testid={`earner-tick-note-${m}`}>
          {said(t, m, served, 'note')}
        </p>
      ))}
    </div>
  ) : null

  return { toggle, node }
}

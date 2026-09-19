/**
 * One ticked earner's INCOME box on the student's Documents tab — TD-262 F2.
 *
 * ⚠ THREE DOORWAYS OF EQUAL WEIGHT, AND THAT IS THE POINT OF THIS FILE. The owner's rule
 * (2026-07-25) is that a household shows an earner's income ANY ONE way: a payslip, an EPF
 * (KWSP) statement, or — for the very families this scholarship exists for — the amount they
 * are paid in cash, backed by one simple letter. The screen did not say that. It drew two
 * upload cards and hid the third way behind a text link, so the fourth way read as a
 * confession of failure rather than an answer. It is now a card beside the other two: closed
 * until tapped, opening in place to the amount field and the letter it needs.
 *
 * ⚠ AND THE DOOR IS NO LONGER LOCKED BY A DOCUMENT THAT PROVES NOTHING. The cash panel used to
 * be hidden whenever ANY salary or EPF file existed for the earner — pure document PRESENCE. A
 * family whose only payslip was a photo of the wrong thing, or whose EPF statement nothing
 * could be read off, was therefore in a dead end: the server said their income was not shown,
 * and the one screen that could fix it had closed the way. The gate is now the SERVED answer
 * (`apps/scholarship/income_shown.py`, read through `@/lib/incomeShown`) — the same answer the
 * submission gate, the officer's chase list and the AI verdict read. Presence is not evidence.
 *
 * ⚠ THE GREEN TICK IS NOT THIS RULE AND MUST NOT BE FOLDED INTO IT. `shown` comes in as a prop
 * from `ScholarshipDocuments.memberIncomeShown`, the student-side cue the owner ruled on in
 * chunk 1 (no STR arm; an untagged letter counts). The door and the tick answer different
 * questions — "is there still a way in?" and "is this earner done?" — and one of them was
 * deliberately left alone by F2.
 */
import { useState, type ReactNode } from 'react'
import type { MemberBlock, WorkingMember } from '@/lib/incomeWizard'
import { answerFor, type IncomeShownMap } from '@/lib/incomeShown'

/** The student's application payload also carries the served per-earner answer.
 *
 *  ⚠ IT IS DECLARED HERE, NOT ON `ScholarshipApplication`, AND THAT IS THE PHASE-4 STANDING RULE
 *  OF 2026-09-19, NOT AN OVERSIGHT. `src/lib/api.ts` sits EXACTLY on its oversize ceiling (2,488
 *  lines, recorded 2,468 + the 20-line allowance) and is waiting on H13 to become a barrel; a
 *  feature sprint does not add lines to a file whose split is already scheduled. So the field is
 *  declared beside the only code that reads it, and H13 folds it into `ScholarshipApplication`
 *  when that file is split. Nothing is lost in the meantime: every entry read out of this map
 *  goes through `answerFor`, which validates the shape and answers `null` for anything else. */
export interface ServesIncomeShown {
  income_shown?: IncomeShownMap | null
}

/** Is this earner's income already carried by an upload, so the cash door has nothing to add?
 *
 *  ⚠ `declared_letter` is NOT a lock. That way IS the cash door; closing the panel on it would
 *  hide the family's own typed figure and the letter card beneath it the moment they finished.
 *  Only a payslip or an EPF that READ closes the door.
 *
 *  ⚠ A `null` answer means "no served answer", NOT "nothing is shown". The two services deploy
 *  together but not atomically, so an older payload falls back to the presence reading this
 *  replaced — leaving the screen exactly as it was rather than re-opening a door for everyone.
 */
export function cashDoorClosed(
  served: IncomeShownMap | null | undefined,
  member: WorkingMember,
  presenceFallback: boolean,
): boolean {
  const answer = answerFor(served, member)
  if (!answer) return presenceFallback
  return answer.shown && answer.way !== 'declared_letter'
}

export default function MemberIncomeGroup({
  block,
  t,
  iq,
  shown,
  served,
  presenceFallback,
  declared,
  onDeclare,
  renderCard,
  memberHelp,
  memberTitle,
  clusterCoachDocs,
  docKeyOf,
  clusterDocKeyOf,
  salaryAnchor,
  coach,
}: {
  block: MemberBlock
  t: (key: string) => string
  /** `scholarship.docs.income.wizard.*` — the wizard's own namespace. */
  iq: (key: string) => string
  /** The green "this earner is done" cue — `memberIncomeShown`, unchanged by F2. */
  shown: boolean
  served: IncomeShownMap | null | undefined
  /** What the old presence rule said, used only when nothing is served. */
  presenceFallback: boolean
  /** This earner's declared monthly amount (RM), 0 when none. */
  declared: number
  onDeclare: (member: WorkingMember, raw: string) => void
  renderCard: (docType: string, opts?: { required?: boolean; helpOverride?: string; titleOverride?: string; member?: string; suppressCoach?: boolean }) => ReactNode
  memberHelp: (docType: string, member: string) => string | undefined
  memberTitle: (docType: string, member: string) => string | undefined
  clusterCoachDocs: Set<string>
  docKeyOf: (docType: string, member?: string) => string
  clusterDocKeyOf: (docType: string, member: string) => string
  salaryAnchor: string
  coach: ReactNode
}) {
  // Seeded open for a returning family who already typed a figure, so their own answer is never
  // hidden behind a tap they have to remember making.
  const [open, setOpen] = useState(declared > 0)
  const doorClosed = cashDoorClosed(served, block.member, presenceFallback)

  return (
    <div className={`rounded-lg border p-2.5 space-y-2 ${
      shown ? 'border-positive-200 bg-positive-50/40' : 'border-dashed border-ground-200 bg-ground-0'}`}>
      <div className="flex items-start gap-2">
        <span aria-hidden className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full ${
          shown ? 'bg-positive-fill text-positive-fill-ink' : 'border border-ground-300 text-ground-400'}`}>
          {shown ? (
            <svg viewBox="0 0 24 24" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
          ) : (
            <svg viewBox="0 0 24 24" className="h-2.5 w-2.5" fill="none" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
          )}
        </span>
        <div className="min-w-0">
          <p className="text-xs font-semibold text-ground-700">{iq('incomeGroupTitle')}</p>
          <p className={`text-xs ${shown ? 'text-positive-700' : 'text-ground-500'}`}>
            {shown ? iq('incomeShown') : iq('incomeAnyOne')}
          </p>
        </div>
      </div>

      {/* Doors 1 and 2 — the payslip and the EPF (KWSP) statement. */}
      {block.optional.map(({ docType, member }) => (
        <div key={docKeyOf(docType, member)}>
          {renderCard(docType, { required: false, member,
            helpOverride: memberHelp(docType, block.member),
            titleOverride: memberTitle(docType, block.member),
            suppressCoach: clusterCoachDocs.has(docType) })}
          {clusterDocKeyOf(docType, member) === salaryAnchor && coach}
        </div>
      ))}

      {/* Door 3 — paid in cash / works informally. Same card shape as the two above, so the
          three read as three ways of answering one question, not two answers and an excuse. */}
      {!doorClosed && (
        <>
          <div className="border rounded-lg p-3">
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              aria-expanded={open}
              className="flex w-full items-start justify-between gap-2 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 rounded"
            >
              <span className="min-w-0">
                <span className="block text-sm font-medium text-ground-800">{iq('declared.cantGet')}</span>
                <span className="mt-0.5 block text-xs text-ground-500">
                  {t('scholarship.docs.help.income_support_doc')}
                </span>
              </span>
              <svg aria-hidden viewBox="0 0 24 24" className={`h-4 w-4 shrink-0 text-ground-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
              </svg>
            </button>
            {open && (
              <div className="mt-2.5 rounded-md bg-info-50 ring-1 ring-info-100 p-2.5 space-y-2">
                <p className="text-xs text-info-900/90">{iq('declared.prompt')}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-ground-500">RM</span>
                  <input
                    type="number" inputMode="numeric" min={0} step={50}
                    defaultValue={declared || ''}
                    placeholder={iq('declared.placeholder')}
                    onBlur={(e) => onDeclare(block.member, e.target.value)}
                    className="w-28 text-sm rounded border border-ground-300 px-2 py-1 focus:border-primary-400 focus:outline-none"
                  />
                  <span className="text-xs text-ground-400">{iq('declared.perMonth')}</span>
                </div>
                {/* The letter card appears only once there is an amount for it to support —
                    an upload slot with nothing to back reads as one more thing to find. */}
                {declared > 0 && renderCard('income_support_doc', { required: false, member: block.member,
                  titleOverride: iq('supportLetterTitle'), helpOverride: iq('declared.needsDoc') })}
              </div>
            )}
          </div>
          {/* Nothing on the screen used to say this, and a family with two cash earners had every
              reason to assume a letter each. The api counts one untagged letter for every
              earner, so the sentence is true as well as kind. */}
          <p className="text-xs text-ground-500">{iq('declared.oneLetterWholeFamily')}</p>
        </>
      )}
    </div>
  )
}

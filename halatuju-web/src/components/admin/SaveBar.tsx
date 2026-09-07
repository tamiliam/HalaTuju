'use client'

// The console's ONE save bar (owner, 2026-09-07, reading the Configuration screens side by side:
// *"The save button should be in the right, as is the platform standard"* and *"there is no need to
// say 'Nothing to save' as the colour of the button is supposed to convey that message"*).
//
// ⚠ FOUR TABS HAD THREE LAYOUTS AND FOUR IDLE SENTENCES, and every one of them was written by
// somebody copying the neighbour they happened to look at. Measured before this was built:
// Organisation → Configuration said "No unsaved changes", Colours said "Nothing to save",
// "What we ask for" said "Nothing changed yet.", and the Rules tab said "Nothing to save — no
// changes have been made" **beside a button on the LEFT with no bar at all**. A house style that
// lives only in the last person's memory is not a house style.
//
// ⚠ IDLE RENDERS NOTHING, AND THAT IS THE RULE THIS COMPONENT EXISTS TO HOLD. A greyed button
// already says there is nothing to save; a sentence repeating it is the loudest thing in the bar
// and it is saying the least. Say something only when there IS something: work pending, a save
// that landed, a refusal.
//
// ⚠ WHAT THIS DOES **NOT** OWN: whether the button sleeps. Each tab keeps its own `dirty`
// computation and its own closed outcome union — that is deliberate, because the dangerous
// direction is the opposite of the reported bug (request #6, 2026-08-01: a Save wrongly ASLEEP
// strands real work with no way to keep it), and one shared "is this dirty?" across four unrelated
// shapes of state is exactly how a tab starts sleeping through an edit. This owns the LAYOUT and
// the SILENCE. Pass `title={t('common.nothingToSave')}` on a sleeping button so the reason is one
// hover away.

import type { ReactNode } from 'react'

/** The primary (brand-filled) action. One home, so four bars cannot drift apart on padding. */
export const SAVE_BAR_PRIMARY =
  'rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink'
  + ' hover:bg-brand-fill-hover disabled:opacity-50'

/** A secondary action beside it — Discard, Revert, Save draft. */
export const SAVE_BAR_SECONDARY =
  'rounded-lg border border-ground-300 bg-ground-0 px-4 py-2 text-sm font-medium'
  + ' text-ground-700 disabled:opacity-50'

export default function SaveBar({ status, children, testId = 'save-outcome' }: {
  /** What to say. Pass `null` when there is nothing worth saying — see the idle rule above. */
  status?: ReactNode
  /** The buttons, in reading order. They sit on the RIGHT. */
  children: ReactNode
  /** Overridable only because three tabs shipped with their own outcome test ids. */
  testId?: string
}) {
  return (
    <div data-testid="save-bar"
      className="sticky bottom-0 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ground-200 bg-ground-50 px-5 py-3">
      <div className="text-sm text-ground-700" data-testid={testId}>{status ?? null}</div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

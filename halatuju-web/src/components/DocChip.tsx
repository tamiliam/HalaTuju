'use client'

/** ONE chip and ONE pill for every document screen. The colours come from `lib/docChips` only. */
import type { ReactNode } from 'react'
import { useT } from '@/lib/i18n'
import { CHIP_SYMBOL, PILL_COLOURS, STATE_COLOURS, STATE_WORD_KEY, type ChipPillWord, type ChipState } from '@/lib/docChips'

/** The spoken state word, in the active language. `useT` throws outside the provider (a bare chip in a
 *  unit test), and `useContext` has already run by then, so the hook order is the same either way: a
 *  chip with no provider simply has no spoken word. The app always has the provider. */
function useStateWord(state: ChipState): string {
  try {
    return useT().t(STATE_WORD_KEY[state])
  } catch {
    return ''
  }
}

export function DocChip({ state, children, plain = false, spoken = true }: {
  state: ChipState
  children: ReactNode
  /** A plain copied value: the value only, no ring, never green. */
  plain?: boolean
  /** Add the sr-only state word. False when the chip text is already a result word or a year. */
  spoken?: boolean
}) {
  const word = useStateWord(state)
  if (plain) return <span className="shrink-0 text-[11px] text-ground-600" data-chip="plain">{children}</span>
  const sym = CHIP_SYMBOL[state]
  return (
    <span data-chip={state}
      className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${STATE_COLOURS[state].chip}`}>
      {sym && <span aria-hidden className="text-[9px] font-extrabold">{sym}</span>}
      {children}
      {spoken && word && <span className="sr-only" data-chip-state>{word}</span>}
    </span>
  )
}

export function DocPill({ pill, children }: { pill: ChipPillWord; children: ReactNode }) {
  return (
    <span data-pill={pill} className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${PILL_COLOURS[pill]}`}>
      {children}
    </span>
  )
}

'use client'

/** ONE chip and ONE pill for every document screen. The colours come from `lib/docChips` only. */
import type { ReactNode } from 'react'
import { CHIP_SYMBOL, PILL_COLOURS, STATE_COLOURS, type ChipPillWord, type ChipState } from '@/lib/docChips'

export function DocChip({ state, children, plain = false }: {
  state: ChipState
  children: ReactNode
  /** A plain copied value: the value only, no ring, never green. */
  plain?: boolean
}) {
  if (plain) return <span className="shrink-0 text-[11px] text-ground-600" data-chip="plain">{children}</span>
  const sym = CHIP_SYMBOL[state]
  return (
    <span data-chip={state}
      className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ${STATE_COLOURS[state].chip}`}>
      {sym && <span aria-hidden className="text-[9px] font-extrabold">{sym}</span>}
      {children}
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

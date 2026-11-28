'use client'

/**
 * The apply page's two one-card answers (a closed gift, an already-finished application), in ONE
 * module so `LazyApplyNotice` fetches a single chunk. Drawn only on those branches, which most
 * visitors never reach, so they do not pay for the cards in first-load JS (G8 bundle budget).
 */
import AlreadyApplied from './AlreadyApplied'
import GiftClosed from './GiftClosed'
import ResultsRouteNote from './LazyResultsRouteNote'   // TD-773: Step 3's notes ride this chunk too
import type { ResultsNoteKind } from './ResultsRouteNote'   // a type only: erased

export default function ApplyNotice({ kind, onSeeOpen }: { kind: 'closed' | 'applied' | ResultsNoteKind; onSeeOpen?: () => void }) {
  if (kind !== 'closed' && kind !== 'applied') return <ResultsRouteNote kind={kind} />
  return kind === 'closed' ? <GiftClosed onSeeOpen={onSeeOpen} /> : <AlreadyApplied onSeeOpen={onSeeOpen} />
}

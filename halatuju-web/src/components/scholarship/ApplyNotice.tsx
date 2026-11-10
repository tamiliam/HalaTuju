'use client'

/**
 * The apply page's two one-card answers (a closed gift, an already-finished application), in ONE
 * module so `LazyApplyNotice` fetches a single chunk. Drawn only on those branches, which most
 * visitors never reach, so they do not pay for the cards in first-load JS (G8 bundle budget).
 */
import AlreadyApplied from './AlreadyApplied'
import GiftClosed from './GiftClosed'

export default function ApplyNotice({ kind, onSeeOpen }: { kind: 'closed' | 'applied'; onSeeOpen?: () => void }) {
  return kind === 'closed' ? <GiftClosed onSeeOpen={onSeeOpen} /> : <AlreadyApplied onSeeOpen={onSeeOpen} />
}

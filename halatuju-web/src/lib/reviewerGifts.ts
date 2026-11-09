/**
 * Which gifts a reviewer covers: the tick list's rules (multi-gift tagging, owner design 2026-11-06).
 *
 * One list, three screens: the pencil pop-over on Team -> Reviewers, the reviewer invite form and,
 * since Invitations I3 (2026-11-08), the SPONSOR invite form — which starts with nothing ticked
 * (`NO_GIFT`, `allowNone`): see `NO_GIFT`.
 *
 * ⚠ **NO GIFT TICKED MEANS EVERY GIFT**, and it is the DEFAULT. The server stores it as no rows and
 * serves it as `gifts: []`. There is no state in which somebody covers nothing, so clearing the last
 * tick puts "Every gift" back on rather than leaving an empty list that would read as "none".
 *
 * ⚠ "Every gift" and a gift are never both ticked. Ticking "Every gift" clears the gifts; the gifts
 * are greyed while it is ticked; un-ticking it lets you pick them.
 */

/** The tick list's state. `picked` is always empty while `every` is on. */
export interface GiftTicks {
  every: boolean
  picked: number[]
}

/** The default: every gift. */
export const EVERY_GIFT: GiftTicks = { every: true, picked: [] }

/** The ticks for gifts as served (`[]` = every gift). */
export function ticksFrom(gifts: ReadonlyArray<{ id: number }>): GiftTicks {
  return gifts.length === 0 ? EVERY_GIFT : { every: false, picked: gifts.map((g) => g.id) }
}

/** Tick or un-tick "Every gift". Ticking it clears the gifts. */
export function tickEvery(_state: GiftTicks, on: boolean): GiftTicks {
  return on ? EVERY_GIFT : { every: false, picked: [] }
}

/**
 * NOTHING TICKED — a SPONSOR invite's starting state (Invitations I3, 2026-11-08). A sponsor joins
 * each gift as its own pending membership, so "every gift" is a choice they must make, not a
 * default; the form refuses to send until something is ticked.
 */
export const NO_GIFT: GiftTicks = { every: false, picked: [] }

/** True when neither "Every gift" nor any gift is ticked (only reachable with `allowNone`). */
export function nothingTicked(state: GiftTicks): boolean {
  return !state.every && state.picked.length === 0
}

/** A sponsor invite's ticks before anyone touches them: the one gift when there is exactly one,
 *  otherwise nothing. */
export function sponsorStartTicks(options: ReadonlyArray<{ id: number }>): GiftTicks {
  return options.length === 1 ? { every: false, picked: [options[0].id] } : NO_GIFT
}

/** Tick or un-tick one gift. Ignored while "Every gift" is on. Clearing the last tick returns to
 *  "Every gift" — or, with `allowNone` (the sponsor invite), to nothing ticked. */
export function tickGift(state: GiftTicks, id: number, allowNone = false): GiftTicks {
  if (state.every) return state
  const picked = state.picked.includes(id)
    ? state.picked.filter((p) => p !== id) : [...state.picked, id]
  if (picked.length > 0) return { every: false, picked }
  return allowNone ? NO_GIFT : EVERY_GIFT
}

/** What the server is sent: `[]` for every gift, else the ticked ids in order. */
export function idsToSave(state: GiftTicks): number[] {
  return state.every ? [] : [...state.picked].sort((a, b) => a - b)
}

/**
 * The gifts the pop-over may offer for this reviewer: their own organisation's only. A super is
 * served every organisation's gifts, and the server refuses a foreign one with a 404. Either side
 * unknown (an older payload) offers the whole list and leaves the refusal to the server.
 */
export function giftsForReviewer<G extends { organisation_id?: number | null }>(
  options: G[], organisationId: number | null | undefined,
): G[] {
  if (organisationId == null) return options
  return options.filter((g) => g.organisation_id == null || g.organisation_id === organisationId)
}

/**
 * The tick list's rules for which gifts a reviewer covers (multi-gift, owner design 2026-11-06).
 * No ticked gift means EVERY gift, and it is the default; "Every gift" and a gift are never both on.
 */
import {
  EVERY_GIFT, giftsForReviewer, idsToSave, tickEvery, tickGift, ticksFrom,
} from '@/lib/reviewerGifts'

describe('reviewerGifts', () => {
  it('reads no gifts as EVERY gift, and a list as those gifts', () => {
    expect(ticksFrom([])).toEqual({ every: true, picked: [] })
    expect(ticksFrom([{ id: 9 }, { id: 7 }])).toEqual({ every: false, picked: [9, 7] })
  })

  it('ticking Every gift clears the gifts; un-ticking it leaves them to pick', () => {
    expect(tickEvery({ every: false, picked: [7, 9] }, true)).toEqual(EVERY_GIFT)
    expect(tickEvery(EVERY_GIFT, false)).toEqual({ every: false, picked: [] })
  })

  it('ignores a gift tick while Every gift is on (the gifts are greyed)', () => {
    expect(tickGift(EVERY_GIFT, 7)).toEqual(EVERY_GIFT)
  })

  it('toggles a gift, and clearing the LAST one puts Every gift back on', () => {
    const one = tickGift({ every: false, picked: [] }, 7)
    expect(one).toEqual({ every: false, picked: [7] })
    const two = tickGift(one, 9)
    expect(two).toEqual({ every: false, picked: [7, 9] })
    expect(tickGift(two, 7)).toEqual({ every: false, picked: [9] })
    expect(tickGift({ every: false, picked: [9] }, 9)).toEqual(EVERY_GIFT)
  })

  it('sends an empty list for every gift, else the ids in order', () => {
    expect(idsToSave(EVERY_GIFT)).toEqual([])
    expect(idsToSave({ every: false, picked: [9, 7] })).toEqual([7, 9])
  })

  it('offers only the reviewer\'s own organisation\'s gifts', () => {
    const options = [
      { id: 7, organisation_id: 1 }, { id: 9, organisation_id: 1 }, { id: 11, organisation_id: 2 },
    ]
    expect(giftsForReviewer(options, 1).map((g) => g.id)).toEqual([7, 9])
    expect(giftsForReviewer(options, 2).map((g) => g.id)).toEqual([11])
  })

  it('offers the whole list when either side is unknown — the server refuses a foreign gift', () => {
    const options = [{ id: 7, organisation_id: 1 }, { id: 11 }]
    expect(giftsForReviewer(options, null).map((g) => g.id)).toEqual([7, 11])
    expect(giftsForReviewer(options, undefined).map((g) => g.id)).toEqual([7, 11])
    expect(giftsForReviewer(options, 2).map((g) => g.id)).toEqual([11])
  })
})

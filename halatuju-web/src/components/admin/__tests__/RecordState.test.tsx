/**
 * @jest-environment jsdom
 *
 * THE SHARED RECORD STATE, AND THE ONE THING ITS WORDING MAY NOT SAY.
 *
 * Two claims:
 *
 *  1. **It draws one state or the other, never both and never neither.** The defect this
 *     component retires is an early return in the wrong order, so "the not-found state is on
 *     screen AND the loading line is gone" is asserted as one thing. A test that only looked for
 *     the message would have passed on the broken pages too, because they set the message.
 *  2. **The copy never says the record does not exist, and never says you may not see it.** The
 *     admin organisation fence answers 404 — not 403 — for a record belonging to another
 *     organisation, so that its existence is never leaked. "This record does not exist" is FALSE
 *     for such a record; "you do not have access" LEAKS that it exists. Both are the natural
 *     thing to write, which is why this is a test and not a comment, and why it runs against all
 *     three locales: the leak can be introduced in Malay or Tamil alone.
 */
import { render, screen } from '@testing-library/react'

import RecordState from '../RecordState'
import en from '@/messages/en.json'
import ms from '@/messages/ms.json'
import ta from '@/messages/ta.json'

jest.mock('@/lib/i18n', () => ({ useT: () => ({ t: (k: string) => k }) }))

describe('which state is drawn', () => {
  it('says it is still loading, and does not say anything is missing', () => {
    render(<RecordState loading />)
    expect(screen.getByText('common.loading')).toBeTruthy()
    expect(screen.queryByTestId('record-not-found')).toBeNull()
  })

  it('says it could not be found, and the loading line is GONE', () => {
    render(<RecordState loading={false} />)
    expect(screen.getByTestId('record-not-found')).toBeTruthy()
    expect(screen.getByText('errors.recordNotFound')).toBeTruthy()
    expect(screen.getByText('errors.recordNotFoundDesc')).toBeTruthy()
    // ⚠ THE WHOLE BUG, IN ONE ASSERTION. Every broken screen had the message in state and the
    // spinner on screen; only the absence of the spinner proves the person is not still waiting.
    expect(screen.queryByText('common.loading')).toBeNull()
  })
})

describe('the copy claims nothing about why', () => {
  // The neutral sentence, pinned verbatim. If a future change wants different words, it changes
  // this line deliberately — it does not drift.
  it('reads "We could not find that." in English', () => {
    expect(en.errors.recordNotFound).toBe('We could not find that.')
    // And the help line offers a next step without a diagnosis of its own.
    expect(en.errors.recordNotFoundDesc)
      .toBe('Check the address, or go back to the list you came from.')
  })

  /**
   * What an "improvement" would reach for, per locale, with the reason it is refused.
   *
   * ⚠ Each pattern is matched against BOTH keys joined. Tamil's "முடியவில்லை" ("could not") is
   * deliberately NOT read as a non-existence claim — it is a statement about US, which is the
   * whole point; what is refused is a claim about the RECORD ("இல்லாத"/"நீக்கப்பட்டது") or about
   * the reader's permission ("அணுகல்").
   */
  const FORBIDDEN: Array<[string, Record<string, string>, Array<[RegExp, string]>]> = [
    ['en', en.errors, [
      [/does ?n[o']t exist|no longer exists|was deleted|has been deleted/i,
       'false for a cross-org record, which does exist'],
      [/access|permission|not allowed|forbidden/i,
       'leaks that the record exists'],
    ]],
    ['ms', ms.errors, [
      [/tidak wujud|telah dipadam|sudah dipadam/i,
       'false for a cross-org record, which does exist'],
      [/akses|kebenaran|tidak dibenarkan|dilarang/i,
       'leaks that the record exists'],
    ]],
    ['ta', ta.errors, [
      [/இல்லாத|நீக்கப்பட்ட|அழிக்கப்பட்ட/,
       'false for a cross-org record, which does exist'],
      [/அணுகல்|அனுமதி|தடைசெய்/,
       'leaks that the record exists'],
    ]],
  ]

  it.each(FORBIDDEN)('%s says neither "it does not exist" nor "you cannot see it"',
    (_locale, errors, patterns) => {
      const copy = `${errors.recordNotFound} ${errors.recordNotFoundDesc}`
      expect(copy.trim().length).toBeGreaterThan(10)        // a real sentence, not a stub
      for (const [pattern, why] of patterns) {
        expect({ copy, why, matched: pattern.test(copy) })
          .toEqual({ copy, why, matched: false })
      }
    })
})

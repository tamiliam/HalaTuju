/**
 * DRIFT (R4): the card's invisible-character class is the server's `_INVISIBLE`, character for character,
 * so the card trims and blanks exactly as the server does. The card's behaviour is `ReviewerNotesCard.test.tsx`.
 */
import { INVISIBLE } from './ReviewerNotesCard'
import { readApi } from '@/test/apiSource'

describe('DRIFT: the card trims and blanks exactly as the server does (R4)', () => {
  it('the invisible character class is the same source, character for character', () => {
    const src = readApi('apps/scholarship/reviewer_notes.py')
    const m = src.match(/_INVISIBLE = re\.compile\(r'([^']*)'\)/)
    if (!m) throw new Error('drift test: no _INVISIBLE = re.compile(r...) in reviewer_notes.py — follow it.')
    expect(m[1].length).toBeGreaterThan(40)
    expect(INVISIBLE.source).toBe(m[1])
  })
})

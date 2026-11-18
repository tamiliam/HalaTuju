/**
 * Request #69 (2026-11-17): every word of "Highest position held" — the profile field, its four
 * choices, the banner question, the completion item, the person page line and the sponsor's
 * "Our volunteers" — is present and non-empty in en, ms and ta, and the four English choices are the
 * organisation's own wording, exactly.
 */
import en from '../en.json'
import ms from '../ms.json'
import ta from '../ta.json'

const LEVELS = ['c_level', 'head', 'manager', 'individual']
const KEYS = [
  'admin.myProfile.highestPosition', 'admin.myProfile.highestPositionHint', 'admin.myProfile.highestPositionNote',
  'admin.myProfile.chooseOne', 'admin.myProfile.error.bad_highest_position',
  'admin.myProfile.completion.done.highest_position', 'admin.myProfile.completion.todo.highest_position',
  'admin.nudge.positionQuestion', 'admin.nudge.positionWhy', 'admin.nudge.positionThanks', 'admin.nudge.positionFailed',
  'admin.person.highestPosition',
  ...LEVELS.map((k) => `admin.position.${k}`),
  'sponsorPortal.trust.volunteers.title', 'sponsorPortal.trust.volunteers.headline',
  'sponsorPortal.trust.volunteers.basedOn',
  ...LEVELS.map((k) => `sponsorPortal.trust.volunteers.level.${k}`),
]
const at = (tree: unknown, key: string) =>
  key.split('.').reduce<unknown>((n, part) => (n as Record<string, unknown> | undefined)?.[part], tree)

it.each([['en', en], ['ms', ms], ['ta', ta]])('%s holds every key, as words', (_, tree) => {
  for (const key of KEYS) {
    const v = at(tree, key)
    expect([key, typeof v]).toEqual([key, 'string'])
    expect((v as string).trim()).not.toBe('')
  }
  expect(at(tree, 'sponsorPortal.trust.volunteers.headline')).toContain('{pct}')
  expect(at(tree, 'sponsorPortal.trust.volunteers.basedOn')).toContain('{n}+')   // a band, never exact
})

it('the review round\'s words: the banded footnote and the Malay top level', () => {
  expect(at(en, 'sponsorPortal.trust.volunteers.basedOn')).toBe('Based on {n}+ volunteers who have told us.')
  expect(at(ms, 'sponsorPortal.trust.volunteers.basedOn')).toBe('Berdasarkan {n}+ sukarelawan yang telah memberitahu kami.')
  expect(at(ta, 'sponsorPortal.trust.volunteers.basedOn')).toBe('எங்களிடம் தெரிவித்த {n}+ தன்னார்வலர்களின் அடிப்படையில்.')
  for (const key of ['admin.position.c_level', 'sponsorPortal.trust.volunteers.level.c_level']) {
    expect(at(ms, key)).toBe('Pengurusan tertinggi (C-level), pengasas atau pemilik perniagaan')
  }
})

it('the four English choices are the organisation\'s own words, on both surfaces', () => {
  const words = ['C-level, founder or business owner', 'Head of department or senior manager', 'Manager',
    'Individual contributor (academic, doctor, etc.)']
  expect(LEVELS.map((k) => at(en, `admin.position.${k}`))).toEqual(words)
  expect(LEVELS.map((k) => at(en, `sponsorPortal.trust.volunteers.level.${k}`))).toEqual(words)
})

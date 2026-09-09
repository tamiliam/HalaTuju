/**
 * The apply page's copy belongs to the GIFT (2026-09-09).
 *
 * ⚠ THE URL TEST IS THE LOAD-BEARING ONE. This whole sprint is a value threaded end to end, and
 * "a prop that is never fed will stay never fed, because nothing fails" (lessons.md, 2026-09-08).
 * A default parameter and a starved one render identically — so the test PASSES the code and
 * asserts the request carries it, rather than merely asserting the function accepts an argument.
 */
import { applyCard } from '../applyCopy'
import { toDraft, toPayload } from '@/components/admin/ApplyCopyTab'
import { getScholarshipIntake } from '../api'

const PLATFORM = {
  title: 'Apply for B40 Education Assistance',
  intro: 'Financial assistance for B40 students.',
  criteria: ['Income within B40.', 'At least 5 A’s.', 'Continuing.', 'Contactable.'],
}

const GIFT = {
  title: 'Apply for the Sabah Bursary',
  intro: 'Support for Sabahan school leavers.',
  criteria: ['Resident in Sabah.'],
}

describe('which words the apply page shows', () => {
  it('uses the platform default when the gift wrote nothing', () => {
    const card = applyCard(undefined, 'en', PLATFORM)
    expect(card.title).toBe(PLATFORM.title)
    expect(card.fromGift).toBe(false)
  })

  it('uses the gift’s own words when it wrote them', () => {
    const card = applyCard({ en: GIFT }, 'en', PLATFORM)
    expect(card.title).toBe(GIFT.title)
    expect(card.criteria).toEqual(GIFT.criteria)
    expect(card.fromGift).toBe(true)
  })

  it('falls back to the GIFT’S English, never the platform’s Malay', () => {
    // ⚠ A wrong-language truth beats a right-language falsehood. Falling back to the platform
    // here would tell a Malay-reading Sabah applicant they must be B40 with five A's.
    const card = applyCard({ en: GIFT }, 'ms', PLATFORM)
    expect(card.title).toBe(GIFT.title)
    expect(card.criteria).toEqual(GIFT.criteria)
  })

  it('refuses to MIX a gift heading with platform criteria', () => {
    // A half-filled block can only arrive from a stale client; the platform default is the safe
    // whole, never a merge.
    const card = applyCard({ en: { ...GIFT, criteria: [] } }, 'en', PLATFORM)
    expect(card.title).toBe(PLATFORM.title)
    expect(card.criteria).toEqual(PLATFORM.criteria)
  })

  it('renders however many bullets the gift wrote, not always four', () => {
    const three = { ...GIFT, criteria: ['A.', 'B.', 'C.'] }
    expect(applyCard({ en: three }, 'en', PLATFORM).criteria).toHaveLength(3)
  })
})

describe('the intake request carries the gift code', () => {
  const realFetch = global.fetch

  afterEach(() => { global.fetch = realFetch })

  function capture() {
    const seen: string[] = []
    global.fetch = jest.fn(async (url: RequestInfo | URL) => {
      seen.push(String(url))
      return { ok: true, status: 200, json: async () => ({ open: false, cohort_name: '' }) } as Response
    }) as unknown as typeof fetch
    return seen
  }

  it('⚠ SENDS ?programme= so the gate answers about THIS gift', async () => {
    const seen = capture()
    await getScholarshipIntake('brightpath-flagship')
    expect(seen[0]).toContain('programme=brightpath-flagship')
  })

  it('sends no parameter when the visitor named no gift', async () => {
    const seen = capture()
    await getScholarshipIntake()
    expect(seen[0]).not.toContain('programme=')
  })

  it('encodes the code rather than pasting it into the URL', async () => {
    const seen = capture()
    await getScholarshipIntake('a b&c')
    expect(seen[0]).toContain('programme=a%20b%26c')
  })
})

describe('the editor’s draft round-trip', () => {
  it('a missing language is BLANK, never pre-filled with English', () => {
    // Pre-filling would silently promote the English text into a field nobody typed.
    const d = toDraft({ en: GIFT })
    expect(d.ms.title).toBe('')
    expect(d.ta.intro).toBe('')
  })

  it('a wholly blank language is omitted from the payload', () => {
    const d = toDraft({ en: GIFT })
    expect(Object.keys(toPayload(d))).toEqual(['en'])
  })

  it('blank bullet rows are dropped, not sent', () => {
    const d = toDraft({ en: { ...GIFT, criteria: ['One.', '', '  ', 'Two.'] } })
    expect(toPayload(d).en?.criteria).toEqual(['One.', 'Two.'])
  })

  it('an empty draft round-trips to {} — the way "use the default" is said', () => {
    expect(toPayload(toDraft(undefined))).toEqual({})
  })
})

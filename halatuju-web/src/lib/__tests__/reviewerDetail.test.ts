/**
 * Reviewer detail — the pure decisions (request #10, 2026-08-02).
 *
 * Each of these exists because the obvious version is wrong for volunteers: a null turnaround that
 * reads as instant, an empty caseload that reads as a criticism, a percentage that says "100%"
 * about one decision, and a phone number shown past the consent its owner withheld.
 */
import type { AdminReviewer, AdminReviewerDetail } from '@/lib/admin-api'
import {
  LONG_WAIT_DAYS, credentialLines, hasNoHistory, isFree, orderedLanguages, outcomeSegments,
  phoneState, turnaroundBand,
} from '@/lib/reviewerDetail'

const R = (over: Partial<AdminReviewer> = {}): AdminReviewer => ({
  id: 1, name: 'Aisha', email: 'a@example.org', role: 'reviewer', languages: ['en'],
  open_now: 0, completed: 0, turnaround_days: null, paused: false, ...over,
})

const D = (over: Partial<AdminReviewerDetail> = {}): AdminReviewerDetail => ({
  ...R(), decided_by_other: 0, progressed: 0, declined: 0,
  created_at: '2026-03-01T00:00:00Z', qualification: '', university: '',
  graduation_year: null, field_of_study: '', phone: '', share_phone_with_students: false,
  reopens: [], ...over,
})

describe('turnaroundBand', () => {
  it('makes "no measurement" its own answer — never zero', () => {
    // Six of the thirteen have completed nothing; "no reviews yet" and "instant" must not render
    // the same.
    expect(turnaroundBand(null)).toBe('unknown')
    expect(turnaroundBand(0)).toBe('measured')
  })

  it('bands only the actionable end, and it is about the STUDENT\'s wait', () => {
    expect(turnaroundBand(LONG_WAIT_DAYS - 0.1)).toBe('measured')
    expect(turnaroundBand(LONG_WAIT_DAYS)).toBe('waiting')
  })

  it('does not fire on any turnaround production has today', () => {
    // Verified against production on 2026-08-02: the eleven reviewers who have decided anything
    // have medians of 2.0 to 10.1 days. A guard that stays quiet on current data is working, not
    // missing — this pins that it would speak up if the spread moved.
    for (const d of [2.0, 4.2, 5.7, 8.7, 10.1]) expect(turnaroundBand(d)).toBe('measured')
  })
})

describe('isFree', () => {
  it('is a plain fact about the caseload, not a judgement', () => {
    expect(isFree(R({ open_now: 0 }))).toBe(true)
    expect(isFree(R({ open_now: 1 }))).toBe(false)
  })
})

describe('outcomeSegments', () => {
  it('is empty when nothing was decided — no bar of nothing', () => {
    expect(outcomeSegments(D())).toEqual([])
  })

  it('leaves DECIDED-BY-SOMEBODY-ELSE out of the bar entirely', () => {
    // Those are not this person's outcomes. The page states the number separately, in words.
    const segs = outcomeSegments(D({ progressed: 3, declined: 1, decided_by_other: 5 }))
    expect(segs.map((s) => s.key)).toEqual(['progressed', 'declined'])
    expect(segs.reduce((n, s) => n + s.count, 0)).toBe(4)
  })

  it('takes its percentages over decided cases, and they sum to 100', () => {
    const segs = outcomeSegments(D({ progressed: 3, declined: 1 }))
    expect(segs.map((s) => s.pct)).toEqual([75, 25])
  })

  it('survives a single decision without dividing by zero', () => {
    expect(outcomeSegments(D({ progressed: 1 }))).toEqual([
      { key: 'progressed', count: 1, pct: 100 },
      { key: 'declined', count: 0, pct: 0 },
    ])
  })
})

describe('hasNoHistory', () => {
  it('is true only when nothing at all has passed through them', () => {
    expect(hasNoHistory(D())).toBe(true)
    expect(hasNoHistory(D({ open_now: 1 }))).toBe(false)
    expect(hasNoHistory(D({ completed: 1 }))).toBe(false)
    // Assigned cases somebody else decided are still history — the page must not claim otherwise.
    expect(hasNoHistory(D({ decided_by_other: 1 }))).toBe(false)
  })
})

describe('credentialLines', () => {
  it('drops blanks rather than drawing a form of empty rows', () => {
    expect(credentialLines(D())).toEqual([])
  })

  it('keeps the order the labels are read in, and stringifies the year', () => {
    const lines = credentialLines(D({
      qualification: 'MSc', university: 'UM', graduation_year: 2014, field_of_study: 'Physics',
    }))
    expect(lines.map((l) => l.key))
      .toEqual(['qualification', 'university', 'graduationYear', 'fieldOfStudy'])
    expect(lines[2].value).toBe('2014')
  })

  it('drops a partly-filled profile\'s blanks only', () => {
    expect(credentialLines(D({ university: 'UPM' })))
      .toEqual([{ key: 'university', value: 'UPM' }])
  })
})

describe('orderedLanguages', () => {
  it('is a FIXED order, so the chips never re-shuffle between rows', () => {
    expect(orderedLanguages(R({ languages: ['ta', 'en'] }))).toEqual(['en', 'ta'])
    expect(orderedLanguages(R({ languages: ['ta', 'ms', 'en'] }))).toEqual(['en', 'ms', 'ta'])
  })

  it('ignores a code the screen has no label for', () => {
    expect(orderedLanguages(R({ languages: ['zh', 'ms'] }))).toEqual(['ms'])
  })

  it('is empty for a reviewer with no profile', () => {
    expect(orderedLanguages(R({ languages: [] }))).toEqual([])
  })
})

describe('phoneState — three states, not two', () => {
  it('says NOTHING GIVEN when there is no number', () => {
    expect(phoneState(D())).toBe('none')
  })

  it('distinguishes a number an admin may use from one students may be given', () => {
    // Showing a withheld number without saying so would defeat the consent this organisation
    // asked the reviewer for.
    expect(phoneState(D({ phone: '012', share_phone_with_students: false }))).toBe('staff_only')
    expect(phoneState(D({ phone: '012', share_phone_with_students: true }))).toBe('shared')
  })

  it('is "none" even when consent was given, if there is no number to share', () => {
    expect(phoneState(D({ phone: '', share_phone_with_students: true }))).toBe('none')
  })
})

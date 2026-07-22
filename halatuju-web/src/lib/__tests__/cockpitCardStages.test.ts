/**
 * Which right-column cards appear at which stage (owner 2026-07-22).
 *
 * Both rules are whole-lifecycle, so each case below asserts across EVERY status rather than the
 * two or three that motivated the change — a status added later shows up here as a decision to
 * make, not as a card that silently appears in the wrong place.
 */
import { showsReportingDateBox, showsReviewerAssignedCard, showsWitnessCard } from '@/lib/officerCockpit'

/** Every ScholarshipApplication.STATUS_CHOICES value, in lifecycle order. */
const ALL = [
  'submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed',
  'recommended', 'awarded', 'active', 'maintenance', 'closed',
  'rejected', 'withdrawn', 'expired',
]

const shown = (fn: (s: string) => boolean) => ALL.filter(fn)

describe('showsReviewerAssignedCard', () => {
  it('is visible only while the assignment can still change', () => {
    expect(shown(showsReviewerAssignedCard)).toEqual([
      'submitted', 'profile_complete', 'interviewing', 'interviewed',
    ])
  })

  it('is hidden at shortlisted — the Reject card takes that slot', () => {
    expect(showsReviewerAssignedCard('shortlisted')).toBe(false)
  })

  it('is hidden from recommended onward, where the Recommendation box names the reviewer', () => {
    for (const s of ['recommended', 'awarded', 'active', 'maintenance', 'closed']) {
      expect(showsReviewerAssignedCard(s)).toBe(false)
    }
  })

  it('is hidden on the terminal off-ramps too (owner: "yes, rejected as well")', () => {
    for (const s of ['rejected', 'withdrawn', 'expired']) {
      expect(showsReviewerAssignedCard(s)).toBe(false)
    }
  })

  it('returns at Awaiting QC and below, which is where a reopen lands the case', () => {
    // reopen.reopen_decision: recommended -> interviewed, interviewed -> interviewing.
    expect(showsReviewerAssignedCard('interviewed')).toBe(true)
    expect(showsReviewerAssignedCard('interviewing')).toBe(true)
  })

  it('treats a missing status as not-shown rather than throwing', () => {
    expect(showsReviewerAssignedCard(null)).toBe(true)      // '' is not a hidden status
    expect(showsReviewerAssignedCard(undefined)).toBe(true)
  })
})

describe('showsWitnessCard', () => {
  it('is offered from Awaiting QC onward, so an org admin can assign before the award', () => {
    expect(shown(showsWitnessCard)).toEqual([
      'interviewed', 'recommended', 'awarded', 'active', 'maintenance', 'closed',
    ])
  })

  it('is hidden before QC — nothing to witness yet', () => {
    for (const s of ['submitted', 'shortlisted', 'profile_complete', 'interviewing']) {
      expect(showsWitnessCard(s)).toBe(false)
    }
  })

  it('is hidden on the off-ramps — those students never sign an agreement', () => {
    for (const s of ['rejected', 'withdrawn', 'expired']) {
      expect(showsWitnessCard(s)).toBe(false)
    }
  })

  it('covers awarded, the stage that actually needs a witness to sign', () => {
    expect(showsWitnessCard('awarded')).toBe(true)
  })
})

describe('the two cards never both occupy the slot pointlessly', () => {
  it('overlap only at interviewed, where a reviewer may still change AND a witness can be set', () => {
    const both = ALL.filter((s) => showsReviewerAssignedCard(s) && showsWitnessCard(s))
    expect(both).toEqual(['interviewed'])
  })
})

describe('showsReportingDateBox', () => {
  const base = { status: 'interviewing', decisionReopened: false, letterHasDate: false }

  it('shows while a reviewer is working the case', () => {
    expect(showsReportingDateBox(base)).toBe(true)
  })

  it('stays hidden when the offer letter already carries a date', () => {
    expect(showsReportingDateBox({ ...base, letterHasDate: true })).toBe(false)
  })

  it('is hidden at every stage outside the reviewer window', () => {
    const shown = ALL.filter((status) => showsReportingDateBox({ ...base, status }))
    expect(shown).toEqual(['interviewing'])
  })

  it('returns on a reopen, wherever the reopen landed', () => {
    // reopen_decision: recommended -> interviewed, interviewed -> interviewing. Keying on
    // status alone would miss a case bounced back from Recommended.
    for (const status of ['interviewed', 'interviewing']) {
      expect(showsReportingDateBox({ ...base, status, decisionReopened: true })).toBe(true)
    }
  })

  it('is hidden at Awaiting QC when NOT reopened — QC bounces it back instead', () => {
    expect(showsReportingDateBox({ ...base, status: 'interviewed' })).toBe(false)
  })
})

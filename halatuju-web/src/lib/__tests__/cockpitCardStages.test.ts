/**
 * Which right-column cards appear at which stage (owner 2026-07-22).
 *
 * Both rules are whole-lifecycle, so each case below asserts across EVERY status rather than the
 * two or three that motivated the change — a status added later shows up here as a decision to
 * make, not as a card that silently appears in the wrong place.
 */
import {
  isCaseClosed,
  queryingLockReason,
  showsCheck2Box,
  showsDecisionCards,
  showsGeneratedProfileCard,
  showsInterviewStage,
  showsReportingDateBox,
  showsReviewerAssignedCard,
  showsWitnessCard,
} from '@/lib/officerCockpit'

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

/**
 * The closed end of the lifecycle (2026-08-18).
 *
 * `showsPostSubmissionCards` guarded only `shortlisted`, so on the 44 production applications
 * that expired or were rejected before review these three cards rendered fully live: a billable
 * gap-suggestion, Save draft / Submit findings, Pass/Fail buttons and an Approve that reached an
 * ungated `record-verdict`. `services.review_writes_closed` is the backend mirror — the two must
 * agree, or the cockpit offers a control the endpoint refuses.
 */
describe('the closed-case gates', () => {
  const LIVE = ALL.filter((s) => !['rejected', 'withdrawn', 'expired'].includes(s))

  describe('isCaseClosed', () => {
    it('is true on the three terminal off-ramps', () => {
      expect(ALL.filter((status) => isCaseClosed({ status }))).toEqual([
        'rejected', 'withdrawn', 'expired',
      ])
    })

    it('is false on a REOPENED case, however terminal the status reads', () => {
      // reopen_decision does not remap 'rejected': a reopened rejected case sits at 'rejected'
      // and is expected to be re-decided from there.
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(isCaseClosed({ status, decisionReopened: true })).toBe(false)
      }
    })
  })

  describe('showsInterviewStage', () => {
    it('is hidden on a closed case that never held an interview', () => {
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(showsInterviewStage({ status, hasInterviewSession: false })).toBe(false)
      }
    })

    it('KEEPS the box on a closed case that does hold one — that is a record, not a control', () => {
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(showsInterviewStage({ status, hasInterviewSession: true })).toBe(true)
      }
    })

    it('is shown at every live stage past submission, with or without a session', () => {
      // The negative half: a gate that hid everything would pass the two cases above.
      for (const status of LIVE.filter((s) => s !== 'shortlisted')) {
        expect(showsInterviewStage({ status, hasInterviewSession: false })).toBe(true)
      }
    })

    it('stays hidden at shortlisted — the pre-submission rule is unchanged', () => {
      expect(showsInterviewStage({ status: 'shortlisted', hasInterviewSession: false })).toBe(false)
    })

    it('returns on a reopen even with no session', () => {
      expect(showsInterviewStage({
        status: 'rejected', decisionReopened: true, hasInterviewSession: false,
      })).toBe(true)
    })
  })

  describe('showsDecisionCards', () => {
    it('is hidden on a closed case with no recorded verdict', () => {
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(showsDecisionCards({ status, decisionRecorded: false })).toBe(false)
      }
    })

    it('KEEPS the cards on a closed case WITH a verdict — the frozen decision trail', () => {
      // 21 of the 41 rejected records on 2026-08-18. Hiding these would delete the
      // "Declined by … · date" history from the screen.
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(showsDecisionCards({ status, decisionRecorded: true })).toBe(true)
      }
    })

    it('is shown at every live stage past submission, verdict or not', () => {
      for (const status of LIVE.filter((s) => s !== 'shortlisted')) {
        expect(showsDecisionCards({ status, decisionRecorded: false })).toBe(true)
      }
    })

    it('stays hidden at shortlisted', () => {
      expect(showsDecisionCards({ status: 'shortlisted', decisionRecorded: false })).toBe(false)
    })

    it('returns on a reopen so the reopened decision can actually be re-recorded', () => {
      expect(showsDecisionCards({
        status: 'rejected', decisionReopened: true, decisionRecorded: true,
      })).toBe(true)
    })
  })

  it('treats a missing status as open rather than throwing', () => {
    expect(showsInterviewStage({ status: null, hasInterviewSession: false })).toBe(true)
    expect(showsDecisionCards({ status: undefined, decisionRecorded: false })).toBe(true)
  })

  describe('showsGeneratedProfileCard', () => {
    it('is hidden on a closed case holding no profile', () => {
      // Empty, the card claims a draft that does not exist, promises a final version at a
      // verdict that cannot be recorded, and offers a language selector wired to that call.
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(showsGeneratedProfileCard({ status, hasProfile: false })).toBe(false)
      }
    })

    it('KEEPS a closed case that holds one — the profile is a record', () => {
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(showsGeneratedProfileCard({ status, hasProfile: true })).toBe(true)
      }
    })

    it('is shown at every live stage past submission, profile or not', () => {
      for (const status of LIVE.filter((s) => s !== 'shortlisted')) {
        expect(showsGeneratedProfileCard({ status, hasProfile: false })).toBe(true)
      }
    })

    it('stays hidden at shortlisted', () => {
      expect(showsGeneratedProfileCard({ status: 'shortlisted', hasProfile: true })).toBe(false)
    })
  })

  describe('showsCheck2Box', () => {
    it('is hidden on a closed case with nothing in it', () => {
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(showsCheck2Box({ status, hasItems: false })).toBe(false)
      }
    })

    it('KEEPS a closed case that holds items — that is the record of what was asked', () => {
      for (const status of ['rejected', 'withdrawn', 'expired']) {
        expect(showsCheck2Box({ status, hasItems: true })).toBe(true)
      }
    })

    it('is shown at EVERY live stage, empty included — unlike the other cards', () => {
      // Deliberately not gated on showsPostSubmissionCards: at `shortlisted` an empty Check 2
      // is the working surface for chasing a student, and hiding it would break the one stage
      // the box exists for. The negative half that proves this gate is about closure only.
      for (const status of LIVE) {
        expect(showsCheck2Box({ status, hasItems: false })).toBe(true)
      }
    })
  })
})

/**
 * WHY querying is locked. `isQueryingLocked` folds two independent reasons into one boolean and
 * the copy used to hard-code the interview one, on 44 records that never held an interview.
 */
describe('queryingLockReason', () => {
  it('is null while querying is open', () => {
    expect(queryingLockReason('shortlisted')).toBeNull()
    expect(queryingLockReason('profile_complete')).toBeNull()
    expect(queryingLockReason('interviewing')).toBeNull()
  })

  it('names the INTERVIEW when one was actually submitted', () => {
    expect(queryingLockReason('interviewing', 'submitted')).toBe('interview')
    // 83 production records reach a locked status with a submitted session; their copy is
    // unchanged by this fix.
    for (const status of ['interviewed', 'recommended', 'awarded', 'rejected']) {
      expect(queryingLockReason(status, 'submitted')).toBe('interview')
    }
  })

  it('names CLOSURE on a terminal case that never held an interview', () => {
    for (const status of ['rejected', 'withdrawn', 'expired']) {
      expect(queryingLockReason(status)).toBe('closed')
      expect(queryingLockReason(status, 'draft')).toBe('closed')
    }
  })

  it('never claims an interview on a status-only lock', () => {
    // The defect in one line: every locked status with no submitted session must NOT say
    // "the interview is concluded".
    for (const status of ['interviewed', 'recommended', 'awarded', 'active', 'maintenance',
      'closed', 'rejected', 'withdrawn', 'expired']) {
      expect(queryingLockReason(status)).not.toBe('interview')
    }
  })
})

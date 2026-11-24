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
  reviewerCardState,
  isWaitingForReviewer,
  showsCheck2Box,
  showsEstimateCard,
  showsNotesCard,
  showsRecommendationCard,
  showsDecisionCards,
  showsGeneratedProfileCard,
  showsInterviewStage,
  showsReportingDateBox,
  showsReviewerAssignedCard,
  showsWitnessCard,
  isRejectedBeforeReview,
  isRejectedAfterInterview,
} from '@/lib/officerCockpit'

describe('owner 2026-11-23: a case rejected before any review keeps only its record', () => {
  it('is a reject at Shortlisted or before interview, and not once reopened', () => {
    expect(isRejectedBeforeReview({ status: 'rejected', rejectionCategory: 'pre_interview' })).toBe(true)
    expect(isRejectedBeforeReview({ status: 'rejected', rejectionCategory: 'incomplete' })).toBe(true)
    expect(isRejectedBeforeReview({ status: 'rejected', rejectionCategory: 'interview' })).toBe(false)
    expect(isRejectedBeforeReview({ status: 'rejected', rejectionCategory: 'pre_interview', decisionReopened: true })).toBe(false)
    expect(isRejectedBeforeReview({ status: 'shortlisted', rejectionCategory: 'pre_interview' })).toBe(false)
  })

  it('hides the estimate, notes, decision and rate cards', () => {
    const o = { status: 'rejected', rejectionCategory: 'pre_interview', decisionRecorded: true }
    expect(showsEstimateCard(o)).toBe(false)
    expect(showsNotesCard(o)).toBe(false)
    expect(showsDecisionCards(o)).toBe(false)
    expect(showsRecommendationCard(o)).toBe(false)
  })
})

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
      'profile_complete', 'interviewing', 'interviewed',
    ])
  })

  it('is hidden at submitted and shortlisted (owner 2026-11-19; the Reject card takes the shortlisted slot)', () => {
    expect(showsReviewerAssignedCard('submitted')).toBe(false)
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
  // 'closed' joined 2026-10-06 (TD-352): an officer may close a stalled case from any in-play status.
  const CLOSED = ['closed', 'rejected', 'withdrawn', 'expired']
  const LIVE = ALL.filter((s) => !CLOSED.includes(s))

  describe('isCaseClosed', () => {
    it('is true on the four terminal off-ramps', () => {
      expect(ALL.filter((status) => isCaseClosed({ status }))).toEqual(CLOSED)
    })

    it('is false on a REOPENED case, however terminal the status reads', () => {
      // reopen_decision does not remap 'rejected': a reopened rejected case sits at 'rejected'
      // and is expected to be re-decided from there.
      for (const status of CLOSED) {
        expect(isCaseClosed({ status, decisionReopened: true })).toBe(false)
      }
    })
  })

  describe('showsInterviewStage', () => {
    it('is hidden on a closed case that never held an interview', () => {
      for (const status of CLOSED) {
        expect(showsInterviewStage({ status, hasInterviewSession: false })).toBe(false)
      }
    })

    it('KEEPS the box on a closed case that does hold one — that is a record, not a control', () => {
      for (const status of CLOSED) {
        expect(showsInterviewStage({ status, hasInterviewSession: true })).toBe(true)
      }
    })

    it('is shown at every live stage past submission, with or without a session', () => {
      // The negative half: a gate that hid everything would pass the two cases above.
      for (const status of LIVE.filter((s) => s !== 'shortlisted' && s !== 'submitted')) {
        expect(showsInterviewStage({ status, hasInterviewSession: false })).toBe(true)
      }
    })

    it('stays hidden at submitted too (owner 2026-11-19)', () => {
      expect(showsInterviewStage({ status: 'submitted', hasInterviewSession: false })).toBe(false)
      expect(showsDecisionCards({ status: 'submitted', decisionRecorded: false })).toBe(false)
      expect(showsGeneratedProfileCard({ status: 'submitted', hasProfile: false })).toBe(false)
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
      for (const status of CLOSED) {
        expect(showsDecisionCards({ status, decisionRecorded: false })).toBe(false)
      }
    })

    it('KEEPS the cards on a closed case WITH a verdict — the frozen decision trail', () => {
      // 21 of the 41 rejected records on 2026-08-18. Hiding these would delete the
      // "Declined by … · date" history from the screen.
      for (const status of CLOSED) {
        expect(showsDecisionCards({ status, decisionRecorded: true })).toBe(true)
      }
    })

    it('is shown at every live stage past submission, verdict or not', () => {
      for (const status of LIVE.filter((s) => s !== 'shortlisted' && s !== 'submitted')) {
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
      for (const status of CLOSED) {
        expect(showsGeneratedProfileCard({ status, hasProfile: false })).toBe(false)
      }
    })

    it('KEEPS a closed case that holds one — the profile is a record', () => {
      for (const status of CLOSED) {
        expect(showsGeneratedProfileCard({ status, hasProfile: true })).toBe(true)
      }
    })

    it('is shown at every live stage past submission, profile or not', () => {
      for (const status of LIVE.filter((s) => s !== 'shortlisted' && s !== 'submitted')) {
        expect(showsGeneratedProfileCard({ status, hasProfile: false })).toBe(true)
      }
    })

    it('stays hidden at shortlisted', () => {
      expect(showsGeneratedProfileCard({ status: 'shortlisted', hasProfile: true })).toBe(false)
    })
  })

  describe('showsCheck2Box', () => {
    it('is hidden on a closed case with nothing in it', () => {
      for (const status of CLOSED) {
        expect(showsCheck2Box({ status, hasItems: false })).toBe(false)
      }
    })

    it('KEEPS a closed case that holds items — that is the record of what was asked', () => {
      for (const status of CLOSED) {
        expect(showsCheck2Box({ status, hasItems: true })).toBe(true)
      }
    })

    it('is hidden at submitted and shortlisted when empty, kept when it has items', () => {
      for (const status of ['submitted', 'shortlisted']) {
        expect(showsCheck2Box({ status, hasItems: false })).toBe(false)
        expect(showsCheck2Box({ status })).toBe(false)
        expect(showsCheck2Box({ status, hasItems: true })).toBe(true)
      }
    })

    it('is shown at every other live stage, empty included', () => {
      for (const status of LIVE.filter((s) => s !== 'submitted' && s !== 'shortlisted')) {
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

describe('reviewerCardState (TD-613: read from what the server serves, never the role)', () => {
  it('shows the card at a reopened funded or declined case whose holder has gone', () => {
    for (const status of ['recommended', 'rejected', 'interviewed']) {
      const card = reviewerCardState({ status, assignable: true, needs_new_holder: true, may_unassign: false }, true)
      expect(card).toEqual({ shows: true, locked: false, mayUnassign: false, needsNewHolder: true })
    }
  })

  it('offers Unassigned exactly when the server serves may_unassign (review F2), never from needs_new_holder', () => {
    // A stranded case at Completed / interviewing may still be left with nobody on the server.
    expect(reviewerCardState({ status: 'interviewing', assignable: true, needs_new_holder: true, may_unassign: true }, false)
      .mayUnassign).toBe(true)
    expect(reviewerCardState({ status: 'interviewed', assignable: true, needs_new_holder: true, may_unassign: false }, false)
      .mayUnassign).toBe(false)
    expect(reviewerCardState({ status: 'interviewing', assignable: true, needs_new_holder: false, may_unassign: false }, false)
      .mayUnassign).toBe(false)
  })

  it('follows the served assignable, not the decision lock, when it is served', () => {
    expect(reviewerCardState({ status: 'interviewed', assignable: false }, false).locked).toBe(true)
    expect(reviewerCardState({ status: 'interviewing', assignable: true }, true).locked).toBe(false)
  })

  it('keeps the decision lock for a payload that does not serve assignable', () => {
    expect(reviewerCardState({ status: 'interviewing' }, true).locked).toBe(true)
    expect(reviewerCardState({ status: 'interviewing' }, false).locked).toBe(false)
  })

  it('leaves the stage window alone when the holder can still work the case', () => {
    for (const status of ALL) {
      const card = reviewerCardState({ status, assignable: false, needs_new_holder: false }, false)
      expect(card.shows).toBe(showsReviewerAssignedCard(status))
      expect(card.mayUnassign).toBe(true)
      expect(card.needsNewHolder).toBe(false)
    }
  })
})

describe('isWaitingForReviewer and the four cards it hides (owner 2026-11-19)', () => {
  const waiting = { status: 'profile_complete', assignedToId: null }
  it('is true only at Awaiting review, unassigned, not reopened', () => {
    expect(isWaitingForReviewer(waiting)).toBe(true)
    expect(isWaitingForReviewer({ ...waiting, assignedToId: 42 })).toBe(false)
    expect(isWaitingForReviewer({ ...waiting, decisionReopened: true })).toBe(false)
    expect(isWaitingForReviewer({ status: 'profile_complete' })).toBe(false)   // not told
    expect(isWaitingForReviewer({ status: 'interviewing', assignedToId: null })).toBe(false)
  })
  it('hides interview, estimate, recommendation and notes while waiting', () => {
    expect(showsInterviewStage(waiting)).toBe(false)
    expect(showsEstimateCard(waiting)).toBe(false)
    expect(showsRecommendationCard(waiting)).toBe(false)
    expect(showsNotesCard(waiting)).toBe(false)
  })
  it('shows them once assigned or reopened', () => {
    for (const o of [{ ...waiting, assignedToId: 42 }, { ...waiting, decisionReopened: true }]) {
      expect(showsInterviewStage(o)).toBe(true)
      expect(showsEstimateCard(o)).toBe(true)
      expect(showsRecommendationCard(o)).toBe(true)
      expect(showsNotesCard(o)).toBe(true)
    }
  })
  it('notes and estimate stay hidden at submitted and shortlisted, shown after', () => {
    for (const status of ['submitted', 'shortlisted']) {
      expect(showsNotesCard({ status, assignedToId: null })).toBe(false)
      expect(showsEstimateCard({ status, assignedToId: null })).toBe(false)
    }
    expect(showsNotesCard({ status: 'interviewed', assignedToId: null })).toBe(true)
  })
})

describe('TD-716 (owner 2026-11-24): the estimated need box hides after an interview rejection', () => {
  const base = { status: 'rejected', assignedToId: 42 }
  it('hides on a case rejected after an interview, not once reopened', () => {
    for (const rejectionCategory of ['interview', 'contractual']) {
      expect(isRejectedAfterInterview({ ...base, rejectionCategory })).toBe(true)
      expect(showsEstimateCard({ ...base, rejectionCategory })).toBe(false)
      expect(showsEstimateCard({ ...base, rejectionCategory, decisionReopened: true })).toBe(true)
    }
  })
  it('shows on a live case', () => {
    for (const status of ['interviewing', 'interviewed', 'recommended', 'awarded']) {
      expect(showsEstimateCard({ status, assignedToId: 42 })).toBe(true)
    }
    expect(isRejectedAfterInterview({ status: 'interviewed', rejectionCategory: 'interview' })).toBe(false)
  })
})

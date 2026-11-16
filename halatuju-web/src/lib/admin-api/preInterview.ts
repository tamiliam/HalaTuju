/**
 * Request #75 (2026-11-16): reject a student BEFORE interview, at Awaiting review with no reviewer.
 *
 * The door, the reason list and the note's limit are all SERVED (`pre_interview` on the detail read,
 * from `services/pre_interview.offer_for`): present only for a viewer holding the `qc` key at Awaiting
 * review, so the cockpit derives nothing. The decline email waits for the organisation's QC decline
 * hold and is cancelled through the ordinary `cancelPendingDecline`. Refusal codes: `bad_status`,
 * `has_reviewer`, `reason_required`, `comments_required`, `comments_too_long`.
 *
 * Types only: the call is `rejectBeforeInterview` in `decisions.ts`, so `applications.ts` can extend these
 * without an import loop.
 */
/** The panel's main reasons, in the panel's order (the server's list). */
export type PreInterviewReason =
  | 'not_b40' | 'not_government_institution' | 'results_too_low'
  | 'programme_requirements' | 'not_responsive' | 'other'

export interface PreInterviewOffer {
  /** How long the decline email is held (the organisation's QC decline hold). The confirm step adds
   *  it to the moment of confirming to say when the email goes. */
  hold_hours: number
  reasons: PreInterviewReason[]
  note_max: number
}

/** The detail read's #75 fields (`AdminScholarshipDetail` extends this). */
export interface PreInterviewDetailFields {
  /** Served only to a `qc` key holder at Awaiting review; null (or absent) otherwise. */
  pre_interview?: PreInterviewOffer | null
  /** The main reason of a reject before interview ('' otherwise). Internal, never sent to the student. */
  rejection_reason?: string
  /** When THIS decline's email went to the student (null while it is held). */
  decline_email_sent_at?: string | null
}

/** The list row's #75 field (`AdminScholarshipListItem` extends this): the decline kind. */
export interface PreInterviewListFields {
  rejection_category?: string
}

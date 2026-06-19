// Pure, node-testable derivation of the per-student journey tracker shown on the
// My Giving "students you support" cards. Display logic lives here (not the backend),
// driven by the non-identifying signals the sponsorship serializer returns.

export type JourneyStatus = 'done' | 'now' | 'todo'
export type JourneyKey = 'matched' | 'onboarded' | 'studying' | 'graduated'
export interface JourneyStage { key: JourneyKey; status: JourneyStatus }

export interface JourneySignals {
  onboarded: boolean
  progressState: string | null // null | on_track | semester_completed | needs_attention | graduated
}

/**
 * Matched → Onboarded → Studying → Graduated. An active sponsorship is always
 * 'matched'; onboarding is the current step until completed; studying runs until
 * the latest result marks graduation, which completes the whole journey.
 */
export function journeyStages({ onboarded, progressState }: JourneySignals): JourneyStage[] {
  const graduated = progressState === 'graduated'
  const onboardedStatus: JourneyStatus = onboarded ? 'done' : 'now'
  let studying: JourneyStatus
  let graduatedStatus: JourneyStatus
  if (graduated) {
    studying = 'done'
    graduatedStatus = 'done'
  } else if (onboarded) {
    studying = 'now'
    graduatedStatus = 'todo'
  } else {
    studying = 'todo'
    graduatedStatus = 'todo'
  }
  return [
    { key: 'matched', status: 'done' },
    { key: 'onboarded', status: onboardedStatus },
    { key: 'studying', status: studying },
    { key: 'graduated', status: graduatedStatus },
  ]
}

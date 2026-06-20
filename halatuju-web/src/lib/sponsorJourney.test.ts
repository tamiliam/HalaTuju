import { journeyStages } from './sponsorJourney'

const statuses = (s: { onboarded: boolean; progressState: string | null }) =>
  journeyStages(s).map((x) => x.status)

describe('journeyStages', () => {
  it('matched but not onboarded → onboarding is the current step', () => {
    expect(statuses({ onboarded: false, progressState: 'on_track' })).toEqual(['done', 'now', 'todo', 'todo'])
  })

  it('onboarded and studying', () => {
    expect(statuses({ onboarded: true, progressState: 'semester_completed' })).toEqual(['done', 'done', 'now', 'todo'])
    expect(statuses({ onboarded: true, progressState: 'needs_attention' })).toEqual(['done', 'done', 'now', 'todo'])
  })

  it('graduated completes the whole journey', () => {
    expect(statuses({ onboarded: true, progressState: 'graduated' })).toEqual(['done', 'done', 'done', 'done'])
  })

  it('exposes the four stage keys in order', () => {
    expect(journeyStages({ onboarded: false, progressState: null }).map((s) => s.key)).toEqual([
      'matched', 'onboarded', 'studying', 'graduated',
    ])
  })
})

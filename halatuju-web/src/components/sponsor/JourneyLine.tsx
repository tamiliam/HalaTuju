'use client'

/**
 * The Matched → Onboarded → Studying → Graduated tracker on a supported student (My Giving's rows and
 * the student's own page) — Mobile M5. It was four dots with a 9 px (My Giving) or 11 px (the student's
 * page) word under each: unreadable on a phone (rule 12), and at 12 px four Tamil words ("பொருத்தப்பட்டது"…)
 * no longer fit a 328 px row. Now: a stepped line of four segments, and ONE 12 px line naming the stage
 * the student is at (plus the semesters done), at every width. A discontinued student's Studying segment
 * is red and the line says "Withdrew" — the same signal as before, in words.
 *
 * The full journey is still read out: the line is an image whose label names all four stages.
 */
import { journeyStages, type JourneyKey } from '@/lib/sponsorJourney'
import type { SponsorPoolCard } from '@/lib/api'

export default function JourneyLine({ onboarded, state, semesters, discontinued, t, className = 'mt-3' }: {
  onboarded: boolean
  state: SponsorPoolCard['progress_state']
  semesters: number
  discontinued?: boolean
  t: (k: string) => string
  className?: string
}) {
  const stages = journeyStages({ onboarded, progressState: state })
  const withdrew = (k: JourneyKey) => !!discontinued && k === 'studying'
  // The stage she is at: the one marked `now`, else the last one done (a graduate).
  const at = stages.find((s) => s.status === 'now') ?? [...stages].reverse().find((s) => s.status === 'done') ?? stages[0]
  const name = (k: JourneyKey) => t(withdrew(k) ? 'sponsorPortal.journey.withdrew' : `sponsorPortal.journey.${k}`)
  const atWithdrew = !!discontinued && (at.key === 'studying' || at.key === 'graduated')
  return (
    <div className={className} data-testid="journey-line">
      <div role="img" className="flex gap-1" aria-label={stages.map((s) => `${name(s.key)}${s.status === 'done' ? ' ✓' : ''}`).join(', ')}>
        {stages.map((s) => (
          <span key={s.key} className={`h-1.5 flex-1 rounded-full ${
            withdrew(s.key) ? 'bg-critical-500'
              : s.status === 'done' ? 'bg-positive-500'
              : s.status === 'now' ? 'bg-info-500' : 'bg-ground-200'}`} />
        ))}
      </div>
      <p className={`mt-1.5 text-xs ${atWithdrew ? 'font-semibold text-critical-600' : 'text-ground-600'}`}>
        <span className="font-semibold">{atWithdrew ? t('sponsorPortal.journey.withdrew') : name(at.key)}</span>
        {semesters > 0 && !discontinued && (
          <> · {t('sponsorPortal.journey.semesters').replace('{n}', String(semesters))}</>
        )}
      </p>
    </div>
  )
}

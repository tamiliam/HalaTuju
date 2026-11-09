'use client'

import type { CompletionKey } from '@/lib/admin-api'
import { CARD, type CardProps } from './shared'

/**
 * Where each completion item is filled in: the card it scrolls to (`CardFrame` gives every card the
 * id `profile-card-<id>`). A map of PLACES, not a rule — which items count is the server's
 * (`apps/scholarship/profile_completion.py`).
 */
export const ITEM_CARD: Record<CompletionKey, string> = {
  photo: 'you', name: 'you', job_title: 'you', about: 'you', phone: 'contact',
  qualifications: 'qualifications', language: 'qualifications', address: 'address', mentoring_area: 'mentoring',
}

const P = 'admin.myProfile.completion'
const link = 'text-info-700 hover:underline max-md:inline-flex max-md:min-h-11 max-md:items-center'   // 44 px on a phone

/**
 * "Your profile is N% complete" — the top of My Profile (staff nudges, 2026-11-08; the owner-approved
 * mock-up): a bar, "N of M done", a tick for each item done and a link to the card for each one
 * missing. At 100% it is one line. Everything comes from the server (`admin/me/` `completion`); a super
 * is served none and sees nothing.
 */
export default function CompletionCard({ state }: CardProps) {
  const { t, completion } = state
  if (!completion) return null
  if (completion.done >= completion.total) {
    return (
      <section className={CARD} data-testid="profile-completion" aria-label={t(`${P}.complete`)}>
        <p className="text-sm font-semibold text-positive-700">{t(`${P}.complete`)} <span aria-hidden>✓</span></p>
      </section>
    )
  }
  const pct = Math.max(0, Math.min(100, completion.percent))
  const title = t(`${P}.title`, { percent: String(pct) })
  return (
    <section className={CARD} data-testid="profile-completion" aria-label={title}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="font-semibold">{title}</h2>
        <span className="text-sm text-ground-600">
          {t(`${P}.count`, { done: String(completion.done), total: String(completion.total) })}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-ground-200" role="progressbar" aria-label={title}
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        <div className="h-2 rounded-full bg-info-600" style={{ width: `${pct}%` }} />
      </div>
      <ul className="flex flex-col gap-1 text-sm sm:flex-row sm:flex-wrap sm:gap-x-5 sm:gap-y-2">
        {completion.items.map(({ key, done }) => (done ? (
          <li key={key} className="text-positive-700 max-sm:hidden" data-testid={`completion-done-${key}`}>
            <span aria-hidden>✓ </span>{t(`${P}.done.${key}`)}
          </li>
        ) : (
          <li key={key} data-testid={`completion-todo-${key}`}>
            <a href={`#profile-card-${ITEM_CARD[key]}`} className={link}>{t(`${P}.todo.${key}`)}</a>
          </li>
        )))}
      </ul>
      <p className="text-xs text-ground-600">{t(`${P}.note`)}</p>
    </section>
  )
}

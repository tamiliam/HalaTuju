'use client'

import { useState, type ReactNode } from 'react'
import { setReviewerPaused } from '@/lib/admin-api'
import { formatDate, formatDateTime } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { seenAgo } from '@/lib/lastSeen'
import { STAFF_STATUS_TONE, staffStatusKey } from '@/lib/staffStatus'
import TableChips from '@/components/admin/TableChips'
import ReviewerGiftsCell from '@/components/admin/ReviewerGifts'
import { ReviewerFigures } from './ReviewerParts'
import type { TeamPersonData } from './useTeamPerson'

/**
 * Sprint T3 (D9, M1, M4, M5): the header card every person page shares.
 *
 *   Name                                 ← O11 (owner, 2026-11-10): no email under it; it is in About
 *   [Admin] [Reviewer] [Mentor]          ← the tables they sit in: the "Also in" chips' own labels
 *   (Status) · Joined 3 Mar 2026 · Last seen 2 days ago
 *   Covers: … / Gifts: …                 ← a reviewer's gifts; a mentor's (Invitations I4)
 *   [Pause new cases] [Revoke] [Delete]  ← one actions row, the same place on every page (M5)
 *   figures                              ← a reviewer's and a mentor's (M4), above the tabs
 *
 * ⚠ NO ROLE WORD under the name (D9, the owner: "if they are in the Reviewers table, they are a
 * reviewer"). The chips say it.
 * ⚠ LAST SEEN IS RELATIVE (M1), the exact date and time in `title`. A NULL `last_seen_at` is "not
 * recorded", never "never signed in"; somebody with no sign-in recorded reads the Invited wording.
 */
export default function PersonHeader({ data, token, mayManage, actions, mentorFigures, mentorGifts, onPatch }: {
  data: TeamPersonData
  token: string | null
  mayManage: boolean
  /** Revoke / Restore / Delete — a staff person's or a pure mentor's (the page decides which). */
  actions: ReactNode
  /** A mentor's figures (the Mentors table's chunk), or null. */
  mentorFigures: ReactNode
  /** Invitations I4: the gifts a mentor mentors in (the Mentors table's chunk), or null. */
  mentorGifts?: ReactNode
  onPatch: (next: (d: TeamPersonData) => TeamPersonData) => void
}) {
  const { t } = useT()
  const { person: p, reviewer } = data
  const [busy, setBusy] = useState(false)
  const [pauseError, setPauseError] = useState('')
  const status = staffStatusKey(p)
  // ⚠ The target side is the server's (#39 S4): `pausable` is the pause endpoint's own rule. D9: only
  // a reviewer is offered Pause. T3 review: a payload without `pausable` (an older api) offers none — a
  // switch the endpoint might refuse is worse than one that is missing for a few minutes.
  const mayPause = !!reviewer && mayManage && !!token && reviewer.pausable === true
  const seen = p.signed_in && p.last_seen_at ? seenAgo(p.last_seen_at) : null

  const pause = async () => {
    if (!reviewer || !token) return
    setBusy(true); setPauseError('')
    try {
      const r = await setReviewerPaused(reviewer.id, !reviewer.paused, { token })
      // Patch just this pair: a full re-read would only make the page flicker.
      onPatch((d) => ({ ...d, person: { ...d.person, paused: r.paused },
        reviewer: d.reviewer && { ...d.reviewer, paused: r.paused, paused_at: r.paused_at } }))
    } catch {
      setPauseError(t('admin.reviewers.detail.pauseFailed'))
    } finally { setBusy(false) }
  }

  return (
    <section className="bg-ground-0 rounded-xl shadow-sm border px-4 sm:px-5 py-4" data-testid="person-header">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="min-w-0 space-y-1.5">
          <h1 className="text-lg sm:text-xl font-bold [overflow-wrap:anywhere]">{p.name || p.email}</h1>
          <TableChips tables={p.tables} lead={p.lead} testId="person-tables" />
          <p className="text-sm text-ground-500 flex flex-wrap items-center gap-x-1.5 gap-y-1" data-testid="person-facts">
            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${STAFF_STATUS_TONE[status]}`}
              data-testid="person-status">{t(`admin.reviewers.status.${status}`)}</span>
            <span aria-hidden>·</span>
            <span data-testid="person-joined">{t('admin.reviewers.detail.joined', { date: formatDate(p.joined_at) })}</span>
            <span aria-hidden>·</span>
            {!p.signed_in ? (
              <span className="text-caution-700" data-testid="person-invited">{t('admin.person.invited')}</span>
            ) : seen ? (
              <span data-testid="person-last-seen" title={formatDateTime(p.last_seen_at)} tabIndex={0}>
                {t('admin.person.lastSeen', {
                  when: t(`admin.person.seen.${seen.key}`, {
                    n: 'n' in seen ? String(seen.n) : '',
                    date: 'date' in seen ? formatDate(seen.date) : '',
                  }),
                })}
              </span>
            ) : (
              <span data-testid="person-last-seen">{t('admin.person.seenUnknown')}</span>
            )}
          </p>
          {/* Which gifts they cover — shown only when there is a choice; NO gift means EVERY gift. */}
          {reviewer && (reviewer.programmes ?? []).length > 1 && (
            <div className="text-sm text-ground-500 flex flex-wrap items-center gap-x-2 gap-y-1">
              <span>{t('admin.reviewers.detail.giftLabel')}</span>
              <ReviewerGiftsCell reviewer={reviewer} options={reviewer.programmes} token={token} canEdit={mayManage}
                onSaved={(gifts) => onPatch((d) => ({ ...d, reviewer: d.reviewer && { ...d.reviewer, gifts } }))} />
            </div>
          )}
          {mentorGifts}
          {(mayPause || actions) && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1" data-testid="person-action-row">
              {mayPause && (
                <button type="button" disabled={busy} onClick={() => void pause()}
                  // What a pause leaves alone rides on the control itself: this is not a revoke.
                  title={t(`admin.reviewers.detail.pauseNote${reviewer.paused ? 'Paused' : 'Active'}`)}
                  className="text-sm font-medium text-primary-600 hover:text-primary-800 hover:underline disabled:opacity-50 max-md:inline-flex max-md:min-h-11 max-md:items-center">
                  {t(`admin.reviewers.detail.${reviewer.paused ? 'unpause' : 'pause'}`)}
                </button>
              )}
              {actions}
            </div>
          )}
          {mayPause && reviewer.paused && (
            <p className="text-xs text-caution-700 max-w-2xl">{t('admin.reviewers.detail.pauseNotePaused')}</p>
          )}
          {pauseError && <p className="text-sm text-critical-600" role="alert">{pauseError}</p>}
        </div>
        {reviewer && <ReviewerFigures detail={reviewer} />}
      </div>
      {mentorFigures && <div className="mt-4">{mentorFigures}</div>}
    </section>
  )
}

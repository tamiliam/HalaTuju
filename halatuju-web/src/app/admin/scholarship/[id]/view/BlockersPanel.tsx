'use client'

/**
 * BLOCKERS — exactly what this student still owes, in the OFFICER's voice, plus the org-admin's
 * manual "you haven't submitted yet" reminder.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import {
  showsBlockerBox,
  parseBlocker,
  stuckStep,
  blockerLabelKey,
  memberLabelKey,
  nudgeButton,
} from '@/lib/blockers'
import { formatDate } from '@/lib/formatDate'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import type { T, AdminRole } from './shared'

export function BlockersPanel({ app, t, busy, isSuper, role, nudgeMsg, doNudge }: {
  app: AdminScholarshipDetail
  t: T
  busy: string
  isSuper: boolean
  role: AdminRole
  nudgeMsg: string
  doNudge: () => void
}) {
  return (<>

      {/* ── Blockers — exactly what this student still owes, in the OFFICER's voice, so they can
            advise the student directly instead of asking for screenshots (owner 2026-07-22).
            Source: `consent_blockers` — the SAME gate the student's own submission enforces, so
            the officer and the student can never be told different things. Read-only (no write
            gate): a reviewer/QC needs the answer too. Shown for shortlisted + profile_complete
            (BLOCKER_BOX_STATUSES — drop `profile_complete` there to retire it). ── */}
      {showsBlockerBox(app.status) && (() => {
        const codes = app.consent_blockers || []
        const step = stuckStep(codes)
        return (
          <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
            <h2 className="text-base font-semibold tracking-tight text-ground-900">
              {t('admin.scholarship.blockers.title')}
            </h2>
            {codes.length > 0 ? (
              <div className="rounded-lg border border-caution-200 bg-caution-50 p-3 text-sm">
                <p className="font-medium text-caution-900">{t('admin.scholarship.blockers.owes')}</p>
                <ul className="mt-1.5 ml-5 list-disc space-y-1 text-caution-800">
                  {codes.map((raw) => {
                    // Income codes are member-qualified ("parent_ic_missing:mother") so the line
                    // names the person; everything else is a plain code.
                    const { member } = parseBlocker(raw)
                    return (
                      <li key={raw}>
                        {member
                          ? t(blockerLabelKey(raw), { member: t(memberLabelKey(member)) })
                          : t(blockerLabelKey(raw))}
                      </li>
                    )
                  })}
                </ul>
                {step && (
                  <p className="mt-2.5 text-caution-900">
                    {t('admin.scholarship.blockers.stuck', {
                      step: t(`admin.scholarship.blockers.step.${step}`),
                    })}
                  </p>
                )}
              </div>
            ) : !app.completeness.consent_done ? (
              /* Nothing outstanding but consent not yet given — the gate never emits a
                 "consent missing" code (it IS the gate to consent), so say it plainly. */
              <p className="rounded-lg border border-info-200 bg-info-50 p-3 text-sm text-info-800">
                {t('admin.scholarship.blockers.awaitingConsent')}
              </p>
            ) : (
              <p className="rounded-lg border border-positive-200 bg-positive-50 p-3 text-sm text-positive-800">
                {t('admin.scholarship.blockers.none')}
              </p>
            )}
            {/* ── Reminder: org-admin manual nudge for a consented-but-unsubmitted student. The
                 auto nudge fires once ~30 min after consent; this is the human follow-up. The
                 whole state (show / enabled / label / note) is server-computed (app.nudge). ── */}
            {(() => {
              const nb = nudgeButton(app.nudge, isSuper || role?.role === 'org_admin')
              if (!nb.show) return null
              const at = app.nudge.available_at ? formatDate(app.nudge.available_at) : ''
              const sent = app.nudge.sent_at ? formatDate(app.nudge.sent_at) : ''
              return (
                <div className="space-y-2 border-t border-ground-100 pt-3">
                  <button type="button" onClick={doNudge} disabled={!nb.enabled || !!busy}
                    className="w-full rounded-lg border border-info-300 px-3 py-2 text-sm font-medium
                               text-primary-700 hover:bg-primary-50 disabled:opacity-50 disabled:hover:bg-transparent">
                    {busy === 'nudge'
                      ? t('admin.scholarship.blockers.nudge.sending')
                      : t(`admin.scholarship.blockers.nudge.${nb.label}`)}
                  </button>
                  {nb.note === 'pending' && (
                    <p className="text-xs text-ground-500">{t('admin.scholarship.blockers.nudge.pending')}</p>
                  )}
                  {nb.note === 'cooldown' && (
                    <p className="text-xs text-ground-500">
                      {t('admin.scholarship.blockers.nudge.cooldown', { date: sent, next: at })}
                    </p>
                  )}
                  {nb.note === 'sent' && (
                    <p className="text-xs text-ground-500">
                      {t('admin.scholarship.blockers.nudge.sent', { date: sent })}
                    </p>
                  )}
                  {nudgeMsg && <p className="text-xs text-ground-600">{nudgeMsg}</p>}
                </div>
              )
            })()}
          </div>
        )
      })()}

  </>)
}

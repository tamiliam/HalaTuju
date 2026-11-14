'use client'

import { useEffect, useState } from 'react'
import { getTeamAdminEmails } from '@/lib/admin-api'
import ReviewerEmailsCard from '@/components/reviewers/ReviewerEmailsCard'
import Link from 'next/link'

type T = (key: string, params?: Record<string, string>) => string

// Team tables T4 (owner ruling 1 and 9): Team -> Emails and Team -> Terms, each in three sections in the
// order of the tables — Admin, Reviewer, Mentor.
//
// ⚠ NOTHING HERE CHANGES WHAT SENDS OR WHO EDITS.
//   * Admin emails is READ-ONLY: the rows are the server's one registry (`admin_email_catalogue`, which
//     names each sender), served as keys and worded here. No switch, no editor — "editable later".
//   * Reviewer emails is `ReviewerEmailsCard`, moved whole (the five with their switches, and the six we
//     maintain under them). Not rewritten.
//   * Mentor emails is a one-line pointer (M2d E6): invitation emails, the mentor's included, are edited
//     in ONE place, Invitations -> Emails. No card here, so no second door to the same template.
// The tab is offered exactly as before (`mayEditEmails` on the Team page); every endpoint is the fence.

function Section({ title, testId, children }: { title: string; testId: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3" data-testid={testId}>
      <h2 className="text-lg font-semibold text-ground-900">{title}</h2>
      {children}
    </section>
  )
}

function AdminEmails({ token, t }: { token: string | null; t: T }) {
  const [rows, setRows] = useState<string[] | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (!token) return
    getTeamAdminEmails({ token })
      .then((r) => setRows(r.emails.map((e) => e.key)))
      .catch(() => setFailed(true))
  }, [token])

  return (
    <div className="overflow-hidden rounded-xl border bg-ground-0 shadow-sm">
      <p className="border-b px-4 py-3 text-sm text-ground-500 sm:px-5">{t('admin.team.emails.adminNote')}</p>
      {failed ? (
        <p className="px-4 py-4 text-sm text-critical-600 sm:px-5">{t('admin.team.emails.adminLoadError')}</p>
      ) : (
        <ul className="divide-y divide-ground-100" data-testid="team-admin-emails">
          {(rows ?? []).map((key) => (
            <li key={key} className="px-4 py-4 sm:px-5" data-testid={`team-admin-email-${key}`}>
              <p className="font-medium text-ground-900">{t(`admin.team.emails.kind.${key}`)}</p>
              <p className="mt-0.5 text-sm text-ground-500">{t(`admin.team.emails.when.${key}`)}</p>
              <p className="mt-1 text-sm text-ground-700">
                <span className="text-ground-400">{t('admin.team.emails.toLabel')} </span>
                {t(`admin.team.emails.to.${key}`)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function TeamEmails({ token, t }: { token: string | null; t: T }) {
  return (
    <div className="space-y-8">
      <Section title={t('admin.team.emails.adminTitle')} testId="team-emails-admin">
        <AdminEmails token={token} t={t} />
      </Section>
      <Section title={t('admin.team.emails.reviewerTitle')} testId="team-emails-reviewer">
        <ReviewerEmailsCard token={token} t={t} />
      </Section>
      <Section title={t('admin.team.emails.mentorTitle')} testId="team-emails-mentor">
        <p className="rounded-xl border bg-ground-0 px-4 py-4 text-sm text-ground-600 shadow-sm sm:px-5"
          data-testid="team-emails-mentor-pointer">
          {t('admin.team.emails.mentorPointer')}{' '}
          <Link href="/admin/organisation/staff" className="font-medium text-primary-600 hover:text-primary-800 hover:underline max-md:inline-flex max-md:min-h-11 max-md:items-center">
            {t('admin.team.emails.mentorPointerLink')}
          </Link>
        </p>
      </Section>
    </div>
  )
}

/** Team -> Terms: the same three sections, none built yet. Nobody signs anything on Team today. */
export function TeamTerms({ t }: { t: (key: string) => string }) {
  return (
    <div className="space-y-4" data-testid="team-terms">
      {(['admin', 'reviewer', 'mentor'] as const).map((k) => (
        <section key={k} className="rounded-xl border bg-ground-0 px-4 py-4 shadow-sm sm:px-5"
          data-testid={`team-terms-${k}`}>
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-ground-900">{t(`admin.team.terms.${k}Title`)}</h2>
            <span className="rounded-full bg-ground-100 px-2 py-0.5 text-[11px] font-semibold text-ground-600">
              {t('admin.team.terms.soon')}
            </span>
          </div>
          <p className="mt-1 text-sm text-ground-500">{t(`admin.team.terms.${k}Text`)}</p>
        </section>
      ))}
    </div>
  )
}

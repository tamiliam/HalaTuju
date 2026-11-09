'use client'

import { Fragment, type ReactNode } from 'react'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { displayPhone, phoneState } from '@/lib/reviewerDetail'
import { Block, ReviewerOutcomes, ReviewerReopens } from './ReviewerParts'
import type { TeamPersonData } from './useTeamPerson'

/**
 * Sprint T3: the **Profile** tab, the same for every person (M3, M6).
 *
 * One fact sheet from the `person` block — the same fields under the same rules whichever door the
 * viewer came in by — then the parts of each table they sit in: a reviewer's Outcomes and Reopens,
 * a mentor's scholars (`mentorWork`, the Mentors table's chunk).
 *
 * ⚠ M3: a field the person has not filled in reads "Not given" — never hidden, so a reader can tell
 * "not filled in" from "not shown to you". The HOME ADDRESS is never in the payload and never here
 * (role-matrix.md): assigning a case is not a reason to read where somebody lives.
 * ⚠ The phone is the server's to give (`staff_person.phone_of`): '' reads "Not given" as well.
 */
export default function PersonProfile({ data, mentorWork }: { data: TeamPersonData; mentorWork: ReactNode }) {
  const { t } = useT()
  const { person: p, reviewer, mentor } = data
  const pr = p.profile
  const none = <span className="text-ground-400">{t('admin.reviewers.detail.phoneNone')}</span>
  const text = (v: string | number | null | undefined) => (v === null || v === undefined || v === '' ? none : String(v))
  const languages = [...pr.languages.map((c) => t(`admin.reviewers.lang.${c}`)),
    ...(pr.other_language ? [pr.other_language] : [])].join(', ')
  const phone = reviewer ? phoneState(reviewer) : null
  const rows: { key: string; label: string; value: ReactNode }[] = [
    { key: 'jobTitle', label: t('admin.myProfile.jobTitle'), value: text(pr.job_title) },
    { key: 'about', label: t('admin.person.aboutField'), value: text(pr.about) },
    { key: 'email', label: t('admin.reviewers.detail.email'), value: text(p.email) },
    { key: 'phone', label: t('admin.reviewers.detail.phone'), value: pr.phone ? (<>
      {/* ⚠ The country code is added HERE: it is stored without one, so this is display only. */}
      {displayPhone(pr.phone)}
      {phone && phone !== 'none' && (
        <span className="block text-xs text-ground-500 mt-0.5">{t(`admin.reviewers.detail.phone_${phone}`)}</span>
      )}
    </>) : none },
    { key: 'languages', label: t('admin.reviewers.colLanguages'), value: text(languages) },
    { key: 'qualification', label: t('admin.reviewers.detail.qualification'), value: text(pr.qualification) },
    { key: 'university', label: t('admin.reviewers.detail.university'), value: text(pr.university) },
    { key: 'fieldOfStudy', label: t('admin.reviewers.detail.fieldOfStudy'), value: text(pr.field_of_study) },
    { key: 'graduationYear', label: t('admin.reviewers.detail.graduationYear'), value: text(pr.graduation_year) },
    ...(mentor ? [
      { key: 'area', label: t('admin.person.areaField'), value: text(mentor.mentor.area) },
      { key: 'mentoringSince', label: t('admin.person.mentoringSince'),
        value: mentor.mentoring_since ? formatDate(mentor.mentoring_since) : none },
    ] : []),
  ]

  const about = (
    <Block title={t('admin.reviewers.detail.about')} note={t('admin.person.privacyNote')} testId="person-profile">
      <dl className="px-4 sm:px-5 py-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2.5 items-baseline">
        {rows.map((r) => (
          <Fragment key={r.key}>
            <dt className="text-sm text-ground-500 sm:whitespace-nowrap">{r.label}</dt>
            <dd className="m-0 min-w-0 text-sm text-ground-900 [overflow-wrap:anywhere] whitespace-pre-line"
              data-testid={`person-field-${r.key}`}>{r.value}</dd>
          </Fragment>
        ))}
      </dl>
    </Block>
  )

  return (
    <div className="space-y-3.5">
      {reviewer ? (
        <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_.85fr] gap-3.5">
          <ReviewerOutcomes detail={reviewer} />
          {about}
        </div>
      ) : about}
      {reviewer && <ReviewerReopens detail={reviewer} />}
      {mentorWork}
    </div>
  )
}

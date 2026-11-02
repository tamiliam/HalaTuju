'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { getMyStudent, type MyStudent } from '@/lib/admin-api'
import LogMeetingSheet from './LogMeetingSheet'
import GrowthWork from '@/components/development/GrowthWork'
import { PRIMARY, ResultChip, SECONDARY, helpWords, telHref } from './mentorBits'

const K = 'admin.myStudents'

/**
 * One student, for their MENTOR (student maintenance S7c; the approved MentorStudentFile board): who
 * they are and how to reach them, since when, the latest result, what they asked for help with, and the
 * meetings of THIS mentoring — the mentor's own in full, the team's as date + how only. "Log a meeting"
 * opens the shared Sheet. A student who is no longer theirs reads as "not one of your current students"
 * (the server's 404), never as an error.
 */
export default function MyStudentFile({ id }: { id: number }) {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<MyStudent | null>(null)
  const [state, setState] = useState<'loading' | 'ok' | 'gone' | 'failed'>('loading')
  const [logging, setLogging] = useState(false)
  const [banner, setBanner] = useState('')

  const load = useCallback(() => {
    if (!token) return
    getMyStudent(id, { token })
      .then((d) => { setData(d); setState('ok') })
      .catch((e: { status?: number }) => setState(e?.status === 404 ? 'gone' : 'failed'))
  }, [id, token])
  useEffect(() => { load() }, [load])

  const back = (
    <Link href="/admin/my-students" className="-my-2.5 inline-flex min-h-11 items-center self-start py-2.5 text-sm text-primary-600 hover:underline">
      {t(`${K}.back`)}
    </Link>
  )
  if (state === 'loading') return <div className="flex flex-col gap-4">{back}<p className="text-sm text-ground-500">{t('common.loading')}</p></div>
  if (state === 'gone' || state === 'failed' || !data) {
    return (
      <div className="flex flex-col gap-4">
        {back}
        <p role="alert" className="text-sm text-ground-700" data-testid="my-student-gone">
          {t(state === 'gone' ? `${K}.notYours` : `${K}.loadFailed`)}
        </p>
      </div>
    )
  }
  const org = data.organisation || t(`${K}.theOrganisation`)
  const help = helpWords(t, data.asked_for_help)

  return (
    <div className="flex max-w-4xl flex-col gap-5" data-testid="my-student-file">
      {back}
      {banner && <p role="status" className="rounded-lg border border-positive-200 bg-positive-50 p-3 text-sm text-positive-800">{banner}</p>}

      <header className="flex flex-col gap-4 rounded-xl border border-ground-200 bg-ground-0 p-4 md:flex-row md:justify-between md:p-6">
        <div className="flex min-w-0 flex-col gap-1.5">
          <h1 className="break-words text-2xl font-semibold text-ground-900">{data.name || '—'}</h1>
          <p className="break-words text-sm text-ground-600">{[data.course, data.institution].filter(Boolean).join(' · ') || '—'}</p>
          <span className="break-words text-sm text-ground-700" data-testid="my-student-contact">
            {[data.email, data.phone].filter(Boolean).join(' · ')}
          </span>
          <span className="text-sm text-ground-600">{t(`${K}.since`, { date: formatDate(data.since) })}</span>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          {data.email && <a href={`mailto:${data.email}`} className={SECONDARY}>{t(`${K}.email`)}</a>}
          {data.phone && <a href={telHref(data.phone)} className={SECONDARY}>{t(`${K}.call`)}</a>}
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <section aria-label={t(`${K}.latest`)} className="flex flex-col gap-2 rounded-xl border border-ground-200 bg-ground-0 p-4 md:p-5">
          <span className="text-xs font-semibold uppercase tracking-wide text-ground-600">{t(`${K}.latest`)}</span>
          <ResultChip t={t} result={data.latest_result} standing={data.standing} />
          {data.latest_result?.semester && (
            <span className="text-sm text-ground-600">{t(`${K}.term`, { term: data.latest_result.semester, org })}</span>
          )}
        </section>
        <section aria-label={t(`${K}.askedTitle`)} className="flex flex-col gap-2 rounded-xl border border-ground-200 bg-ground-0 p-4 md:p-5">
          <span className="text-xs font-semibold uppercase tracking-wide text-ground-600">{t(`${K}.askedTitle`)}</span>
          <span className="text-sm text-ground-900">{help || t(`${K}.askedNothing`)}</span>
          <span className="text-xs text-ground-600">{t(`${K}.notShown`)}</span>
        </section>
      </div>

      <section aria-label={t(`${K}.meetingsTitle`)} className="flex flex-col rounded-xl border border-ground-200 bg-ground-0"
        data-testid="my-student-meetings">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ground-200 px-4 py-3 md:px-5">
          <h2 className="text-base font-semibold text-ground-900">{t(`${K}.meetingsTitle`)}</h2>
          <button type="button" className={PRIMARY} onClick={() => { setBanner(''); setLogging(true) }}
            data-testid="my-student-log">
            {t(`${K}.log`)}
          </button>
        </div>
        {data.meetings.length === 0 && <p className="px-4 py-4 text-sm text-ground-600 md:px-5">{t(`${K}.noMeetingsYet`)}</p>}
        {data.meetings.map((m) => (
          <article key={m.id} className="flex flex-col gap-1 border-b border-ground-100 px-4 py-4 last:border-b-0 md:px-5"
            data-testid={`my-meeting-${m.id}`}>
            <strong className="text-sm text-ground-900">
              {[formatDate(m.met_on), t(`admin.scholars.mentoring.mode.${m.mode}`),
                m.by_you && m.minutes ? t('admin.scholars.mentoring.meetings.minutesShort', { count: String(m.minutes) }) : '']
                .filter(Boolean).join(' · ')}
            </strong>
            <span className="text-xs text-ground-600">
              {m.by_you ? t(`${K}.byYou`) : t(`${K}.byTeam`, { org })}
            </span>
            {m.by_you && m.notes && <p className="whitespace-pre-line break-words text-sm text-ground-700">{m.notes}</p>}
            {m.by_you && m.next_step && (
              <p className="break-words text-sm text-ground-700">
                {t('admin.scholars.mentoring.meetings.nextStepLine', { step: m.next_step })}
              </p>
            )}
            {m.by_you && m.concern && (
              <span className="self-start rounded-full bg-critical-50 px-2.5 py-0.5 text-xs font-medium text-critical-700">
                {t(`${K}.toldTeam`)}
              </span>
            )}
          </article>
        ))}
        <p className="border-t border-ground-100 px-4 py-3 text-xs text-ground-600 md:px-5">{t(`${K}.meetingsNote`)}</p>
      </section>

      {/* S10: their development modules — read-only (the server's allowlist, `development_progress.mentor_rows`). */}
      {(data.modules?.length ?? 0) > 0 && (
        <section aria-label={t('admin.scholars.growth.title')} data-testid="my-student-growth"
          className="flex flex-col rounded-xl border border-ground-200 bg-ground-0 px-4 py-3 md:px-5">
          <h2 className="text-base font-semibold text-ground-900">{t('admin.scholars.growth.title')}</h2>
          <GrowthWork rows={data.modules ?? []} t={t}
            openFile={(r) => { if (r.task_file?.url) window.open(r.task_file.url, '_blank', 'noopener') }} />
          <p className="text-xs text-ground-600">{t('admin.scholars.growth.mentorNote')}</p>
        </section>
      )}

      {logging && (
        <LogMeetingSheet open studentId={data.id} studentName={data.name} organisation={data.organisation}
          token={token} onClose={() => setLogging(false)}
          onSaved={(page, concern) => {
            setLogging(false)
            if (page) { setData(page); setBanner(t(concern ? `${K}.savedConcern` : `${K}.saved`)) } else load()
          }} />
      )}
    </div>
  )
}

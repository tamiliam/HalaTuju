'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { getMyStudents, type MyStudentCard, type MyStudents as Payload } from '@/lib/admin-api'
import LogMeetingSheet from './LogMeetingSheet'
import { PRIMARY, ResultChip, SECONDARY, helpWords, telHref } from './mentorBits'

const K = 'admin.myStudents'

/**
 * My students — a MENTOR's landing page (student maintenance S7c; the approved MentorStudents and
 * MentorPhone boards). One card per CURRENT student: name, programme and institution, the latest result
 * with its standing, what they asked for help with, since when and the meetings. "Log a meeting" opens
 * the shared Sheet; "Call" dials on a phone. The server serves only this mentor's current students.
 */
export default function MyStudents() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [failed, setFailed] = useState(false)
  const [logging, setLogging] = useState<MyStudentCard | null>(null)
  const [banner, setBanner] = useState('')

  const load = useCallback(() => {
    if (!token) return
    getMyStudents({ token }).then((d) => { setData(d); setFailed(false) }).catch(() => setFailed(true))
  }, [token])
  useEffect(() => { load() }, [load])

  const org = data?.organisation || t(`${K}.theOrganisation`)

  return (
    <div className="flex max-w-4xl flex-col gap-5" data-testid="my-students">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold text-ground-900">{t(`${K}.title`)}</h1>
        <p className="text-sm text-ground-600">{t(`${K}.subtitle`, { org })}</p>
      </header>
      {banner && <p role="status" className="rounded-lg border border-positive-200 bg-positive-50 p-3 text-sm text-positive-800">{banner}</p>}
      {failed && <p role="alert" className="text-sm text-critical-600">{t(`${K}.loadFailed`)}</p>}
      {!data && !failed && <p className="text-sm text-ground-500">{t('common.loading')}</p>}

      {data && data.students.length === 0 && (
        <section className="flex flex-col gap-1 rounded-xl border border-dashed border-ground-300 bg-ground-0 p-5"
          data-testid="my-students-empty">
          <strong className="text-base text-ground-900">{t(`${K}.emptyTitle`)}</strong>
          <span className="text-sm text-ground-600">{t(`${K}.emptyBody`, { org })}</span>
        </section>
      )}

      {data && data.students.length > 0 && (
        <section aria-label={t(`${K}.title`)} className="flex flex-col gap-3">
          {data.students.map((s) => {
            const help = helpWords(t, s.asked_for_help)
            return (
              <article key={s.id} data-testid={`my-student-${s.id}`}
                className="flex flex-col gap-3 rounded-xl border border-ground-200 bg-ground-0 p-4 md:flex-row md:justify-between md:p-5">
                <div className="flex min-w-0 flex-col gap-1.5">
                  <Link href={`/admin/my-students/${s.id}`}
                    className="-my-2.5 inline-flex min-h-11 items-center self-start break-words py-2.5 text-base font-semibold text-primary-600 hover:underline">
                    {s.name || '—'}
                  </Link>
                  <span className="break-words text-sm text-ground-700">
                    {[s.course, s.institution].filter(Boolean).join(' · ') || '—'}
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    <ResultChip t={t} result={s.latest_result} standing={s.standing} />
                    {help && (
                      <span className="rounded-full bg-caution-50 px-2.5 py-0.5 text-xs font-medium text-caution-800">{help}</span>
                    )}
                  </div>
                  <span className="text-sm text-ground-600">
                    {[t(`${K}.since`, { date: formatDate(s.since) }),
                      s.meetings ? t(`${K}.meetings`, { count: String(s.meetings) }) : t(`${K}.noMeetings`),
                      s.last_meeting ? t(`${K}.last`, { date: formatDate(s.last_meeting) }) : '']
                      .filter(Boolean).join(' · ')}
                  </span>
                </div>
                <div className="flex flex-wrap items-start gap-2">
                  <button type="button" className={`${PRIMARY} flex-1 md:flex-none`} data-testid={`log-meeting-${s.id}`}
                    onClick={() => { setBanner(''); setLogging(s) }}>
                    {t(`${K}.log`)}
                  </button>
                  {s.phone && <a href={telHref(s.phone)} className={`${SECONDARY} md:hidden`}>{t(`${K}.call`)}</a>}
                  <Link href={`/admin/my-students/${s.id}`} className={`${SECONDARY} hidden md:inline-flex`}>{t(`${K}.open`)}</Link>
                </div>
              </article>
            )
          })}
        </section>
      )}

      <p className="text-xs text-ground-600">{t(`${K}.footnote`)}</p>

      {logging && (
        <LogMeetingSheet open studentId={logging.id} studentName={logging.name} organisation={data?.organisation ?? ''}
          token={token} onClose={() => setLogging(null)}
          onSaved={(_page, concern) => {
            setLogging(null)
            setBanner(t(concern ? `${K}.savedConcern` : `${K}.saved`))
            load()
          }} />
      )}
    </div>
  )
}

'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { getScholarSurveys, type AnswerValue, type QuestionKind, type ScholarSurveys as Payload } from '@/lib/admin-api'

const K = 'admin.scholars.surveys'
const CARD = 'rounded-xl border border-ground-200 bg-ground-0 p-5'

type T = (k: string, vars?: Record<string, string>) => string

function valueText(t: T, kind: QuestionKind, v: AnswerValue): string {
  if (kind === 'yes_no') return t(v ? 'admin.surveys.yes' : 'admin.surveys.no')
  if (Array.isArray(v)) return v.join(', ')
  return String(v)
}

/**
 * The scholar file's **Surveys** tab (student maintenance S9): each survey this scholar answered, with their
 * answers against the questions, and the open ones still waiting for them. Read-only.
 *
 * ⚠ THE SERVER'S FENCE: the file's own (`_file_for`) AND the survey makers' roles (super, org_admin, admin);
 * the page draws the tab only for them. Its own chunk, fetched the first time the tab is opened.
 */
export default function ScholarSurveys({ id, token }: { id: number; token: string | null }) {
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!token) return
    let live = true
    getScholarSurveys(id, { token })
      .then((d) => { if (live) { setData(d); setFailed(false) } })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [id, token])

  if (failed) return <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadError`)}</p>
  if (!data) return <p className="text-sm text-ground-500">{t('common.loading')}</p>

  return (
    <div className="space-y-4" data-testid="scholar-surveys">
      {data.waiting.length > 0 && (
        <p className="text-sm text-ground-700" data-testid="scholar-surveys-waiting">
          {t(`${K}.waiting`, { list: data.waiting.map((w) => `${w.title} (${formatDate(w.closes_at)})`).join(', ') })}
        </p>
      )}
      {data.answered.length === 0 ? (
        <p className={`${CARD} text-sm text-ground-600`} data-testid="scholar-surveys-none">{t(`${K}.none`)}</p>
      ) : data.answered.map((s) => (
        <article key={s.id} className={`${CARD} space-y-3`} data-testid={`scholar-survey-${s.id}`}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <Link href={`/admin/programme/surveys/${s.id}`} className="break-words font-semibold text-primary-600 hover:underline">
              {s.title}
            </Link>
            <span className="text-xs text-ground-600">
              {t(`${K}.sent`, { date: formatDate(s.updated_at) })} · {t(`admin.surveys.tab.${s.status}`)}
            </span>
          </div>
          <dl className="space-y-2">
            {s.answers.map((a) => (
              <div key={a.question_id}>
                <dt className="break-words text-xs text-ground-600">{a.text}</dt>
                <dd className="whitespace-pre-line break-words text-sm text-ground-900">{valueText(t, a.kind, a.value)}</dd>
              </div>
            ))}
          </dl>
        </article>
      ))}
    </div>
  )
}

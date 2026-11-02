'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
// The hook from the LEAF (no Supabase client in this chunk) — see `lib/adminAuthCore.ts`.
import { useAdminAuth } from '@/lib/adminAuthCore'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { isSuperRole } from '@/lib/superRole'
import {
  fetchSurveyCsv, getSurveyResults, remindSurvey,
  type AnswerValue, type SurveyQuestionRow, type SurveyResults as Payload, type SurveySummaryItem, type SurveyWho,
} from '@/lib/admin-api'
import PanelTabs from '@/components/admin/PanelTabs'
import { MAKER_ROLES, audienceLabel, giftHref } from './shared'

const K = 'admin.surveys.results'
const CARD = 'max-w-3xl space-y-3 rounded-xl border border-ground-200 bg-ground-0 p-5'
const LINK = 'text-primary-600 hover:underline'
const BTN = 'min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-sm text-ground-800 disabled:opacity-60'
/** How many written answers a question shows before "Show all". */
const SHOW = 5

type T = (k: string, vars?: Record<string, string>) => string
type View = 'summary' | 'each' | 'pending'

/** The value as staff read it. */
export function valueText(t: T, q: SurveyQuestionRow | undefined, v: AnswerValue | undefined): string {
  if (v === undefined || v === null || v === '') return '—'
  if (q?.kind === 'yes_no') return t(v ? 'admin.surveys.yes' : 'admin.surveys.no')
  if (Array.isArray(v)) return v.join(', ')
  return String(v)
}

function Who({ who }: { who: SurveyWho[] }) {
  return (
    <span className="flex flex-wrap gap-x-3">
      {who.map((w) => (
        <Link key={w.application_id} href={`/admin/scholars/${w.application_id}`} className={LINK}>{w.name || '—'}</Link>
      ))}
    </span>
  )
}

function OptionBars({ item, q, t }: { item: SurveySummaryItem; q: SurveyQuestionRow; t: T }) {
  const [open, setOpen] = useState<string | null>(null)
  const max = Math.max(1, ...(item.options ?? []).map((o) => o.count))
  return (
    <div className="space-y-2">
      {(item.options ?? []).map((o) => {
        const key = String(o.option)
        const label = q.kind === 'yes_no' ? t(o.option ? 'admin.surveys.yes' : 'admin.surveys.no') : key
        return (
          <div key={key} data-testid={`bar-${q.id}-${key}`}>
            <div className="grid grid-cols-[minmax(0,8rem)_1fr_auto] items-center gap-3 text-sm">
              <span className="break-words text-ground-800">{label}</span>
              <span className="h-3.5 rounded bg-ground-100">
                <span className="block h-3.5 rounded bg-brand-shape" style={{ width: `${(o.count / max) * 100}%` }} />
              </span>
              <span className="tabular-nums text-ground-800">
                {o.count}
                {o.count > 0 && (
                  <button type="button" onClick={() => setOpen(open === key ? null : key)}
                    className="-my-3 ml-2 inline-flex min-h-11 items-center text-primary-600 hover:underline"
                    data-testid={`who-${q.id}-${key}`} aria-expanded={open === key}>{t(`${K}.who`)}</button>
                )}
              </span>
            </div>
            {open === key && <div className="mt-1 pl-1 text-sm"><Who who={o.who} /></div>}
          </div>
        )
      })}
    </div>
  )
}

function Written({ item, t }: { item: SurveySummaryItem; t: T }) {
  const [all, setAll] = useState(false)
  const list = item.written ?? []
  const shown = all ? list : list.slice(0, SHOW)
  if (list.length === 0) return <p className="text-sm text-ground-500">{t(`${K}.noneYet`)}</p>
  return (
    <div className="space-y-2">
      {shown.map((w) => (
        <p key={w.application_id} className="whitespace-pre-line break-words text-sm text-ground-800">
          “{w.text}” — <Link href={`/admin/scholars/${w.application_id}`} className={LINK}>{w.name || '—'}</Link>
        </p>
      ))}
      {list.length > SHOW && !all && (
        <button type="button" onClick={() => setAll(true)} className="inline-flex min-h-11 items-center text-sm text-primary-600 hover:underline">
          {t(`${K}.showAll`, { count: String(list.length) })}
        </button>
      )}
    </div>
  )
}

/**
 * A survey's Results (student maintenance S9; the SurveyResults board): Summary (per question — counts and
 * bars with who chose each, the average for a rating, the written answers with names), Each scholar (one
 * row per response), Not answered (with "Remind those who have not answered"), and Download CSV.
 *
 * ⚠ STAFF ONLY, THE SERVER'S FENCE: the same roles and organisation as the Surveys page; another
 * organisation's survey is 404 here and on the CSV. Names link to the scholar's file, whose Surveys tab
 * shows the same answers. The Remind button is the job's own reminder, once per scholar (never twice).
 */
export default function SurveyResults({ id, programme }: { id: number; programme?: string }) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = isSuperRole(role) ? 'super' : (role?.role ?? '')
  const allowed = MAKER_ROLES.includes(r)
  const [data, setData] = useState<Payload | null>(null)
  const [failed, setFailed] = useState(false)
  const [view, setView] = useState<View>('summary')
  const [busy, setBusy] = useState(false)
  const [banner, setBanner] = useState<{ ok: boolean; text: string } | null>(null)

  const load = useCallback(async () => {
    if (!token || !allowed || !Number.isFinite(id)) return
    try { setData(await getSurveyResults(id, { token })); setFailed(false) } catch { setFailed(true) }
  }, [token, allowed, id])
  useEffect(() => { void load() }, [load])

  if (role && !allowed) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  if (failed) return <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadError`)}</p>
  if (!data) return <p className="text-sm text-ground-500">{t('common.loading')}</p>

  const s = data.survey
  const byId = new Map(s.questions.map((q) => [q.id, q]))
  const pct = s.audience_count ? Math.round((s.answered_count / s.audience_count) * 100) : 0

  const remind = async () => {
    if (!token || !window.confirm(t(`${K}.confirmRemind`, { count: String(data.not_answered.length) }))) return
    setBusy(true); setBanner(null)
    try {
      const out = await remindSurvey(s.id, { token })
      setData({ ...data, ...out })
      setBanner({ ok: true, text: t(`${K}.reminded`, { count: String(out.sent) }) })
    } catch {
      setBanner({ ok: false, text: t(`${K}.remindFailed`) })
    } finally { setBusy(false) }
  }

  const download = async () => {
    if (!token) return
    try {
      const text = await fetchSurveyCsv(s.id, { token })
      const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `survey-${s.id}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      setBanner({ ok: false, text: t(`${K}.csvFailed`) })
    }
  }

  const remindButton = data.can_remind && (
    <button type="button" disabled={busy} onClick={remind} className={BTN} data-testid="survey-remind">{t(`${K}.remind`)}</button>
  )

  return (
    <div className="space-y-5" data-testid="survey-results">
      <Link href={giftHref('/admin/programme/surveys', programme)} className="text-sm text-primary-600 hover:underline">
        ← {t('admin.surveys.title')}
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-semibold text-ground-900">{t(`${K}.title`, { title: s.title })}</h1>
          <p className="text-sm text-ground-600" data-testid="survey-results-sub">
            {[audienceLabel(t, s), t(`${K}.dates`, { from: formatDate(s.opens_at), to: formatDate(s.closes_at) }),
              t(`${K}.answered`, { n: String(s.answered_count), count: String(s.audience_count), pct: String(pct) })]
              .join(' · ')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={download} className={BTN} data-testid="survey-csv">{t(`${K}.csv`)}</button>
          {remindButton}
        </div>
      </div>
      {banner && (
        <p role={banner.ok ? 'status' : 'alert'}
          className={`rounded-lg border p-3 text-sm ${banner.ok ? 'border-positive-200 bg-positive-50 text-positive-800'
            : 'border-caution-200 bg-caution-50 text-caution-900'}`}>{banner.text}</p>
      )}

      <PanelTabs ariaLabelKey={`${K}.tabsAria`} active={view} onSelect={setView} tabs={[
        { key: 'summary', labelKey: `${K}.tab.summary` },
        { key: 'each', labelKey: `${K}.tab.each`, count: data.responses.length },
        { key: 'pending', labelKey: `${K}.tab.pending`, count: data.not_answered.length },
      ]} />

      {view === 'summary' && data.summary.map((item, i) => {
        const q = byId.get(item.question_id)
        if (!q) return null
        return (
          <section key={q.id} className={CARD} data-testid={`summary-${q.id}`}>
            <h2 className="break-words font-semibold text-ground-900">{i + 1}. {q.text}</h2>
            <p className="text-xs text-ground-600">
              {t(`${K}.answersCount`, { count: String(item.answered) })}
              {q.mentor_only ? ` · ${t('admin.surveys.form.mentorOnlyShort')}` : ''}
            </p>
            {q.kind === 'rating' && (
              <p className="text-sm text-ground-800" data-testid={`average-${q.id}`}>
                {item.average == null ? t(`${K}.noneYet`) : t(`${K}.average`, { avg: String(item.average) })}
              </p>
            )}
            {item.options && <OptionBars item={item} q={q} t={t} />}
            {item.written && <Written item={item} t={t} />}
          </section>
        )
      })}

      {view === 'each' && (
        data.responses.length === 0 ? <p className="text-sm text-ground-500">{t(`${K}.noneYet`)}</p> : (
          <div className="max-w-3xl space-y-3">
            {data.responses.map((resp) => (
              <article key={resp.application_id} className={CARD} data-testid={`response-${resp.application_id}`}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <Link href={`/admin/scholars/${resp.application_id}`} className={`${LINK} font-medium`}>{resp.name || '—'}</Link>
                  <span className="text-xs text-ground-600">{t(`${K}.sent`, { date: formatDate(resp.updated_at) })}</span>
                </div>
                <dl className="space-y-2">
                  {s.questions.filter((q) => resp.answers[String(q.id)] !== undefined).map((q) => (
                    <div key={q.id}>
                      <dt className="break-words text-xs text-ground-600">{q.text}</dt>
                      <dd className="whitespace-pre-line break-words text-sm text-ground-900">
                        {valueText(t, q, resp.answers[String(q.id)])}
                      </dd>
                    </div>
                  ))}
                </dl>
              </article>
            ))}
          </div>
        )
      )}

      {view === 'pending' && (
        <div className="max-w-3xl space-y-3">
          {data.not_answered.length === 0 ? <p className="text-sm text-ground-500">{t(`${K}.everyone`)}</p> : (
            <ul className={`${CARD} divide-y divide-ground-100 space-y-0 p-0`}>
              {data.not_answered.map((p) => (
                <li key={p.application_id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3 text-sm"
                  data-testid={`pending-${p.application_id}`}>
                  <Link href={`/admin/scholars/${p.application_id}`} className={LINK}>{p.name || '—'}</Link>
                  {p.reminded && <span className="text-xs text-ground-600">{t(`${K}.remindedOne`)}</span>}
                </li>
              ))}
            </ul>
          )}
          {remindButton}
        </div>
      )}
      <p className="max-w-3xl text-xs text-ground-600">{t(`${K}.footnote`)}</p>
    </div>
  )
}

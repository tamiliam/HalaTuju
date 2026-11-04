'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
// The hook from the LEAF (no Supabase client in this chunk) — see `lib/adminAuthCore.ts`.
import { useAdminAuth } from '@/lib/adminAuthCore'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { opensDoorOr } from '@/lib/pageGuard'
import {
  fetchModuleCsv, getModuleProgress, remindModule, reviewTask, taskFileLink,
  type ModuleProgress, type ProgressBucket, type ProgressRow,
} from '@/lib/admin-api/development'
import PanelTabs from '@/components/admin/PanelTabs'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import { MAKER_ROLES, audienceLabel, giftHref, openSigned } from './shared'

const K = 'admin.development.progress'
const BTN = 'min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-sm text-ground-800 disabled:opacity-60'
const LINK = 'inline-flex min-h-11 items-center text-primary-600 hover:underline'
const TABS: readonly ProgressBucket[] = ['to_review', 'done', 'in_progress', 'not_started']

type T = (k: string, vars?: Record<string, string>) => string

function Review({ moduleId, row, token, t, onSaved }: {
  moduleId: number; row: ProgressRow; token: string | null; t: T; onSaved: (p: Omit<ModuleProgress, 'module'>) => void
}) {
  const [comment, setComment] = useState(row.review_comment)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const save = async () => {
    if (!token) return
    setBusy(true); setError('')
    try { onSaved(await reviewTask(moduleId, row.application_id, comment.trim(), { token })) }
    catch { setError(t(`${K}.reviewFailed`)) } finally { setBusy(false) }
  }
  return (
    <section className="max-w-3xl space-y-3 rounded-xl border-2 border-info-500 bg-ground-0 p-5" data-testid={`review-${row.application_id}`}>
      <strong className="break-words text-ground-900">
        {t(row.task_file ? `${K}.upload` : `${K}.reflection`, { name: row.name || '—' })}
      </strong>
      {row.task_text && <p className="whitespace-pre-line break-words text-sm leading-relaxed text-ground-800">{row.task_text}</p>}
      {row.task_file && (
        <button type="button" className={`${LINK} text-sm`} data-testid="review-file"
          onClick={() => openSigned(() => taskFileLink(moduleId, row.application_id, { token: token ?? undefined }), () => setError(t(`${K}.reviewFailed`)))}>
          {t(`${K}.openFile`, { name: row.task_file.name })}
        </button>
      )}
      {row.reviewed_at && (
        <p className="text-xs text-ground-600">{t(`${K}.reviewedOn`, { date: formatDate(row.reviewed_at), who: row.reviewed_by })}</p>
      )}
      <label className="flex flex-col gap-1 text-sm font-medium text-ground-700">{t(`${K}.comment`)}
        <textarea value={comment} maxLength={1000} rows={3} onChange={(e) => setComment(e.target.value)} data-testid="review-comment"
          className="w-full rounded-lg border border-ground-300 bg-ground-0 px-3 py-2 text-ground-900" />
      </label>
      {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      <button type="button" disabled={busy} onClick={save} data-testid="review-save"
        className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink disabled:opacity-60">
        {t(row.reviewed_at ? `${K}.updateReview` : `${K}.markReviewed`)}
      </button>
    </section>
  )
}

/**
 * One module's **Progress** (student maintenance S10; the ModuleProgress board): To review / Done / In progress /
 * Not started, per scholar — lessons read x of y, the task's date, the mentor, "Late" after the due date when not
 * done; read a reflection or open an upload (a short signed link), comment and "Mark reviewed" (the scholar sees
 * the comment); "Remind those not done" (the job's own reminder, once per scholar) and the CSV.
 *
 * ⚠ STAFF ONLY, THE SERVER'S FENCE: another organisation's module is 404 here, on the CSV and on every file.
 */
export default function ModuleProgressView({ id, programme }: { id: number; programme?: string }) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = opensDoorOr(role, 'development', MAKER_ROLES)   // T5c P4: the server's door
  const [data, setData] = useState<ModuleProgress | null>(null)
  const [failed, setFailed] = useState(false)
  const [tab, setTab] = useState<ProgressBucket>('to_review')
  const [reading, setReading] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [banner, setBanner] = useState<{ ok: boolean; text: string } | null>(null)

  const load = useCallback(async () => {
    if (!token || !allowed || !Number.isFinite(id)) return
    try { setData(await getModuleProgress(id, { token })); setFailed(false) } catch { setFailed(true) }
  }, [token, allowed, id])
  useEffect(() => { void load() }, [load])

  if (role && !allowed) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>
  if (failed) return <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadError`)}</p>
  if (!data) return <p className="text-sm text-ground-500">{t('common.loading')}</p>

  const m = data.module
  const done = data.counts.done
  const total = m.audience_count || data.rows.length
  const pct = total ? Math.round((done / total) * 100) : 0
  const rows = data.rows.filter((x) => (tab === 'to_review' ? x.to_review : x.bucket === tab))
  const open = data.rows.find((x) => x.application_id === reading)

  const remind = async () => {
    if (!token || !window.confirm(t(`${K}.confirmRemind`))) return
    setBusy(true); setBanner(null)
    try {
      const out = await remindModule(m.id, { token })
      setData({ ...data, ...out })
      setBanner({ ok: true, text: t(`${K}.reminded`, { count: String(out.sent) }) })
    } catch { setBanner({ ok: false, text: t(`${K}.remindFailed`) }) } finally { setBusy(false) }
  }

  const download = async () => {
    if (!token) return
    try {
      const text = await fetchModuleCsv(m.id, { token })
      const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `module-${m.id}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch { setBanner({ ok: false, text: t(`${K}.csvFailed`) }) }
  }

  // With the organisation's module email switched off, the button is not offered (the server refuses it, 409
  // switched_off, and writes nothing) — a short reason stands in its place.
  const remindButton = data.email_switch_on === false ? (
    data.can_remind && <p className="text-xs text-ground-600" data-testid="module-remind-off">{t(`${K}.remindOff`)}</p>
  ) : data.can_remind && (
    <button type="button" disabled={busy} onClick={remind} className={BTN} data-testid="module-remind">{t(`${K}.remind`)}</button>
  )

  return (
    <div className="space-y-5" data-testid="module-progress">
      <Link href={giftHref('/admin/programme/development', programme)} className={`${LINK} text-sm`}>← {t(`${K}.back`)}</Link>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-semibold text-ground-900">{t(`${K}.title`, { title: m.title })}</h1>
          <p className="text-sm text-ground-600" data-testid="module-progress-sub">
            {[audienceLabel(t, m), m.due_on ? t(`${K}.due`, { date: formatDate(m.due_on) }) : '',
              t(`${K}.doneOf`, { n: String(done), count: String(total), pct: String(pct) }),
              data.counts.to_review ? t(`${K}.toReview`, { count: String(data.counts.to_review) }) : '']
              .filter(Boolean).join(' · ')}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={download} className={BTN} data-testid="module-csv">{t(`${K}.csv`)}</button>
          {remindButton}
        </div>
      </div>
      {banner && (
        <p role={banner.ok ? 'status' : 'alert'}
          className={`rounded-lg border p-3 text-sm ${banner.ok ? 'border-positive-200 bg-positive-50 text-positive-800'
            : 'border-caution-200 bg-caution-50 text-caution-900'}`}>{banner.text}</p>
      )}

      <PanelTabs ariaLabelKey={`${K}.tabsAria`} active={tab} onSelect={(k) => { setTab(k); setReading(null) }}
        tabs={TABS.map((k) => ({ key: k, labelKey: `${K}.tab.${k}`, count: data.counts[k] ?? 0 }))} />
      {rows.length === 0 ? (
        <p className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500" data-testid="progress-empty">
          {t(`${K}.empty`)}</p>
      ) : (
        <TableFrame minWidth={720} label={t(`${K}.title`, { title: m.title })} phoneRows>
          <table className="w-full text-sm">
            <thead className="border-b bg-ground-50">
              <tr>
                {['scholar', 'lessons', 'task', 'mentor'].map((c) => <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>)}
                <th className={TH}><span className="sr-only">{t(`${K}.col.actions`)}</span></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((x) => (
                <tr key={x.application_id} data-testid={`progress-row-${x.application_id}`}>
                  <td className="px-4 py-3">
                    <Link href={`/admin/scholars/${x.application_id}`} className="text-primary-600 hover:underline">{x.name || '—'}</Link>
                    {x.late && <span className="ml-2 text-xs font-semibold text-critical-700" data-testid={`late-${x.application_id}`}>{t(`${K}.late`)}</span>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3" data-label={t(`${K}.col.lessons`)}>{t(`${K}.lessonsOf`, { read: String(x.read), count: String(x.lessons) })}</td>
                  <td className="whitespace-nowrap px-4 py-3" data-label={t(`${K}.col.task`)}>{x.task_sent_at ? t(`${K}.sentOn`, { date: formatDate(x.task_sent_at) }) : '—'}</td>
                  <td className="px-4 py-3" data-label={t(`${K}.col.mentor`)}>{x.mentor || '—'}</td>
                  <td className="whitespace-nowrap px-4 py-3">
                    {x.task_sent_at && (
                      <button type="button" className={LINK} data-testid={`read-${x.application_id}`}
                        onClick={() => setReading(reading === x.application_id ? null : x.application_id)}>
                        {t(reading === x.application_id ? `${K}.close` : `${K}.read`)}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableFrame>
      )}
      {open && (
        <Review key={open.application_id} moduleId={m.id} row={open} token={token} t={t}
          onSaved={(next) => { setData({ ...data, ...next }); setBanner({ ok: true, text: t(`${K}.saved`) }) }} />
      )}
      <p className="max-w-3xl text-xs text-ground-600">{t(`${K}.footnote`)}</p>
    </div>
  )
}

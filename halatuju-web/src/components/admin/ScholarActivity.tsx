'use client'

import { useCallback, useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import Toggle from '@/components/Toggle'
import { useToast } from '@/components/ToastContext'
import { formatDateTime } from '@/lib/formatDate'
import { activityDot, activityText } from '@/lib/scholars'
import {
  addScholarActivity, getScholarActivity, type ScholarActivity as Entry,
} from '@/lib/admin-api'

const KINDS = ['note', 'call', 'meeting'] as const
type Kind = (typeof KINDS)[number]

/**
 * A scholar's activity log — the timeline and the composer (student maintenance Sprint 2), modelled
 * on the requests thread (`app/admin/requests/[id]`): one stream, newest first, who wrote it and when.
 *
 * ⚠ "Staff only" is the site `Toggle`, never a checkbox (house rule). Nothing in this log reaches a
 * student today — the flag is recorded now so the day a student view of the log exists, the rows an
 * officer meant for colleagues are already marked.
 * ⚠ A system row is a translated sentence from its event code (`lib/scholars.activityText`), never
 * the raw meta, so a payment's run reference reads as a sentence and nothing internal leaks as JSON.
 */
export default function ScholarActivity({ id, token, compact = false }: {
  id: number
  token: string | null
  /** The Overview's side panel shows the newest few; the Activity tab shows them all. */
  compact?: boolean
}) {
  const { t } = useT()
  const { showToast } = useToast()
  const [rows, setRows] = useState<Entry[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [kind, setKind] = useState<Kind>('note')
  const [body, setBody] = useState('')
  const [internal, setInternal] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!token) return
    getScholarActivity(id, { token })
      .then((p) => { setRows(p.results); setFailed(false) })
      .catch(() => setFailed(true))
  }, [id, token])
  useEffect(() => { load() }, [load])

  async function save() {
    if (!token || !body.trim()) return
    setBusy(true)
    try {
      await addScholarActivity(id, { kind, body, internal }, { token })
      setBody(''); setInternal(false)
      showToast(t('admin.scholars.activity.saved'), 'success')
      load()
    } catch {
      showToast(t('admin.scholars.activity.saveFailed'), 'error')
    } finally { setBusy(false) }
  }

  const shown = compact ? (rows ?? []).slice(0, 6) : (rows ?? [])
  return (
    <section aria-label={t('admin.scholars.activity.title')}
      className="rounded-xl border border-ground-200 bg-ground-0 p-5">
      <h2 className="mb-3 text-base font-semibold text-ground-900">{t('admin.scholars.activity.title')}</h2>

      <div className="space-y-2">
        <div role="group" aria-label={t('admin.scholars.activity.kindLabel')} className="flex flex-wrap gap-1.5">
          {KINDS.map((k) => (
            <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${kind === k
                ? 'border-info-600 bg-info-50 text-info-700'
                : 'border-ground-300 bg-ground-0 text-ground-700 hover:bg-ground-50'}`}>
              {t(`admin.scholars.activity.kind.${k}`)}
            </button>
          ))}
        </div>
        <label className="block text-xs text-ground-600">
          {t('admin.scholars.activity.addLabel')}
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3}
            placeholder={t('admin.scholars.activity.placeholder')}
            className="mt-1 w-full rounded-lg border border-ground-300 px-3 py-2 text-sm focus:ring-2 focus:ring-info-500" />
        </label>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="flex items-center gap-2 text-sm text-ground-700">
            <Toggle on={internal} onChange={setInternal} label={t('admin.scholars.activity.staffOnly')} />
            {t('admin.scholars.activity.staffOnly')}
          </span>
          <button type="button" disabled={busy || !body.trim()} onClick={save}
            className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
            {busy ? t('admin.saving') : t('admin.scholars.activity.save')}
          </button>
        </div>
      </div>

      {failed && <p className="mt-4 text-sm text-critical-600">{t('admin.scholars.activity.loadFailed')}</p>}
      {rows !== null && rows.length === 0 && (
        <p className="mt-4 text-sm text-ground-400" data-testid="activity-empty">
          {t('admin.scholars.activity.empty')}
        </p>
      )}
      <ol className="mt-3">
        {shown.map((a) => (
          <li key={a.id} className="flex gap-2.5 border-t border-ground-100 py-2.5" data-testid="activity-row">
            <span aria-hidden className={`mt-1.5 h-2 w-2 flex-none rounded-full ${activityDot(a)}`} />
            <div className="min-w-0">
              <p className="whitespace-pre-wrap text-sm text-ground-900">{activityText(a, t)}</p>
              <p className="mt-0.5 text-xs text-ground-500">
                {t(`admin.scholars.activity.kind.${a.kind}`)}
                {' · '}{a.actor_email || t('admin.scholars.activity.bySystem')}
                {' · '}{formatDateTime(a.created_at)}
                {a.internal && a.kind !== 'system' && (
                  <span className="ml-2 rounded-full bg-caution-100 px-1.5 py-0.5 text-[10px] font-medium text-caution-800">
                    {t('admin.scholars.activity.staffOnly')}
                  </span>
                )}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

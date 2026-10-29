'use client'

import { useCallback, useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import DocViewer, { type ViewerDoc } from '@/components/DocViewer'
import { useToast } from '@/components/ToastContext'
import { formatDate } from '@/lib/formatDate'
import { REVIEW_TONE } from '@/lib/scholars'
import { getScholarResults, reviewScholarResult, type ScholarResultRow } from '@/lib/admin-api'

/**
 * The scholar file's Results tab (student maintenance S4a): every result she recorded, newest first,
 * with her slip (in the shared `DocViewer`) and the officer's review — Accept, or Query with a note
 * she will see. Only an ACCEPTED result counts for her standing and for anything a sponsor reads.
 *
 * ⚠ The buttons are an offer (`canReview`, the server's `controls.can_review_results`); the review
 * endpoint judges every request again (`_can_review_app`). Re-reviewing is allowed — a queried
 * result she has explained may be accepted.
 */
export default function ScholarResults({ id, token, canReview, onChanged }: {
  id: number
  token: string | null
  canReview: boolean
  /** A review moves her standing and the activity log — the file re-reads. */
  onChanged: () => void
}) {
  const { t } = useT()
  const { showToast } = useToast()
  const [rows, setRows] = useState<ScholarResultRow[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [viewing, setViewing] = useState<ViewerDoc | null>(null)
  const [querying, setQuerying] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(0)

  const load = useCallback(() => {
    if (!token) return
    getScholarResults(id, { token })
      .then((r) => { setRows(r.results); setFailed(false) })
      .catch(() => setFailed(true))
  }, [id, token])
  useEffect(() => { load() }, [load])

  async function decide(row: ScholarResultRow, decision: 'accepted' | 'queried') {
    if (!token) return
    setBusy(row.id)
    try {
      await reviewScholarResult(id, row.id, { decision, note: decision === 'queried' ? note : '' }, { token })
      setQuerying(null); setNote('')
      showToast(t(`admin.scholars.results.done.${decision}`), 'success')
      load(); onChanged()
    } catch (e) {
      const code = (e as { code?: string })?.code || ''
      showToast(t(['note_required', 'file_closed'].includes(code)
        ? `admin.scholars.results.error.${code}` : 'admin.scholars.results.error.generic'), 'error')
    } finally { setBusy(0) }
  }

  const open = (row: ScholarResultRow) => {
    if (!row.slip?.url) return
    const pdf = row.slip.content_type === 'application/pdf' || row.slip.filename.toLowerCase().endsWith('.pdf')
    setViewing({ label: row.semester || t('admin.scholars.results.slip'), filename: row.slip.filename,
      url: row.slip.url, kind: pdf ? 'pdf' : 'image' })
  }

  return (
    <section aria-label={t('admin.scholars.tab.results')} className="rounded-xl border border-ground-200 bg-ground-0 p-5">
      <h2 className="text-base font-semibold text-ground-900">{t('admin.scholars.tab.results')}</h2>
      <p className="mt-1 text-xs text-ground-500">{t('admin.scholars.results.intro')}</p>
      {failed && <p className="mt-3 text-sm text-critical-600">{t('admin.scholars.results.loadFailed')}</p>}
      {rows !== null && rows.length === 0 && (
        <p className="mt-3 text-sm text-ground-500" data-testid="results-empty">{t('admin.scholars.file.noResult')}</p>
      )}
      <ul className="mt-3 divide-y divide-ground-100">
        {(rows ?? []).map((r) => (
          <li key={r.id} className="py-3" data-testid="admin-result-row">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-medium text-ground-900">
                  {r.semester || '—'} · {r.graduated ? t('admin.scholars.results.graduated')
                    : t('admin.scholars.results.cgpa', { cgpa: r.cgpa ?? '—' })}
                </p>
                <p className="text-xs text-ground-500">
                  {t('admin.scholars.results.submitted', { date: formatDate(r.created_at) })}
                  {r.reviewed_at && ` · ${t('admin.scholars.results.reviewed', {
                    by: r.reviewed_by || '—', date: formatDate(r.reviewed_at) })}`}
                </p>
              </div>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${REVIEW_TONE[r.review_status] ?? REVIEW_TONE.pending}`}>
                {t(`admin.scholars.results.status.${r.review_status}`)}
              </span>
            </div>
            {r.review_note && <p className="mt-1 text-xs text-ground-600">“{r.review_note}”</p>}
            {r.note && <p className="mt-1 text-xs text-ground-500">{t('admin.scholars.results.studentNote', { note: r.note })}</p>}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {r.slip?.url ? (
                <button type="button" onClick={() => open(r)}
                  className="rounded-lg border border-ground-300 px-3 py-1 text-xs font-medium text-primary-600 hover:bg-ground-50">
                  {t('admin.scholars.results.viewSlip')}
                </button>
              ) : <span className="text-xs text-ground-400">{t('admin.scholars.results.noSlip')}</span>}
              {canReview && r.review_status !== 'accepted' && (
                <button type="button" onClick={() => decide(r, 'accepted')} disabled={busy === r.id}
                  className="rounded-lg bg-brand-fill px-3 py-1 text-xs font-medium text-brand-fill-ink disabled:opacity-50">
                  {t('admin.scholars.results.accept')}
                </button>
              )}
              {canReview && querying !== r.id && (
                <button type="button" onClick={() => { setQuerying(r.id); setNote('') }} disabled={busy === r.id}
                  className="rounded-lg border border-caution-300 px-3 py-1 text-xs font-medium text-caution-700 hover:bg-caution-50 disabled:opacity-50">
                  {t('admin.scholars.results.query')}
                </button>
              )}
            </div>
            {canReview && querying === r.id && (
              <div className="mt-2 space-y-2" data-testid="query-box">
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500}
                  placeholder={t('admin.scholars.results.queryPlaceholder')}
                  className="w-full rounded-lg border border-ground-300 px-3 py-2 text-sm" />
                <div className="flex gap-2">
                  <button type="button" onClick={() => decide(r, 'queried')} disabled={busy === r.id || !note.trim()}
                    className="rounded-lg bg-caution-fill px-3 py-1 text-xs font-medium text-caution-fill-ink disabled:opacity-50">
                    {t('admin.scholars.results.sendQuery')}
                  </button>
                  <button type="button" onClick={() => setQuerying(null)}
                    className="rounded-lg px-3 py-1 text-xs text-ground-600">{t('common.cancel')}</button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
      <DocViewer doc={viewing} onClose={() => setViewing(null)} />
    </section>
  )
}

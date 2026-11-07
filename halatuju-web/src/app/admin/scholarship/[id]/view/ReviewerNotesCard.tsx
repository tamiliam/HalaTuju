'use client'

/**
 * NOTES FOR THE REVIEWER (request #55, 2026-11-07), directly under "Reviewer assigned".
 *
 * Two faces, one card (the owner-approved mock-up):
 *   • the WRITER (org admin, super, inside the window): the list, "Add a note", a live counter
 *     ("97 / 2,000"), the append-only line and the Add note button;
 *   • a READER (the assigned reviewer, QC, a view-only admin): the list, read-only, or
 *     "No notes from your org admin."
 *
 * ⚠ SERVE, NEVER DERIVE: whether the box shows is the server's `can_add` (the window AND the role),
 * and the limit is its `max_length`. `isWriter` only picks the wording of the intro and the empty
 * state; it never opens the box. The notes are their OWN fetch (the detail GET stays at 38 queries),
 * re-read when the case's status or verdict stamp moves, because those close the window.
 */
import { useEffect, useState } from 'react'
import { addReviewerNote, getReviewerNotes, type ReviewerNotes } from '@/lib/admin-api'
import { formatDateTime } from '@/lib/formatDate'

import type { T } from './shared'

const CODES = ['writer_only', 'notes_closed', 'empty_body', 'too_long'] as const

/** Characters as the server counts them (code points, after trimming the ends). */
export function noteLength(text: string): number {
  return Array.from(text.trim()).length
}

export function ReviewerNotesCard({ appId, token, t, isWriter, refreshKey }: {
  appId: number
  token: string | null | undefined
  t: T
  isWriter: boolean
  refreshKey: string
}) {
  const [data, setData] = useState<ReviewerNotes | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let live = true
    getReviewerNotes(appId, { token })
      .then((d) => { if (live) { setData(d); setLoadFailed(false) } })
      .catch(() => { if (live) setLoadFailed(true) })
    return () => { live = false }
  }, [appId, token, refreshKey])

  if (!data && !loadFailed) return null
  const max = data?.max_length ?? 2000
  const fmt = (n: number) => n.toLocaleString('en-GB')
  const length = noteLength(draft)
  const over = length > max

  const submit = async () => {
    if (!token || busy || length === 0 || over) return
    setBusy(true); setError('')
    try {
      const next = await addReviewerNote(appId, draft, { token })
      setData(next); setDraft('')
    } catch (e) {
      const code = (e as { code?: string }).code ?? ''
      setError((CODES as readonly string[]).includes(code)
        ? t(`admin.scholarship.reviewerNotes.error.${code}`, { max: fmt(max) })
        : t('admin.scholarship.reviewerNotes.error.generic'))
      if (code === 'notes_closed' || code === 'writer_only') {
        getReviewerNotes(appId, { token }).then(setData).catch(() => {})
      }
    } finally {
      setBusy(false)
    }
  }

  const notes = data?.notes ?? []
  return (
    <section data-reviewer-notes
      className="border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-ground-200 md:bg-ground-0 md:p-5 md:shadow-sm space-y-3">
      <div className="space-y-1">
        <h2 className="text-base font-semibold tracking-tight text-ground-900">
          {t('admin.scholarship.reviewerNotes.title')}
        </h2>
        <p className="text-sm text-ground-600">
          {t(isWriter ? 'admin.scholarship.reviewerNotes.introWriter' : 'admin.scholarship.reviewerNotes.introReader')}
        </p>
      </div>

      {loadFailed && !data && (
        <p className="text-sm text-critical-600">{t('admin.scholarship.reviewerNotes.loadError')}</p>
      )}

      {notes.length > 0 ? (
        <ol className="space-y-2.5">
          {notes.map((n) => (
            <li key={n.id} className="rounded-xl border border-ground-200 bg-ground-50 px-3.5 py-3 space-y-1.5">
              <div className="flex flex-wrap justify-between gap-x-2 text-xs text-ground-600">
                <span className="font-semibold text-ground-900 break-words">{n.author_name}</span>
                <span>{formatDateTime(n.created_at)}</span>
              </div>
              <p className="text-sm leading-relaxed text-ground-900 whitespace-pre-line break-words">{n.body}</p>
            </li>
          ))}
        </ol>
      ) : data && !data.can_add && !isWriter && (
        <p className="text-sm text-ground-500">{t('admin.scholarship.reviewerNotes.empty')}</p>
      )}

      {data?.can_add && (
        <div className="space-y-2">
          <label htmlFor={`reviewer-note-${appId}`} className="block text-sm font-medium text-ground-700">
            {t('admin.scholarship.reviewerNotes.addLabel')}
          </label>
          <textarea id={`reviewer-note-${appId}`} rows={5} value={draft}
            onChange={(e) => { setDraft(e.target.value); setError('') }}
            placeholder={t('admin.scholarship.reviewerNotes.placeholder')}
            aria-describedby={`reviewer-note-${appId}-count`}
            className="w-full rounded-lg border border-ground-300 px-3 py-2 text-sm leading-relaxed focus:border-info-500 focus:ring-2 focus:ring-info-500" />
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
            <span className="text-xs text-ground-600">{t('admin.scholarship.reviewerNotes.appendOnly')}</span>
            <span id={`reviewer-note-${appId}-count`} aria-live="polite"
              className={`text-xs whitespace-nowrap ${over ? 'font-semibold text-critical-600' : 'text-ground-600'}`}>
              {t('admin.scholarship.reviewerNotes.counter', { count: fmt(length), max: fmt(max) })}
            </span>
          </div>
          <button type="button" onClick={submit} disabled={busy || length === 0 || over}
            className="w-full min-h-11 rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
            {busy ? t('admin.scholarship.reviewerNotes.adding') : t('admin.scholarship.reviewerNotes.add')}
          </button>
        </div>
      )}

      {error && <p role="alert" className="text-sm text-critical-600">{error}</p>}

      {isWriter && data && !data.window_open && (
        <p className="text-xs text-ground-500">{t('admin.scholarship.reviewerNotes.closedHint')}</p>
      )}
    </section>
  )
}

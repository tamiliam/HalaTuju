'use client'

/**
 * ORG ADMIN AND REVIEWER NOTES (request #55, 2026-11-07; two-way since request #73, 2026-11-16), directly
 * under "Reviewer assigned".
 *
 * One conversation, oldest first. Each note names its author, their side ("Org admin", "Reviewer", with
 * "(you)" on the caller's own notes) and the date; the reviewer's notes carry the brand tint so the two sides read apart.
 * Three faces, chosen by the SERVED `viewer`:
 *   • `org_admin` (an org admin or a super with students.edit): "Add a note" / "Add note";
 *   • `reviewer` (the reviewer assigned to the case): "Reply" / "Send reply";
 *   • `reader` (QC, a view-only admin): the list, read-only.
 * Writers get a live counter ("97 / 2,000") and the append-only line. While the window is shut both writers
 * see why, from the SERVED `reason`: 'not_yet' (the case has not reached Awaiting review) or 'finished'.
 *
 * ⚠ SERVE, NEVER DERIVE: the side is the server's `viewer`, whether the box shows is its `can_add` (the
 * window AND the side) and the limit is its `max_length`. The notes are their OWN fetch (the detail GET
 * stays at 38 queries), re-read when the case's status or verdict stamp moves, because those close the
 * window. Reading them clears the caller's "New note" mark on the server.
 */
import { useEffect, useState } from 'react'
import { addReviewerNote, getReviewerNotes, type ReviewerNote, type ReviewerNotes } from '@/lib/admin-api'
import { formatDateTime } from '@/lib/formatDate'

import type { T } from './shared'

const CODES = ['writer_only', 'notes_not_yet', 'notes_closed', 'bad_body', 'empty_body', 'too_long'] as const

/** What does not count as writing. ⚠ THE SERVER'S `_INVISIBLE` (`apps/scholarship/reviewer_notes.py`), source for
 *  source: `trim()` alone disagrees with it (U+FEFF, the Hangul fillers), and then the 2,000 boundary and the
 *  blank check would answer differently here and there. `ReviewerNotesCardDrift.test.tsx` compares the two. */
export const INVISIBLE = /[\t\n\v\f\r \x1c-\x1f\x85\xa0\xad\u115f\u1160\u1680\u180e\u2000-\u200f\u2028-\u202f\u205f-\u2064\u2800\u3000\u3164\ufeff\uffa0]/
const EDGES = new RegExp(`^${INVISIBLE.source}+|${INVISIBLE.source}+$`, 'g')
const ALL_INVISIBLE = new RegExp(INVISIBLE.source, 'g')

/** Characters as the server counts them (code points, after trimming the invisible ends). */
export function noteLength(text: string): number {
  return Array.from(text.replace(EDGES, '')).length
}

/** True when the note would store nothing visible (the server's `empty_body`). */
export function looksEmpty(text: string): boolean {
  return text.replace(ALL_INVISIBLE, '').length === 0
}

const P = 'admin.scholarship.reviewerNotes'

export function ReviewerNotesCard({ appId, token, t, refreshKey }: {
  appId: number
  token: string | null | undefined
  t: T
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
      // Review R6: a failed REFRESH is said out loud; the notes already on screen stay, marked stale.
      .catch(() => { if (live) setLoadFailed(true) })
    return () => { live = false }
  }, [appId, token, refreshKey])

  if (!data && !loadFailed) return null
  const max = data?.max_length ?? 2000
  const fmt = (n: number) => n.toLocaleString('en-GB')
  const length = noteLength(draft)
  const over = length > max
  const blank = looksEmpty(draft)

  const submit = async () => {
    if (!token || busy || blank || over) return
    setBusy(true); setError('')
    try {
      const next = await addReviewerNote(appId, draft, { token })
      setData(next); setDraft('')
    } catch (e) {
      const code = (e as { code?: string }).code ?? ''
      setError((CODES as readonly string[]).includes(code)
        ? t(`${P}.error.${code}`, { max: fmt(max) })
        : t(`${P}.error.generic`))
      if (code === 'notes_not_yet' || code === 'notes_closed' || code === 'writer_only') {
        getReviewerNotes(appId, { token }).then(setData).catch(() => {})
      }
    } finally {
      setBusy(false)
    }
  }

  const notes = data?.notes ?? []
  const viewer = data?.viewer ?? 'reader'
  const replying = viewer === 'reviewer'
  const intro = viewer === 'org_admin' ? 'introOrgAdmin' : replying ? 'introReviewer' : 'introReader'
  const roleOf = (n: ReviewerNote) =>
    t(`${P}.role.${n.author_role === 'reviewer' ? (n.is_you ? 'reviewerYou' : 'reviewer') : (n.is_you ? 'orgAdminYou' : 'org_admin')}`)
  return (
    <section data-reviewer-notes
      className="border-b border-ground-100 py-4 md:rounded-2xl md:border md:border-ground-200 md:bg-ground-0 md:p-5 md:shadow-sm space-y-3">
      <div className="space-y-1">
        <h2 className="text-base font-semibold tracking-tight text-ground-900">{t(`${P}.title`)}</h2>
        <p className="text-sm text-ground-600">{t(`${P}.${intro}`)}</p>
      </div>

      {loadFailed && <p className="text-sm text-critical-600">{t(`${P}.loadError`)}</p>}

      {notes.length > 0 ? (
        <ol className="space-y-2.5">
          {notes.map((n) => (
            <li key={n.id} data-note-side={n.author_role}
              className={`rounded-xl border px-3.5 py-3 space-y-1.5 ${n.author_role === 'reviewer'
                ? 'border-primary-100 bg-primary-50' : 'border-ground-200 bg-ground-50'}`}>
              <div className="flex flex-wrap justify-between gap-x-2 text-xs text-ground-600">
                <span className="break-words">
                  <span className="font-semibold text-ground-900">{n.author_name}</span>
                  {' · '}{roleOf(n)}
                </span>
                <span>{formatDateTime(n.created_at)}</span>
              </div>
              <p className="text-sm leading-relaxed text-ground-900 whitespace-pre-wrap break-words">{n.body}</p>
            </li>
          ))}
        </ol>
      ) : data && !data.can_add && (
        <p className="text-sm text-ground-500">{t(`${P}.empty`)}</p>
      )}

      {data?.can_add && (
        <div className="space-y-2">
          <label htmlFor={`reviewer-note-${appId}`} className="block text-sm font-medium text-ground-700">
            {t(`${P}.${replying ? 'replyLabel' : 'addLabel'}`)}
          </label>
          <textarea id={`reviewer-note-${appId}`} rows={5} value={draft}
            onChange={(e) => { setDraft(e.target.value); setError('') }}
            placeholder={t(`${P}.${replying ? 'replyPlaceholder' : 'placeholder'}`)}
            aria-describedby={`reviewer-note-${appId}-count`}
            className="w-full rounded-lg border border-ground-300 px-3 py-2 text-sm leading-relaxed focus:border-info-500 focus:ring-2 focus:ring-info-500" />
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
            <span className="text-xs text-ground-600">{t(`${P}.appendOnly`)}</span>
            <span id={`reviewer-note-${appId}-count`} aria-live="polite"
              className={`text-xs whitespace-nowrap ${over ? 'font-semibold text-critical-600' : 'text-ground-600'}`}>
              {t(`${P}.counter`, { count: fmt(length), max: fmt(max) })}
            </span>
          </div>
          <button type="button" onClick={submit} disabled={busy || blank || over}
            className="w-full min-h-11 rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
            {replying
              ? t(`${P}.${busy ? 'sending' : 'sendReply'}`)
              : t(`${P}.${busy ? 'adding' : 'add'}`)}
          </button>
        </div>
      )}

      {error && <p role="alert" className="text-sm text-critical-600">{error}</p>}

      {data && viewer !== 'reader' && !data.window_open && (
        <p className="text-xs text-ground-500">{t(`${P}.${data.reason === 'not_yet' ? 'notYetHint' : 'closedHint'}`)}</p>
      )}
    </section>
  )
}

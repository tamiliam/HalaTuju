'use client'

import { useRef, useState, type KeyboardEvent } from 'react'
import { useT } from '@/lib/i18n'
import Toggle from '@/components/Toggle'
import StaffAvatar from '@/components/admin/StaffAvatar'
import { formatDate, formatDateTime, relativeTime } from '@/lib/formatDate'
import { activityDot, activityText } from '@/lib/scholarActivity'
import type { ScholarActivity as Entry } from '@/lib/admin-api'

type T = (k: string, p?: Record<string, string>) => string

/**
 * The pieces of a scholar's activity box (sprint P1, 2026-11-09): one row, its time, and the composer.
 * `ScholarActivity.tsx` holds the list, the paging and the filter.
 */

/** "9 days ago", with the exact date and time in the `title` and for a screen reader (P1-e). */
export function When({ at }: { at: string }) {
  const { t } = useT()
  const exact = formatDateTime(at)
  const r = relativeTime(at)
  if (!r) return null
  const words = r.key === 'on' ? formatDate(r.date)
    : 'n' in r ? t(`admin.relativeTime.${r.key}`, { n: String(r.n) }) : t(`admin.relativeTime.${r.key}`)
  return (
    <time dateTime={at} title={exact}>
      <span aria-hidden>{words}</span><span className="sr-only">{exact}</span>
    </time>
  )
}

/** WHO a row names (P1-d): a person had any hand in it → their name and photo (or initials); only a
 *  fully automatic row is the System. Never an email for a known person — the server sends a name. */
function whoOf(a: Entry, t: T): { name: string; photo: string | null; system: boolean } {
  const actor = a.actor
  if (actor === undefined) {   // an older payload: the email it carried, or the System
    return a.actor_email ? { name: a.actor_email, photo: null, system: false }
      : { name: t('admin.scholars.activity.bySystem'), photo: null, system: true }
  }
  if (actor === null) return { name: t('admin.scholars.activity.bySystem'), photo: null, system: true }
  const fallback = actor.kind === 'scholar' ? t('admin.scholars.activity.theScholar')
    : actor.kind === 'mentor' ? t('admin.scholars.activity.aMentor') : '?'
  return { name: actor.name || fallback, photo: actor.photo_url, system: false }
}

/** The System's mark: a cog on the row's tone (money green, a status change amber, else grey). */
function SystemIcon({ tone }: { tone: string }) {
  return (
    <span aria-hidden data-testid="activity-system-icon"
      className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-white ${tone}`}>
      <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
        <path fillRule="evenodd" d="M8.34 1.8a1 1 0 0 1 .98-.8h1.36a1 1 0 0 1 .98.8l.22 1.1a6.97 6.97 0 0 1 1.6.93l1.07-.36a1 1 0 0 1 1.18.45l.68 1.18a1 1 0 0 1-.2 1.25l-.85.75a7.05 7.05 0 0 1 0 1.84l.85.75a1 1 0 0 1 .2 1.25l-.68 1.18a1 1 0 0 1-1.18.45l-1.07-.36c-.49.38-1.03.7-1.6.93l-.22 1.1a1 1 0 0 1-.98.8H9.32a1 1 0 0 1-.98-.8l-.22-1.1a6.97 6.97 0 0 1-1.6-.93l-1.07.36a1 1 0 0 1-1.18-.45l-.68-1.18a1 1 0 0 1 .2-1.25l.85-.75a7.05 7.05 0 0 1 0-1.84l-.85-.75a1 1 0 0 1-.2-1.25l.68-1.18a1 1 0 0 1 1.18-.45l1.07.36c.49-.38 1.03-.7 1.6-.93l.22-1.1ZM10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" clipRule="evenodd" />
      </svg>
    </span>
  )
}

/** One entry: who, the kind word (not for a plain note, P1-a), when, the staff-only chip, the words. */
export function ActivityRow({ a }: { a: Entry }) {
  const { t } = useT()
  const who = whoOf(a, t)
  const kindWord = a.kind === 'note' || (who.system && a.kind === 'system') ? ''
    : t(`admin.scholars.activity.kind.${a.kind}`)
  return (
    <li className="flex gap-2.5 py-2.5" data-testid="activity-row">
      {who.system ? <SystemIcon tone={activityDot(a)} />
        : <StaffAvatar name={who.name} photoUrl={who.photo} size={32} />}
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-baseline gap-x-1.5 text-xs text-ground-500">
          <span className="min-w-0 text-sm font-medium text-ground-900 [overflow-wrap:anywhere]"
            data-testid="activity-who">{who.name}</span>
          {kindWord && <span>· {kindWord}</span>}
          <span>· <When at={a.created_at} /></span>
          {a.internal && a.kind !== 'system' && (
            <span className="rounded-full bg-caution-100 px-1.5 py-0.5 text-[10px] font-medium text-caution-800">
              {t('admin.scholars.activity.staffOnly')}
            </span>
          )}
        </p>
        <p className="mt-0.5 whitespace-pre-wrap text-sm text-ground-900 [overflow-wrap:anywhere]">
          {activityText(a, t)}
        </p>
      </div>
    </li>
  )
}

/**
 * "Add a note…" — one line until it is focused, then three rows, the Staff only `Toggle` (never a
 * checkbox), Cancel and Save (P1-g). Save, Cancel, or Esc on an empty box closes it. Only notes (P1-a).
 */
export function ActivityComposer({ onSave }: {
  /** Resolves true when the entry was saved (the box then empties and closes). */
  onSave: (entry: { body: string; internal: boolean }) => Promise<boolean>
}) {
  const { t } = useT()
  const box = useRef<HTMLTextAreaElement>(null)
  const [open, setOpen] = useState(false)
  const [body, setBody] = useState('')
  const [internal, setInternal] = useState(false)
  const [busy, setBusy] = useState(false)

  function close() {
    setOpen(false); setBody(''); setInternal(false)
    box.current?.blur()
  }
  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Escape' && !body.trim()) { e.preventDefault(); close() }
  }
  async function save() {
    if (!body.trim() || busy) return
    setBusy(true)
    try {
      if (await onSave({ body, internal })) close()
    } finally { setBusy(false) }
  }

  return (
    <div className="mt-3 border-t border-ground-100 pt-3" data-testid="activity-composer">
      <textarea ref={box} value={body} onChange={(e) => setBody(e.target.value)} onFocus={() => setOpen(true)}
        onKeyDown={onKey} rows={open ? 3 : 1} aria-label={t('admin.scholars.activity.addLabel')}
        placeholder={t('admin.scholars.activity.placeholder')}
        className="block w-full resize-none rounded-lg border border-ground-300 px-3 py-2 text-sm focus:ring-2 focus:ring-info-500" />
      {open && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <span className="flex items-center gap-2 text-sm text-ground-700">
            <Toggle on={internal} onChange={setInternal} label={t('admin.scholars.activity.staffOnly')} />
            {t('admin.scholars.activity.staffOnly')}
          </span>
          <span className="flex items-center gap-2">
            <button type="button" onClick={close} disabled={busy}
              className="rounded-lg px-3 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50 max-md:min-h-11">
              {t('admin.scholars.activity.cancel')}
            </button>
            <button type="button" disabled={busy || !body.trim()} onClick={save}
              className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50 max-md:min-h-11">
              {busy ? t('admin.saving') : t('admin.scholars.activity.save')}
            </button>
          </span>
        </div>
      )}
    </div>
  )
}

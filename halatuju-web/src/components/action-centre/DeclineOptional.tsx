'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { declineResolutionItem, type ResolutionItem } from '@/lib/api'

/**
 * H7 "I don't have this", for an OPTIONAL document ask (the server serves `decline_reasons`; empty
 * for a required ask, so no button is drawn). Two states, both driven by the card (`open`):
 *  - closed: one outline button under Upload;
 *  - open: "Why don't you have it?" and the reasons as tap buttons. A tap sends at once, except
 *    "Other", which opens a required text box and a Send button. Cancel goes back to Upload.
 * The ask then closes server-side and is never asked again; `onDone` re-fetches the list.
 */
export function DeclineOptional({ item, token, open, onOpen, onCancel, onDone }: {
  item: ResolutionItem
  token: string | null
  open: boolean
  onOpen: () => void
  onCancel: () => void
  onDone: () => void
}) {
  const { t } = useT()
  const reasons = item.decline_reasons ?? []
  const [picked, setPicked] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  if (reasons.length === 0) return null

  const send = async (reason: string, words: string) => {
    if (!token) return
    setBusy(true); setError('')
    try {
      await declineResolutionItem(item.id, reason, words, { token })
      onDone()
    } catch {
      setError(t('documentsTab.actionCentre.decline.error'))
    } finally {
      setBusy(false)
    }
  }
  const cancel = () => { setPicked(''); setNote(''); setError(''); onCancel() }
  const label = (key: string) => t(`scholarship.actionCentre.decline.reasons.${item.doc_type}.${key}`)

  if (!open) {
    return (
      <button type="button" onClick={onOpen}
        className="mt-2 min-h-11 w-full rounded-xl border border-brand-shape px-4 py-2.5 text-sm font-semibold text-primary-600 transition-colors hover:bg-primary-50">
        {t('documentsTab.actionCentre.decline.button')}
      </button>
    )
  }

  const face = 'min-h-11 w-full rounded-xl border px-4 py-2.5 text-left text-sm transition-colors disabled:opacity-50'
  return (
    <div>
      <p className="text-sm font-semibold text-ground-900">{t('documentsTab.actionCentre.decline.ask')}</p>
      <div className="mt-2 space-y-2">
        {reasons.map((key) => (
          <button key={key} type="button" disabled={busy}
            aria-pressed={key === 'other' ? picked === 'other' : undefined}
            onClick={() => (key === 'other' ? setPicked('other') : send(key, ''))}
            className={`${face} ${picked === key ? 'border-primary-600 bg-primary-50 font-semibold text-ground-900' : 'border-ground-200 bg-white text-ground-800 hover:bg-ground-50'}`}>
            {label(key)}
          </button>
        ))}
      </div>
      {picked === 'other' && (
        <div className="mt-3 space-y-2">
          <label className="block text-sm font-semibold text-ground-900" htmlFor={`decline-note-${item.id}`}>
            {t('documentsTab.actionCentre.decline.noteLabel')}
          </label>
          <textarea id={`decline-note-${item.id}`} className="input" rows={3} value={note} disabled={busy}
            maxLength={500} onChange={(e) => setNote(e.target.value)} />
          <button type="button" disabled={busy || !note.trim()} onClick={() => send('other', note.trim())}
            className="min-h-11 w-full rounded-xl bg-brand-fill px-4 py-2.5 text-sm font-semibold text-brand-fill-ink transition-colors hover:bg-brand-fill-hover disabled:opacity-50">
            {busy ? t('documentsTab.actionCentre.decline.sending') : t('documentsTab.actionCentre.decline.send')}
          </button>
        </div>
      )}
      {error && <p role="alert" className="mt-2 text-sm text-critical-600">{error}</p>}
      <button type="button" onClick={cancel} disabled={busy}
        className="mt-3 min-h-11 w-full text-center text-sm font-semibold text-ground-700 underline">
        {t('documentsTab.actionCentre.decline.cancel')}
      </button>
    </div>
  )
}

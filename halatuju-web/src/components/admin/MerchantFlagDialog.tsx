'use client'

/**
 * One shop's flag for review, and its notes log (request #28 follow-up, 2026-10-06).
 *
 * ⚠ A MODAL OVER THE PAGE, NEVER A POPOVER IN THE TABLE. `TableFrame` clips twice (rounded corners
 * and the horizontal scroller) — see `SpendingShops`' header — so this is drawn ONCE, outside the
 * table, `fixed` over everything. The shape is `CommandPalette`'s: `aria-modal`, Escape and a
 * backdrop press close it, focus goes to the note on open and back to the flag button on close.
 * The body follows `GuardianCallRecord` (note box, Cancel + the action, a `role="alert"` refusal).
 *
 * ⚠ A NOTE IS REQUIRED FOR EVERY ACTION — flagging says why, and so does clearing. The server
 * refuses a blank one too (`note_required`); the buttons here simply wait for words.
 *
 * ⚠ THE FLAG IS THIS ORGANISATION'S. The log is read fresh on every opening (a colleague may have
 * written since the page loaded), and after any change the page re-reads its list so the filled
 * flag and the "Flagged only" filter agree with the log.
 *
 * Loaded as its own chunk by `LazyMerchantFlagDialog` — most visits to the screen never open it.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDateTime } from '@/lib/formatDate'
import {
  changeMerchantFlag, getMerchantFlag, type MerchantFlagLog, type MerchantFlagNote,
} from '@/lib/admin-api'

/** The label in front of each entry. ⚠ Literal keys, so the i18n scan can see every one. */
const KIND: Record<MerchantFlagNote['kind'], string> = {
  open: 'admin.spending.flag.opened', note: 'common.note', close: 'admin.spending.flag.closed',
}

export interface MerchantFlagDialogProps {
  merchant: string
  /** The gift the table on screen belongs to — the same one a category correction names. */
  programme: string | undefined
  onClose: () => void
  /** A flag was opened, noted or cleared: the page re-reads its list. */
  onChanged: () => void
}

export default function MerchantFlagDialog({
  merchant, programme, onClose, onChanged,
}: MerchantFlagDialogProps) {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [log, setLog] = useState<MerchantFlagLog | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  /** An i18n KEY, not text — so nothing that reads the server needs `t`. */
  const [error, setError] = useState('')
  const noteRef = useRef<HTMLTextAreaElement>(null)
  const restoreTo = useRef<Element | null>(null)

  // Remember where focus was (the flag button) and give it back on close.
  useEffect(() => {
    restoreTo.current = document.activeElement
    noteRef.current?.focus()
    return () => { (restoreTo.current as HTMLElement | null)?.focus?.() }
  }, [])

  const read = useCallback(() => {
    if (!token) return
    getMerchantFlag(merchant, programme, { token })
      .then(setLog)
      .catch(() => setError('errors.somethingWentWrong'))
  }, [merchant, programme, token])
  useEffect(read, [read])

  const act = async (action: MerchantFlagNote['kind']) => {
    if (!token || !note.trim()) return
    setBusy(true); setError('')
    try {
      setLog(await changeMerchantFlag(merchant, action, note.trim(), programme, { token }))
      setNote('')
      onChanged()
    } catch (e) {
      const code = (e as Error & { code?: string }).code || ''
      setError(code === 'unknown_merchant'
        ? 'admin.spending.error.unknown_merchant' : 'admin.spending.saveFailed')
      // Somebody else changed it meanwhile: show the log as it now stands, and the list too.
      if (code === 'already_flagged' || code === 'not_flagged') { read(); onChanged() }
    } finally { setBusy(false) }
  }

  const ready = !!log && !busy && note.trim() !== ''
  const button = 'rounded-md px-3 py-1.5 text-xs font-medium disabled:opacity-50'
  const primary = `${button} bg-brand-fill text-brand-fill-ink`
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ground-900/40 px-4 pt-[12vh]"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${t('admin.spending.flag.col')} — ${merchant}`}
        className="w-full max-w-lg space-y-3 rounded-2xl border border-ground-200 bg-ground-0 p-4 shadow-2xl"
        onKeyDown={(e) => { if (e.key === 'Escape') { e.preventDefault(); onClose() } }}
      >
        <h2 className="text-sm font-semibold text-ground-900">{merchant}</h2>
        {!log && !error && <p className="text-xs text-ground-500">{t('common.loading')}</p>}
        {log && log.notes.length > 0 && (
          <ol className="max-h-64 space-y-2 overflow-y-auto" data-testid="flag-log">
            {log.notes.map((n, i) => (
              <li key={i} className="rounded-md bg-ground-50 px-3 py-2 text-sm">
                <p className="text-[11px] text-ground-500">
                  <span className="font-semibold text-ground-700">{t(KIND[n.kind])}</span>
                  {' · '}{n.author}{' · '}{formatDateTime(n.at)}
                </p>
                <p className="mt-0.5 whitespace-pre-wrap text-ground-800">{n.body}</p>
              </li>
            ))}
          </ol>
        )}
        <textarea
          ref={noteRef} aria-label={t('common.note')} placeholder={t('common.note')}
          value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} rows={3}
          className="w-full rounded-md border border-ground-300 px-2 py-1.5 text-sm"
        />
        {error && <p role="alert" className="text-xs text-critical-600">{t(error)}</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <button type="button" onClick={onClose}
            className={`${button} border border-ground-300 text-ground-700`}>
            {t('common.cancel')}
          </button>
          {log?.flagged ? (
            <>
              <button type="button" onClick={() => act('close')} disabled={!ready}
                className={`${button} border border-ground-300 text-ground-700`}>
                {t('admin.spending.flag.clear')}
              </button>
              <button type="button" onClick={() => act('note')} disabled={!ready} className={primary}>
                {t('common.save')}
              </button>
            </>
          ) : (
            <button type="button" onClick={() => act('open')} disabled={!ready} className={primary}>
              {t('admin.spending.flag.col')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

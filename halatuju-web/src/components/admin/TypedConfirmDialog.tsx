'use client'

import { useState, type ReactNode } from 'react'

import { useT } from '@/lib/i18n'

/**
 * A destructive action that will not happen until the exact `phrase` is typed.
 *
 * The gift-programme delete's pattern (`GiftProgrammes.tsx`, owner 2026-09-07), lifted into a
 * component for the staff delete (2026-10-09): a second "are you sure?" is answered by the same
 * reflex that pressed the first button, and typing a person's own address cannot be. Compared
 * after trimming and collapsing whitespace, case-insensitively — what the gift dialog does, so the
 * button is never asleep on a difference nobody would call a different answer. The SERVER still
 * decides; this dialog explains the step, it is not the guard.
 */
export default function TypedConfirmDialog({ title, body, phrase, cta, busy = false, onCancel,
                                            onConfirm }: {
  title: string
  body: ReactNode
  /** What must be typed, shown in the label. */
  phrase: string
  cta: string
  busy?: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  const { t } = useT()
  const [typed, setTyped] = useState('')
  const norm = (s: string) => s.trim().replace(/\s+/g, ' ').toLowerCase()
  const matches = norm(typed) !== '' && norm(typed) === norm(phrase)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={() => !busy && onCancel()}>
      <div role="dialog" aria-modal="true" aria-label={title}
        className="w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-critical-700">{title}</h2>
        <div className="mt-2 text-sm text-ground-700">{body}</div>
        <label htmlFor="typed-confirm" className="mt-4 block text-sm font-medium text-ground-700">
          {t('admin.programmes.deleteConfirmLabel', { phrase })}
        </label>
        <input id="typed-confirm" value={typed} autoComplete="off"
          onChange={(e) => setTyped(e.target.value)}
          className="mt-1 w-full rounded-lg border border-ground-300 px-3 py-2" />
        <div className="mt-5 flex justify-end gap-3">
          <button type="button" onClick={onCancel} disabled={busy}
            className="rounded-lg px-4 py-2 text-sm font-medium text-ground-600 hover:text-ground-900 disabled:opacity-50">
            {t('common.cancel')}
          </button>
          <button type="button" data-testid="typed-confirm-go" disabled={busy || !matches}
            onClick={onConfirm}
            className="rounded-lg bg-critical-fill px-4 py-2 text-sm font-semibold text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50">
            {cta}
          </button>
        </div>
      </div>
    </div>
  )
}

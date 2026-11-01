'use client'

/**
 * "Remove this file?" — the documents tab's confirm sheet (Mobile M4, owner-approved mock).
 *
 * LOADED LAZILY by `ScholarshipDocuments.handleDelete` (the tab rides on /scholarship/application,
 * the tightest bundle line). If this chunk cannot load, that handler asks with the phone's own
 * confirm instead — never a delete without a question (lessons.md: a lazy way out needs an eager one).
 *
 * Its words are the documents tab's own slice (`documentsTab.card.*`), loaded with the tab's chunk.
 *
 * Focus opens on "Keep it", the safe answer; the sheet cannot be closed while the delete is in flight
 * (`busy`), and the Remove button is off then too — one tap, one delete.
 */
import { useRef } from 'react'
import Sheet from '@/components/Sheet'
import { useT } from '@/lib/i18n'

export interface RemoveConfirmProps {
  /** The file's name as she uploaded it (or the document's name). */
  name: string
  busy: boolean
  onCancel: () => void
  onConfirm: () => void
}

export default function RemoveConfirm({ name, busy, onCancel, onConfirm }: RemoveConfirmProps) {
  const { t } = useT()
  const keep = useRef<HTMLButtonElement>(null)
  return (
    <Sheet open onClose={onCancel} busy={busy} role="alertdialog" tone="critical" size="sm"
      initialFocus={keep} testId="remove-confirm"
      title={t('documentsTab.card.removeTitle')}
      footer={<>
        <button type="button" onClick={onConfirm} disabled={busy}
          className="min-h-12 w-full rounded-xl bg-critical-fill px-4 font-semibold text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50">
          {t('scholarship.docs.remove')}
        </button>
        <button ref={keep} type="button" onClick={onCancel} disabled={busy}
          className="min-h-12 w-full rounded-xl border border-ground-300 px-4 font-medium text-ground-700 hover:bg-ground-50">
          {t('documentsTab.card.keep')}
        </button>
      </>}>
      {/* The question in the BODY, not the header's description: a sheet with an empty body draws a gap. */}
      <p className="text-ground-700">{t('documentsTab.card.removeBody', { name })}</p>
    </Sheet>
  )
}

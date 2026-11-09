'use client'

/**
 * THE COCKPIT'S "ARE YOU SURE?" — the site's own dialog (Sheet) in place of `window.confirm`
 * (audit A3.3, TD-480). A browser may suppress a native confirm and a phone draws it as its own
 * box (mobile-standard.md rule 5). The words are the ones the three questions always had: the
 * action's label as the title and the confirm button, the question as the body.
 *
 * `dismissible={false}` for anything that touches a decision or an award (cancel a scheduled
 * decline, hold a pending award): a stray tap or Escape must not answer for the officer, so only the
 * two buttons do. The reminder to a student can be dismissed.
 */
import Sheet from '@/components/Sheet'

export function ConfirmSheet({
  t, title, question, confirmLabel, busy, dismissible, onCancel, onConfirm,
}: {
  t: (key: string, params?: Record<string, string>) => string
  title: string
  question: string
  confirmLabel: string
  busy: boolean
  dismissible: boolean
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <Sheet open onClose={onCancel} busy={busy} role="alertdialog" size="sm" dismissible={dismissible}
      testId="cockpit-confirm" title={title}
      footer={<>
        <button type="button" onClick={onConfirm} disabled={busy}
          className="min-h-12 w-full rounded-xl bg-primary-600 px-4 font-semibold text-white hover:bg-primary-700 disabled:opacity-50">
          {confirmLabel}
        </button>
        <button type="button" onClick={onCancel} disabled={busy}
          className="min-h-12 w-full rounded-xl border border-ground-300 px-4 font-medium text-ground-700 hover:bg-ground-50">
          {t('common.cancel')}
        </button>
      </>}>
      <p className="text-ground-700">{question}</p>
    </Sheet>
  )
}

'use client'

/**
 * The cockpit's "why?" box — a required reason before an irreversible step. Lifted whole out of
 * `DecisionCard` (the decision reopen's prompt) at A1.13 so the award withdrawal (TD-198) reuses
 * the same dialog rather than a new design: a titled caution panel, a hint, a text box, and a
 * Confirm that stays disabled until the reason has text, beside Cancel.
 */
export function ReasonBox({
  title, hint, placeholder, confirmLabel, workingLabel, cancelLabel, value, onChange, onConfirm,
  onCancel, disabled, working, testId,
}: {
  title: string
  hint: string
  placeholder: string
  confirmLabel: string
  workingLabel: string
  cancelLabel: string
  value: string
  onChange: (value: string) => void
  onConfirm: () => void
  onCancel: () => void
  /** Something else is in flight: both buttons rest. */
  disabled: boolean
  /** THIS box's step is in flight: Confirm shows `workingLabel`. */
  working: boolean
  testId?: string
}) {
  return (
    <div className="rounded-lg border border-caution-200 bg-caution-50 p-3 space-y-2" data-testid={testId}>
      <p className="text-xs font-medium text-caution-900">{title}</p>
      <p className="text-xs md:text-[11px] text-caution-800">{hint}</p>
      <textarea value={value} rows={2} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border rounded-lg px-3 py-2 text-sm" />
      <div className="flex items-center gap-2">
        <button onClick={onConfirm} disabled={disabled || !value.trim()}
          className="px-3 py-1.5 bg-critical-fill text-critical-fill-ink rounded-lg text-sm disabled:opacity-50 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center">
          {working ? workingLabel : confirmLabel}
        </button>
        <button onClick={onCancel} disabled={disabled}
          className="px-3 py-1.5 border rounded-lg text-sm text-ground-600 disabled:opacity-50 max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center">
          {cancelLabel}
        </button>
      </div>
    </div>
  )
}

'use client'

// Shared bits of the Sources module. The Toggle was defined inside the Sources page until the
// partner-emails card needed the same switch — lifted here rather than cloned, so the page has one
// switch and not two that drift apart.

export function Toggle({ on, onClick, disabled, label }: {
  on: boolean; onClick: () => void; disabled?: boolean; label: string
}) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label}
      onClick={disabled ? undefined : onClick} disabled={disabled}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
        on ? 'bg-info-600' : 'bg-ground-300'}`}>
      <span className={`inline-block h-4 w-4 transform rounded-full bg-ground-0 transition-transform ${
        on ? 'translate-x-6' : 'translate-x-1'}`} />
    </button>
  )
}

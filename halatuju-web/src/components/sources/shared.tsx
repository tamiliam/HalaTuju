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

/**
 * Has anybody signed in for this source (source sign-in S2)? One badge for the Sources list and the
 * Invitations → Source form, so the three states read the same in both: "Not invited", "Invited,
 * waiting", "Joined". Absent (a payload from before S2) reads as not invited.
 */
export function SignInBadge({ state, t }: {
  state?: 'none' | 'invited' | 'joined'; t: (k: string) => string
}) {
  const s = state ?? 'none'
  const tone = s === 'joined' ? 'bg-positive-100 text-positive-800 font-semibold'
    : s === 'invited' ? 'bg-caution-100 text-caution-700' : 'text-ground-500'
  return (
    <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs ${tone}`}>
      {t(`admin.sources.signIn.${s}`)}
    </span>
  )
}

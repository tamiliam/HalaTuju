'use client'

/** Minimal iOS-style toggle (no external dep, keyboard-accessible). Used across
 *  the B40 apply form for yes/no answers (STR, JKM) and the consent control.
 *
 *  ⚠ 44 × 44 TO A THUMB, 44 × 24 TO THE EYE (Mobile M1a, mobile-standard.md rule 3). The button is
 *  the 44 px square a finger has to hit; the track you SEE is the inner span. The button's -10 px
 *  vertical margins cancel the extra height, so nothing around a toggle moves. Role, label, state
 *  and the click are on the button exactly as before. */
export default function Toggle({
  on,
  onChange,
  label,
  disabled = false,
}: {
  on: boolean
  onChange: (v: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled}
      onClick={() => { if (!disabled) onChange(!on) }}
      className={`relative -my-[10px] inline-flex h-11 w-11 shrink-0 items-center ${
        disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <span className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        on ? 'bg-brand-shape' : 'bg-ground-300'
      }`}>
        <span className={`inline-block h-5 w-5 transform rounded-full bg-ground-0 shadow transition-transform ${on ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </span>
    </button>
  )
}

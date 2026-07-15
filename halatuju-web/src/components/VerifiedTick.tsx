/**
 * A very small, non-obtrusive "verified" badge (the FB/X seal-check) shown after a field value
 * whose typed value has been MATCHED against an uploaded, machine-read document. Monochrome +
 * ~14px so it sits quietly beside the value; the `label` is the hover tooltip (and aria-label)
 * that names WHAT it was matched against (e.g. "Matches MyKad"). Absence of the tick means "not
 * corroborated" — we never render a red/failed state here (the Documents drawer owns mismatches).
 */
export default function VerifiedTick({ label }: { label: string }) {
  return (
    <span
      title={label}
      aria-label={label}
      role="img"
      className="ml-1 inline-flex shrink-0 align-middle text-sky-500"
    >
      <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" aria-hidden>
        <path
          fill="currentColor"
          d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"
        />
        <path
          d="m9 12 2 2 4-4"
          fill="none"
          stroke="#fff"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  )
}

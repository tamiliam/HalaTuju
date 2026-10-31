import InfoTip from './InfoTip'

/**
 * A very small, non-obtrusive "verified" badge (the FB/X seal-check) shown after a field value
 * whose typed value has been MATCHED against an uploaded, machine-read document. Monochrome +
 * ~14px so it sits quietly beside the value; the `label` names WHAT it was matched against (e.g.
 * "Matches MyKad"). Absence of the tick means "not corroborated" — we never render a red/failed
 * state here (the Documents drawer owns mismatches).
 *
 * ⚠ THE LABEL IS REACHABLE BY TAP (Mobile M1a, mobile-standard.md rule 4). It used to live in
 * `title` only — a hover tooltip, which a phone never shows, so on a reviewer's phone the tick
 * explained nothing. The seal is now the trigger of an `InfoTip`: tap (or click, or Enter) shows
 * the label in a bubble, through a 44 px target that looks exactly like the old 14 px seal. The
 * `title` stays for a desktop mouse — so InfoTip's own hover bubble is off (`hoverOpens={false}`),
 * or a hover would show two tooltips.
 */
export default function VerifiedTick({ label }: { label: string }) {
  return (
    <InfoTip text={label} markSize={14} hoverOpens={false} mark={
      <span
        title={label}
        aria-label={label}
        role="img"
        className="inline-flex shrink-0 align-middle text-info-600"
      >
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" aria-hidden>
          <path
            fill="currentColor"
            d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"
          />
          {/* `stroke-white` (a literal), never `--ground-0`: this tick sits ON the coloured seal,
              so it must NOT invert with the ground — the same rule the codemod applies to
              `text-white`. It was a raw `#fff`, which a class scan cannot see. */}
          <path
            d="m9 12 2 2 4-4"
            fill="none"
            className="stroke-white"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    } />
  )
}

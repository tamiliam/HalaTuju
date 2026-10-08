'use client'

// "Who referred you?" on the apply form (per-gift referral sources, Sprint 2, 2026-10-08).
//
// The options are THIS gift's served sources (the server's names) and then the three fixed choices
// (`lib/referralSources`). Two rules live here so the page stays small:
//
//   • A CHOICE NOT IN THE LIST IS CLEARED, never silently resubmitted. A profile can carry a code
//     another gift offered, a source since switched off, or nothing the form offers at all; once the
//     intake has answered, such a value goes back to blank and the student chooses again. Nothing is
//     cleared before the intake answers — the list is not known yet.
//   • AFTER THE SERVER REFUSES THE CODE (`referral_source_not_offered`), the page re-reads the list
//     (`useApplyGift.refuseReferral`) and this field says, in plain words, to choose again — until she
//     does. Everything else she typed is untouched.

import { useEffect, useMemo, useRef } from 'react'
import { useT } from '@/lib/i18n'
import { referralOptions, type ReferralOption, type ReferralSource } from '@/lib/referralSources'

/** The options for the form, and the clearing rule above. Call it ABOVE the page's early returns. */
export function useReferralOptions(
  settled: boolean, sources: ReferralSource[] | null, value: string, clear: () => void,
): ReferralOption[] {
  const { t } = useT()
  const options = useMemo(() => referralOptions(sources, t), [sources, t])
  const codes = options.map((o) => o.code).join('|')
  // The latest `clear`, without making the effect re-run on every new arrow the page passes.
  const clearRef = useRef(clear)
  clearRef.current = clear
  useEffect(() => {
    if (settled && value && !codes.split('|').includes(value)) clearRef.current()
  }, [settled, codes, value])
  return options
}

export default function ReferralSelect({ options, value, onChange, refused }: {
  options: ReferralOption[]
  value: string
  onChange: (code: string) => void
  /** The server refused the last submit's code; shown until a new choice is made. */
  refused: boolean
}) {
  const { t } = useT()
  return (
    <>
      <select className="input" value={value} data-testid="referral-select"
        onChange={(e) => onChange(e.target.value)}>
        <option value="">{t('scholarship.apply.orgPlaceholder')}</option>
        {options.map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
      </select>
      {refused && !value && (
        <p role="alert" className="mt-1 text-sm text-critical-600" data-testid="referral-refused">
          {t('scholarship.apply.error.orgNotOffered')}
        </p>
      )}
    </>
  )
}

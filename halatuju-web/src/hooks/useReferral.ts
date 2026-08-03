'use client'

import { useEffect } from 'react'
import { usePathname, useSearchParams } from 'next/navigation'
import { KEY_REFERRAL_SOURCE, KEY_SPONSOR_REF } from '@/lib/storage'

/**
 * Captures `?ref=` on arrival. TWO different referrals wear the same parameter name, and until
 * 2026-08-03 only one of them was ever written down.
 *
 * ⚠ A SPONSOR INVITE CODE IS NOT A PARTNER CODE, and the differences are not cosmetic:
 *   - it is `secrets.token_urlsafe(9)` and therefore **CASE-SENSITIVE** — lower-casing it, which is
 *     right for a partner code, destroys it;
 *   - it belongs in sessionStorage under `KEY_SPONSOR_REF`, which is where `SponsorDetailsForm`
 *     and the register page read it from;
 *   - it must NOT also land in the student key, or a sponsor's invite code becomes that person's
 *     "how did you hear about us" the day they apply as a student.
 *
 * The bug this fixes: `KEY_SPONSOR_REF` had a reader and no writer anywhere in the codebase, so
 * `referrals.attribute_referral(code, ...)` could never fire from the live UI — every attribution
 * fell through to the email fallback. It is why five of eight invitees once still read "Invited"
 * after they had joined.
 *
 * First touch wins on both, matching the original behaviour.
 */
export function useReferral() {
  const searchParams = useSearchParams()
  const pathname = usePathname()

  useEffect(() => {
    const ref = searchParams.get('ref')
    if (!ref) return

    // A sponsor invite always lands somewhere under /sponsor — the landing page, or the register
    // page directly. Keyed on the PATH rather than the code's shape: a code is opaque by design,
    // so there is nothing about it to recognise.
    if (pathname?.startsWith('/sponsor')) {
      try {
        if (!sessionStorage.getItem(KEY_SPONSOR_REF)) {
          sessionStorage.setItem(KEY_SPONSOR_REF, ref.trim())   // verbatim — see above
        }
      } catch { /* sessionStorage unavailable (private browsing) — registration still works */ }
      return
    }

    try {
      if (!localStorage.getItem(KEY_REFERRAL_SOURCE)) {
        localStorage.setItem(KEY_REFERRAL_SOURCE, ref.toLowerCase().trim())
      }
    } catch { /* localStorage unavailable — the self-reported source question still catches it */ }
  }, [searchParams, pathname])
}

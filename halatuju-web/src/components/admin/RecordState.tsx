'use client'

import { useT } from '@/lib/i18n'

/**
 * ONE RECORD'S TWO UNHAPPY STATES — "still arriving" and "we could not find that" — from state
 * the caller passes in, because the caller is the only thing that knows which it is.
 *
 * ⚠ **WHY IT IS SHARED RATHER THAN SEVEN COPIES.** A detail screen loads one record and has two
 * early returns. Written by hand, the order of those two returns is the whole bug: on
 * `/admin/payments/[id]` the fetch failed, `setError(…)` ran, and an EARLIER
 * `if (!run) return <Loading/>` fired, so the message was set and never reached. The page span
 * on "Loading…" for ever — a 200, a mounted page, and no way out but the Back button. Five
 * screens were written in four different orders and the order was invisible at a glance. One
 * component, one line per call site, and the state is named at the call site.
 *
 * ⚠ **IT IS ONE LINE AT EVERY CALL SITE BECAUSE OF A HARD BUDGET, TOO.**
 * `admin/scholarship/[id]/view.tsx` sits in the `oversize_files` ledger with four lines of room
 * and `admin/sponsors/[id]/page.tsx` has three before it joins it (halatuju-web/code-standards.json,
 * enforced by `src/lib/__tests__/codeStandards.test.ts` inside the deploy gate). If a state ever
 * needs more markup, it goes HERE — never back into a call site.
 *
 * ⚠⚠ **THE WORDING IS A CORRECTNESS RULE, NOT A STYLE PREFERENCE. DO NOT "IMPROVE" IT.**
 * The admin organisation fence answers **404, never 403**, for a record belonging to ANOTHER
 * organisation, precisely so that its existence is never leaked (docs/decisions.md — the
 * org-fence rule, and "an unknown programme reads CLOSED, never 404"). So this copy must stay
 * NEUTRAL about why:
 *
 *     "We could not find that."
 *
 *   * NEVER "this record does not exist" — FALSE for a cross-org record, which does exist;
 *   * NEVER "you do not have access" — that LEAKS that it exists.
 *
 * Both of those are the natural things to write and both undo the fence. `errors.recordNotFound`
 * / `errors.recordNotFoundDesc` are checked for them by
 * `src/components/admin/__tests__/RecordState.test.tsx`, in all three locales.
 *
 * ⚠ No way-out link is drawn here, and that is deliberate: every caller renders INSIDE
 * `app/admin/layout.tsx`, so the menu and the breadcrumb are already on screen. A button of our
 * own would have to name a destination, and where an admin goes is DERIVED from the route
 * registry, never named (`lib/adminLanding.ts`). The console's own 404 page is where that
 * belongs — see `app/admin/not-found.tsx`.
 */
export default function RecordState({ loading }: { loading: boolean }) {
  const { t } = useT()
  if (loading) return <div className="text-center text-ground-500 mt-8">{t('common.loading')}</div>
  return (
    <div className="text-center mt-8" data-testid="record-not-found">
      <p className="text-ground-900 font-semibold">{t('errors.recordNotFound')}</p>
      <p className="text-ground-500 text-sm mt-1">{t('errors.recordNotFoundDesc')}</p>
    </div>
  )
}

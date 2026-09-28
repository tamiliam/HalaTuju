'use client'

/**
 * YOU ENTER A GIFT FIRST — the gate on the pages that act on one gift's money (2026-09-28).
 *
 * The owner, after an admin at BrightPath pressed New payment run with two gifts live and got a
 * refusal she had nowhere to answer: *"since we access the payment run by first selecting the gift
 * programme, that question shouldn't even arise"* — and then: *"the user should be redirected to
 * the Programmes page, which lists the gifts."* So Payments and Spending, reached with several
 * gifts and none chosen, SEND THE PERSON TO THE DOOR rather than drawing every gift's money and a
 * button the server can only refuse.
 *
 * Three answers:
 *   · `'wait'` — not yet known. The address bar has not been read (`useGiftInUrl`), the scopes list
 *     has not come back, or the role has not, or we are about to redirect. The page draws its loading line and NOTHING ELSE: no list, no button. The
 *     list is empty before it arrives, which reads as "one gift" — so acting before `settled`
 *     would either bounce every page load or flash every gift's runs.
 *   · `'ask'`  — several gifts, none chosen, and this role has NO door: the Programmes page shows
 *     its gift cards only to super and org_admin (`organisation/page.tsx` `maySeeGifts`), so a
 *     plain `admin` or `finance` sent there would find no gift to click. They get the house
 *     `ChooseProgramme` box on the page instead. Never a redirect somewhere they cannot go.
 *     Also, for EVERY role, a chosen DRAFT while a live gift exists (TD-296): not payable.
 *   · `'open'` — the gift is known (one gift, one chosen, or a detail page's pin). Exactly as before.
 *
 * ⚠ THE DOOR IS ONE PREDICATE, `hasGiftDoor` in `navigation.ts`, read by the rail too. For a role
 * without a door the rail keeps Payments visible outside a gift and this page's question is how
 * they choose one — finance's only way in, since the Programmes page shows it no cards.
 *
 * ⚠ ONLY LIVE GIFTS COUNT (`ambiguous`): one live gift plus a draft is one gift, as on the server.
 *
 * ⚠ `router.replace`, NOT `push`, AND ONCE PER MOUNT. Back must not return to a page that would
 * only bounce again, and a re-render must not queue a second navigation.
 *
 * ⚠ IT CANNOT LOOP THROUGH THE DOOR. Every gift card calls `select(p.code)` before it navigates
 * (`GiftProgrammes.enterGift`), and the cards list the same gifts the scope does — a super's
 * scopes are every programme, as are their cards; everyone else's are their own organisation's —
 * so arriving from a card resolves the gift and this answers `'open'`. A rendered test pins it.
 *
 * STILL DISPLAY, NOT A FENCE. The endpoints re-resolve `?programme=` inside the caller's own
 * organisation and refuse `programme_required` exactly as before.
 */
import { useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'

import { effectiveRole, hasGiftDoor } from '@/lib/navigation'
import { useProgrammeScope } from '@/lib/programmeScope'
import { useGiftInUrl } from '@/lib/useGiftInUrl'

export type GiftGate = 'wait' | 'ask' | 'open'

/** Where the gifts are listed. */
export const GIFT_DOOR = '/admin/organisation'

export function useGiftGate(
  role: { role?: string; is_super_admin?: boolean } | null | undefined,
): GiftGate {
  // ⚠ THE ADDRESS BAR FIRST (TD-296). A shared `/admin/payments?programme=<code>` must open into
  // that gift — so nothing below may decide until the query has been read into the scope and the
  // list can recognise it. Without this the redirect fired on the very render that was about to
  // apply the link's gift, and a colleague's link bounced to the Programmes page.
  const urlRead = useGiftInUrl()
  const { settled, ambiguous, chosen, unrecognised, programme, live } = useProgrammeScope()
  const router = useRouter()
  const known = urlRead && settled
  // A gift asked for and not recognised (a typo, another organisation's, not in the list yet) is no
  // gift — even on a single-gift tenant, where the only gift is NOT what the link asked for.
  const noGift = known && !chosen && (ambiguous || unrecognised)
  // ⚠ A DRAFT IS NOT PAYABLE (TD-296 (c), the F1 rule). The crumb offers drafts for Configuration,
  // and a link can name one; the server 404s a run against one. So with a live gift to offer, a
  // chosen draft gets the question — for EVERY role: a door role sent to the Programmes page would
  // find the draft's own card there and could bounce straight back.
  const draft = known && programme?.isActive === false && live.length > 0
  // ⚠ THE SAME PREDICATE THE RAIL READS (`hasGiftDoor`), so the row and the page can never
  // disagree: a role whose row is hidden outside a gift is exactly a role that gets redirected.
  const hasDoor = !!role && hasGiftDoor(effectiveRole(role))
  const redirect = noGift && hasDoor

  const sent = useRef(false)
  useEffect(() => {
    if (!redirect || sent.current) return
    sent.current = true
    router.replace(GIFT_DOOR)
  }, [redirect, router])

  if (!known) return 'wait'
  if (draft) return 'ask'
  if (!noGift) return 'open'
  // Several gifts and none chosen: redirect (still `wait` for the instant before it lands), or —
  // for a role with no door — ask here. With the role not yet known, wait rather than guess.
  return !role || hasDoor ? 'wait' : 'ask'
}

'use client'

/**
 * THE URL CARRIES THE GIFT — a list link can be shared, and a reload never forgets (TD-296,
 * 2026-09-28). Called once by each Programme-scope LIST page: Overview, Applications and
 * Configuration directly; Payments and Spending through `useGiftGate`, which must not decide
 * before this has read the address bar.
 *
 * Two jobs, and the difference between them is the whole design:
 *
 *   1. **READ ONCE, ON MOUNT.** `?programme=<code>` goes into the scope's `select` — so it OUTRANKS
 *      whatever the person had picked before (the link is the more specific instruction) and then
 *      meets the scope's own guard: a code not in `choices` resolves to NOTHING and the page asks
 *      or redirects, exactly as with no code at all. It is never read again while the page stays
 *      mounted; after mount the crumb is the control.
 *   2. **AFTER MOUNT, THE QUERY FOLLOWS THE CRUMB — with `router.replace`, never `push`.** When the
 *      gift changes (the crumb's switch, the page's own question), the address bar is rewritten in
 *      place so it keeps telling the truth, and NO history entry is added: Back leaves the page, it
 *      does not become a gift-switcher. It writes only on a CHANGE of `chosen` after mount: a page
 *      whose gift was already known when it mounted (moving inside the console) is left as it
 *      arrived. ⚠ On a REAL fresh load the scopes list arrives AFTER mount, so `chosen` goes '' →
 *      the gift — and on a single-gift tenant that IS a change: the only gift is written into the
 *      address bar, once, in place (review F4; a test pins it). A link that already named the gift
 *      is not rewritten (`giftIn(search) === chosen`).
 *
 * Returns `ready`: the address bar has been read, and — when it named a gift — the shell's scopes
 * list has settled, so the name can be recognised. Until then a page must not fetch or decide: a
 * shared link would otherwise flash every gift's list (or bounce) before its own gift applied.
 *
 * ⚠ `window.location`, NOT `useSearchParams`, as `?tab=` on Configuration already does: this runs
 * inside PAGE files, where `useSearchParams` needs a Suspense boundary or `next build` refuses
 * (docs/lessons.md, F7c). Reading once on mount is the whole need.
 *
 * ⚠ STILL DISPLAY STATE. No cookie, no header, nothing stored; the code reaches an endpoint only
 * through the page's explicit `?programme=`, which the server re-fences on the caller's own
 * organisation. A client ignoring the query reaches what it reached before.
 */
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'

import { giftIn, withGift } from '@/lib/giftHref'
import { useProgrammeScope } from '@/lib/programmeScopeCore'

export function useGiftInUrl(): boolean {
  const { select, chosen, settled, unrecognised } = useProgrammeScope()
  const router = useRouter()
  // `null` until the address bar has been read; then the code it named, or ''.
  const [asked, setAsked] = useState<string | null>(null)

  // ONCE per mount — the ref, not the dependency list, is what makes it once: re-reading would let
  // the address bar overrule the crumb it is meant to follow. (`select` is stable anyway.)
  const read = useRef(false)
  useEffect(() => {
    if (read.current) return
    read.current = true
    const code = giftIn(window.location.search)
    if (code) select(code)
    setAsked(code)
  }, [select])

  // ⚠ AN UNRECOGNISED CODE IS JUDGED ONCE, THEN FORGOTTEN (adversarial review F2). It has to be
  // held as the pick while this page is open — that is what makes it "no gift" here, and what lets
  // it resolve if the list reloads with it. But left stored, a mistyped link poisoned the session:
  // on a single-gift tenant every later plain Payments visit redirected again and the rail hid the
  // money rows. So when the page goes, a pick the list STILL does not recognise is cleared; a real
  // pick made meanwhile (the crumb, the page's question) is recognised, and is left alone.
  const scopeNow = useRef({ unrecognised, select })
  scopeNow.current = { unrecognised, select }
  useEffect(() => () => {
    if (scopeNow.current.unrecognised) scopeNow.current.select('')
  }, [])

  // What `chosen` was when the page first knew its answer; a later difference is a switch.
  const was = useRef<string | null>(null)
  useEffect(() => {
    if (asked === null) return
    if (was.current === null) { was.current = chosen; return }
    if (!chosen || chosen === was.current) return
    was.current = chosen
    const { pathname, search } = window.location
    if (giftIn(search) === chosen) return
    router.replace(withGift(pathname + search, chosen), { scroll: false })
  }, [asked, chosen, router])

  return asked !== null && (asked === '' || settled)
}

'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { useT } from '@/lib/i18n'
import { bannerKey, dismiss, isDismissed, type DismissScope } from '@/lib/topBanner'
import type { CompletionKey, ProfileCompletion } from '@/lib/admin-api'
import { getOverdueSummary, type OverdueSummary } from '@/lib/admin-api/invoices'
import { formatMyr } from '@/lib/billingCosts'
import { TopBanner, type BannerTone } from './TopBanner'

/**
 * The console's top-banner SLOT (staff nudges, 2026-11-08): under the top bar on every admin page,
 * ONE banner at a time (decision 7). Lazily loaded by the shell (`LazyShellBanners`), so its weight is
 * off every route's first load.
 *
 * Each candidate names its tone, text, link and how its X hides it (`lib/topBanner` `DismissScope`);
 * the FIRST candidate that applies and was not hidden shows. Phase B puts the red overdue banner
 * FIRST in `candidates` (decision 7: overdue wins), with `{ kind: 'signIn', stamp }`.
 *
 * The profile banner (decision 4): blue; when the SERVER says an important item is missing
 * (`completion.important_missing`: photo, phone, a mentor's area — never derived here); not on the
 * Profile page itself; the X hides it for 7 days in this browser, for this account; it returns while
 * still incomplete and is gone once filled.
 *
 * The overdue banner (decisions 5-7, Phase B): red, FIRST; the server's summary of the caller's own
 * organisation (`GET billing/overdue/`, the ONE rule in `invoice_overdue.py` — never derived here):
 * the oldest overdue invoice, what is owed, how many days late, "and N more"; "View invoice" opens
 * Billing; the X hides it until the next sign-in (`signIn` scope, stamped with this sign-in); gone once
 * paid or declared. Asked only while the shell's billing probe is live (the same people the server lets
 * read invoices; it still refuses everyone else), and asked again on entering or leaving Billing, so a
 * declaration made there clears it.
 *
 * ⚠ Storage is read only after mount (`mounted`), so the server render and the first browser render
 * agree (hydration): no banner is painted until then.
 */
export interface ShellBannersProps {
  pathname: string
  /** The signed-in account (`admin/role/` `admin_id`): dismissals are kept per account. */
  accountId: number | null | undefined
  /** `admin/me/` `completion` (null for a super, or until it arrives). */
  completion: ProfileCompletion | null | undefined
  profileHref: string
  /** The admin bearer token, to ask for the overdue summary. */
  token?: string | null
  /** The shell's billing probe answered (`useNavProbes`): only then is the overdue summary asked for. */
  billingLive?: boolean
  /** Names THIS sign-in (the session user's `last_sign_in_at`): the overdue X lasts until it changes. */
  signInStamp?: string | null
}

interface Candidate {
  id: string
  tone: BannerTone
  text: ReactNode
  link?: { href: string; label: string }
  dismissLabel: string
  scope: DismissScope
}

export const PROFILE_DISMISS: DismissScope = { kind: 'days', days: 7 }
export const BILLING_HREF = '/admin/billing'

/** "a, b and c" — the reader's own word for "and". */
export function joinList(items: string[], and: string): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} ${and} ${items[items.length - 1]}`
}

export default function ShellBanners(
  { pathname, accountId, completion, profileHref, token, billingLive, signInStamp }: ShellBannersProps,
) {
  const { t } = useT()
  const [mounted, setMounted] = useState(false)
  // Hidden in THIS page view, whatever storage says (a browser that refuses storage, or no stamp).
  const [hiddenNow, setHiddenNow] = useState<string[]>([])
  const [overdue, setOverdue] = useState<OverdueSummary | null>(null)
  const onBilling = pathname === BILLING_HREF || pathname.startsWith(`${BILLING_HREF}/`)
  useEffect(() => { setMounted(true) }, [])
  useEffect(() => {
    if (!token || !billingLive) { setOverdue(null); return }
    let live = true
    // A refusal (403 / dark 404) or a blip is simply "no banner": a nudge never breaks the console.
    getOverdueSummary({ token })
      .then((d) => { if (live) setOverdue(d.overdue ?? null) })
      .catch(() => { if (live) setOverdue(null) })
    return () => { live = false }
  }, [token, billingLive, onBilling])
  if (!mounted || accountId == null) return null

  const candidates: Candidate[] = []
  if (overdue) {
    // Decision 7: overdue FIRST. Text, link and X as the owner-approved mock-up.
    const facts = { number: overdue.number, amount: formatMyr(overdue.balance_myr), days: String(overdue.days_overdue) }
    const more = overdue.more > 0
      ? ` ${t(overdue.more > 1 ? 'admin.nudge.overdueMoreMany' : 'admin.nudge.overdueMoreOne', { count: String(overdue.more) })}`
      : ''
    candidates.push({
      id: 'overdue', tone: 'critical',
      text: (<><strong className="font-semibold">{t('admin.nudge.overdueTitle')}</strong>{' '}
        {t(overdue.days_overdue > 1 ? 'admin.nudge.overdueMany' : 'admin.nudge.overdueOne', facts)}{more}</>),
      link: { href: BILLING_HREF, label: t('admin.nudge.overdueLink') },
      dismissLabel: t('admin.nudge.overdueHide'),
      scope: { kind: 'signIn', stamp: signInStamp ?? '' },
    })
  }
  const missing: CompletionKey[] = completion?.important_missing ?? []
  const onProfile = pathname === profileHref || pathname.startsWith(`${profileHref}/`)
  if (missing.length && !onProfile) {
    const items = joinList(missing.map((k) => t(`admin.nudge.item.${k}`)), t('admin.nudge.and'))
    candidates.push({
      id: 'profile', tone: 'info',
      text: `${t('admin.nudge.missing', { items })} ${t(missing.length > 1 ? 'admin.nudge.helpMany' : 'admin.nudge.helpOne')}`,
      link: { href: profileHref, label: t('admin.nudge.link') },
      dismissLabel: t('admin.nudge.hide7'),
      scope: PROFILE_DISMISS,
    })
  }

  const shown = candidates.find((c) => !hiddenNow.includes(c.id) && !isDismissed(bannerKey(c.id, accountId), c.scope))
  if (!shown) return null
  return (
    <TopBanner tone={shown.tone} link={shown.link} dismissLabel={shown.dismissLabel}
      testId={`top-banner-${shown.id}`}
      onDismiss={() => {
        dismiss(bannerKey(shown.id, accountId), shown.scope)
        setHiddenNow((h) => [...h, shown.id])
      }}>
      {shown.text}
    </TopBanner>
  )
}

'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { useT } from '@/lib/i18n'
import { bannerKey, dismiss, isDismissed, type DismissScope } from '@/lib/topBanner'
import type { CompletionKey, ProfileCompletion } from '@/lib/admin-api'
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

/** "a, b and c" — the reader's own word for "and". */
export function joinList(items: string[], and: string): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} ${and} ${items[items.length - 1]}`
}

export default function ShellBanners({ pathname, accountId, completion, profileHref }: ShellBannersProps) {
  const { t } = useT()
  const [mounted, setMounted] = useState(false)
  const [, setTick] = useState(0)
  useEffect(() => { setMounted(true) }, [])
  if (!mounted || accountId == null) return null

  const candidates: Candidate[] = []
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

  const shown = candidates.find((c) => !isDismissed(bannerKey(c.id, accountId), c.scope))
  if (!shown) return null
  return (
    <TopBanner tone={shown.tone} link={shown.link} dismissLabel={shown.dismissLabel}
      testId={`top-banner-${shown.id}`}
      onDismiss={() => { dismiss(bannerKey(shown.id, accountId), shown.scope); setTick((n) => n + 1) }}>
      {shown.text}
    </TopBanner>
  )
}

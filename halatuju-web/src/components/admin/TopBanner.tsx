'use client'

import Link from 'next/link'
import type { ReactNode } from 'react'

/**
 * ONE banner under the console's top bar (staff nudges, 2026-11-08; the owner-approved mock-up).
 * Presentational only: the text, an optional link and the X. Which banner shows, and whether it was
 * hidden, is `ShellBanners`' job (one at a time).
 *
 * `info` is the blue profile nudge; `critical` the red overdue banner (Phase B), announced as an alert.
 * Mobile Standard: the text wraps, the link drops under it on a phone and is 44 px tall, the X is a
 * 44 x 44 target that stays at the right.
 */
export type BannerTone = 'info' | 'critical'

const TONE: Record<BannerTone, { box: string; text: string; link: string }> = {
  info: { box: 'bg-info-50 border-info-200', text: 'text-info-900', link: 'text-info-700' },
  critical: { box: 'bg-critical-50 border-critical-200', text: 'text-critical-800', link: 'text-critical-800' },
}

export interface TopBannerProps {
  tone: BannerTone
  children: ReactNode
  link?: { href: string; label: string }
  /** The X's accessible name, saying for how long ("Hide for 7 days"). */
  dismissLabel: string
  onDismiss: () => void
  testId?: string
}

export function TopBanner({ tone, children, link, dismissLabel, onDismiss, testId }: TopBannerProps) {
  const c = TONE[tone]
  return (
    <div role={tone === 'critical' ? 'alert' : 'status'} data-testid={testId}
      className={`flex items-start gap-1 border-b py-1 pl-4 pr-1 md:items-center md:gap-4 md:pl-6 md:pr-2 ${c.box}`}>
      <div className="flex min-w-0 flex-1 flex-col md:flex-row md:items-center md:gap-4">
        <p className={`min-w-0 flex-1 break-words pt-2.5 text-sm leading-snug md:pt-0 ${c.text}`}>{children}</p>
        {link && (
          <Link href={link.href}
            className={`inline-flex min-h-11 items-center self-start whitespace-nowrap text-sm font-semibold hover:underline md:self-auto md:px-2 ${c.link}`}>
            {link.label}
          </Link>
        )}
      </div>
      <button type="button" onClick={onDismiss} aria-label={dismissLabel}
        className={`inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg hover:bg-ground-100 ${c.text}`}>
        <span aria-hidden className="text-xl leading-none">×</span>
      </button>
    </div>
  )
}

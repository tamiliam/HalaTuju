'use client'

import { useState } from 'react'
import { HIGHEST_POSITIONS, updateAdminMe, type HighestPosition, type ProfileCompletion } from '@/lib/admin-api/profiles'

/**
 * Request #69 (2026-11-17, board 4 of the approved mock-up): the one-tap question in the console's
 * top-banner slot — "What is the highest position you have held?", the four choices as buttons, a line
 * on why, and the X. The same blue look as the profile banner (`TopBanner` `info`).
 *
 * One tap saves straight away through `PATCH admin/me/` (the profile's own writer; it makes the profile
 * row when there is none) and hands the server's new `completion` to `onSaved`; `ShellBanners` then
 * shows `PositionThanks` for a few seconds. A refused or failed save says so here and keeps the
 * buttons. Which banner shows, and the X's memory, are `ShellBanners`' job.
 */
const BOX = 'flex items-start gap-1 border-b border-info-200 bg-info-50 py-1 pl-4 pr-1 md:gap-4 md:pl-6 md:pr-2'
const BUTTON = 'min-h-11 rounded-lg border border-info-200 bg-ground-0 px-3 py-2 text-left text-sm font-semibold text-info-700 hover:bg-info-100 disabled:opacity-50'

export interface PositionBannerProps {
  t: (key: string, vars?: Record<string, string>) => string
  token?: string | null
  dismissLabel: string
  onDismiss: () => void
  onSaved: (completion: ProfileCompletion | null) => void
}

export function PositionBanner({ t, token, dismissLabel, onDismiss, onSaved }: PositionBannerProps) {
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)
  const pick = async (key: HighestPosition) => {
    setBusy(true); setFailed(false)
    try {
      const me = await updateAdminMe({ highest_position: key }, { token: token ?? undefined })
      onSaved(me?.completion ?? null)
    } catch {
      setFailed(true); setBusy(false)
    }
  }
  return (
    <div role="status" data-testid="top-banner-position" className={BOX}>
      <div className="min-w-0 flex-1 space-y-2 py-2 text-sm text-info-900">
        <p className="font-semibold">{t('admin.nudge.positionQuestion')}</p>
        <div className="flex flex-wrap gap-2">
          {HIGHEST_POSITIONS.map((k) => (
            <button key={k} type="button" className={BUTTON} disabled={busy} onClick={() => void pick(k)}
              data-testid={`position-choice-${k}`}>
              {t(`admin.position.${k}`)}
            </button>
          ))}
        </div>
        <p className="text-xs text-info-900">{t('admin.nudge.positionWhy')}</p>
        {failed && <p role="alert" className="text-sm text-critical-600">{t('admin.nudge.positionFailed')}</p>}
      </div>
      <button type="button" onClick={onDismiss} aria-label={dismissLabel}
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-info-900 hover:bg-ground-100">
        <span aria-hidden className="text-xl leading-none">×</span>
      </button>
    </div>
  )
}

/** "✓ Thank you. Your answer is saved on your profile." — shown after the tap, then gone by itself. */
export function PositionThanks({ text }: { text: string }) {
  return (
    <div role="status" data-testid="top-banner-position-thanks" className={BOX}>
      <p className="min-w-0 flex-1 py-2.5 text-sm font-semibold text-info-900">
        <span aria-hidden>✓ </span>{text}
      </p>
    </div>
  )
}

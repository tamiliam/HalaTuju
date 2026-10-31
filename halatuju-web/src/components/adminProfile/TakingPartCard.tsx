'use client'

import Toggle from '@/components/Toggle'
import { CardFrame, type CardProps } from './shared'

/**
 * "Taking part" — the person's own pause switch (request #10, 2026-08-02), behaviour unchanged.
 * Holders of `review`, never a super.
 *
 * ⚠ It is deliberately NOT phrased as leaving, and it is not a revoke: the account, the cases
 * already theirs, and the sign-in all stay exactly as they are. A volunteer who has to justify
 * stepping back tends to disappear instead, which is worse for everyone; this is the
 * non-pejorative way out and back.
 */
export default function TakingPartCard({ state }: CardProps) {
  const { t, draft, setRev } = state
  const paused = draft.reviewer?.paused ?? false
  return (
    <CardFrame title={t('admin.reviewer.takingPartTitle')} subtitle={t('admin.reviewer.takingPartSubtitle')}
      icon="⏸" testId="takingPart">
      <div className="flex items-start gap-3 text-sm text-ground-700">
        <Toggle on={paused} label={t('admin.reviewer.pauseLabel')} onChange={(v) => setRev({ paused: v })} />
        <span>{t('admin.reviewer.pauseLabel')}</span>
      </div>
      {paused && <p className="text-sm text-caution-700">{t('admin.reviewer.pausedNote')}</p>}
    </CardFrame>
  )
}

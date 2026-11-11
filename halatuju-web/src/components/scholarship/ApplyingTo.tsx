'use client'

/**
 * "You are applying to: <round name>" on the apply form — the round the intake named for the code
 * in force, which is the code submit sends (`useApplyGift`). Draws nothing until it is named.
 * `onChange` is passed only when another gift is open; it returns to the chooser, edits kept.
 * Kept tiny: it rides in `/scholarship/apply`'s first-load JS on every visit.
 */
import { useT } from '@/lib/i18n'

export default function ApplyingTo({ name, onChange, failed, onRetry }: {
  name: string; onChange?: () => void; failed?: boolean; onRetry?: () => void
}) {
  const { t } = useT()
  // TD-343: the intake could not be asked — say so (with a retry) instead of showing no gift in silence.
  if (!name && failed) {
    return (
      <p className="mb-3 text-sm text-caution-800" role="status" data-testid="apply-gift-failed">
        {t('scholarship.apply.giftCheckFailed')}
        {onRetry && (
          <> <button type="button" onClick={onRetry} data-testid="apply-gift-retry"
            className="font-medium text-primary-600 hover:underline">{t('scholarship.apply.giftCheckRetry')}</button></>
        )}
      </p>
    )
  }
  if (!name) return null
  return (
    <p className="mb-3 text-sm text-ground-600" data-testid="apply-gift-line">
      {t('scholarship.apply.applyingTo')} <span className="font-medium text-ground-900">{name}</span>
      {onChange && (
        <> · <button type="button" onClick={onChange} data-testid="apply-gift-change"
          className="font-medium text-primary-600 hover:underline">{t('scholarship.apply.changeGift')}</button></>
      )}
    </p>
  )
}

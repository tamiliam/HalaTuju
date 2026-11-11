/**
 * TD-463: the award page's payment-schedule sentence, composed in the reader's language from the
 * parts the server serves (`bursary_preview.payment_schedule_parts`). The server's own English
 * one-liner is what the signed agreement freezes, so it stays; this is only for the screen.
 */
import type { Locale } from '@/lib/i18n'

export interface PaymentScheduleParts {
  monthly_amount: string
  count: number
  /** 1-12, or 0 when the row names no first month. */
  start_month: number
  total: string
}

const INTL_TAG: Record<Locale, string> = { en: 'en-GB', ms: 'ms-MY', ta: 'ta-IN' }

export function monthName(month: number, locale: Locale): string {
  return new Intl.DateTimeFormat(INTL_TAG[locale], { month: 'long' }).format(new Date(2000, month - 1, 1))
}

export function scheduleSentence(
  parts: PaymentScheduleParts,
  t: (key: string, params?: Record<string, string>) => string,
  locale: Locale,
): string {
  const base = {
    amount: parts.monthly_amount,
    count: String(parts.count),
    total: parts.total,
  }
  if (parts.start_month >= 1 && parts.start_month <= 12) {
    return t('scholarship.award.bursary.scheduleLine', { ...base, month: monthName(parts.start_month, locale) })
  }
  return t('scholarship.award.bursary.scheduleLineNoStart', base)
}

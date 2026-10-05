'use client'

/**
 * "Applications closed" on a closed gift's own apply page (owner's live test, 2026-10-05).
 *
 * The link used to bounce silently to `/scholarship`, so a student on a closed gift's poster — or
 * midway through its form when the round closed — was never told why. This card says it in the
 * landing's own words, paired exactly as the landing pairs them (`app/scholarship/page.tsx`): the
 * closed label, the closed note, and "Already applied? Continue from your dashboard." One new string:
 * the opt-in button ("See programmes that are open") — the landing's "Apply" read as a contradiction.
 *
 * ⚠ OTHER OPEN GIFTS ARE OFFERED BY LINK, NEVER BY REDIRECT, AND NEVER PRE-SELECTED. `onSeeOpen` is
 * passed only when another round is open; it goes to the bare apply page (the hook's `change`, so a
 * typed form survives), where the chooser asks.
 */
import Link from 'next/link'

import { useT } from '@/lib/i18n'

export default function GiftClosed({ onSeeOpen }: { onSeeOpen?: () => void }) {
  const { t } = useT()
  return (
    <div className="bg-ground-0 border rounded-2xl p-6 shadow-sm" data-testid="apply-gift-closed">
      <h2 className="font-semibold text-ground-900 mb-2">{t('scholarship.landing.closed.btn')}</h2>
      <p className="text-ground-700">
        {t('scholarship.landing.closed.note')}{' '}
        <Link href="/dashboard" className="text-primary-600 underline font-medium">
          {t('scholarship.landing.closed.continue')}
        </Link>
      </p>
      {onSeeOpen && (
        <button type="button" onClick={onSeeOpen} className="btn-primary mt-5" data-testid="apply-gift-others">
          {t('scholarship.apply.seeOpen')} →
        </button>
      )}
    </div>
  )
}

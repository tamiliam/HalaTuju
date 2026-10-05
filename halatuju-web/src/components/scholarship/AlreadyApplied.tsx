'use client'

/**
 * "You have already applied to this programme this year" — the apply page's answer when the server
 * gate says `already_applied` (2026-10-05, TD-337): she holds a FINISHED application in this very
 * round, so the form must not let her in again, but bouncing her away would hide why.
 *
 * One new string; the link reuses the application page's own title, and the opt-in button is the
 * closed card's (`scholarship.apply.seeOpen`), passed only when another gift is open — it goes to
 * the bare apply page, where the chooser asks. Never a redirect, never a pre-selection.
 */
import Link from 'next/link'

import { useT } from '@/lib/i18n'

export default function AlreadyApplied({ onSeeOpen }: { onSeeOpen?: () => void }) {
  const { t } = useT()
  return (
    <div className="bg-ground-0 border rounded-2xl p-6 shadow-sm" data-testid="apply-already-applied">
      <p className="text-ground-700">{t('scholarship.apply.alreadyApplied')}</p>
      <div className="mt-5 flex flex-wrap gap-3">
        <Link href="/scholarship/application" className="btn-primary">{t('scholarship.application.title')} →</Link>
        {onSeeOpen && (
          <button type="button" onClick={onSeeOpen} className="btn-secondary" data-testid="apply-already-others">
            {t('scholarship.apply.seeOpen')}
          </button>
        )}
      </div>
    </div>
  )
}

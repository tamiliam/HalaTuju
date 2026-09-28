'use client'

// "Which gift?" — shown by a Programme-scope tab when the answer is not yet known.
//
// ⚠ THIS EXISTS SO NOTHING PICKS SILENTLY. With several gifts and no choice made, the honest
// screen is a question: an admin who thinks they are editing Sabah's rules while looking at
// BrightPath's would change who qualifies for a live programme. It is the same refusal
// `resolve_open_cohort` makes on the student's side (PF-1) — raise rather than guess — and the
// same shape the Layer 0 configuration endpoint already returns as `programme_required`.
//
// Choosing here goes through the breadcrumb switcher's own context, so the crumb at the top of the
// page updates with it. One selection, two places showing it, no second source of truth.

import { useT } from '@/lib/i18n'
import { useProgrammeScope } from '@/lib/programmeScope'
import type { AdminProgramme } from '@/lib/admin-api'

function Box({ options, onSelect }: {
  options: ReadonlyArray<{ code: string; label: string }>
  onSelect: (code: string) => void
}) {
  const { t } = useT()

  return (
    <div className="mt-6 rounded-xl border border-ground-200 bg-ground-0 p-4" data-testid="choose-programme">
      <p className="text-sm font-medium text-ground-800">{t('admin.programmeScope.choose')}</p>
      <p className="mt-0.5 text-xs text-ground-500">{t('admin.programmeScope.chooseHint')}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {options.map((p) => (
          <button key={p.code} type="button" onClick={() => onSelect(p.code)}
            className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm hover:bg-ground-50">
            {p.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function ChooseProgramme(
  { programmes, onSelect }: { programmes: AdminProgramme[]; onSelect: (code: string) => void },
) {
  return <Box options={programmes.map((p) => ({ code: p.code, label: p.name_en }))} onSelect={onSelect} />
}

/**
 * The same box, fed from the breadcrumb's OWN list and answered through its own `select`.
 *
 * ⚠ FOR THE MONEY PAGES (Payments, Spending — 2026-09-28), and it cannot use the full records the
 * Configuration tabs use: `getAdminProgrammes` is org_admin-only, and a plain `admin` or `finance`
 * opens these pages too. The scopes list is what the crumb offers everybody, so the question and
 * the crumb can never offer different gifts.
 */
export function ChooseFromScope() {
  // LIVE gifts only: a draft cannot be paid from (the server 404s it), so offering one here would
  // be offering an answer that fails.
  const { live, select } = useProgrammeScope()
  return <Box options={live.map((c) => ({ code: c.code, label: c.name }))} onSelect={select} />
}

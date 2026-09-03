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
import type { AdminProgramme } from '@/lib/admin-api'

export default function ChooseProgramme(
  { programmes, onSelect }: { programmes: AdminProgramme[]; onSelect: (code: string) => void },
) {
  const { t } = useT()

  return (
    <div className="mt-6 rounded-xl border border-ground-200 bg-ground-0 p-4" data-testid="choose-programme">
      <p className="text-sm font-medium text-ground-800">{t('admin.programmeScope.choose')}</p>
      <p className="mt-0.5 text-xs text-ground-500">{t('admin.programmeScope.chooseHint')}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {programmes.map((p) => (
          <button key={p.id} type="button" onClick={() => onSelect(p.code)}
            className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm hover:bg-ground-50">
            {p.name_en}
          </button>
        ))}
      </div>
    </div>
  )
}

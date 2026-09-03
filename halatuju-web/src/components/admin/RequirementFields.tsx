'use client'

// The six shortlisting requirements, as tick boxes with an open value. Shared by the Rules tab
// (editing the round you are running) and the Intake-year form (setting them on a new round).
//
// ⚠ THE VALUE IS THE SWITCH. There is deliberately no companion on/off state: two columns can
// disagree — on-but-blank, off-but-4 — and one cannot, so ticking writes a value and clearing the
// value unticks it (Sabah S2a). Do not "improve" this into a boolean plus a number.
//
// ⚠ `Req` IS AT MODULE SCOPE AND MUST STAY THERE. Declared inside a component body it is a NEW
// component type on every render, so React unmounts and remounts each input and the field loses
// focus after one character. That is exactly the defect the 2026-07-21 invite form shipped (see
// lessons.md, `Section` hoisted to module scope) and it was live here from S2b until 2026-09-03 —
// invisible to every test, because a source-shape guard cannot see focus.

import { useT } from '@/lib/i18n'
import type { RequirementDraft } from '@/lib/intakeYears'

const MINI = 'w-24 rounded-lg border border-ground-300 px-2.5 py-1.5 text-sm text-right'
  + ' tabular-nums focus:border-brand-shape focus:ring-2 focus:ring-brand-shape outline-none'

function Req({ id, label, hint, value, onChange }: {
  id: string; label: string; hint?: string; value: string; onChange: (v: string) => void
}) {
  return (
    <label htmlFor={id} className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${
      value.trim() ? 'border-primary-200 bg-primary-50/50' : 'border-ground-200 bg-ground-0'}`}>
      <input type="checkbox" checked={value.trim() !== ''} aria-label={label}
        onChange={(e) => onChange(e.target.checked ? '0' : '')}
        className="h-4 w-4 shrink-0 accent-primary-600" />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-ground-900">{label}</span>
        {hint && <span className="mt-0.5 block text-xs text-ground-500">{hint}</span>}
      </span>
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder="—" inputMode="decimal" className={MINI} />
    </label>
  )
}

/** `idPrefix` keeps the two mounts apart: the Rules tab and the create dialog can both be in the
 *  DOM, and a duplicated `id` would point every label at the first one. */
export default function RequirementFields(
  { draft, onChange, idPrefix }: {
    draft: RequirementDraft
    onChange: (next: RequirementDraft) => void
    idPrefix: string
  },
) {
  const { t } = useT()
  const set = (k: keyof RequirementDraft) => (v: string) => onChange({ ...draft, [k]: v })

  return (
    <div className="space-y-2">
      <Req id={`${idPrefix}-a`} label={t('admin.years.req.spmA')}
        value={draft.aCount} onChange={set('aCount')} />
      <Req id={`${idPrefix}-b`} label={t('admin.years.req.spmB')} hint={t('admin.years.req.spmBHint')}
        value={draft.spmExtra} onChange={set('spmExtra')} />
      <Req id={`${idPrefix}-p`} label={t('admin.years.req.pngk')}
        value={draft.pngk} onChange={set('pngk')} />
      <Req id={`${idPrefix}-m`} label={t('admin.years.req.merit')} hint={t('admin.years.req.meritHint')}
        value={draft.merit} onChange={set('merit')} />
      <Req id={`${idPrefix}-i`} label={t('admin.years.req.income')}
        value={draft.income} onChange={set('income')} />
      <Req id={`${idPrefix}-c`} label={t('admin.years.req.perPerson')} hint={t('admin.years.req.perPersonHint')}
        value={draft.perPerson} onChange={set('perPerson')} />
    </div>
  )
}

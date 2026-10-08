'use client'

// The shortlisting requirements: seven tick boxes with an open value, and the "Born in" group
// (request #31) of one tick per state. Shared by the Rules tab (editing the round you are running)
// and the Intake-year form (setting them on a new round).
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
import { BIRTH_STATES, toggleBirthState } from '@/lib/birthStates'
import type { RequirementDraft } from '@/lib/intakeYears'

const BIRTH_STATE_KEYS: readonly string[] = BIRTH_STATES.map((s) => s.key)

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
  const set = (k: Exclude<keyof RequirementDraft, 'birthStates'>) => (v: string) =>
    onChange({ ...draft, [k]: v })

  return (
    <div className="space-y-2">
      <Req id={`${idPrefix}-a`} label={t('admin.years.req.spmA')}
        value={draft.aCount} onChange={set('aCount')} />
      <Req id={`${idPrefix}-b`} label={t('admin.years.req.spmB')} hint={t('admin.years.req.spmBHint')}
        value={draft.spmExtra} onChange={set('spmExtra')} />
      <Req id={`${idPrefix}-cr`} label={t('admin.years.req.spmC')} hint={t('admin.years.req.spmCHint')}
        value={draft.credits} onChange={set('credits')} />
      <Req id={`${idPrefix}-p`} label={t('admin.years.req.pngk')}
        value={draft.pngk} onChange={set('pngk')} />
      <Req id={`${idPrefix}-m`} label={t('admin.years.req.merit')} hint={t('admin.years.req.meritHint')}
        value={draft.merit} onChange={set('merit')} />
      <Req id={`${idPrefix}-i`} label={t('admin.years.req.income')}
        value={draft.income} onChange={set('income')} />
      <Req id={`${idPrefix}-c`} label={t('admin.years.req.perPerson')} hint={t('admin.years.req.perPersonHint')}
        value={draft.perPerson} onChange={set('perPerson')} />
      {/* Request #31. ⚠ NOTHING TICKED IS THE RULE SWITCHED OFF — the same switch as an empty box,
          in list form. The server reads the IC's place-of-birth code; born abroad, code 82 or an
          unreadable IC never passes a ticked rule. State names are proper names, untranslated. */}
      <fieldset data-testid={`${idPrefix}-born`} className={`rounded-lg border px-3 py-2.5 ${
        draft.birthStates.length ? 'border-primary-200 bg-primary-50/50' : 'border-ground-200 bg-ground-0'}`}>
        <legend className="sr-only">{t('admin.years.req.bornIn')}</legend>
        <span aria-hidden className="block text-sm font-medium text-ground-900">{t('admin.years.req.bornIn')}</span>
        <span className="mt-0.5 block text-xs text-ground-500">{t('admin.years.req.bornInHint')}</span>
        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 sm:grid-cols-3">
          {BIRTH_STATES.map((s) => (
            <label key={s.key} htmlFor={`${idPrefix}-born-${s.key}`}
              className="flex items-center gap-2 text-sm text-ground-800">
              <input id={`${idPrefix}-born-${s.key}`} type="checkbox"
                checked={draft.birthStates.includes(s.key)}
                onChange={(e) => onChange({
                  ...draft, birthStates: toggleBirthState(draft.birthStates, s.key, e.target.checked),
                })}
                className="h-4 w-4 shrink-0 accent-primary-600" />
              {s.name}
            </label>
          ))}
          {/* TD-373: a stored key the sixteen do not offer (only a database edit stores one — a
              wrong case, a stray word). The server enforces it, so it is SHOWN, ticked and
              labelled as stored, never hidden: saving it is refused, unticking it removes it.
              The key is quoted, in red, so a stored 'Sabah' never reads as the Sabah box. */}
          {draft.birthStates.filter((k) => !BIRTH_STATE_KEYS.includes(k)).map((k, i) => (
            <label key={`x${i}`} htmlFor={`${idPrefix}-born-x${i}`}
              className="flex items-center gap-2 text-sm text-critical-700">
              <input id={`${idPrefix}-born-x${i}`} type="checkbox" checked
                onChange={() => onChange({
                  ...draft, birthStates: toggleBirthState(draft.birthStates, k, false),
                })}
                className="h-4 w-4 shrink-0 accent-primary-600" />
              <span className="font-mono">{`"${k}"`}</span>
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  )
}

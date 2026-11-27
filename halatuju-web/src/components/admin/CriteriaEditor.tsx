'use client'

// The criteria editor (criteria editor Sprint 4, design v9). It replaces the seven-box
// RequirementFields: it edits the intake's stored criteria TREE through `criteriaTree.ts`.
//
// Owner copy rules (final): no section numbers, no section subtitles, no AND/THEN between
// sections (sections always join by "and"), the course-start card has no heading and only flags,
// the income test is said in the gift's own cut-off words (never a programme label), and every
// on/off is the site Toggle - never a tick box.
//
// ⚠ Sub-components live at module scope: one defined inside the editor is a new component on
// every render, so its input would lose focus on each key press.

import { useT } from '@/lib/i18n'
import Toggle from '@/components/Toggle'
import InfoTip from '@/components/InfoTip'
import { BIRTH_STATES, toggleBirthState } from '@/lib/birthStates'
import { GRADES, nextGrade, serverProblemKey, type Problem, type EditorState, type Grade, type GradeRow, type ResultsJoin, type IncomeJoin } from '@/lib/criteriaTree'

type T = (key: string, vars?: Record<string, string>) => string

// One width for every value box on the right of a row (tests, grade rules, course start: owner,
// 2026-11-27), so the boxes line up down the screen.
const INPUT = 'w-28 rounded-lg border border-ground-300 px-3 py-2 text-sm disabled:bg-ground-100 disabled:text-ground-400'

function TestCard({ on, onToggle, title, hint, value, onValue, testId, disabled }: {
  on: boolean; onToggle: (v: boolean) => void; title: string; hint?: string
  value: string; onValue: (v: string) => void; testId: string; disabled?: boolean
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-ground-200 p-3" data-testid={testId}>
      <Toggle on={on} onChange={onToggle} label={title} disabled={disabled} testId={`${testId}-switch`} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-ground-800">{title}</p>
        {hint && <p className="text-xs text-ground-500">{hint}</p>}
      </div>
      <input type="text" inputMode="decimal" aria-label={title} value={value}
        disabled={disabled || !on} onChange={(e) => onValue(e.target.value)}
        data-testid={`${testId}-value`} className={INPUT} />
    </div>
  )
}

function JoinChoice<J extends string>({ value, options, onChange, t, testId, disabled }: {
  value: J; options: readonly J[]; onChange: (v: J) => void; t: T; testId: string; disabled?: boolean
}) {
  return (
    // On the right of the row, like the other inputs (owner, 2026-11-27).
    <div className="mt-2 flex flex-wrap items-center justify-end gap-2 text-sm" data-testid={testId}>
      <span className="text-ground-600">{t('admin.criteria.join.label')}</span>
      <div role="radiogroup" aria-label={t('admin.criteria.join.label')} className="inline-flex flex-wrap rounded-lg border border-ground-300 p-0.5">
        {options.map((o) => (
          <button key={o} type="button" role="radio" aria-checked={value === o} disabled={disabled}
            onClick={() => onChange(o)} data-testid={`${testId}-${o}`}
            className={`rounded-md px-3 py-1.5 ${value === o ? 'bg-brand-fill text-brand-fill-ink' : 'text-ground-700'}`}>
            {t(`admin.criteria.join.${o}`)}
          </button>
        ))}
      </div>
    </div>
  )
}

function GradeRowLine({ row, index, onChange, onRemove, t, disabled }: {
  row: GradeRow; index: number; onChange: (r: GradeRow) => void; onRemove: () => void; t: T; disabled?: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm" data-testid={`grade-row-${index}`}>
      <span>{t(index === 0 ? 'admin.criteria.grades.first' : 'admin.criteria.grades.next')}</span>
      <input type="text" inputMode="numeric" value={row.count} disabled={disabled}
        aria-label={t('admin.criteria.grades.count')} data-testid={`grade-row-${index}-count`}
        onChange={(e) => onChange({ ...row, count: e.target.value })} className={INPUT} />
      <span>{t('admin.criteria.grades.subjectsAt')}</span>
      <select value={row.grade} disabled={disabled} aria-label={t('admin.criteria.grades.grade')}
        data-testid={`grade-row-${index}-grade`} onChange={(e) => onChange({ ...row, grade: e.target.value as Grade })}
        className={INPUT}>
        {GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
      </select>
      <span>{t('admin.criteria.grades.orBetter')}</span>
      <button type="button" onClick={onRemove} disabled={disabled} aria-label={t('admin.criteria.grades.remove')}
        data-testid={`grade-row-${index}-remove`} className="px-2 text-ground-500 hover:text-critical-600">×</button>
    </div>
  )
}

function Group({ title, on, onToggle, testId, children, disabled }: {
  title: string; on: boolean; onToggle: (v: boolean) => void; testId: string
  children: React.ReactNode; disabled?: boolean
}) {
  return (
    <div className="rounded-xl border border-ground-200 p-3" data-testid={testId}>
      <div className="flex items-center gap-3">
        <Toggle on={on} onChange={onToggle} label={title} disabled={disabled} testId={`${testId}-switch`} />
        <p className="text-sm font-semibold text-ground-800">{title}</p>
      </div>
      {on && <div className="mt-3 space-y-3">{children}</div>}
    </div>
  )
}

/** The server's `bad_criteria` problems, in the admin's language: a known string shows the
 *  screen's own reason; an unknown one is shown as sent, under a "technical detail" label. */
export function ServerProblemList({ problems, testId }: { problems: string[]; testId: string }) {
  const { t } = useT()
  const known = [...new Set(problems.map(serverProblemKey).filter((k): k is Problem => k !== null))]
  const unknown = problems.filter((p) => serverProblemKey(p) === null)
  return (
    <div className="mt-3 text-sm text-critical-600" data-testid={testId}>
      {known.length > 0 && (
        <ul className="list-disc pl-5">
          {known.map((k) => <li key={k}>{t(`admin.criteria.problem.${k}`)}</li>)}
        </ul>
      )}
      {unknown.length > 0 && (
        <div className="mt-2" data-testid={`${testId}-technical`}>
          <p className="text-xs font-medium text-ground-600">{t('admin.criteria.technical')}</p>
          <ul className="list-disc pl-5 font-mono text-xs">
            {unknown.map((p) => <li key={p}>{p}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

// Strict to loose (owner, 2026-11-27): all of these | their highest result | any one of these.
export const RESULTS_JOINS: readonly ResultsJoin[] = ['all', 'own', 'any']
export const INCOME_JOINS: readonly IncomeJoin[] = ['all', 'any']

export default function CriteriaEditor({ state, onChange, disabled = false, idPrefix = 'crit' }: {
  state: EditorState; onChange: (s: EditorState) => void; disabled?: boolean; idPrefix?: string
}) {
  const { t } = useT()
  const set = (patch: Partial<EditorState>) => onChange({ ...state, ...patch })
  const setRow = (i: number, r: GradeRow) => set({ rows: state.rows.map((x, j) => (j === i ? r : x)) })
  const spmNothingOn = state.rows.length === 0 && !state.spmMeritOn

  return (
    <div className="space-y-6" data-testid={`${idPrefix}-editor`}>
      <section>
        <h3 className="text-sm font-semibold text-ground-900">{t('admin.criteria.results')}</h3>
        {state.postOn && state.spmOn && (
          <JoinChoice value={state.resultsJoin} options={RESULTS_JOINS} t={t} disabled={disabled}
            testId={`${idPrefix}-results-join`} onChange={(v) => set({ resultsJoin: v })} />
        )}
        <div className="mt-3 space-y-3">
          <Group title={t('admin.criteria.post.title')} on={state.postOn} disabled={disabled}
            testId={`${idPrefix}-post`} onToggle={(v) => set({ postOn: v })}>
            <TestCard on={state.pngkOn} title={t('admin.criteria.post.pngk')} hint={t('admin.criteria.post.pngkHint')}
              value={state.pngk} testId={`${idPrefix}-pngk`} disabled={disabled}
              onToggle={(v) => set({ pngkOn: v })} onValue={(v) => set({ pngk: v })} />
            <TestCard on={state.postMeritOn} title={t('admin.criteria.merit')} hint={t('admin.criteria.post.meritHint')}
              value={state.postMerit} testId={`${idPrefix}-post-merit`} disabled={disabled}
              onToggle={(v) => set({ postMeritOn: v })} onValue={(v) => set({ postMerit: v })} />
          </Group>
          <Group title={t('admin.criteria.spm.title')} on={state.spmOn} disabled={disabled}
            testId={`${idPrefix}-spm`} onToggle={(v) => set({ spmOn: v })}>
            <div className="rounded-xl border border-ground-200 p-3" data-testid={`${idPrefix}-grades`}>
              <div className="space-y-2">
                {state.rows.map((r, i) => (
                  <GradeRowLine key={i} row={r} index={i} t={t} disabled={disabled}
                    onChange={(nr) => setRow(i, nr)}
                    onRemove={() => set({ rows: state.rows.filter((_, j) => j !== i) })} />
                ))}
                {state.rows.length === 0 && (
                  <p className="text-xs text-ground-500">{t('admin.criteria.grades.none')}</p>
                )}
              </div>
              <button type="button" disabled={disabled} data-testid={`${idPrefix}-add-grade`}
                onClick={() => set({ rows: [...state.rows, { count: '', grade: nextGrade(state.rows) }] })}
                className="mt-2 text-sm font-medium text-brand-ink hover:underline">
                {t('admin.criteria.grades.add')}
              </button>
            </div>
            <TestCard on={state.spmMeritOn} title={t('admin.criteria.merit')} hint={t('admin.criteria.spm.meritHint')}
              value={state.spmMerit} testId={`${idPrefix}-spm-merit`} disabled={disabled}
              onToggle={(v) => set({ spmMeritOn: v })} onValue={(v) => set({ spmMerit: v })} />
            {spmNothingOn && <p className="text-xs text-ground-500">{t('admin.criteria.spm.passAll')}</p>}
          </Group>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-ground-900">{t('admin.criteria.income.title')}</h3>
        {state.householdOn && state.perPersonOn && (
          <JoinChoice value={state.incomeJoin} options={INCOME_JOINS} t={t} disabled={disabled}
            testId={`${idPrefix}-income-join`} onChange={(v) => set({ incomeJoin: v })} />
        )}
        <div className="mt-3 space-y-3">
          <TestCard on={state.householdOn} title={t('admin.criteria.income.household')}
            value={state.household} testId={`${idPrefix}-household`} disabled={disabled}
            onToggle={(v) => set({ householdOn: v })} onValue={(v) => set({ household: v })} />
          <TestCard on={state.perPersonOn} title={t('admin.criteria.income.perPerson')}
            value={state.perPerson} testId={`${idPrefix}-per-person`} disabled={disabled}
            onToggle={(v) => set({ perPersonOn: v })} onValue={(v) => set({ perPerson: v })} />
        </div>
      </section>

      <section>
        <h3 className="flex items-center gap-1 text-sm font-semibold text-ground-900">
          {t('admin.criteria.bornIn.title')}
          <InfoTip text={t('admin.criteria.bornIn.hint')} />
        </h3>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {BIRTH_STATES.map((s) => (
            <div key={s.key} className="flex items-center gap-3 text-sm">
              <Toggle on={state.bornIn.includes(s.key)} label={s.name} disabled={disabled}
                testId={`${idPrefix}-born-${s.key}`}
                onChange={(v) => set({ bornIn: toggleBirthState(state.bornIn, s.key, v) })} />
              <span>{s.name}</span>
            </div>
          ))}
        </div>
      </section>

      {/* The course-start card: no heading (owner), its own switch (v9). It only flags a student,
          never declines. Laid out like a TestCard: the box sits on the right of its label. */}
      <div className="flex items-start gap-3 rounded-xl border border-ground-200 p-3" data-testid={`${idPrefix}-start`}>
        <Toggle on={state.startOn} onChange={(v) => set({ startOn: v })} label={t('admin.criteria.startYears')}
          disabled={disabled} testId={`${idPrefix}-start-switch`} />
        <p className="flex min-w-0 flex-1 items-center gap-1 text-sm font-medium text-ground-800">
          <label htmlFor={`${idPrefix}-start-years`}>{t('admin.criteria.startYears')}</label>
          <InfoTip text={t('admin.criteria.startYearsHint')} />
        </p>
        <input id={`${idPrefix}-start-years`} type="text" value={state.startYears} disabled={disabled || !state.startOn}
          onChange={(e) => set({ startYears: e.target.value })} data-testid={`${idPrefix}-start-years`}
          className={INPUT} />
      </div>
    </div>
  )
}

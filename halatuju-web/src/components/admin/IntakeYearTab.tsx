'use client'

// Programme → Configuration → Intake year. Was its own page and its own menu row for one sprint
// (Sabah S2b); became a tab on 2026-09-03.
//
// ⚠ WHY IT IS NOT A PAGE (owner, 2026-09-03). "The intake year is merely a column within the
// application table, and not a superset" — an application carries a `cohort` column, only one
// round may be open at a time, and the year row's other job is holding the six thresholds the
// Rules tab edits. So a year is neither a level above the applications nor a sibling of the gift's
// settings: it is part of what you configure about the gift, and it sits beside the rules that
// live on the very same row. `/admin/programme/years` redirects here.
//
// ⚠ IT IS TAB ONE NOW (2026-09-06), and being a CHILD is why. The rules the next tab edits are
// COLUMNS ON THIS ROW, so a gift created a minute ago has nothing for them to write to — opening a
// brand-new gift on Rules landed a person on the one screen that could not work yet. Setup order
// follows data order; the year exists first because everything else is stored on it.
//
// Three things are deliberate and must not be "simplified":
//
// ⚠ CREATING NEVER OPENS. The button says so. `is_open` defaults to TRUE on the model, so a form
// that just created a row would let real students in with the same press. Opening is the moment an
// intake becomes real, and it gets its own action.
//
// ⚠ THE WINDOW DESCRIBES; IT OPENS NOTHING (owner, 2026-09-06). `opens_on`/`closes_on` say when
// the round is MEANT to run and are shown to whoever reads this screen. A person still presses
// Open. A clock would fire whether or not the gift's rules and questions had been finished.
//
// ⚠ ONE OPEN ROUND PER **GIFT PROGRAMME** — not per organisation (owner, 2026-09-06: *"if the org
// has two programmes, there could be two open applications"*), and the server refuses a second
// round of the SAME gift. `resolve_open_cohort` RAISES when it cannot tell which round a student
// means — but that refusal reaches the STUDENT, so the apply page now asks them before the form.
// This screen shows which round of this gift is open before the admin creates the ambiguity.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useSelectedProgramme } from '@/lib/useSelectedProgramme'
import InfoBox from '@/components/InfoBox'
import { formatDate } from '@/lib/formatDate'
import ChooseProgramme from '@/components/admin/ChooseProgramme'
import RequirementFields from '@/components/admin/RequirementFields'
import {
  getAdminIntakeYears, createAdminIntakeYear, updateAdminIntakeYear, type AdminIntakeYear,
} from '@/lib/admin-api'
// ⚠ In `lib`, not beside the page: a page module may carry NO export beyond its default, and
// `next build` is the only gate that says so (Layer 1 F7c, three times).
import { draftToRequirements, EMPTY_REQUIREMENTS, type RequirementDraft } from '@/lib/intakeYears'

const CODE_OK = /^[a-z0-9][a-z0-9-]{1,49}$/

const EMPTY_FORM = { year: '', code: '', name: '', opens_on: '', closes_on: '' }

export default function IntakeYearTab() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const { programme, programmes, loading, mustChoose, select } = useSelectedProgramme()

  const [years, setYears] = useState<AdminIntakeYear[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [draft, setDraft] = useState<RequirementDraft>(EMPTY_REQUIREMENTS)

  const programmeId = programme?.id ?? null

  const load = useCallback(async () => {
    if (!token || programmeId === null) { setYears([]); return }
    try {
      setYears((await getAdminIntakeYears(programmeId, { token })).years)
      setError('')
    } catch {
      setError(t('admin.years.loadFailed'))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, programmeId])

  useEffect(() => { void load() }, [load])

  const openElsewhere = useMemo(() => years.find((y) => y.is_open) ?? null, [years])

  const errKey = (c?: string) =>
    c === 'bad_code' ? 'badCode'
      : c === 'code_taken' ? 'codeTaken'
        : c === 'bad_year' ? 'badYear'
          : c === 'another_year_open' ? 'anotherOpen'
            : c === 'programme_not_active' ? 'notActive'
              : c === 'name_required' ? 'nameRequired'
                // The window, named per field so the message can point at the right box. The
                // server REFUSES a backwards window rather than swapping the dates — a silent
                // swap turns a typo into a stated fact nobody was told about.
                : c === 'window_backwards' ? 'windowBackwards'
                  : c === 'opens_on' ? 'badOpensOn'
                    : c === 'closes_on' ? 'badClosesOn' : 'generic'

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('')
    try { await fn(); await load(); return true } catch (e) {
      setError(t(`admin.years.error.${errKey((e as { code?: string })?.code)}`)); return false
    } finally { setBusy(false) }
  }

  const create = async () => {
    if (programmeId === null) return
    const ok = await run(() => createAdminIntakeYear(programmeId, {
      code: form.code.trim().toLowerCase(), name: form.name.trim(), year: Number(form.year),
      // ⚠ A BLANK BOX SENDS null, NOT '' — "no window stated" is a real answer and must reach the
      // server as one. Sending an empty string would make an unstated window look like a failed
      // parse; sending nothing at all would make it impossible to CLEAR one later.
      opens_on: form.opens_on || null,
      closes_on: form.closes_on || null,
      ...draftToRequirements(draft),
    }, { token: token! }))
    if (ok) {
      setOpen(false); setForm(EMPTY_FORM); setDraft(EMPTY_REQUIREMENTS)
    }
  }

  const inputCls = 'w-full rounded-lg border border-ground-300 px-3 py-2 text-sm'
    + ' focus:border-brand-shape focus:ring-2 focus:ring-brand-shape outline-none'

  if (mustChoose) return <ChooseProgramme programmes={programmes} onSelect={select} />

  if (!loading && programmes.length === 0) {
    return (
      <p className="mt-6 rounded-2xl border border-dashed border-ground-300 px-4 py-10 text-center text-sm text-ground-400">
        {t('admin.years.noProgrammes')}
      </p>
    )
  }

  return (
    <div>
      <div className="mt-6 flex items-start justify-between gap-4">
        <p className="text-sm text-ground-600">{t('admin.years.subtitle')}</p>
        {programme && (
          <button type="button" onClick={() => { setError(''); setOpen(true) }}
            className="shrink-0 rounded-lg bg-brand-fill px-4 py-2.5 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
            + {t('admin.years.new')}
          </button>
        )}
      </div>

      {error && <div className="mt-4"><InfoBox kind="block">{error}</InfoBox></div>}

      {programme && (
        <>
          <div className="mt-4 overflow-hidden rounded-2xl border border-ground-200 bg-ground-0 shadow-sm">
            <table className="w-full text-sm">
              <thead className="border-b border-ground-200 bg-ground-50">
                <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
                  {(['year', 'name', 'window', 'applications', 'status'] as const).map((k) => (
                    <th key={k} className="px-4 py-3 font-semibold">{t(`admin.years.col.${k}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-ground-100">
                {years.map((y) => (
                  <tr key={y.id} data-testid={`year-${y.code}`}>
                    <td className="px-4 py-3 tabular-nums text-ground-700">{y.year}</td>
                    <td className="px-4 py-3 text-ground-700">{y.name}</td>
                    {/* ⚠ A ROUND WITH NO STATED WINDOW IS NORMAL, NOT BROKEN — it renders a dash,
                        never an error. Every row that predates this column has NULL, including
                        the live 2026 intake, and nothing was backfilled. */}
                    <td className="px-4 py-3 tabular-nums text-ground-600">
                      {y.opens_on || y.closes_on
                        ? `${formatDate(y.opens_on) || '—'} – ${formatDate(y.closes_on) || '—'}`
                        : '—'}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-ground-700">{y.applications}</td>
                    <td className="px-4 py-3">
                      <span className="flex flex-wrap items-center gap-3">
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                          y.is_open ? 'bg-positive-100 text-positive-800' : 'bg-ground-100 text-ground-600'}`}>
                          {t(y.is_open ? 'admin.years.open' : 'admin.years.closed')}
                        </span>
                        <button type="button" disabled={busy}
                          onClick={() => run(() => updateAdminIntakeYear(
                            y.id, { is_open: !y.is_open }, { token: token! }))}
                          className="text-xs font-medium text-primary-600 hover:underline disabled:opacity-50">
                          {t(y.is_open ? 'admin.years.close' : 'admin.years.openIt')}
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
                {years.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-ground-400">
                    {t('admin.years.empty')}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-4">
            <InfoBox kind="warning">
              {openElsewhere
                ? t('admin.years.oneOpenNamed', { code: openElsewhere.name })
                : t('admin.years.oneOpen')}
            </InfoBox>
          </div>

          {/* ⚠ THE ONWARD POINTER IS GONE, DELIBERATELY (owner, 2026-09-07: *"Why is it there?"*).
              I added it as the second half of a setup trail and got the CONDITION backwards: it
              appeared once a year EXISTED, so it appeared for ever — on a gift running its second
              intake it still read "Next: set the rules", like unfinished homework that never
              clears. Its twin on the Rules tab is correct and stays, because it appears only when
              there is NO year: a real dead end, unblocked once.

              And it was redundant even when it was right — the Rules tab is one click away,
              directly above it. Do not restore this without a condition that can turn OFF. */}
        </>
      )}

      {open && programme && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 p-4"
          onClick={() => !busy && setOpen(false)}>
          <div className="my-8 w-full max-w-lg rounded-2xl bg-ground-0 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.years.new')}</h2>

            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="y-year" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.year')}
                </label>
                <input id="y-year" inputMode="numeric" value={form.year}
                  onChange={(e) => setForm({ ...form, year: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
              <div>
                <label htmlFor="y-code" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.code')}
                </label>
                <input id="y-code" value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
            </div>
            <div className="mt-4">
              <label htmlFor="y-name" className="block text-sm font-medium text-ground-700">
                {t('admin.years.field.name')}
              </label>
              <input id="y-name" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className={`mt-1 ${inputCls}`} />
            </div>

            {/* ⚠ THE WINDOW SAYS WHEN THE ROUND RUNS. IT DOES NOT OPEN IT (owner, 2026-09-06).
                The note below is not decoration — it is the whole ruling, on the screen where
                somebody would otherwise assume a start date starts something. Both boxes are
                optional: a round with no stated window is a normal round. */}
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="y-opens" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.opensOn')}
                </label>
                <input id="y-opens" type="date" value={form.opens_on}
                  onChange={(e) => setForm({ ...form, opens_on: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
              <div>
                <label htmlFor="y-closes" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.closesOn')}
                </label>
                <input id="y-closes" type="date" value={form.closes_on}
                  onChange={(e) => setForm({ ...form, closes_on: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
            </div>
            <p className="mt-1.5 text-xs text-ground-600">{t('admin.years.windowNote')}</p>

            <hr className="mt-5 border-ground-100" />
            <p className="mt-4 text-sm font-semibold text-ground-700">{t('admin.years.reqTitle')}</p>
            <p className="mt-0.5 text-xs text-ground-500">{t('admin.years.reqHint')}</p>

            <div className="mt-3">
              <RequirementFields draft={draft} onChange={setDraft} idPrefix="new" />
            </div>

            {error && <p className="mt-3 text-sm text-critical-600">{error}</p>}

            <div className="mt-5 flex items-center justify-end gap-3">
              <button type="button" onClick={() => setOpen(false)} disabled={busy}
                className="text-sm font-medium text-ground-500 hover:text-ground-700">
                {t('common.cancel')}
              </button>
              {/* The label carries the promise: creating never opens. */}
              <button type="button" onClick={create}
                disabled={busy || !form.name.trim() || !form.year.trim()
                  || !CODE_OK.test(form.code.trim().toLowerCase())}
                className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('admin.years.createClosed')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

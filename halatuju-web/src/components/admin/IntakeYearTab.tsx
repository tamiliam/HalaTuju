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
// ⚠ THE WINDOW DESCRIBES; IT OPENS NOTHING (owner, 2026-09-06, RE-AFFIRMED 2026-09-07). Both
// halves of that are load-bearing and they arrived a day apart.
//   · It opens nothing: a person still presses Open, because a clock would fire whether or not the
//     gift's rules and questions had been finished — real students applying against a half-built
//     form. On 2026-09-07 the owner asked for dates that DO control opening; the ruling they made
//     the day before was put back to them with that reason, plus two gaps a clock would hit today
//     (every existing round has NULL dates, and nothing runs on a schedule for this), and they
//     chose to keep it. Do not build the clock without re-opening that conversation.
//   · It DESCRIBES, and until 2026-09-07 it did not even do that — the dates printed as a bare
//     range that said nothing, which the owner read as furniture, the same complaint that killed
//     "Next: set the rules". So the dates now SPEAK (`windowState` puts a plain-words line under
//     the range) and they WARN (opening outside the stated window asks first). They still decide
//     nothing, and the server still accepts an out-of-window open without argument.
//
// ⚠ A ROUND'S YEAR AND SHORT CODE ARE FIXED; ITS NAME AND WINDOW ARE NOT. The edit dialog offers
// exactly what `AdminIntakeYearDetailView.patch` accepts. The code is the round's permanent
// identifier (applications and links hang off it) and the year is what the list sorts on — the
// endpoint has never taken either, and the dialog says so on screen rather than offering a box
// that would be silently ignored.
//
// ⚠ ONE OPEN ROUND PER **GIFT PROGRAMME** — not per organisation (owner, 2026-09-06: *"if the org
// has two programmes, there could be two open applications"*), and the server refuses a second
// round of the SAME gift. `resolve_open_cohort` RAISES when it cannot tell which round a student
// means — but that refusal reaches the STUDENT, so the apply page now asks them before the form.
// This screen shows which round of this gift is open before the admin creates the ambiguity.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import TableFrame from '@/components/admin/TableFrame'
import { useSelectedProgramme } from '@/lib/useSelectedProgramme'
import InfoBox from '@/components/InfoBox'
import { formatDate } from '@/lib/formatDate'
import ChooseProgramme from '@/components/admin/ChooseProgramme'
import RequirementFields from '@/components/admin/RequirementFields'
import {
  getAdminIntakeYears, createAdminIntakeYear, updateAdminIntakeYear, finishAdminIntakeYear,
  type AdminIntakeYear,
} from '@/lib/admin-api'
import { Menu, MenuHeading, MenuItem } from '@/components/admin/Menu'
// ⚠ In `lib`, not beside the page: a page module may carry NO export beyond its default, and
// `next build` is the only gate that says so (Layer 1 F7c, three times).
import {
  draftToRequirements, EMPTY_REQUIREMENTS, outsideWindow, todayIso, windowState,
  type RequirementDraft, type WindowState,
} from '@/lib/intakeYears'

const CODE_OK = /^[a-z0-9][a-z0-9-]{1,49}$/

const EMPTY_FORM = { year: '', code: '', name: '', opens_on: '', closes_on: '' }

const EMPTY_EDIT = { name: '', opens_on: '', closes_on: '' }

// ⚠ THE BROWSER'S YEAR SLOT TAKES SIX DIGITS (owner, 2026-09-08, having typed `07/07/202026`).
// Chrome's date input accepts a year up to 275760, so typing over an existing value produces a
// well-formed but absurd date. The server already refuses it — `date.fromisoformat` wants four
// digits — but the message it can give back is only "enter a valid closing date", which does not
// say the YEAR is the problem. `min`/`max` make the browser itself refuse, at the keystroke.
const DATE_MIN = '2000-01-01'
const DATE_MAX = '2099-12-31'

/**
 * The "When it runs" cell: the stated dates, and what they MEAN today.
 *
 * ⚠ A ROUND WITH NO STATED WINDOW IS NORMAL, NOT BROKEN — it renders a dash and nothing else,
 * never an error and never a state line. Every row that predates this column has NULL, including
 * the live 2026 intake, and nothing was backfilled.
 *
 * ⚠ THE RANGE STAYS ABOVE THE PLAIN-WORDS LINE, both of them. The line alone would lose the dates
 * an admin came to read; the dates alone were what the owner reported as furniture. The line is
 * muted because it is derived — the dates are the record.
 *
 * ⚠ AT MODULE SCOPE, not inside the tab's body. A component defined inside another component is a
 * new type on every render, so React unmounts and remounts its subtree — the identical defect that
 * made the requirement inputs lose focus on each keystroke (2026-09-03) and the invite form before
 * that (2026-07-21).
 */
function WindowCell({ year, today, t }: {
  year: AdminIntakeYear
  today: string
  t: (k: string, p?: Record<string, string>) => string
}) {
  const state: WindowState = windowState(year, today)
  if (state.kind === 'none') return <span className="tabular-nums">—</span>
  return (
    <span className="block" data-testid={`window-${year.code}`}>
      <span className="block tabular-nums">
        {`${formatDate(year.opens_on) || '—'} – ${formatDate(year.closes_on) || '—'}`}
      </span>
      <span className="mt-0.5 block text-xs text-ground-500" data-window-state={state.kind}>
        {t(`admin.years.win.${state.kind}`)}
      </span>
    </span>
  )
}

/**
 * The round's state, and the badge IS the control — the shape the owner approved on the gift card
 * (2026-09-07) and asked for here (2026-09-08: *"the button seems odd sitting there, and at present
 * it would sit there in perpetuity"*). A round closed two months ago with 143 applications will
 * never reopen; a loose "Open applications" link beside it for ever is furniture.
 *
 * ⚠ FOUR TONES, AND NONE OF THEM IS RED. `critical` in this product means something is WRONG, and
 * every one of these is a normal point in a round's life. Same ruling as the gift card's badge.
 *
 * ⚠ THE MENU'S HEADING IS THE POINT, not decoration. "Closed" has a behaviour nobody could see:
 * no NEW applications, but anyone already started may still finish. That grace period is what the
 * 2026 intake actually ran on between 1 and 7 July, and the only place it is now stated.
 *
 * ⚠ FINISHED OFFERS NOTHING. It is terminal (owner's ruling) and the server refuses to reopen one,
 * so the menu explains rather than pretending there is a move.
 */
const ROUND_TONE: Record<AdminIntakeYear['state'], string> = {
  draft: 'bg-ground-100 text-ground-600',
  open: 'bg-positive-100 text-positive-800',
  closed: 'bg-caution-100 text-caution-800',
  finished: 'bg-info-100 text-info-800',
}

function RoundBadge({ year: y, busy, onOpen, onClose, onFinish, t }: {
  year: AdminIntakeYear
  busy: boolean
  onOpen: (y: AdminIntakeYear) => void
  onClose: (y: AdminIntakeYear) => void
  onFinish: (y: AdminIntakeYear) => void
  t: (k: string, p?: Record<string, string>) => string
}) {
  const s = y.state
  return (
    <Menu
      label={t('admin.years.state.change', { name: y.name })}
      align="left"
      width="w-72"
      trigger={
        <span data-testid={`state-${y.code}`}
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${ROUND_TONE[s]}`}>
          {t(`admin.years.state.${s}`)}
          <span aria-hidden className="text-[9px] leading-none opacity-70">▾</span>
        </span>
      }
    >
      <MenuHeading>{t(`admin.years.state.means.${s}`)}</MenuHeading>
      {s === 'open' && (
        <MenuItem onClick={() => !busy && onClose(y)}>{t('admin.years.state.closeIt')}</MenuItem>
      )}
      {(s === 'draft' || s === 'closed') && (
        <MenuItem onClick={() => !busy && onOpen(y)}>{t('admin.years.state.openIt')}</MenuItem>
      )}
      {/* Only a round that has actually taken applications can be "finished" — finishing a draft
          nobody applied to says nothing and would spend a terminal action on an empty row. */}
      {s === 'closed' && (
        <MenuItem onClick={() => !busy && onFinish(y)}>{t('admin.years.state.finishIt')}</MenuItem>
      )}
    </Menu>
  )
}

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
  /** The round being edited, and the boxes for it. Null = the dialog is shut. */
  const [editing, setEditing] = useState<AdminIntakeYear | null>(null)
  const [edit, setEdit] = useState(EMPTY_EDIT)
  /** A round the admin has asked to open AGAINST its own stated schedule, held for a confirm. */
  const [confirmOpen, setConfirmOpen] = useState<AdminIntakeYear | null>(null)
  /** A round being closed FOR GOOD, and the phrase typed to confirm it. Terminal, so it asks. */
  const [finishing, setFinishing] = useState<AdminIntakeYear | null>(null)
  const [finishPhrase, setFinishPhrase] = useState('')

  const programmeId = programme?.id ?? null
  // Read ONCE per render rather than per row, so every row on the page is judged against the same
  // day. Two rows disagreeing across a midnight tick would be a very hard bug to believe.
  const today = todayIso()

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
                    : c === 'closes_on' ? 'badClosesOn'
                      // ⚠ The three refusals a FINISH can meet. `roundFinished` is the terminal
                      // one: the server refuses to reopen, whatever a stale screen offers.
                      : c === 'round_finished' ? 'roundFinished'
                        : c === 'still_open' ? 'stillOpen'
                          : c === 'already_finished' ? 'alreadyFinished'
                            : c === 'confirm_mismatch' ? 'confirmMismatch' : 'generic'

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

  const startEdit = (y: AdminIntakeYear) => {
    setError('')
    setEditing(y)
    // ⚠ A BLANK BOX IS A REAL STATE HERE TOO. A round with no stated window loads two empty boxes
    // and, cleared, sends null — `_window_from` reads absent / empty / a date as three different
    // instructions, so a window can be WITHDRAWN, not only changed.
    setEdit({ name: y.name, opens_on: y.opens_on || '', closes_on: y.closes_on || '' })
  }

  /**
   * Has anything in the edit dialog actually changed? (Owner, 2026-09-08: *"the save is enabled
   * even though no change has been made. It should follow the platform rule."*)
   *
   * ⚠ COMPARED THE WAY IT WILL BE SENT, not the way it is typed. `saveEdit` trims the name and
   * turns a blank box into null, so a trailing space is not a change and neither is '' against a
   * null window. Comparing the raw boxes would wake the button up for a keystroke that sends
   * exactly what the server already holds.
   */
  const editDirty = !!editing && (
    edit.name.trim() !== editing.name
    || edit.opens_on !== (editing.opens_on || '')
    || edit.closes_on !== (editing.closes_on || '')
  )

  const saveEdit = async () => {
    if (!editing) return
    const ok = await run(() => updateAdminIntakeYear(editing.id, {
      name: edit.name.trim(),
      opens_on: edit.opens_on || null,
      closes_on: edit.closes_on || null,
    }, { token: token! }))
    if (ok) setEditing(null)
  }

  const setOpenState = (y: AdminIntakeYear, want: boolean) =>
    run(() => updateAdminIntakeYear(y.id, { is_open: want }, { token: token! }))

  /** Closing never asks. Opening asks only when it goes against the round's OWN stated schedule —
   *  and the answer is always allowed, because the schedule describes and the person decides. */
  const pressOpenToggle = (y: AdminIntakeYear) => {
    if (y.is_open) { void setOpenState(y, false); return }
    if (outsideWindow(windowState(y, today))) { setError(''); setConfirmOpen(y); return }
    void setOpenState(y, true)
  }

  const saveFinish = async () => {
    if (!finishing) return
    const ok = await run(() => finishAdminIntakeYear(
      finishing.id, finishPhrase.trim(), { token: token! }))
    if (ok) { setFinishing(null); setFinishPhrase('') }
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
          {/* ⚠ THE RULE COMES BEFORE THE THING IT GOVERNS (owner, 2026-09-07: *"should be on top,
              I think like other pages"*). It sat UNDER the table and was the only banner on the
              four Configuration screens that did — the Rules tab and "What we ask for" both open
              with theirs. A caution read after the control it constrains has already lost. */}
          <div className="mt-4">
            <InfoBox kind="warning">
              {openElsewhere
                ? t('admin.years.oneOpenNamed', { code: openElsewhere.name })
                : t('admin.years.oneOpen')}
            </InfoBox>
          </div>

          {/* Was a bare overflow-hidden card: on a phone the right-hand columns were CLIPPED
              with no scrollbar. TableFrame keeps the corners clipped and the scrolling separate. */}
          <TableFrame className="mt-4" minWidth={760} label={t('admin.years.subtitle')}>
            <table className="w-full text-sm">
              <thead className="border-b border-ground-200 bg-ground-50">
                <tr className="text-left text-xs uppercase tracking-wider text-ground-500">
                  {(['year', 'name', 'window', 'applications', 'status', 'actions'] as const).map((k) => (
                    <th key={k} className="px-4 py-3 font-semibold">{t(`admin.years.col.${k}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-ground-100">
                {years.map((y) => (
                  <tr key={y.id} data-testid={`year-${y.code}`}>
                    <td className="px-4 py-3 tabular-nums text-ground-700">{y.year}</td>
                    <td className="px-4 py-3 text-ground-700">{y.name}</td>
                    <td className="px-4 py-3 text-ground-600">
                      <WindowCell year={y} today={today} t={t} />
                    </td>
                    <td className="px-4 py-3 tabular-nums text-ground-700">{y.applications}</td>
                    <td className="px-4 py-3">
                      {/* ⚠ THE BADGE IS THE CONTROL. The loose Open/Close link is gone — it sat
                          beside a two-month-old closed round for ever, offering a move nobody
                          would ever make. Every move a round can make now lives in its own menu,
                          under a line saying what the state actually means. */}
                      <RoundBadge year={y} busy={busy} t={t}
                        onOpen={pressOpenToggle}
                        onClose={(r) => void setOpenState(r, false)}
                        onFinish={(r) => { setError(''); setFinishPhrase(''); setFinishing(r) }} />
                    </td>
                    <td className="px-4 py-3">
                      <button type="button" disabled={busy}
                        data-testid={`edit-${y.code}`} onClick={() => startEdit(y)}
                        className="text-xs font-medium text-primary-600 hover:underline disabled:opacity-50">
                        {t('admin.years.edit')}
                      </button>
                    </td>
                  </tr>
                ))}
                {years.length === 0 && (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-ground-400">
                    {t('admin.years.empty')}
                  </td></tr>
                )}
              </tbody>
            </table>
          </TableFrame>

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
                <input id="y-opens" type="date" min={DATE_MIN} max={DATE_MAX} value={form.opens_on}
                  onChange={(e) => setForm({ ...form, opens_on: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
              <div>
                <label htmlFor="y-closes" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.closesOn')}
                </label>
                <input id="y-closes" type="date" min={DATE_MIN} max={DATE_MAX} value={form.closes_on}
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

      {/* ── Edit a round ──────────────────────────────────────────────────────────────────────
          Name and window only. See the header note: the year and the short code are what the
          endpoint has never accepted, and offering a box the server ignores is worse than not
          offering one. Opening and closing stay on the row — this dialog changes the SCHEDULE,
          never the state. */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 p-4"
          onClick={() => !busy && setEditing(null)}>
          <div className="my-8 w-full max-w-lg rounded-2xl bg-ground-0 p-6 shadow-xl"
            data-testid="edit-year-dialog" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.years.editTitle')}</h2>
            <p className="mt-1 text-sm text-ground-600">
              {t('admin.years.editFixed', { year: String(editing.year), code: editing.code })}
            </p>

            <div className="mt-4">
              <label htmlFor="e-name" className="block text-sm font-medium text-ground-700">
                {t('admin.years.field.name')}
              </label>
              <input id="e-name" value={edit.name}
                onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                className={`mt-1 ${inputCls}`} />
            </div>

            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="e-opens" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.opensOn')}
                </label>
                <input id="e-opens" type="date" min={DATE_MIN} max={DATE_MAX} value={edit.opens_on}
                  onChange={(e) => setEdit({ ...edit, opens_on: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
              <div>
                <label htmlFor="e-closes" className="block text-sm font-medium text-ground-700">
                  {t('admin.years.field.closesOn')}
                </label>
                <input id="e-closes" type="date" min={DATE_MIN} max={DATE_MAX} value={edit.closes_on}
                  onChange={(e) => setEdit({ ...edit, closes_on: e.target.value })}
                  className={`mt-1 ${inputCls}`} />
              </div>
            </div>
            <p className="mt-1.5 text-xs text-ground-600">{t('admin.years.windowNote')}</p>

            {error && <p className="mt-3 text-sm text-critical-600">{error}</p>}

            <div className="mt-5 flex items-center justify-end gap-3">
              <button type="button" onClick={() => setEditing(null)} disabled={busy}
                className="text-sm font-medium text-ground-500 hover:text-ground-700">
                {t('common.cancel')}
              </button>
              <button type="button" onClick={saveEdit} data-testid="save-edit"
                disabled={busy || !edit.name.trim() || !editDirty}
                className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('common.save')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Closing a round FOR GOOD ─────────────────────────────────────────────────────────
          ⚠ TERMINAL, AND THE TYPED CODE IS WHY IT ASKS (owner, 2026-09-08: *"when an application
          is finished, can it be opened again? I don't think it should be"*). Nothing in the
          product clears `finished_at`; the server refuses to reopen. Same shape as deleting a
          gift — the code is printed in the dialog's own label, so typing it is closer to copying
          than to deciding, and the pause is the point.

          ⚠ IT NAMES THE PEOPLE IT WOULD SHUT OUT. A closed round still lets anyone already
          started submit; finishing ends that. `unsubmitted` is the one fact the reader cannot see
          from here, and silence would mean pressing this and quietly locking someone out. */}
      {finishing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 p-4"
          onClick={() => !busy && setFinishing(null)}>
          <div className="my-8 w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl"
            data-testid="finish-dialog" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ground-900">
              {t('admin.years.finish.title')}
            </h2>
            <p className="mt-2 text-sm text-ground-600">{t('admin.years.finish.body')}</p>
            {finishing.unsubmitted > 0 && (
              <div className="mt-3">
                <InfoBox kind="warning" >
                  <span data-testid="finish-unsubmitted">
                    {t('admin.years.finish.stranded', { n: String(finishing.unsubmitted) })}
                  </span>
                </InfoBox>
              </div>
            )}

            <label htmlFor="finish-confirm"
              className="mt-4 block text-sm font-medium text-ground-700">
              {t('admin.years.finish.typeCode', { code: finishing.code })}
            </label>
            <input id="finish-confirm" value={finishPhrase} autoComplete="off"
              onChange={(e) => setFinishPhrase(e.target.value)}
              className={`mt-1 ${inputCls}`} />

            {error && <p className="mt-3 text-sm text-critical-600">{error}</p>}

            <div className="mt-5 flex items-center justify-end gap-3">
              <button type="button" onClick={() => setFinishing(null)} disabled={busy}
                className="text-sm font-medium text-ground-500 hover:text-ground-700">
                {t('common.cancel')}
              </button>
              <button type="button" data-testid="finish-confirm-yes"
                onClick={saveFinish}
                disabled={busy || finishPhrase.trim().toLowerCase() !== finishing.code.toLowerCase()}
                className="rounded-lg bg-critical-fill px-5 py-2 text-sm font-semibold text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50">
                {t('admin.years.finish.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Opening against the round's own schedule ──────────────────────────────────────────
          ⚠ THIS ASKS; IT DOES NOT REFUSE. The server accepts an out-of-window open deliberately
          (the window describes, the person decides), so this must never grow into a gate — that
          would be a client-side rule the server does not hold, which is how a button starts
          lying. It exists because a schedule nobody is reminded of is a schedule nobody keeps. */}
      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/40 p-4"
          onClick={() => !busy && setConfirmOpen(null)}>
          <div className="my-8 w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl"
            data-testid="confirm-open-dialog" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ground-900">
              {t('admin.years.confirmOpenTitle')}
            </h2>
            {/* ⚠ TENSE FOLLOWS THE DATE (owner, 2026-09-08: it *"is talking about a date that is
                long past as a 'due to close'"*). A window that ended reads in the past; one that
                has not started reads in the present. Two short lines, not three long ones — the
                "these dates only record the schedule" sentence lives in the Edit dialog, which is
                where somebody is actually setting them. */}
            <p className="mt-2 text-sm text-ground-600">
              {(() => {
                const s = windowState(confirmOpen, today)
                return s.kind === 'before'
                  ? t('admin.years.confirmOpenBefore', { date: formatDate(s.opensOn) })
                  : s.kind === 'after'
                    ? t('admin.years.confirmOpenAfter', { date: formatDate(s.closesOn) })
                    // Unreachable: nothing opens this dialog for a round inside its window. Kept
                    // so the branch is total rather than rendering an empty paragraph.
                    : t('admin.years.confirmOpenGeneric')
              })()}
            </p>
            <p className="mt-1 text-sm text-ground-600">{t('admin.years.confirmOpenNote')}</p>

            <div className="mt-5 flex items-center justify-end gap-3">
              <button type="button" onClick={() => setConfirmOpen(null)} disabled={busy}
                className="text-sm font-medium text-ground-500 hover:text-ground-700">
                {t('common.cancel')}
              </button>
              <button type="button" data-testid="confirm-open-yes" disabled={busy}
                onClick={() => {
                  const y = confirmOpen
                  setConfirmOpen(null)
                  void setOpenState(y, true)
                }}
                className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('admin.years.confirmOpenYes')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

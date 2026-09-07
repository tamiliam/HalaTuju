'use client'

// The gifts this organisation runs — a SECTION of Organisation → Overview (owner, 2026-09-03).
//
// ⚠ IT WAS A MENU ROW OF ITS OWN AND IS NOT ANY MORE. Creating a gift is an organisation-level
// act, so the page was in the right SCOPE; it was in the wrong PLACE. The gifts an organisation
// runs are what that organisation IS, which is precisely what an overview owes its reader — and a
// whole sidebar entry for a list of one read as a feature rather than a fact. The old route
// `/admin/organisation/programmes` redirects here and the registry matches it, so a bookmark still
// lights the Overview row.
//
// ⚠ THE FENCE IS THE ENDPOINT. This renders what the server chose to return, and a cross-org id is
// a 404 there. Nothing here decides who may see what.

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useT } from '@/lib/i18n'
import { useProgrammeScope } from '@/lib/programmeScope'
import InfoBox from '@/components/InfoBox'
import { Menu, MenuHeading, MenuItem } from '@/components/admin/Menu'
import {
  getAdminProgrammes, createAdminProgramme, updateAdminProgramme, deleteAdminProgramme,
  type AdminProgramme,
} from '@/lib/admin-api'

const CODE_OK = /^[a-z0-9][a-z0-9-]{1,49}$/

/** Is the server's delete refusal already legible from the card above it? (owner, 2026-09-07)
 *
 *  ⚠ ONLY `has_applications`, and only because the card carries an APPLICATIONS column. The other
 *  four reasons — benefactors, money, payment runs, `in_use` — appear nowhere on this card, so
 *  their sentence must stay or the greyed button explains nothing. */
const redundantWithCard = (p: AdminProgramme) => p.delete_blocked_by === 'has_applications'

/** The colour of each state. ⚠ RED IS DELIBERATELY ABSENT.
 *
 *  The owner's sketch asked for green / red / blue. In this product red means *something is wrong*
 *  — a blocked delete, a failed check on a student's file — and a gift still being set up is the
 *  normal state of every gift on its first day. Painting it red would report a problem where there
 *  is none, and would spend the one colour that has to keep meaning trouble. Grey says "not live
 *  yet" without saying "broken". (Owner told, 2026-09-07.) */
const BADGE_TONE: Record<AdminProgramme['lifecycle'], string> = {
  active: 'bg-positive-100 text-positive-800',
  draft: 'bg-ground-100 text-ground-600',
  archived: 'bg-info-100 text-info-800',
}

/**
 * The gift's state, and the control that changes it.
 *
 * ⚠⚠ THE BADGE **IS** THE CONTROL, and that is the owner's ruling (2026-09-07). It used to be a
 * label with a separate "Switch off" link two lines below, in a row of verbs, directly under a
 * column headed "Taking applications" — so it read as a second copy of the intake year's
 * Open/Close. It is not: a year decides whether students may apply right now; this decides whether
 * the gift is a thing the organisation runs at all. Showing the state once, where a state belongs,
 * is the fix.
 *
 * ⚠ THE API IS UNCHANGED — this still PATCHes `is_active`. `draft` and `archived` are both "off";
 * which one you land in is decided by the server from whether anybody ever applied. So switching a
 * live gift off returns it to **Draft** if nobody has applied and **Archived** if somebody has,
 * and the menu item says which before you press it.
 */
function LifecycleBadge({ programme: p, busy, onChange }: {
  programme: AdminProgramme
  busy: boolean
  onChange: (p: AdminProgramme, makeActive: boolean) => void
}) {
  const { t } = useT()
  const label = t(`admin.programmes.lifecycle.${p.lifecycle}`)
  // From every state there is exactly ONE move worth offering, so the menu is short by nature.
  // Off → live is always "make it live"; live → off is named by where it will LAND, which the
  // server decides on the same rule the badge reads.
  const action = p.is_active
    ? { makeActive: false, key: p.applications > 0 ? 'archive' : 'toDraft' }
    : { makeActive: true, key: 'makeLive' }

  return (
    <Menu
      label={t('admin.programmes.lifecycle.change', { name: p.name_en })}
      align="left"
      width="w-64"
      trigger={
        <span data-testid={`lifecycle-${p.code}`}
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${BADGE_TONE[p.lifecycle]}`}>
          {label}
          <span aria-hidden className="text-[9px] leading-none opacity-70">▾</span>
        </span>
      }
    >
      <MenuHeading>{t(`admin.programmes.lifecycle.means.${p.lifecycle}`)}</MenuHeading>
      <MenuItem onClick={() => !busy && onChange(p, action.makeActive)}>
        {t(`admin.programmes.lifecycle.${action.key}`)}
      </MenuItem>
    </Menu>
  )
}

export default function GiftProgrammes({ token }: { token: string | null }) {
  const { t } = useT()
  const router = useRouter()
  const { select, reload } = useProgrammeScope()

  const [rows, setRows] = useState<AdminProgramme[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [nameEn, setNameEn] = useState('')
  // The gift whose deletion is being confirmed, and the code typed to confirm it. Null = no
  // dialog. Held as the RECORD, not an id, so the dialog can name what is about to go.
  const [deleting, setDeleting] = useState<AdminProgramme | null>(null)
  const [confirmText, setConfirmText] = useState('')

  const load = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      setRows((await getAdminProgrammes({ token })).programmes)
      setError('')
    } catch {
      setError(t('admin.programmes.loadFailed'))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => { void load() }, [load])

  const errKey = (c?: string) =>
    c === 'bad_code' ? 'badCode'
      : c === 'code_taken' ? 'codeTaken'
        : c === 'name_required' ? 'nameRequired'
          : c === 'has_open_year' ? 'hasOpenYear'
            : c === 'no_org' ? 'noOrg'
              // Why a gift cannot be deleted, named. Each is a relation the model PROTECTS: the
              // gift has become something, and the reader is owed which thing rather than a
              // blanket "that did not work".
              // ⚠ AN INTAKE YEAR IS NOT ONE OF THEM (owner, 2026-09-07) — students hold a gift, a
              // year does not, and an empty year is deleted along with it.
              : c === 'has_applications' ? 'hasApplications'
                : c === 'has_benefactors' ? 'hasBenefactors'
                  : c === 'has_money' ? 'hasMoney'
                    : c === 'has_payment_runs' ? 'hasPaymentRuns'
                      : c === 'in_use' ? 'inUse'
                        : c === 'confirm_mismatch' ? 'confirmMismatch' : 'generic'

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('')
    try {
      await fn()
      await load()
      return true
    } catch (e) {
      setError(t(`admin.programmes.error.${errKey((e as { code?: string })?.code)}`))
      return false
    } finally {
      setBusy(false)
    }
  }

  /** ⚠ CREATE NOW LANDS YOU ON THE NEW GIFT'S INTAKE YEAR (2026-09-06). It used to close the
   *  dialog and stop — the owner's report was that the flow is "disconnected", and a create that
   *  leaves you back on a list is exactly that: the next step exists, and nobody is taken to it.
   *
   *  It goes to the year rather than to Rules because the rules are COLUMNS ON THE YEAR ROW, so a
   *  gift a minute old has nothing for them to write to.
   *
   *  ⚠ IT POINTS, IT DOES NOT DO. Nothing is created for them on arrival — landing somebody on a
   *  screen is a suggestion; filling it in would be a guess about their gift (PF-1's rule).
   */
  const create = async () => {
    const wanted = code.trim().toLowerCase()
    const ok = await run(() => createAdminProgramme(
      { code: wanted, name_en: nameEn.trim() }, { token: token! }))
    if (ok) {
      setOpen(false); setCode(''); setNameEn('')
      // ⚠ REFRESH THE SHELL'S LIST **BEFORE** SELECTING, AND AWAIT IT. The scopes are fetched once
      // per console session, so a gift created just now is not in that list yet — and
      // `programmeScope` refuses to resolve a code it does not recognise. Selecting first left the
      // owner on a screen that asked which gift, forever, with every click a no-op (2026-09-07).
      //
      // ⚠ THE ORDER IS THE FIX. Do not "simplify" this by selecting first and letting the reload
      // catch up: the page would mount against the stale list, ask, and only heal on the next
      // render — which is the same dead screen for as long as the fetch takes.
      await reload()
      select(wanted)
      router.push('/admin/programme?tab=year')
    }
  }

  /** Move a gift between draft/live/archived. Still a PATCH of `is_active` — the third state is
   *  the server's reading of that boolean, not a third value on the wire. The server refuses to
   *  switch a gift off while one of its rounds is taking applications, and that refusal renders in
   *  the same error banner as every other write here. */
  const setLifecycle = (p: AdminProgramme, makeActive: boolean) =>
    run(() => updateAdminProgramme(p.id, { is_active: makeActive }, { token: token! }))

  /** Open a gift's own settings. The choice goes through the breadcrumb switcher's context, so
   *  the crumb and the page agree about which gift you just stepped into. */
  const openSettings = (p: AdminProgramme) => {
    select(p.code)
    router.push('/admin/programme')
  }

  const inputCls = 'w-full rounded-lg border border-ground-300 px-3 py-2 text-sm'
    + ' focus:border-brand-shape focus:ring-2 focus:ring-brand-shape outline-none'

  return (
    <section className="mt-8" data-testid="gift-programmes">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-ground-900">{t('admin.programmes.title')}</h2>
          <p className="mt-0.5 text-sm text-ground-600">{t('admin.programmes.subtitle')}</p>
        </div>
        <button type="button" onClick={() => { setCode(''); setNameEn(''); setError(''); setOpen(true) }}
          className="shrink-0 rounded-lg bg-brand-fill px-4 py-2.5 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
          + {t('admin.programmes.new')}
        </button>
      </div>

      {error && <div className="mt-4"><InfoBox kind="block">{error}</InfoBox></div>}

      <div className="mt-4 space-y-3">
        {rows.map((p) => (
          <div key={p.id} className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm"
            data-testid={`programme-${p.code}`}>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold text-ground-900">{p.name_en}</h3>
              <LifecycleBadge programme={p} busy={busy} onChange={setLifecycle} />
            </div>
            <p className="mt-0.5 font-mono text-xs text-ground-400">{p.code}</p>

            <dl className="mt-4 flex flex-wrap gap-x-9 gap-y-3">
              {([
                ['years', String(p.intake_years)],
                ['applications', String(p.applications)],
                // A programme is never "open"; one of its years is. Say which, or say none.
                ['takingApplications', p.open_year === null
                  ? t('admin.programmes.none') : String(p.open_year)],
              ] as const).map(([k, v]) => (
                <div key={k}>
                  <dt className="text-[10px] font-semibold uppercase tracking-wider text-ground-400">
                    {t(`admin.programmes.col.${k}`)}
                  </dt>
                  <dd className="mt-0.5 text-sm font-semibold tabular-nums text-ground-700">{v}</dd>
                </div>
              ))}
            </dl>

            {/* ⚠ TWO VERBS, AND THE STATE IS NOT ONE OF THEM (owner, 2026-09-07). "Switch off" used
                to sit here beside Delete, one line under a column reading "Taking applications" —
                which made it read as a duplicate of the intake year's Open/Close. It is not: the
                year decides whether students may apply RIGHT NOW, the gift's state decides whether
                it is a thing this organisation runs at all. A state belongs in the badge that
                already shows it, so the control moved there and this row is verbs only. */}
            <div className="mt-4 flex items-center justify-end gap-4 border-t border-ground-100 pt-3">
              <button type="button" onClick={() => openSettings(p)}
                className="text-sm font-medium text-primary-600 hover:underline">
                {t('admin.programmes.openSettings')}
              </button>
              {/* ⚠ DISABLED WHEN THE SERVER SAYS IT IS HELD — SHOWN, NEVER HIDDEN (owner,
                  2026-09-07: *"I feel it should be prevented at the button stage, and not wait
                  until typed to check."*). They were afraid to test Delete on the live flagship,
                  and that fear is the finding: a destructive control you cannot tell is safe to
                  press is one people avoid, so they cannot tidy up either.
                  ⚠ THE ANSWER IS `delete_blocked_by` FROM THE PAYLOAD, never derived from the two
                  counts on this card — those know nothing about benefactors, money or payment
                  runs. Hidden would explain nothing; disabled-with-the-reason explains everything.
                  The server still refuses, and from the same function that filled this field. */}
              <button type="button" data-testid={`delete-${p.code}`}
                disabled={busy || p.delete_blocked_by !== null}
                title={p.delete_blocked_by
                  ? t(`admin.programmes.error.${errKey(p.delete_blocked_by)}`) : undefined}
                onClick={() => { setError(''); setConfirmText(''); setDeleting(p) }}
                className="text-sm font-medium text-critical-600 hover:underline disabled:cursor-not-allowed disabled:text-ground-400 disabled:no-underline">
                {t('admin.programmes.delete')}
              </button>
            </div>
            {/* ⚠ THE REASON IS VISIBLE TEXT, not only the button's `title`. A tooltip needs a hover
                that a touch screen has no way to give, so on a phone the control would simply be
                dead with no explanation — which is the thing being fixed, not a smaller version
                of it.

                ⚠ BUT IT IS HIDDEN FOR THE ONE REASON THE CARD ALREADY STATES (owner, 2026-09-07:
                *"REMOVE. Redundant."*). "Students have applied to this gift" adds nothing beside an
                APPLICATIONS column reading 143. **The other four are NOT on this card** —
                benefactors, money, payment runs and the generic `in_use` — so removing the line
                outright would put back a dead button with no explanation, which is the defect this
                sentence was written for. `redundantWithCard` is the whole rule; extend it only when
                a reason's evidence is genuinely visible above it. */}
            {p.delete_blocked_by && !redundantWithCard(p) && (
              <p className="mt-2 text-right text-xs text-ground-500"
                data-testid={`delete-blocked-${p.code}`}>
                {t(`admin.programmes.error.${errKey(p.delete_blocked_by)}`)}
              </p>
            )}
          </div>
        ))}
        {!loading && rows.length === 0 && (
          <p className="rounded-2xl border border-dashed border-ground-300 px-4 py-10 text-center text-sm text-ground-400">
            {t('admin.programmes.empty')}
          </p>
        )}
        {loading && <p className="text-sm text-ground-400">{t('common.loading')}</p>}
      </div>

      <p className="mt-4 text-xs text-ground-500">{t('admin.programmes.durableNote')}</p>

      {/* ⚠ THE TYPED CODE IS THE POINT. A second "are you sure?" is answered by the same reflex
          that pressed the first button; typing the gift's own code cannot be. The SERVER checks it
          too — this dialog explains the guard, it is not the guard. */}
      {deleting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !busy && setDeleting(null)}>
          <div className="w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-critical-700">
              {t('admin.programmes.deleteTitle', { name: deleting.name_en })}
            </h2>
            <p className="mt-2 text-sm text-ground-700">{t('admin.programmes.deleteBody')}</p>
            {/* ⚠ SAY THAT THE YEARS GO, AND SAY HOW MANY. The years are the one thing being
                removed that the person cannot see from this dialog, and since 2026-09-07 they no
                longer block the delete — so silence here would mean somebody presses Delete on a
                gift and quietly loses three years of rules they had set up. Shown only when there
                is at least one; a gift with none needs no sentence about none. */}
            {deleting.intake_years > 0 && (
              <p className="mt-2 text-sm text-ground-700" data-testid="delete-years-note">
                {t('admin.programmes.deleteYears', { count: String(deleting.intake_years) })}
              </p>
            )}
            <div className="mt-3">
              <InfoBox kind="warning">{t('admin.programmes.deleteKeeps')}</InfoBox>
            </div>

            {/* ⚠ THE PHRASE CARRIES THE VERB — `delete <code>`, not the bare code (owner,
                2026-09-07). The code is printed on the card AND in this very label, so typing it
                alone is closer to copying what is on screen than to stating an intention. */}
            <label htmlFor="p-confirm" className="mt-4 block text-sm font-medium text-ground-700">
              {t('admin.programmes.deleteConfirmLabel', { phrase: `delete ${deleting.code}` })}
            </label>
            <input id="p-confirm" value={confirmText} autoComplete="off"
              onChange={(e) => setConfirmText(e.target.value)}
              className={`mt-1 ${inputCls}`} />

            <div className="mt-5 flex justify-end gap-3">
              <button type="button" onClick={() => setDeleting(null)} disabled={busy}
                className="rounded-lg px-4 py-2 text-sm font-medium text-ground-600 hover:text-ground-900 disabled:opacity-50">
                {t('common.cancel')}
              </button>
              <button type="button" data-testid="delete-confirm"
                // Whitespace-collapsed + lower-cased to match the server's own comparison exactly,
                // so this button is never asleep on a difference the server would have accepted.
                disabled={busy || confirmText.trim().replace(/\s+/g, ' ').toLowerCase()
                  !== `delete ${deleting.code}`.toLowerCase()}
                onClick={async () => {
                  const ok = await run(() => deleteAdminProgramme(
                    deleting.id, confirmText.trim().replace(/\s+/g, ' ').toLowerCase(),
                    { token: token! }))
                  if (ok) {
                    setDeleting(null); setConfirmText('')
                    // The shell's own list must forget it too, or the breadcrumb keeps offering a
                    // gift that no longer exists.
                    await reload()
                  }
                }}
                className="rounded-lg bg-critical-fill px-4 py-2 text-sm font-semibold text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50">
                {t('admin.programmes.deleteCta')}
              </button>
            </div>
          </div>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !busy && setOpen(false)}>
          <div className="w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.programmes.new')}</h2>

            <label htmlFor="p-name" className="mt-4 block text-sm font-medium text-ground-700">
              {t('admin.programmes.field.name')}
            </label>
            <input id="p-name" value={nameEn} onChange={(e) => setNameEn(e.target.value)}
              className={`mt-1 ${inputCls}`} />

            <label htmlFor="p-code" className="mt-4 block text-sm font-medium text-ground-700">
              {t('admin.programmes.field.code')}
            </label>
            <input id="p-code" value={code} onChange={(e) => setCode(e.target.value)}
              className={`mt-1 ${inputCls}`} />
            <p className="mt-1 text-xs text-ground-500">{t('admin.programmes.field.codeHint')}</p>

            <div className="mt-4">
              <InfoBox kind="warning">{t('admin.programmes.codeWarning')}</InfoBox>
            </div>
            {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}

            <div className="mt-5 flex items-center justify-end gap-3">
              <button type="button" onClick={() => setOpen(false)} disabled={busy}
                className="text-sm font-medium text-ground-500 hover:text-ground-700">
                {t('common.cancel')}
              </button>
              <button type="button" onClick={create}
                disabled={busy || !nameEn.trim() || !CODE_OK.test(code.trim().toLowerCase())}
                className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('admin.programmes.create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

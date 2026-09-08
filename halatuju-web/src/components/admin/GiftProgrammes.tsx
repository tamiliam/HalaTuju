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

/*
 * ⚠ `redundantWithCard` WAS DELETED ON 2026-09-08, AND ITS RULING SURVIVES THE DELETION.
 *
 * It suppressed the delete refusal for `has_applications` alone — owner, 2026-09-07: *"REMOVE.
 * Redundant."* — because an APPLICATIONS column reading 143 stood directly above the sentence
 * "students have applied to this gift". That was a statement about ADJACENCY, not about the reason.
 * Delete now lives behind the ⋮ menu, which carries no counts, so the one reason that was redundant
 * beside the number is the only explanation a reader gets in there. The predicate is not stale, it
 * is answered: nothing on that surface makes any refusal redundant.
 */

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
  const { chosen, select, reload } = useProgrammeScope()

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
  // The gift whose code is being changed, and the code being typed. Held as the RECORD so the
  // dialog can show the link that is about to change.
  const [renaming, setRenaming] = useState<AdminProgramme | null>(null)
  const [newCode, setNewCode] = useState('')
  // Which gift's link was just copied, so the confirmation names one card rather than all of them.
  const [copied, setCopied] = useState('')

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

  /**
   * Step into a gift. The choice goes through the breadcrumb switcher's context, so the crumb, the
   * sidebar and the page all agree about which gift you just entered.
   *
   * ⚠ TWO DESTINATIONS ON PURPOSE, AND THE CARD TAKES THE COMMON ONE (owner, 2026-09-08:
   * *"it should link to Applications. To reach settings, there are the three dots."*). Configuration
   * is something you set up once; the applicants are what you come back to. The ⋮ menu keeps the
   * named route to Configuration for the once-in-a-while visit.
   *
   * ⚠ EITHER DOOR ALSO REVEALS THE PROGRAMME MENU. `select` is what fills in the gift the
   * Configuration row waits for (`needsProgramme`), so entering through Applications still makes
   * both Programme rows appear — the two changes compose rather than fight.
   */
  const enterGift = (p: AdminProgramme, where: '/admin/scholarship' | '/admin/programme') => {
    select(p.code)
    router.push(where)
  }

  /**
   * Put the gift's apply link on the clipboard.
   *
   * ⚠ THE LINK IS THE SERVER'S (`p.apply_url`), never assembled here — see `AdminProgramme`.
   *
   * ⚠ AND THE FAILURE PATH MATTERS MORE THAN THE HAPPY ONE. `navigator.clipboard.writeText`
   * REJECTS on an insecure origin and wherever the browser withholds permission, so a bare
   * `await` would leave somebody pressing a menu item that does nothing at all. On a refusal the
   * banner prints the link itself, which is the thing they actually came for.
   */
  const copyApplyLink = async (p: AdminProgramme) => {
    setError('')
    try {
      await navigator.clipboard.writeText(p.apply_url)
      setCopied(p.code)
      setTimeout(() => setCopied(''), 2500)
    } catch {
      setError(t('admin.programmes.copyFailed', { url: p.apply_url }))
    }
  }

  /**
   * Change a gift's code. The server keeps the old one as an alias, so every link already printed
   * keeps working — the dialog says so, because otherwise this reads as a destructive act.
   *
   * ⚠ RE-SELECT ONLY WHEN THIS GIFT WAS THE CHOSEN ONE. The breadcrumb holds a CODE, so renaming
   * the gift somebody is currently inside would leave the shell holding a code the scope list no
   * longer knows — and `programmeScope` refuses to resolve an unknown code, which is the dead
   * "which gift?" screen from 2026-09-07. Re-selecting unconditionally would be worse: it would
   * silently move the reader into a gift they were not in.
   */
  const rename = async (p: AdminProgramme) => {
    const wanted = newCode.trim().toLowerCase()
    const wasChosen = chosen === p.code
    const ok = await run(() => updateAdminProgramme(p.id, { code: wanted }, { token: token! }))
    if (ok) {
      setRenaming(null); setNewCode('')
      await reload()
      if (wasChosen) select(wanted)
    }
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

      {/*
        ⚠ TWO ACROSS FROM `sm` UP (owner, 2026-09-08: *"with 900 px, both cards would sit side by
        side"*). The Overview is a `reading`-width page (max-w-4xl ≈ 896px, `lib/pageWidth`), so at
        `sm` each card gets ~430px — enough for the name, the badge and three facts on one line.
        Below `sm` they stack, which is the phone layout the owner already approved.

        ⚠ THIS IS WHY THE CARD GOT SHORTER FIRST. A full-width card wasted the right-hand half of
        the page on a list of two; halving the height and then halving the width is one change made
        in two passes, not two changes.
      */}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {rows.map((p) => (
          /*
           * ⚠⚠ THE WHOLE CARD IS THE DOOR (owner, 2026-09-08, pointing at Supabase: *"the project
           * card is clickable… we could change the entire gift card to button"*). The old door was
           * a small grey word "Settings" in a row of verbs at the bottom — so the owner never found
           * it and reached a gift the long way round, through Applications and the breadcrumb.
           *
           * ⚠ IT IS A <button>, AND THE TWO CONTROLS INSIDE IT ARE SIBLINGS, NOT CHILDREN. A button
           * inside a button is invalid HTML and the inner one becomes unreachable by keyboard, so
           * the state badge and the ⋮ menu sit OUTSIDE the card button in the same header row, and
           * the button is a positioned overlay behind them. That is why this is a relative box with
           * an inset button rather than the obvious `<button>` wrapping everything.
           */
          <div key={p.id}
            className="relative rounded-2xl border border-ground-200 bg-ground-0 shadow-sm transition-colors focus-within:border-primary-300 hover:border-primary-300"
            data-testid={`programme-${p.code}`}>
            {/* The door. `absolute inset-0` so the whole card is the hit area; `z-0` so the badge
                and the menu above it stay clickable in their own right. */}
            <button type="button" onClick={() => enterGift(p, '/admin/scholarship')}
              data-testid={`open-${p.code}`}
              className="absolute inset-0 z-0 rounded-2xl focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-shape">
              <span className="sr-only">{t('admin.programmes.open', { name: p.name_en })}</span>
            </button>

            {/* ⚠ `pointer-events-none` ON THE TEXT, RE-ENABLED ON THE CONTROLS. Without it the
                headings would sit above the door and swallow the click that opens the gift. */}
            <div className="pointer-events-none relative z-10 p-4">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-ground-900">{p.name_en}</h3>
                    <span className="pointer-events-auto">
                      <LifecycleBadge programme={p} busy={busy} onChange={setLifecycle} />
                    </span>
                  </div>
                  <p className="mt-0.5 flex items-center gap-2 font-mono text-xs text-ground-400">
                    {p.code}
                    {/* Beside the code, not in a toast: the code IS the link, so the confirmation
                        belongs where the reader is already looking, and naming one card keeps two
                        gifts from both claiming to have been copied. */}
                    {copied === p.code && (
                      <span data-testid={`copied-${p.code}`}
                        className="font-sans font-medium text-positive-700">
                        {t('admin.programmes.copied')}
                      </span>
                    )}
                  </p>
                </div>

                {/* ⚠ SETTINGS AND DELETE LIVE BEHIND THE THREE DOTS NOW (owner: *"this is not
                    something we'll be messing with regularly"*). Settings STAYS in the menu even
                    though the card opens it — the card is a shortcut, the menu is the named route,
                    and a reader looking for "where do I configure this" should find the word. */}
                <span className="pointer-events-auto shrink-0">
                  <Menu label={t('admin.programmes.moreFor', { name: p.name_en })} align="right"
                    width="w-64"
                    trigger={
                      <span data-testid={`more-${p.code}`}
                        className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-ground-500 hover:bg-ground-100 hover:text-ground-800">
                        <span aria-hidden className="text-base leading-none">⋮</span>
                      </span>
                    }
                  >
                    {/* ⚠ THE APPLY LINK LIVES HERE, NOT ON THE CARD (owner, 2026-09-08, choosing
                        between the two: one tap, nothing to mistype, and no height added back to a
                        card that was just halved). The code is printed on the card for reading;
                        the LINK is for carrying somewhere else, which is a menu action. */}
                    <MenuItem onClick={() => void copyApplyLink(p)}>
                      {t('admin.programmes.copyLink')}
                    </MenuItem>
                    <MenuItem onClick={() => {
                      setError(''); setNewCode(p.code); setRenaming(p)
                    }}>
                      {t('admin.programmes.changeCode')}
                    </MenuItem>
                    <MenuItem onClick={() => enterGift(p, '/admin/programme')}>
                      {t('admin.programmes.openSettings')}
                    </MenuItem>
                    {/* ⚠ ASLEEP WITH ITS REASON, NEVER HIDDEN — the 2026-09-07 ruling, carried
                        through the move into this menu. The reason comes from the served
                        `delete_blocked_by`, never derived from the counts on this card: those know
                        nothing about benefactors, money or payment runs.
                        ⚠ AND `redundantWithCard` NO LONGER APPLIES. It suppressed the sentence for
                        `has_applications` because an APPLICATIONS column stood right above it; the
                        menu is a separate surface with no counts in it, so the one reason that was
                        redundant on the card is the only explanation there is in here. */}
                    <MenuItem danger
                      disabled={busy || p.delete_blocked_by !== null}
                      reason={p.delete_blocked_by
                        ? t(`admin.programmes.error.${errKey(p.delete_blocked_by)}`) : undefined}
                      onClick={() => { setError(''); setConfirmText(''); setDeleting(p) }}>
                      {t('admin.programmes.delete')}
                    </MenuItem>
                  </Menu>
                </span>
              </div>

              {/* Four facts on one line, then the round. Half the height the card used to be. */}
              <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
                {([
                  ['years', String(p.intake_years)],
                  ['applications', String(p.applications)],
                  // ⚠ "HAS EVER BEEN AWARDED", served. See `AdminProgramme.awarded` — do not
                  // recompute it from a status anywhere in the browser.
                  ['awarded', String(p.awarded)],
                ] as const).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-[10px] font-semibold uppercase tracking-wider text-ground-400">
                      {t(`admin.programmes.col.${k}`)}
                    </dt>
                    <dd className="mt-0.5 text-sm font-semibold tabular-nums text-ground-700">{v}</dd>
                  </div>
                ))}
              </dl>
              {/* A programme is never "open"; one of its years is. Say which, or say none. */}
              <p className="mt-2 text-xs text-ground-500">
                {p.open_year === null
                  ? t('admin.programmes.notTakingApplications')
                  : t('admin.programmes.takingApplicationsFor', { year: String(p.open_year) })}
              </p>
            </div>
          </div>
        ))}
        {!loading && rows.length === 0 && (
          <p className="rounded-2xl border border-dashed border-ground-300 px-4 py-10 text-center text-sm text-ground-400 sm:col-span-2">
            {t('admin.programmes.empty')}
          </p>
        )}
        {loading && <p className="text-sm text-ground-400 sm:col-span-2">{t('common.loading')}</p>}
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

      {/* ⚠ THE LINK IS SHOWN WHERE THE CODE IS SET (owner's choice, 2026-09-08). A code changed
          without seeing the link it drives is a change made blind — this is the one screen where
          the two facts have to sit together. */}
      {renaming && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !busy && setRenaming(null)}>
          <div className="w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-semibold text-ground-900">
              {t('admin.programmes.renameTitle', { name: renaming.name_en })}
            </h2>

            <p className="mt-4 text-sm font-medium text-ground-700">
              {t('admin.programmes.applyLinkLabel')}
            </p>
            <p data-testid="rename-apply-url"
              className="mt-1 break-all rounded-lg bg-ground-50 px-3 py-2 font-mono text-xs text-ground-700">
              {renaming.apply_url}
            </p>

            <label htmlFor="p-newcode" className="mt-4 block text-sm font-medium text-ground-700">
              {t('admin.programmes.field.newCode')}
            </label>
            <input id="p-newcode" value={newCode} autoComplete="off"
              onChange={(e) => setNewCode(e.target.value)} className={`mt-1 ${inputCls}`} />
            <p className="mt-1 text-xs text-ground-500">{t('admin.programmes.field.codeHint')}</p>

            {/* ⚠ SAY THAT THE OLD CODE KEEPS WORKING. Without this sentence the honest reader
                assumes every poster already printed is about to stop working, and does not rename
                a code they should. It is also true: the server writes the old code as an alias. */}
            <div className="mt-4">
              <InfoBox kind="info">{t('admin.programmes.renameKeeps')}</InfoBox>
            </div>
            {error && <p className="mt-2 text-sm text-critical-600">{error}</p>}

            <div className="mt-5 flex justify-end gap-3">
              <button type="button" onClick={() => setRenaming(null)} disabled={busy}
                className="rounded-lg px-4 py-2 text-sm font-medium text-ground-600 hover:text-ground-900 disabled:opacity-50">
                {t('common.cancel')}
              </button>
              <button type="button" data-testid="rename-confirm"
                // Asleep on an unchanged code as well as a malformed one: the server treats the
                // same code as a no-op, so offering the press would promise a change that is not
                // one.
                disabled={busy || !CODE_OK.test(newCode.trim().toLowerCase())
                  || newCode.trim().toLowerCase() === renaming.code}
                onClick={() => void rename(renaming)}
                className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('admin.programmes.renameCta')}
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

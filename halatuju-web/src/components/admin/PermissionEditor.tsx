'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Toggle from '@/components/Toggle'
import PermissionHistory from './PermissionHistory'
import { BoxShell, ChangedPill, LayoutBox, Padlock, type KeyState } from './PermissionBox'
import { permName } from './permName'
import { useT } from '@/lib/i18n'
import { LAYOUT_KEYS, PERMISSION_LAYOUT } from '@/lib/permissionLayout'
import {
  getStaffPermissions, saveStaffPermissions,
  type StaffPermissionsPlan, type StaffPermissionsView, type StaffV2Key,
} from '@/lib/admin-api/admins'

/**
 * People → a person → **What <name> can do** (request #39 Sprint 4). One card: the person's permissions,
 * a "changed" marker on rows changed since the card loaded, a live consequence line, Save and Reset.
 *
 * ⚠ THE SERVER DECIDES EVERYTHING THAT MATTERS. The keys it may show (`keys`, `v2_keys`), the preset, and —
 * on every change — what saving would do: each change asks the endpoint for a DRY RUN, and the line in the
 * save bar is worded from its answer (`added`, `removed`, `consequences`) or shows its refusal (a person
 * holding cases keeps "Review assigned students"). Nothing here re-derives a rule; the one local rule,
 * Quality check bringing Applications, only reflects what the server answers.
 *
 * Loaded in the person page's own chunk (`'ad'`, `admin/person/{Admin,Reviewer}GroupPage`, sprint M2a) — no
 * route entry carries it. Under the card, **Changes**: the same GET's `history`, re-read after every save. A
 * page that already holds the GET passes it as `initial`, and the card asks nothing more until a save.
 *
 * Sprint M2d (owner 2026-11-13, design of record the mock-up approved that day): for somebody in Admins the
 * card is laid out BY PAGE — two collapsible boxes, Organisation and Programme, in sidebar order
 * (`lib/permissionLayout.ts`, the ONE layout). Each power appears once: a page with a view and a change is a
 * three-way choice, a one-key page a switch, a page's further powers sub-items. A key the server marks
 * `never_grantable` or `alias` is not drawn (its old key's row stands in for an alias) and rides along in
 * the saved set untouched. A `lead_only` key is drawn disabled with a padlock, on when it opens today, under
 * ONE legend line. No "Custom" chip: every admin is set up individually (the server's `custom` still tells
 * Reset whether there is anything to undo). The Engagement pages' need for Scholars is a note from the
 * server (`v2_gaps`, the dry run's), never a refusal.
 */

/**
 * Team tables T3: ONE SECTION PER TABLE THE PERSON SITS IN — the server's `tables`. The Admins keys (now
 * placed in the boxes by the layout) only for somebody in Admins; the Reviewers section (`review`, `qc`) only
 * for somebody in Reviewers. Quality check IMPLIES Applications (`see_all`; the server's
 * `staff_permissions.IMPLIES`, T5b; TD-499), so it comes on with Quality check and stays on and locked while
 * Quality check is on; turning it off never takes Quality check away.
 * ⚠ A KEY THE PERSON HOLDS OUTSIDE THEIR SECTIONS IS NEVER DROPPED: the saved set is the whole set the
 * server served, changed only by the controls on screen (and the key Quality check brings).
 * The keys are the server's `staff_tables_admin.ADMIN_TABLE_KEYS` / `REVIEWER_TABLE_KEYS`. */
export const TABLE_KEYS = {
  admins: ['see_all', 'scholars', 'spending', 'payments_prepare', 'payments_check', 'payments_approve',
    'award_withdraw_request', 'award_withdraw_approve'],
  reviewers: ['review', 'qc'],
} as const
export type TeamTable = keyof typeof TABLE_KEYS

export interface PermissionEditorProps {
  adminId: number
  /** Shown until the server's answer arrives, so the title never flickers to a blank. */
  name: string
  token: string
  /** Told after a save lands, so the page can re-read its list (the chips). */
  onSaved?: () => void
  /** The GET this page already made, so the card does not make it twice. */
  initial?: StaffPermissionsView
  /** M1b (owner O12): the Team table the page was opened from — draw ONLY that table's section. Reset then
   *  speaks of that table's keys alone (against the server's `table_presets[table]`); every other key the
   *  person holds rides along untouched in the saved set. Absent: every section they sit in. */
  table?: TeamTable
}

type Refusal = { message: string; code: string }

const sameSet = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && a.every((k) => b.includes(k))

/** M2b: the whole set a card starts from — today's keys, then the stored page keys. */
const heldBy = (v: { permissions: string[]; v2_held?: string[] }) => [...v.permissions, ...(v.v2_held ?? [])]
/** The page a v2 key opens (`sponsors.edit` -> `sponsors`); a key of today has none. */
const pageOf = (key: string) => (key.includes('.') ? key.slice(0, key.indexOf('.')) : null)
/** D3: what the server marks so is never drawn. */
const HIDDEN_REASONS: readonly (string | null)[] = ['never_grantable', 'alias']
const OFF: KeyState = { shown: false, on: false, lock: false, disabled: true, changed: false }

type Translate = ReturnType<typeof useT>['t']

/** Every key as the card draws it: one of today's keys from `keys`, a page key from `v2_keys`. `frozen`: a
 *  fixed card or a save in flight. */
function keyStates(view: StaffPermissionsView, served: Map<string, StaffV2Key>, want: string[], held: string[],
  frozen: boolean): (key: string) => KeyState {
  const fixed = !view.editable
  return (key) => {
    const v2 = served.get(key)
    if (v2) {
      if (HIDDEN_REASONS.includes(v2.reason)) return OFF
      const lock = v2.reason === 'lead_only'
      // D4: a key nobody here may store shows what opens today; so does a fixed card (its set is the server's).
      const on = v2.grantable && !fixed ? want.includes(key) : v2.held
      return { shown: true, on, lock, disabled: frozen || lock,
        changed: v2.grantable && !fixed && on !== held.includes(key) }
    }
    if (!view.keys.includes(key)) return OFF
    const on = want.includes(key)
    // Applications is locked on while Quality check holds it (TD-499).
    return { shown: true, on, lock: false, disabled: frozen || (key === 'see_all' && want.includes('qc')),
      changed: on !== held.includes(key) }
  }
}

/** The save bar's line, worded from the server's dry run (`added`, `removed`, `consequences`). */
function consequenceLine(t: Translate, who: string, saved: boolean, dirty: boolean,
  plan: StaffPermissionsPlan | null): string {
  if (saved) return t('admin.permEditor.saved', { name: who })
  if (!dirty) return t('admin.permEditor.noChange', { name: who })
  if (!plan) return ''
  const names = (keys: string[]) => keys.map((k) => `“${permName(t, k)}”`).join(', ')
  const parts: string[] = []
  if (plan.added.length) parts.push(t('admin.permEditor.gives', { name: who, list: names(plan.added) }))
  if (plan.removed.length) parts.push(t('admin.permEditor.takes', { name: who, list: names(plan.removed) }))
  // Review fix (M2d): `scholars_needed` is worded once, by the caution note (D7), never here as well.
  const effects = plan.consequences.filter((c) => c !== 'scholars_needed')
  for (const c of effects) parts.push(t(`admin.permEditor.effect.${c}`, { name: who }))
  if (!effects.length) parts.push(t('admin.permEditor.nothingElse'))
  return parts.join(' ')
}

/** A switch for a key outside the layout: a Reviewers key, or a key the server adds later. */
function KeyRow({ id, k, onFlip }: { id: string; k: KeyState; onFlip: (key: string, on: boolean) => void }) {
  const { t } = useT()
  const label = id.includes('.') ? permName(t, id) : t(`admin.perm.${id}.name`)
  return (
    <div data-key={id} className="flex items-center justify-between gap-4 px-4 py-3">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ground-900">
          {label}
          {k.changed && <ChangedPill />}
        </div>
        {!id.includes('.') && <div className="text-[13px] text-ground-500">{t(`admin.perm.${id}.desc`)}</div>}
        {id === 'qc' && (
          <div className="text-xs text-ground-500" data-testid="qc-brings-see-all">{t('admin.permEditor.qcBrings')}</div>
        )}
      </div>
      <Toggle on={k.on} disabled={k.disabled} label={label} onChange={(v) => onFlip(id, v)} />
    </div>
  )
}

/** D8: the consequence line, Reset and Save in a bar that stays in view at the foot of the card while it
 *  scrolls (sticky, safe-area aware; the admin shell has no bottom bar to collide with). */
function SaveBar({ refusal, text, reset, resetOff, onReset, resetLabel, saveOff, onSave }: {
  refusal: Refusal | null
  text: string
  reset: boolean
  resetOff: boolean
  onReset: () => void
  resetLabel: string
  saveOff: boolean
  onSave: () => void
}) {
  const { t } = useT()
  return (
    <div data-testid="perm-save-bar"
      className="sticky bottom-0 z-10 -mx-4 grid gap-2.5 border-t border-ground-200 bg-ground-0 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:-mx-5 sm:px-5">
      {refusal ? (
        <div role="alert" className="rounded-lg bg-critical-50 px-3.5 py-2.5 text-sm text-critical-700">
          {refusal.message}
        </div>
      ) : text ? (
        <div role="status" className="rounded-lg bg-primary-50 px-3.5 py-2.5 text-sm text-ground-900">{text}</div>
      ) : null}
      <div className="flex flex-wrap justify-end gap-2.5">
        {/* T3 review: no "back to the preset" for somebody not active or sitting in no table. */}
        {reset && (
          <button type="button" disabled={resetOff} data-testid="perm-reset" onClick={onReset}
            className="min-h-11 rounded-lg border border-ground-300 px-4 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50">
            {resetLabel}
          </button>)}
        <button type="button" onClick={onSave} disabled={saveOff}
          className="min-h-11 rounded-lg bg-brand-fill px-4 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t('admin.permEditor.save')}
        </button>
      </div>
    </div>
  )
}

/** The card's working set and the server's answers about it: the GET (unless the page passed it), the dry
 *  run on every change, the switches' and three-ways' local rules, and Save. */
function useWorkingSet({ adminId, token, onSaved, initial, table }: Omit<PermissionEditorProps, 'name'>) {
  const [view, setView] = useState<StaffPermissionsView | null>(initial ?? null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [want, setWant] = useState<string[]>(initial ? heldBy(initial) : [])
  const [plan, setPlan] = useState<StaffPermissionsPlan | null>(null)
  const [refusal, setRefusal] = useState<Refusal | null>(null)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  // Only the LATEST dry run may paint the line: a slow answer to an older click must not overwrite it.
  const asked = useRef(0)

  useEffect(() => {
    if (initial) return
    let live = true
    getStaffPermissions(adminId, { token })
      .then((v) => { if (live) { setView(v); setWant(heldBy(v)) } })
      .catch(() => { if (live) setLoadFailed(true) })
    return () => { live = false }
  }, [adminId, token, initial])

  const held = view ? heldBy(view) : []
  const dirty = !!view && !sameSet(want, held)

  // Every change asks the server what saving would do; an unchanged set asks nothing.
  useEffect(() => {
    if (!view || !dirty) { setPlan(null); setRefusal(null); return }
    const n = ++asked.current
    // Review fix 9: the previous answer is about the previous set — drop it before asking, so Save
    // (which needs a plan) can never act on a stale preview while this one is in flight.
    setPlan(null); setRefusal(null)
    saveStaffPermissions(adminId, want, true, { token })
      .then((p) => { if (n === asked.current) { setPlan(p); setRefusal(null) } })
      .catch((e: Error & { code?: string }) => {
        if (n === asked.current) { setPlan(null); setRefusal({ message: e.message, code: e.code ?? '' }) }
      })
  }, [adminId, token, view, want, dirty])

  // T3: the sections are the tables the server seated them at when the card loaded (a payload from before
  // T3, with no `tables`, shows both). They stay put while the controls move, and follow the next read.
  const tables = view?.tables
  const seatedAdmins = !tables || tables.includes('admins')
  const inAdmins = (!table || table === 'admins') && seatedAdmins
  const inReviewers = (!table || table === 'reviewers') && (!tables || tables.includes('reviewers'))
  // Quality check brings Applications (`see_all`) along (TD-499: the server's IMPLIES). Somebody NOT in Admins
  // has no Applications switch, so turning Quality check off takes it away again unless it was an ADMIN key
  // before (held without Quality check), so turning Quality check off never leaves somebody seated at Admins
  // by a key nobody ticked (T2's rule, kept). In Admins the switch is on screen and stays as it is.
  const seeAllWasAdmin = !!view && view.permissions.includes('see_all') && !view.permissions.includes('qc')
  const served = useMemo(() => new Map<string, StaffV2Key>((view?.v2_keys ?? []).flatMap((g) => g.keys)
    .map((k) => [k.key, k])), [view])
  const grantable = useMemo(() => new Set(Array.from(served.values()).filter((k) => k.grantable)
    .map((k) => k.key)), [served])
  // M2b: a page's view goes with its change, and off with it (the server stores the view anyway).
  const flip = useCallback((key: string, on: boolean) => {
    setSaved(false)
    setWant((cur) => {
      let next = on ? [...cur, key] : cur.filter((k) => k !== key)
      const page = pageOf(key)
      if (page && on && !key.endsWith('.view') && grantable.has(`${page}.view`) && !next.includes(`${page}.view`)) {
        next = [...next, `${page}.view`]
      }
      if (page && !on && key.endsWith('.view')) next = next.filter((k) => pageOf(k) !== page)
      if (key === 'qc' && on && !next.includes('see_all')) next = [...next, 'see_all']
      // By their SEAT, not by what is drawn (O12): opened from Reviewers, an Admin's key stays theirs.
      if (!seatedAdmins && key === 'qc' && !on && !seeAllWasAdmin) next = next.filter((k) => k !== 'see_all')
      return next
    })
  }, [seatedAdmins, seeAllWasAdmin, grantable])
  // D2: the three-way writes the page's view and change at once; "No access" clears the whole page.
  const choose = useCallback((viewKey: string, editKey: string, level: 0 | 1 | 2) => {
    setSaved(false)
    setWant((cur) => {
      const page = pageOf(viewKey)
      const next = cur.filter((k) => k !== viewKey && k !== editKey && (level > 0 || pageOf(k) !== page))
      if (level >= 1) next.push(viewKey)
      if (level === 2) next.push(editKey)
      return next
    })
  }, [])

  const save = async () => {
    setBusy(true)
    try {
      const p = await saveStaffPermissions(adminId, want, false, { token })
      const v2Held = p.v2_held ?? view?.v2_held
      setView((cur) => (cur ? { ...cur, permissions: p.permissions, custom: p.custom, v2_held: v2Held,
        v2_gaps: p.v2_gaps ?? cur.v2_gaps } : cur))
      setWant(heldBy({ permissions: p.permissions, v2_held: v2Held }))
      setSaved(true)
      onSaved?.()
      // Re-read for the Changes list: the new line is the server's, with its own time and author.
      // A failed re-read leaves the saved card as it is — the save itself has landed.
      getStaffPermissions(adminId, { token })
        .then((v) => setView((cur) => (cur ? { ...cur, history: v.history } : cur)))
        .catch(() => {})
    } catch (e) {
      const err = e as Error & { code?: string }
      setRefusal({ message: err.message, code: err.code ?? '' })
    } finally { setBusy(false) }
  }

  return { view, loadFailed, want, setWant, plan, refusal, busy, saved, setSaved, held, dirty, tables,
    inAdmins, inReviewers, served, grantable, flip, choose, save }
}

export default function PermissionEditor({ adminId, name, token, onSaved, initial, table }: PermissionEditorProps) {
  const { t } = useT()
  const { view, loadFailed, want, setWant, plan, refusal, busy, saved, setSaved, held, dirty, tables,
    inAdmins, inReviewers, served, grantable, flip, choose, save } = useWorkingSet({ adminId, token, onSaved, initial, table })
  if (loadFailed) {
    return <p className="text-sm text-critical-600">{t('admin.permEditor.loadFailed', { name })}</p>
  }
  if (!view) return null
  const who = view.name || name
  const preset = t(`admin.role.${view.role}`)
  // `?? []`: an api a few minutes behind this page serves no history yet; the list says "none".
  const history = <PermissionHistory rows={view.history ?? []} name={who} role={view.role} />
  if (!view.editable && !view.is_active) {
    // A revoked person is not editable (review fix 8): say how to get there, draw no dead controls —
    // but their history still reads.
    return (<>
      <p className="text-sm text-ground-500">{t('admin.permEditor.restoreFirst', { name: who })}</p>
      {history}
    </>)
  }
  // Sprint T3 (M2): somebody active whose set this viewer may not change (an organisation admin, your own) —
  // their keys as LOCKED controls under one line saying so: no Save, no Reset, no dry run.
  const fixed = !view.editable
  const ks = keyStates(view, served, want, held, fixed || busy)
  const row = (key: string) => <KeyRow key={key} id={key} k={ks(key)} onFlip={flip} />

  const reviewerKeys = TABLE_KEYS.reviewers.filter((k) => view.keys.includes(k))
  // D10: the Reviewers section in the same box style, contents unchanged.
  const reviewers = inReviewers && reviewerKeys.length > 0 && (
    <BoxShell title={t('admin.team.colKeys.reviewers')} testId="perm-section-reviewers"
      on={reviewerKeys.filter((k) => want.includes(k)).length} of={reviewerKeys.length}>
      {reviewerKeys.map(row)}
    </BoxShell>
  )
  // A key the server serves that the layout does not place (and D3 does not hide) still gets a switch,
  // under the boxes, rather than vanishing. The layout's guard test fails the build until it is placed.
  const placed: readonly string[] = [...LAYOUT_KEYS, ...TABLE_KEYS.reviewers]
  const other = !inAdmins ? [] : [...view.keys, ...Array.from(served.keys())]
    .filter((k) => !placed.includes(k) && ks(k).shown)
  const locks = inAdmins && !fixed && LAYOUT_KEYS.some((k) => ks(k).shown && ks(k).lock)

  // O12: opened from one table, Reset weighs that table's keys only (M2b: the Admins table's keys include
  // the page keys, and its served preset ends with the role's own).
  const scope: readonly string[] | null = table === 'admins' ? [...TABLE_KEYS.admins, ...Array.from(grantable)]
    : table ? TABLE_KEYS[table] : null
  const mine = (keys: readonly string[]) => (scope ? keys.filter((k) => scope.includes(k)) : [...keys])
  const fullPreset = [...view.preset, ...(view.v2_preset ?? [])]
  const presetHere = scope ? (view.table_presets?.[table as TeamTable] ?? mine(fullPreset)) : fullPreset
  const resetTo = scope ? [...want.filter((k) => !scope.includes(k)), ...presetHere] : fullPreset
  // Review (d): a NULL row (the server's `custom` false) holds its preset although it stores no page key, so
  // until something is changed Reset has nothing to do. The server answers; the web does not re-derive it.
  const onPreset = view.custom === false && !dirty
  // Review fix 1: a Reviewer or QC holding neither key would vanish from People; the server refuses it
  // (`would_leave_people`) and the hint says why before the refusal arrives.
  const unlisted = ['reviewer', 'qc'].includes(view.role)
    && !want.includes('review') && !want.includes('qc')
  // D7: the pages short of Scholars, from the LATEST answer — the dry run while changed, `v2_gaps` at rest.
  const gaps = inAdmins && !fixed ? ((dirty ? plan?.v2_gaps : view.v2_gaps) ?? []) : []

  return (<>
    <section className="rounded-xl border bg-ground-0 px-4 pt-4 shadow-sm sm:px-5"
      aria-labelledby={`perm-editor-${adminId}`} data-testid="permission-editor">
      <h2 id={`perm-editor-${adminId}`} className="text-base font-semibold text-ground-900">
        {t('admin.permEditor.title', { name: who })}
      </h2>
      <p className="mt-0.5 text-sm text-ground-500" data-testid={fixed ? 'perm-fixed' : 'perm-intro'}>
        {fixed ? t('admin.permEditor.fixed', { name: who }) : t('admin.permEditor.intro', { name: who })}</p>
      {locks && (
        <p className="mt-1 flex items-center gap-1.5 text-[13px] text-ground-500" data-testid="perm-legend">
          <Padlock />{t('admin.permEditor.notAssignable')}
        </p>
      )}
      <div className="mt-3 grid gap-3 pb-4">
        {inAdmins && (
          <div className="grid gap-3" data-testid="perm-section-admins">
            {PERMISSION_LAYOUT.map((box) => (
              <LayoutBox key={box.id} box={box} ks={ks} onSwitch={flip} onTri={choose} />
            ))}
          </div>
        )}
        {reviewers}
        {other.length > 0 && (
          <div className="divide-y divide-ground-100 rounded-lg border border-ground-200" data-testid="perm-other">
            {other.map(row)}
          </div>
        )}
        {gaps.length > 0 && (
          <p className="rounded-lg bg-caution-50 px-3.5 py-2.5 text-sm text-caution-700" data-testid="perm-scholars-note">
            {t('admin.permEditor.scholarsNote', {
              pages: gaps.map((p) => t(`admin.permV2.page.${p}`)).join(', ') })}
          </p>
        )}
        {unlisted && !fixed && (
          <p className="text-xs text-caution-700" data-testid="unlisted-hint">{t('admin.permEditor.unlistedHint')}</p>
        )}
        {!fixed && <p className="text-xs text-ground-500">{t('admin.permEditor.footnote')}</p>}
      </div>

      {!fixed && (
        <SaveBar refusal={refusal} text={consequenceLine(t, who, saved, dirty, plan)}
          reset={view.is_active && !(tables && tables.length === 0)}
          resetOff={busy || onPreset || sameSet(want, resetTo)} onReset={() => { setSaved(false); setWant(resetTo) }}
          resetLabel={t('admin.permEditor.reset', { preset })}
          saveOff={!dirty || busy || !!refusal || !plan} onSave={save} />
      )}
    </section>
    {history}
  </>)
}

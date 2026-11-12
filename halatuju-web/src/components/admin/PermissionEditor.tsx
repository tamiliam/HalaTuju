'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Toggle from '@/components/Toggle'
import PermissionHistory from './PermissionHistory'
import { permName } from './permName'
import { useT } from '@/lib/i18n'
import {
  getStaffPermissions, saveStaffPermissions,
  type StaffPermissionsPlan, type StaffPermissionsView, type StaffV2Key,
} from '@/lib/admin-api/admins'

/**
 * People → a person → **What <name> can do** (request #39 Sprint 4). The design of record is the
 * clickable mock the owner approved on 2026-10-21 in place of a Stitch screen: one card, two groups
 * (Students, Money), a site Toggle per permission (owner rule: toggles, never tick boxes), a "Custom"
 * chip beside the preset when the set differs from it, a "changed" marker on rows changed since the
 * card loaded, a live consequence line, Save and Reset.
 *
 * ⚠ THE SERVER DECIDES EVERYTHING THAT MATTERS. The switches it may show (`keys`), the preset, and —
 * on every change — what saving would do: each toggle asks the endpoint for a DRY RUN, and the line
 * under the switches is worded from its answer (`added`, `removed`, `consequences`) or shows its
 * refusal (a person holding cases keeps "Review assigned students"). Nothing here re-derives a rule;
 * the one local rule, Quality check bringing Applications, only reflects what the server answers.
 *
 * Loaded in the person page's own chunk (`'ad'`, `admin/person/{Admin,Reviewer}GroupPage`, sprint M2a) — no route entry carries it.
 *
 * Under the card, **Changes** (2026-10-22): the same GET's `history`, re-read after every save so the
 * new line appears. A page that already holds the GET (the admin person page draws its header from
 * it) passes it as `initial`, and the card asks nothing more until a save.
 */

/**
 * Team tables T3 (owner, 2026-11-03): ONE SECTION PER TABLE THE PERSON SITS IN — the server's `tables`.
 * "Admin permissions" (`see_all`, `scholars`, `spending`, the payment and withdrawal keys) only for somebody in
 * Admins; "Reviewer permissions" (`review`, `qc`) only for somebody in Reviewers. The old Students / Money
 * groups, which showed every key to everyone, are gone. Sprint S1: `see_all` is labelled "Applications" and
 * `scholars` ("Scholars", its own key) sits right after it. "Applications" is an ADMIN permission; Quality check
 * IMPLIES it (the server's `staff_permissions.IMPLIES`, T5b; TD-499), so it comes on with Quality check and
 * stays ticked and locked while Quality check is on; turning it off never takes Quality check away.
 * ⚠ A KEY THE PERSON HOLDS OUTSIDE THEIR SECTIONS IS NEVER DROPPED: the saved set is the whole set the
 * server served, changed only by the switches on screen (and the key Quality check brings).
 * The keys are the server's `staff_tables_admin.ADMIN_TABLE_KEYS` / `REVIEWER_TABLE_KEYS`.
 *
 * Sprint M2b (D9, 2026-11-12): under "Admin permissions", the PAGES, one heading per group (the server's
 * `v2_keys`, in its order) and a switch per page key. What the server will not let anyone here store is
 * drawn LOCKED with its reason (`never_grantable`, `lead_only`, `alias`), on when it opens for them today.
 * The set is ONE list — today's keys and the stored page keys (`v2_held`) — saved with `v2: true`; the
 * server adds a page's view to its change, and the switches follow its answer. "Custom" and Reset weigh
 * the page switches against the role's own (`v2_preset`, or the Admins table's `table_presets`). */
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
  /** M1b (owner O12): the Team table the page was opened from — draw ONLY that table's section. "Custom"
   *  and Reset then speak of that table's keys alone (against the server's `table_presets[table]`); every
   *  other key the person holds rides along untouched in the saved set. Absent: every section they sit in. */
  table?: TeamTable
}

type Refusal = { message: string; code: string }

const sameSet = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && a.every((k) => b.includes(k))

/** M2b: the whole set a card starts from — today's keys, then the stored page keys. */
const heldBy = (v: { permissions: string[]; v2_held?: string[] }) => [...v.permissions, ...(v.v2_held ?? [])]
/** The page a v2 key opens (`sponsors.edit` -> `sponsors`); a key of today has none. */
const pageOf = (key: string) => (key.includes('.') ? key.slice(0, key.indexOf('.')) : null)

export default function PermissionEditor({ adminId, name, token, onSaved, initial, table }: PermissionEditorProps) {
  const { t } = useT()
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
  // T3, with no `tables`, shows both). They stay put while the switches move, and follow the next read.
  const tables = view?.tables
  const seatedAdmins = !tables || tables.includes('admins')
  const inAdmins = (!table || table === 'admins') && seatedAdmins
  const inReviewers = (!table || table === 'reviewers') && (!tables || tables.includes('reviewers'))
  // Quality check brings Applications (`see_all`) along (TD-499: the server's IMPLIES). Somebody NOT in Admins has
  // no "Applications" switch, so turning Quality check off takes it away again unless it was an ADMIN
  // key before (held without Quality check), so turning Quality check off never leaves somebody seated at
  // Admins by a key nobody ticked (T2's rule, kept). In Admins the switch is on screen and stays as it is.
  const seeAllWasAdmin = !!view && view.permissions.includes('see_all') && !view.permissions.includes('qc')
  // M2b: a page's view goes with its change, and off with it (the server stores the view anyway).
  const grantable = useMemo(() => new Set((view?.v2_keys ?? []).flatMap((g) => g.keys)
    .filter((k) => k.grantable).map((k) => k.key)), [view])
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

  if (loadFailed) {
    return <p className="text-sm text-critical-600">{t('admin.permEditor.loadFailed', { name })}</p>
  }
  if (!view) return null
  const who = view.name || name
  const preset = t(`admin.role.${view.role}`)
  // `?? []`: an api a few minutes behind this page serves no history yet; the list says "none".
  const history = <PermissionHistory rows={view.history ?? []} name={who} role={view.role} />
  if (!view.editable && !view.is_active) {
    // A revoked person is not editable (review fix 8): say how to get there, draw no dead switches —
    // but their history still reads.
    return (<>
      <p className="text-sm text-ground-500">{t('admin.permEditor.restoreFirst', { name: who })}</p>
      {history}
    </>)
  }
  // Sprint T3 (M2): somebody active whose set this viewer may not change (an organisation admin, your
  // own) — their keys as LOCKED switches under one line saying so: no Save, no Reset, no dry run.
  const fixed = !view.editable

  const save = async () => {
    setBusy(true)
    try {
      const p = await saveStaffPermissions(adminId, want, false, { token })
      setView({ ...view, permissions: p.permissions, custom: p.custom, v2_held: p.v2_held ?? view.v2_held })
      setWant(heldBy({ permissions: p.permissions, v2_held: p.v2_held ?? view.v2_held }))
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

  const names = (keys: string[]) => keys.map((k) => `“${permName(t, k)}”`).join(', ')
  const line = (): string => {
    if (saved) return t('admin.permEditor.saved', { name: who })
    if (!dirty) return t('admin.permEditor.noChange', { name: who })
    if (!plan) return ''
    const parts: string[] = []
    if (plan.added.length) parts.push(t('admin.permEditor.gives', { name: who, list: names(plan.added) }))
    if (plan.removed.length) parts.push(t('admin.permEditor.takes', { name: who, list: names(plan.removed) }))
    for (const c of plan.consequences) parts.push(t(`admin.permEditor.effect.${c}`, { name: who }))
    if (!plan.consequences.length) parts.push(t('admin.permEditor.nothingElse'))
    return parts.join(' ')
  }

  const row = (key: string) => {
    const on = want.includes(key)
    // Applications is locked on while Quality check holds it (TD-499).
    const locked = key === 'see_all' && want.includes('qc')
    const changed = on !== held.includes(key)
    return (
      <div key={key} data-key={key} className="flex items-center justify-between gap-4 py-2.5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ground-900">
            {t(`admin.perm.${key}.name`)}
            {changed && (
              <span className="rounded-full bg-primary-50 px-2 py-px text-[11px] font-semibold text-primary-700">
                {t('admin.permEditor.changed')}
              </span>
            )}
          </div>
          <div className="text-[13px] text-ground-500">{t(`admin.perm.${key}.desc`)}</div>
          {key === 'qc' && (
            <div className="text-xs text-ground-500" data-testid="qc-brings-see-all">{t('admin.permEditor.qcBrings')}</div>
          )}
        </div>
        <Toggle on={on} disabled={fixed || locked || busy} label={t(`admin.perm.${key}.name`)}
          onChange={(v) => flip(key, v)} />
      </div>
    )
  }

  const group = (testId: string, title: string, keys: readonly string[]) => {
    const shown = keys.filter((k) => view.keys.includes(k))
    if (shown.length === 0) return null
    return (
      <div className="mt-2 border-t border-ground-100 pt-3" data-testid={testId}>
        <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ground-500">{title}</h3>
        {shown.map(row)}
      </div>
    )
  }
  // M2b: one page key. Locked when nobody here may store it, on when it opens for them today.
  const pageRow = (k: StaffV2Key) => {
    const on = k.grantable ? want.includes(k.key) : k.held
    const changed = k.grantable && on !== held.includes(k.key)
    return (
      <div key={k.key} data-key={k.key} className="flex items-center justify-between gap-4 py-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-ground-900">
            {permName(t, k.key)}
            {changed && (
              <span className="rounded-full bg-primary-50 px-2 py-px text-[11px] font-semibold text-primary-700">
                {t('admin.permEditor.changed')}
              </span>
            )}
          </div>
          {k.reason && (
            <div className="text-xs text-ground-500" data-testid={`v2-reason-${k.key}`}>
              {t(`admin.permV2.reason.${k.reason}`)}</div>
          )}
        </div>
        <Toggle on={on} disabled={fixed || busy || !k.grantable} label={permName(t, k.key)}
          onChange={(v) => flip(k.key, v)} />
      </div>
    )
  }
  const pages = (view.v2_keys ?? []).filter((g) => g.keys.length > 0)
  const pageGroups = pages.length === 0 ? null : (
    <div className="mt-2 border-t border-ground-100 pt-3" data-testid="perm-section-pages">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-ground-500">{t('admin.permV2.title')}</h3>
      <p className="mb-1 text-xs text-ground-500">{t('admin.permV2.intro')}</p>
      {pages.map((g) => (
        <div key={g.group} className="mt-2" data-testid={`perm-pages-${g.group}`}>
          <h4 className="text-xs font-semibold text-ground-700">{t(`admin.permV2.group.${g.group}`)}</h4>
          {g.keys.map(pageRow)}
        </div>
      ))}
    </div>
  )

  // A key the server adds later still gets a switch, under the sections, rather than vanishing.
  const known: readonly string[] = [...TABLE_KEYS.admins, ...TABLE_KEYS.reviewers]
  const other = view.keys.filter((k) => !known.includes(k))
  // O12: opened from one table, "Custom" and Reset weigh that table's keys only (M2b: the Admins table's
  // keys include the page keys, and its served preset ends with the role's own).
  const scope: readonly string[] | null = table === 'admins' ? [...TABLE_KEYS.admins, ...Array.from(grantable)]
    : table ? TABLE_KEYS[table] : null
  const mine = (keys: readonly string[]) => (scope ? keys.filter((k) => scope.includes(k)) : [...keys])
  const fullPreset = [...view.preset, ...(view.v2_preset ?? [])]
  const presetHere = scope ? (view.table_presets?.[table as TeamTable] ?? mine(fullPreset)) : fullPreset
  const resetTo = scope ? [...want.filter((k) => !scope.includes(k)), ...presetHere] : fullPreset
  // Review (d): a NULL row (the server's `custom` false) holds its preset although it stores no page key
  // (a NULL finance row reads the organisation through its Admins seat), so until something is changed it
  // is never "Custom" and Reset has nothing to do. The server answers; the web does not re-derive it.
  const onPreset = view.custom === false && !dirty
  const custom = !onPreset && !sameSet(mine(want), presetHere)
  // Review fix 1: a Reviewer or QC holding neither key would vanish from People; the server refuses
  // it (`would_leave_people`) and the hint says why before the refusal arrives.
  const unlisted = ['reviewer', 'qc'].includes(view.role)
    && !want.includes('review') && !want.includes('qc')
  const text = line()

  return (<>
    <section className="rounded-xl border bg-ground-0 px-4 py-4 shadow-sm sm:px-5"
      aria-labelledby={`perm-editor-${adminId}`} data-testid="permission-editor">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id={`perm-editor-${adminId}`} className="text-base font-semibold text-ground-900">
          {t('admin.permEditor.title', { name: who })}
        </h2>
        {custom && (
          <span className="rounded-full bg-caution-100 px-2 py-0.5 text-xs font-semibold text-caution-700">
            {t('admin.permEditor.custom')}
          </span>
        )}
      </div>
      <p className="mb-2 mt-0.5 text-sm text-ground-500" data-testid={fixed ? 'perm-fixed' : undefined}>
        {fixed ? t('admin.permEditor.fixed', { name: who }) : t('admin.permEditor.subtitle', { preset })}</p>
      {inAdmins && group('perm-section-admins', t('admin.team.colKeys.admins'), TABLE_KEYS.admins)}
      {inAdmins && pageGroups}
      {inReviewers && group('perm-section-reviewers', t('admin.team.colKeys.reviewers'), TABLE_KEYS.reviewers)}
      {unlisted && !fixed && (
        <p className="text-xs text-caution-700" data-testid="unlisted-hint">
          {t('admin.permEditor.unlistedHint')}
        </p>
      )}
      {other.length > 0 && <div className="mt-2 border-t border-ground-100 pt-3">{other.map(row)}</div>}

      {fixed ? null : refusal ? (
        <div role="alert" className="mt-4 rounded-lg bg-critical-50 px-3.5 py-3 text-sm text-critical-700">
          {refusal.message}
        </div>
      ) : text ? (
        <div role="status" className="mt-4 rounded-lg bg-primary-50 px-3.5 py-3 text-sm text-ground-900">
          {text}
        </div>
      ) : null}

      {!fixed && (<>
      <div className="mt-4 flex flex-wrap gap-2.5">
        <button type="button" onClick={save} disabled={!dirty || busy || !!refusal || !plan}
          className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t('admin.permEditor.save')}
        </button>
        {/* T3 review: no "back to the preset" for somebody not active or sitting in no table. */}
        {view.is_active && !(tables && tables.length === 0) && (
        <button type="button" disabled={busy || onPreset || sameSet(want, resetTo)} data-testid="perm-reset"
          onClick={() => { setSaved(false); setWant(resetTo) }}
          className="rounded-lg border border-ground-300 px-4 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50">
          {t('admin.permEditor.reset', { preset })}
        </button>)}
      </div>
      <p className="mt-3 text-xs text-ground-500">{t('admin.permEditor.footnote')}</p>
      </>)}
    </section>
    {history}
  </>)
}

'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Toggle from '@/components/Toggle'
import PermissionHistory from './PermissionHistory'
import { useT } from '@/lib/i18n'
import {
  getStaffPermissions, saveStaffPermissions,
  type StaffPermissionsPlan, type StaffPermissionsView,
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
 * the one local rule, Quality check bringing See all students, only mirrors what the server answers.
 *
 * Loaded as its own chunk by `LazyPermissionEditor` — most visits to People never open it.
 *
 * Under the card, **Changes** (2026-10-22): the same GET's `history`, re-read after every save so the
 * new line appears. A page that already holds the GET (the admin person page draws its header from
 * it) passes it as `initial`, and the card asks nothing more until a save.
 */

/**
 * Team tables T3 (owner, 2026-11-03): ONE SECTION PER TABLE THE PERSON SITS IN — the server's `tables`.
 * "Admin permissions" (`see_all`, `spending`, the three payment keys) only for somebody in Admins;
 * "Reviewer permissions" (`review`, `qc`) only for somebody in Reviewers. The old Students / Money groups,
 * which showed every key to everyone, are gone. "See all students" is an ADMIN permission; Quality check
 * IMPLIES it (the server's `staff_permissions.IMPLIES`, T5b; TD-499), so it comes on with Quality check and
 * stays ticked and locked while Quality check is on; turning it off never takes Quality check away.
 * ⚠ A KEY THE PERSON HOLDS OUTSIDE THEIR SECTIONS IS NEVER DROPPED: the saved set is the whole set the
 * server served, changed only by the switches on screen (and the key Quality check brings).
 * The keys are the server's `staff_tables_admin.ADMIN_TABLE_KEYS` / `REVIEWER_TABLE_KEYS`. */
export const TABLE_KEYS = {
  admins: ['see_all', 'spending', 'payments_prepare', 'payments_check', 'payments_approve',
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
}

type Refusal = { message: string; code: string }

const sameSet = (a: readonly string[], b: readonly string[]) =>
  a.length === b.length && a.every((k) => b.includes(k))

export default function PermissionEditor({ adminId, name, token, onSaved, initial }: PermissionEditorProps) {
  const { t } = useT()
  const [view, setView] = useState<StaffPermissionsView | null>(initial ?? null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [want, setWant] = useState<string[]>(initial?.permissions ?? [])
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
      .then((v) => { if (live) { setView(v); setWant(v.permissions) } })
      .catch(() => { if (live) setLoadFailed(true) })
    return () => { live = false }
  }, [adminId, token, initial])

  const dirty = !!view && !sameSet(want, view.permissions)

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
  const inAdmins = !tables || tables.includes('admins')
  const inReviewers = !tables || tables.includes('reviewers')
  // Quality check brings See all students along (TD-499: the server's IMPLIES). Somebody NOT in Admins has
  // no "See all students" switch, so turning Quality check off takes it away again unless it was an ADMIN
  // key before (held without Quality check), so turning Quality check off never leaves somebody seated at
  // Admins by a key nobody ticked (T2's rule, kept). In Admins the switch is on screen and stays as it is.
  const seeAllWasAdmin = !!view && view.permissions.includes('see_all') && !view.permissions.includes('qc')
  const flip = useCallback((key: string, on: boolean) => {
    setSaved(false)
    setWant((cur) => {
      let next = on ? [...cur, key] : cur.filter((k) => k !== key)
      if (key === 'qc' && on && !next.includes('see_all')) next = [...next, 'see_all']
      if (!inAdmins && key === 'qc' && !on && !seeAllWasAdmin) next = next.filter((k) => k !== 'see_all')
      return next
    })
  }, [inAdmins, seeAllWasAdmin])

  if (loadFailed) {
    return <p className="text-sm text-critical-600">{t('admin.permEditor.loadFailed', { name })}</p>
  }
  if (!view) return null
  const who = view.name || name
  const preset = t(`admin.role.${view.role}`)
  // `?? []`: an api a few minutes behind this page serves no history yet; the list says "none".
  const history = <PermissionHistory rows={view.history ?? []} name={who} role={view.role} />
  if (!view.editable) {
    // A revoked person is not editable (review fix 8): say how to get there, draw no dead switches —
    // but their history still reads.
    return (<>
      <p className="text-sm text-ground-500">{t(view.is_active ? 'admin.permEditor.fixed'
        : 'admin.permEditor.restoreFirst', { name: who })}</p>
      {history}
    </>)
  }

  const save = async () => {
    setBusy(true)
    try {
      const p = await saveStaffPermissions(adminId, want, false, { token })
      setView({ ...view, permissions: p.permissions, custom: p.custom })
      setWant(p.permissions)
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

  const names = (keys: string[]) => keys.map((k) => `“${t(`admin.perm.${k}.name`)}”`).join(', ')
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
    // See all students is locked on while Quality check holds it (TD-499).
    const locked = key === 'see_all' && want.includes('qc')
    const changed = on !== view.permissions.includes(key)
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
        <Toggle on={on} disabled={locked || busy} label={t(`admin.perm.${key}.name`)}
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
  // A key the server adds later still gets a switch, under the sections, rather than vanishing.
  const known: readonly string[] = [...TABLE_KEYS.admins, ...TABLE_KEYS.reviewers]
  const other = view.keys.filter((k) => !known.includes(k))
  const custom = !sameSet(want, view.preset)
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
        <span className="rounded-full border border-ground-200 px-2 py-0.5 text-xs font-semibold text-ground-700">
          {preset}
        </span>
        {custom && (
          <span className="rounded-full bg-caution-100 px-2 py-0.5 text-xs font-semibold text-caution-700">
            {t('admin.permEditor.custom')}
          </span>
        )}
      </div>
      <p className="mb-2 mt-0.5 text-sm text-ground-500">{t('admin.permEditor.subtitle', { preset })}</p>
      {inAdmins && group('perm-section-admins', t('admin.team.colKeys.admins'), TABLE_KEYS.admins)}
      {inReviewers && group('perm-section-reviewers', t('admin.team.colKeys.reviewers'), TABLE_KEYS.reviewers)}
      {unlisted && (
        <p className="text-xs text-caution-700" data-testid="unlisted-hint">
          {t('admin.permEditor.unlistedHint')}
        </p>
      )}
      {other.length > 0 && <div className="mt-2 border-t border-ground-100 pt-3">{other.map(row)}</div>}

      {refusal ? (
        <div role="alert" className="mt-4 rounded-lg bg-critical-50 px-3.5 py-3 text-sm text-critical-700">
          {refusal.message}
        </div>
      ) : text ? (
        <div role="status" className="mt-4 rounded-lg bg-primary-50 px-3.5 py-3 text-sm text-ground-900">
          {text}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2.5">
        <button type="button" onClick={save} disabled={!dirty || busy || !!refusal || !plan}
          className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t('admin.permEditor.save')}
        </button>
        {/* T3 review: no "back to the preset" for somebody not active or sitting in no table. */}
        {view.is_active && !(tables && tables.length === 0) && (
        <button type="button" disabled={busy || sameSet(want, view.preset)} data-testid="perm-reset"
          onClick={() => { setSaved(false); setWant(view.preset) }}
          className="rounded-lg border border-ground-300 px-4 py-2 text-sm font-medium text-ground-700 hover:bg-ground-50 disabled:opacity-50">
          {t('admin.permEditor.reset', { preset })}
        </button>)}
      </div>
      <p className="mt-3 text-xs text-ground-500">{t('admin.permEditor.footnote')}</p>
    </section>
    {history}
  </>)
}

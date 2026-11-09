'use client'

import { useEffect, useMemo, useState } from 'react'
import Sheet from '@/components/Sheet'
import TableChips, { CHIP } from '@/components/admin/TableChips'
import { useT } from '@/lib/i18n'
import { roleBadgeClass } from '@/lib/roleBadge'
import {
  changeTeamTable, getTeamCandidates,
  type TeamCandidate, type TeamRemove, type TeamTableName, type TeamTablePlan,
} from '@/lib/admin-api'

/**
 * Team tables T2 (2026-11-03; the TeamAdmins / TeamReviewers boards the owner approved): the pieces both
 * Team tables share — the "Also in" chips, a table's OWN permission chips, the Remove link (or why there
 * is none), the **Add** sheet and the **Remove** confirm.
 *
 * ⚠ THE SERVER DECIDES. Who is offered in Add is `GET admin/team/{table}/candidates/`; where a Remove is
 * accepted is each row's served `remove`; what an Add or a Remove does is the endpoint's dry run, worded
 * here. Nothing in this file re-derives a rule, so the screen cannot offer what the endpoint refuses.
 * Never touches a sign-in; never emails — the sheet says so.
 */

type Seat = { tables?: string[]; lead?: boolean }

/** The person's OTHER tables, as small chips ("Admin (lead)" for the organisation admin). The chips are
 *  `TableChips`, which a person's page (Sprint T3) draws under the name. */
export function AlsoIn({ row, here }: { row: Seat; here: TeamTableName | 'mentors' }) {
  if (!(row.tables ?? []).some((x) => x !== here)) return <span className="text-ground-400">—</span>
  return <TableChips tables={row.tables} lead={row.lead} except={here} testId="also-in" />
}

/** One table's own permission chips (owner ruling 2: each table shows only its own keys). */
export function KeyChips({ keys }: { keys?: string[] }) {
  const { t } = useT()
  if (!keys || keys.length === 0) return <span className="text-ground-400">—</span>
  return (
    <span className="inline-flex flex-wrap gap-1" data-testid="table-keys">
      {keys.map((k) => (
        <span key={k} className="rounded-full border border-info-200 bg-info-50 px-2 py-0.5 text-[11px] text-info-700">
          {t(`admin.perm.${k}.name`)}
        </span>
      ))}
    </span>
  )
}

/** "Remove from {table}", or the short reason there is none (only table, open cases…). Nothing when
 *  the row carries no entry for this table (not in it, or not the viewer's to act on). */
export function RemoveControl({ remove, table, busy, onRemove }: {
  remove?: TeamRemove
  table: TeamTableName
  busy?: boolean
  onRemove: () => void
}) {
  const { t } = useT()
  if (!remove || !(table in remove)) return null
  const code = remove[table]
  if (code === null) {
    return (
      <button type="button" disabled={busy} onClick={onRemove} data-testid={`remove-from-${table}`}
        className="text-xs font-medium text-critical-600 hover:text-critical-800 disabled:opacity-50">
        {t(`admin.team.removeFrom.${table}`)}
      </button>
    )
  }
  // 'last_table' (their only table) shows nothing: Revoke sits beside it (owner 2026-11-07).
  if (code === 'mentors_only' || code === 'has_open_cases') {
    return <span className="text-[11px] text-ground-400" data-testid={`remove-note-${table}`}>
      {t(`admin.team.note.${code}`)}</span>
  }
  return null
}

type T = (k: string, vars?: Record<string, string>) => string

const effects = (t: T, plan: TeamTablePlan, name: string) => [
  ...plan.consequences.map((c) => t(`admin.permEditor.effect.${c}`, { name })),
  plan.opens_admin_pages ? t('admin.team.opensAdminPages') : '',
  plan.finance_check_off ? t('admin.team.financeCheckOff') : '',
  plan.becomes_mentor ? t('admin.team.becomesMentor', { name }) : '',
].filter(Boolean)

/** Team -> Add Admin / Add Reviewer: an EXISTING member of the team, never a new person. `only` (Sprint T3,
 *  D8: a mentor's page): offer that one person, already picked — still from the server's own candidates,
 *  so the sheet can offer nobody the endpoint would refuse. */
export function TeamAddSheet({ open, table, token, onClose, onDone, only }: {
  open: boolean
  table: TeamTableName
  token: string | null
  onClose: () => void
  onDone: (text: string) => void
  only?: number
}) {
  const { t } = useT()
  const [people, setPeople] = useState<TeamCandidate[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [query, setQuery] = useState('')
  const [picked, setPicked] = useState<number | null>(null)
  const [plan, setPlan] = useState<TeamTablePlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !token) return
    let live = true
    setPeople(null); setFailed(false); setQuery(''); setPicked(null); setError(null); setPlan(null)
    getTeamCandidates(table, { token })
      .then((d) => {
        if (!live) return
        const offered = only === undefined ? d.candidates : d.candidates.filter((p) => p.id === only)
        setPeople(offered)
        if (only !== undefined && offered.length === 1) setPicked(only)
      })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [open, token, table, only])

  // What adding the picked person would do — the server's dry run, worded under the list.
  useEffect(() => {
    if (!token || picked === null) { setPlan(null); return }
    let live = true
    setPlan(null); setError(null)
    changeTeamTable(table, picked, 'add', true, { token })
      .then((p) => { if (live) setPlan(p) })
      .catch((e: Error) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [token, table, picked])

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return (people ?? []).filter((p) => !q || p.name.toLowerCase().includes(q) || p.email.toLowerCase().includes(q))
  }, [people, query])
  const chosen = (people ?? []).find((p) => p.id === picked) ?? null

  const add = async () => {
    if (!token || !chosen) return
    setBusy(true); setError(null)
    try {
      await changeTeamTable(table, chosen.id, 'add', false, { token })
      onDone(t(`admin.team.added.${table}`, { name: chosen.name }))
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.actionFailed'))
    } finally { setBusy(false) }
  }

  const said = chosen && plan ? effects(t, plan, chosen.name) : []
  return (
    <Sheet open={open} onClose={onClose} busy={busy} size="lg" testId={`team-add-${table}`}
      title={t(`admin.team.add.${table}`)} description={t(`admin.team.addIntro.${table}`)}
      footer={(
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={add} disabled={!chosen || !plan || busy} data-testid="team-add-confirm"
            className="min-h-11 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
            {chosen ? t(`admin.team.addCta.${table}`, { name: chosen.name }) : t('admin.team.choose')}
          </button>
          <button type="button" onClick={onClose} disabled={busy}
            className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-700 hover:bg-ground-50">
            {t('common.cancel')}
          </button>
        </div>
      )}>
      <div className="space-y-3">
        {only === undefined && <label className="block text-sm text-ground-600">
          {t('admin.team.search')}
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            className="mt-1 w-full rounded-lg border border-ground-300 px-3 py-2 text-base focus:border-info-500 focus:ring-2 focus:ring-info-500" />
        </label>}
        {failed && <p className="text-sm text-critical-600" role="alert">{t('admin.team.loadFailed')}</p>}
        {!people && !failed && <p className="text-sm text-ground-500">{t('common.loading')}</p>}
        {people && (shown.length === 0 ? (
          <p className="text-sm text-ground-500" data-testid="team-add-none">{t('admin.team.none')}</p>
        ) : (
          <div role="listbox" aria-label={t('admin.team.search')} className="divide-y rounded-lg border border-ground-200">
            {shown.map((p) => (
              <button key={p.id} type="button" role="option" aria-selected={picked === p.id}
                onClick={() => setPicked(p.id)} data-testid={`team-candidate-${p.id}`}
                className={`flex min-h-11 w-full flex-wrap items-center justify-between gap-2 px-3 py-2 text-left text-sm ${picked === p.id
                  ? 'bg-info-50 text-info-900' : 'text-ground-800 hover:bg-ground-50'}`}>
                <span className="min-w-0 break-words"><strong>{p.name}</strong> · {p.email}</span>
                <span className="inline-flex flex-wrap gap-1">
                  {p.lead && <span className={`rounded-full px-2 py-0.5 text-[11px] ${roleBadgeClass('org_admin')}`}>{t('admin.role.org_admin')}</span>}
                  {!p.lead && p.tables.map((x) => (
                    <span key={x} className={`rounded-full px-2 py-0.5 text-[11px] ${CHIP[x] ?? 'bg-ground-100'}`}>
                      {t(`admin.team.chip.${x}`)}
                    </span>
                  ))}
                </span>
              </button>
            ))}
          </div>
        ))}
        {said.length > 0 && (
          <p role="status" className="rounded-lg bg-primary-50 px-3 py-2 text-sm text-ground-900">{said.join(' ')}</p>
        )}
        {error && <p className="text-sm text-critical-600" role="alert">{error}</p>}
      </div>
    </Sheet>
  )
}

/** Team -> a row -> "Remove from {table}": a dry run first, so the confirm says what it does. */
export function TeamRemoveSheet({ person, table, token, onClose, onDone }: {
  person: { id: number; name: string } | null
  table: TeamTableName
  token: string | null
  onClose: () => void
  onDone: (text: string) => void
}) {
  const { t } = useT()
  const [plan, setPlan] = useState<TeamTablePlan | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!person || !token) return
    let live = true
    setPlan(null); setError(null)
    changeTeamTable(table, person.id, 'remove', true, { token })
      .then((p) => { if (live) setPlan(p) })
      .catch((e: Error) => { if (live) setError(e.message) })
    return () => { live = false }
  }, [person, token, table])

  const go = async () => {
    if (!token || !person) return
    setBusy(true); setError(null)
    try {
      await changeTeamTable(table, person.id, 'remove', false, { token })
      onDone(t(`admin.team.removed.${table}`, { name: person.name }))
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.actionFailed'))
    } finally { setBusy(false) }
  }

  const name = person?.name ?? ''
  return (
    <Sheet open={!!person} onClose={onClose} busy={busy} tone="critical" role="alertdialog"
      testId={`team-remove-${table}`} title={t(`admin.team.removeTitle.${table}`, { name })}
      footer={(
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={go} disabled={!plan || busy} data-testid="team-remove-confirm"
            className="min-h-11 rounded-lg bg-critical-fill px-4 font-medium text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50">
            {t(`admin.team.removeFrom.${table}`)}
          </button>
          <button type="button" onClick={onClose} disabled={busy}
            className="min-h-11 rounded-lg border border-ground-300 bg-ground-0 px-4 text-ground-700 hover:bg-ground-50">
            {t('common.cancel')}
          </button>
        </div>
      )}>
      <div className="space-y-2 text-sm text-ground-700">
        <p>{t(`admin.team.removeBody.${table}`, { name })}</p>
        {!plan && !error && <p className="text-ground-500">{t('common.loading')}</p>}
        {plan && effects(t, plan, name).map((line) => (
          <p key={line} className="rounded-lg bg-primary-50 px-3 py-2 text-ground-900" data-testid="team-remove-effect">{line}</p>
        ))}
        {error && <p className="text-critical-600" role="alert">{error}</p>}
      </div>
    </Sheet>
  )
}

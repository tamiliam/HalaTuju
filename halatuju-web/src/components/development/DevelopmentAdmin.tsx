'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
// The hook from the LEAF (no Supabase client in this chunk) — see `lib/adminAuthCore.ts`.
import { useAdminAuth } from '@/lib/adminAuthCore'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { isSuperRole } from '@/lib/superRole'
import {
  archiveModule, deleteModule, getModules, updateModule, type ModuleRow, type ModuleStatus, type ModulesPayload,
} from '@/lib/admin-api/development'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import PanelTabs from '@/components/admin/PanelTabs'
import ModuleForm from './ModuleForm'
import { MAKER_ROLES, audienceLabel, contentsLabel, giftHref } from './shared'

/**
 * Programme → **Development** (student maintenance S10, 2026-11-02; the ModulesAdmin board): short modules that
 * help the organisation's scholars grow, done on My Bursary → Growth.
 *
 * ⚠ EVERY RULE IS THE SERVER'S (`apps/scholarship/development.py`): who may make one (super, organisation admin,
 * admin — `may_make`), who it is for (decided when read), the status (scheduled is read from the time), the
 * task-type lock at the first start, the files and the two emails. This screen offers Delete / Archive / Put
 * back only where the row's `can_delete` / `can_archive` / `can_restore` say so.
 * ⚠ ITS OWN CHUNK: the route carries only a loader (`lazySource`), so the first-load median is untouched.
 */
const K = 'admin.development'
const TABS: readonly ModuleStatus[] = ['published', 'scheduled', 'draft', 'archived']
const LINK = 'inline-flex min-h-11 items-center text-sm font-medium text-primary-600 hover:text-primary-800 hover:underline disabled:opacity-50'

type Editing = { row: ModuleRow | null } | null
type Banner = { ok: boolean; text: string } | null
type Act = 'archive' | 'delete' | 'restore'

export default function DevelopmentAdmin({ programme }: { programme?: string }) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = isSuperRole(role) ? 'super' : (role?.role ?? '')
  const allowed = MAKER_ROLES.includes(r)
  const [data, setData] = useState<ModulesPayload | null>(null)
  const [failed, setFailed] = useState<'' | 'load' | 'programme_required'>('')
  const [tab, setTab] = useState<ModuleStatus>('published')
  const [editing, setEditing] = useState<Editing>(null)
  const [banner, setBanner] = useState<Banner>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    if (!token || !allowed) return
    try {
      setData(await getModules(programme, { token })); setFailed('')
    } catch (err) {
      setFailed((err as { code?: string })?.code === 'programme_required' ? 'programme_required' : 'load')
    }
  }, [token, allowed, programme])
  useEffect(() => { void load() }, [load])

  if (role && !allowed) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const act = async (row: ModuleRow, action: Act) => {
    if (!token) return
    if (action !== 'restore' && !window.confirm(t(`${K}.confirm.${action}`, { title: row.title }))) return
    setBusyId(row.id); setBanner(null)
    try {
      if (action === 'archive') await archiveModule(row.id, { token })
      else if (action === 'delete') await deleteModule(row.id, { token })
      else await updateModule(row.id, { action: 'publish' }, { token })
      setBanner({ ok: true, text: t(`${K}.done.${action === 'archive' ? 'archived' : action === 'delete' ? 'deleted' : 'restored'}`) })
    } catch (err) {
      const code = (err as { code?: string })?.code
      setBanner({ ok: false, text: t(`${K}.error.${code === 'archive_instead' ? code : 'generic'}`) })
    } finally {
      setBusyId(null)
      void load()
    }
  }

  const rows = (data?.modules ?? []).filter((m) => m.status === tab)

  return (
    <div className="space-y-5" data-testid="development-admin">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ground-900">{t(`${K}.title`)}</h1>
          <p className="text-sm text-ground-600">{t(`${K}.intro`)}</p>
        </div>
        {data && !editing && (
          <button type="button" onClick={() => { setEditing({ row: null }); setBanner(null) }} data-testid="module-new"
            className="min-h-11 shrink-0 rounded-lg bg-brand-fill px-4 font-medium text-brand-fill-ink hover:bg-brand-fill-hover">
            {t(`${K}.new`)}
          </button>
        )}
      </div>

      {banner && (
        <p role={banner.ok ? 'status' : 'alert'}
          className={`rounded-lg border p-3 text-sm ${banner.ok ? 'border-positive-200 bg-positive-50 text-positive-800'
            : 'border-caution-200 bg-caution-50 text-caution-900'}`}>{banner.text}</p>
      )}
      {failed === 'load' && <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadError`)}</p>}
      {failed === 'programme_required' && <p className="text-sm text-ground-700">{t(`${K}.chooseGift`)}</p>}
      {!data && !failed && <p className="text-sm text-ground-500">{t('common.loading')}</p>}

      {data && editing && (
        <ModuleForm key={editing.row?.id ?? 'new'} row={editing.row} audiences={data.audiences} emailOn={data.email_switch_on} limits={data.limits}
          programme={programme} token={token} t={t}
          onCancel={() => { setEditing(null); void load() }}
          onSaved={(saved, done, keepOpen) => {
            setBanner({ ok: true, text: t(`${K}.done.${done}`) })
            if (keepOpen) setEditing({ row: saved })
            else { setEditing(null); setTab(saved.status) }
            void load()
          }} />
      )}

      {data && (<>
        <PanelTabs ariaLabelKey={`${K}.tabsAria`} active={tab} onSelect={(k) => setTab(k)}
          tabs={TABS.map((k) => ({ key: k, labelKey: `${K}.tab.${k}`, count: data.counts[k] ?? 0 }))} />
        {rows.length === 0 ? (
          <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500"
            data-testid="modules-empty">{t(`${K}.empty.${tab}`)}</div>
        ) : (
          <TableFrame minWidth={820} label={t(`${K}.title`)}>
            <table className="w-full text-sm">
              <thead className="border-b bg-ground-50">
                <tr>
                  {['module', 'for', 'due', 'done'].map((c) => <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>)}
                  <th className={TH}><span className="sr-only">{t(`${K}.col.actions`)}</span></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((m) => {
                  const by = m.author.name || m.author.email
                  return (
                    <tr key={m.id} data-testid={`module-row-${m.id}`}>
                      <td className="px-4 py-3">
                        <span className="break-words font-medium text-ground-900">{m.title}</span>
                        <span className="block text-xs text-ground-500">
                          {[contentsLabel(t, m),
                            by ? (m.author.role ? t(`${K}.byRole`, { name: by, role: t(`admin.role.${m.author.role}`) })
                              : t(`${K}.by`, { name: by })) : '',
                            m.locked ? t(`${K}.started`) : ''].filter(Boolean).join(' · ')}
                        </span>
                      </td>
                      <td className="px-4 py-3">{audienceLabel(t, m)}</td>
                      <td className="whitespace-nowrap px-4 py-3">{m.due_on ? formatDate(m.due_on) : t(`${K}.noDue`)}</td>
                      <td className="whitespace-nowrap px-4 py-3" data-testid={`module-done-${m.id}`}>
                        {m.status === 'draft' ? '—' : (
                          [t(`${K}.doneOf`, { n: String(m.done_count), count: String(m.audience_count) }),
                            m.to_review_count ? t(`${K}.toReview`, { count: String(m.to_review_count) }) : '']
                            .filter(Boolean).join(' · '))}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="flex gap-4">
                          {m.status !== 'draft' && (
                            <Link href={giftHref(`/admin/programme/development/${m.id}`, programme)} className={LINK}
                              data-testid={`module-progress-${m.id}`}>{t(`${K}.action.progress`)}</Link>
                          )}
                          <button type="button" className={LINK} disabled={busyId === m.id || !!editing}
                            data-testid={`module-edit-${m.id}`}
                            onClick={() => { setEditing({ row: m }); setBanner(null) }}>{t(`${K}.action.edit`)}</button>
                          {(['archive', 'restore', 'delete'] as const)
                            .filter((a) => (a === 'archive' ? m.can_archive : a === 'restore' ? m.can_restore : m.can_delete))
                            .map((a) => (
                              <button key={a} type="button" className={LINK} disabled={busyId === m.id}
                                data-testid={`module-${a}-${m.id}`} onClick={() => act(m, a)}>{t(`${K}.action.${a}`)}</button>
                            ))}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </TableFrame>
        )}
        <p className="text-xs text-ground-600">{t(`${K}.footnote`)}</p>
      </>)}
    </div>
  )
}

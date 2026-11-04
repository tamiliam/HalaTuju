'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { opensDoorOr } from '@/lib/pageGuard'
import {
  deleteAnnouncement, getAnnouncements, withdrawAnnouncement,
  type AnnouncementRow, type AnnouncementStatus, type AnnouncementsPayload,
} from '@/lib/admin-api'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import PanelTabs from '@/components/admin/PanelTabs'
import AnnouncementForm from './AnnouncementForm'

/**
 * Programme → **Announcements** (student maintenance S8, 2026-11-01; the AnnouncementsAdmin board).
 *
 * ⚠ EVERY RULE IS THE SERVER'S (`apps/scholarship/announcements.py`): who may post (super, organisation admin,
 * admin — `may_post`), who sees one (decided when read), what an edit may change once it is out, and the
 * email (the hourly job, once per scholar, only while the organisation's "Announcement" email is on).
 * This screen offers Delete / Withdraw only where the row's `can_delete` / `can_withdraw` say so, and draws
 * the server's own counts ("read N of M", "N sent").
 * ⚠ ITS OWN CHUNK: the route carries only a loader (`lazySource`), so the first-load median is untouched.
 */
export const POSTER_ROLES = ['super', 'org_admin', 'admin']
const K = 'admin.announcements'
const TABS: readonly AnnouncementStatus[] = ['published', 'scheduled', 'draft', 'withdrawn']
const LINK = 'text-sm font-medium text-primary-600 hover:text-primary-800 hover:underline disabled:opacity-50'

type T = (k: string, vars?: Record<string, string>) => string
type Editing = { row: AnnouncementRow | null } | null
type Banner = { ok: boolean; text: string } | null

export function audienceLabel(t: T, row: Pick<AnnouncementRow, 'programme' | 'audience_count'>): string {
  const count = String(row.audience_count)
  return row.programme ? t(`${K}.forGift`, { name: row.programme.name, count }) : t(`${K}.forAll`, { count })
}

export function emailedLabel(t: T, row: AnnouncementRow): string {
  if (!row.email_requested) return t(`${K}.emailed.none`)
  if (row.email_switched_off) return t(`${K}.emailed.off`)
  if (!row.emailed_at && row.status === 'published') return t(`${K}.emailed.pending`)
  if (!row.emailed_at) return t(`${K}.emailed.later`)
  return t(`${K}.emailed.sent`, { count: String(row.emailed_count) })
}

export default function AnnouncementsAdmin({ programme }: { programme?: string }) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const allowed = opensDoorOr(role, 'announcements', POSTER_ROLES)   // T5c P4: the server's door
  const [data, setData] = useState<AnnouncementsPayload | null>(null)
  const [failed, setFailed] = useState<'' | 'load' | 'programme_required'>('')
  const [tab, setTab] = useState<AnnouncementStatus>('published')
  const [editing, setEditing] = useState<Editing>(null)
  const [banner, setBanner] = useState<Banner>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    if (!token || !allowed) return
    try {
      setData(await getAnnouncements(programme, { token })); setFailed('')
    } catch (err) {
      setFailed((err as { code?: string })?.code === 'programme_required' ? 'programme_required' : 'load')
    }
  }, [token, allowed, programme])
  useEffect(() => { void load() }, [load])

  if (role && !allowed) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const act = async (row: AnnouncementRow, action: 'withdraw' | 'delete') => {
    if (!token || !window.confirm(t(`${K}.confirm.${action}`, { title: row.title }))) return
    setBusyId(row.id); setBanner(null)
    try {
      if (action === 'withdraw') await withdrawAnnouncement(row.id, { token })
      else await deleteAnnouncement(row.id, { token })
      setBanner({ ok: true, text: t(`${K}.done.${action === 'withdraw' ? 'withdrawn' : 'deleted'}`) })
    } catch {
      setBanner({ ok: false, text: t(`${K}.error.generic`) })
    } finally {
      setBusyId(null)
      void load()
    }
  }

  const rows = (data?.announcements ?? []).filter((a) => a.status === tab)
  const dateCol = tab === 'scheduled' ? 'scheduled' : tab === 'draft' ? 'created' : 'published'

  return (
    <div className="space-y-5" data-testid="announcements-admin">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ground-900">{t(`${K}.title`)}</h1>
          <p className="text-sm text-ground-600">{t(`${K}.intro`)}</p>
        </div>
        {data && !editing && (
          <button type="button" onClick={() => { setEditing({ row: null }); setBanner(null) }}
            data-testid="announcement-new"
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
        <AnnouncementForm row={editing.row} audiences={data.audiences} emailOn={data.email_switch_on}
          limits={data.limits} programme={programme} token={token} t={t}
          onCancel={() => setEditing(null)}
          onSaved={(saved, done) => {
            setEditing(null); setTab(saved.status)
            setBanner({ ok: true, text: t(`${K}.done.${done}`) })
            void load()
          }} />
      )}

      {data && (<>
        <PanelTabs ariaLabelKey={`${K}.tabsAria`} active={tab} onSelect={(k) => setTab(k)}
          tabs={TABS.map((k) => ({ key: k, labelKey: `${K}.tab.${k}`, count: data.counts[k] ?? 0 }))} />
        {rows.length === 0 ? (
          <div className="rounded-lg border border-dashed bg-ground-0 p-6 text-center text-sm text-ground-500"
            data-testid="announcements-empty">{t(`${K}.empty.${tab}`)}</div>
        ) : (
          <TableFrame minWidth={820} label={t(`${K}.title`)} phoneRows>
            <table className="w-full text-sm">
              <thead className="border-b bg-ground-50">
                <tr>
                  {['announcement', 'for', dateCol, 'emailed', 'read'].map((c) => (
                    <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>
                  ))}
                  <th className={TH}><span className="sr-only">{t(`${K}.col.actions`)}</span></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((a) => {
                  const when = tab === 'scheduled' ? a.publish_at : tab === 'draft' ? a.created_at : a.published_at
                  const by = a.author.name || a.author.email
                  return (
                    <tr key={a.id} data-testid={`announcement-row-${a.id}`}>
                      <td className="px-4 py-3">
                        <span className="font-medium text-ground-900 break-words">{a.title}</span>
                        {a.pinned && (
                          <span className="ml-2 rounded-full bg-info-50 px-2 py-0.5 text-xs text-info-800">{t(`${K}.pinned`)}</span>
                        )}
                        <span className="block text-xs text-ground-500">
                          {by && (a.author.role
                            ? t(`${K}.byRole`, { name: by, role: t(`admin.role.${a.author.role}`) })
                            : t(`${K}.by`, { name: by }))}
                          {a.edited_at ? ` · ${t(`${K}.edited`, { date: formatDate(a.edited_at) })}` : ''}
                        </span>
                      </td>
                      <td className="px-4 py-3" data-label={t(`${K}.col.for`)}>{audienceLabel(t, a)}</td>
                      <td className="whitespace-nowrap px-4 py-3" data-label={t(`${K}.col.${dateCol}`)}>{when ? formatDate(when) : '—'}</td>
                      <td className="px-4 py-3" data-label={t(`${K}.col.emailed`)} data-testid={`announcement-emailed-${a.id}`}>{emailedLabel(t, a)}</td>
                      <td className="whitespace-nowrap px-4 py-3 tabular-nums" data-label={t(`${K}.col.read`)} data-testid={`announcement-read-${a.id}`}>
                        {a.status === 'published' || a.status === 'withdrawn'
                          ? t(`${K}.read`, { read: String(a.read_count), count: String(a.audience_count) }) : '—'}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="flex gap-3">
                          {a.status !== 'withdrawn' && (
                            <button type="button" className={LINK} disabled={busyId === a.id || !!editing}
                              data-testid={`announcement-edit-${a.id}`}
                              onClick={() => { setEditing({ row: a }); setBanner(null) }}>{t(`${K}.action.edit`)}</button>
                          )}
                          {a.can_withdraw && (
                            <button type="button" className={LINK} disabled={busyId === a.id}
                              data-testid={`announcement-withdraw-${a.id}`}
                              onClick={() => act(a, 'withdraw')}>{t(`${K}.action.withdraw`)}</button>
                          )}
                          {a.can_delete && (
                            <button type="button" className={LINK} disabled={busyId === a.id}
                              data-testid={`announcement-delete-${a.id}`}
                              onClick={() => act(a, 'delete')}>{t(`${K}.action.delete`)}</button>
                          )}
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

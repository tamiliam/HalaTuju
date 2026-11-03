'use client'

import Link from 'next/link'
import { useCallback, useEffect, useState } from 'react'
// The hook from the LEAF (no Supabase client in this chunk) — see `lib/adminAuthCore.ts`.
import { useAdminAuth } from '@/lib/adminAuthCore'
import { useT } from '@/lib/i18n'
import { formatDate } from '@/lib/formatDate'
import { isSuperRole } from '@/lib/superRole'
import {
  closeSurvey, deleteSurvey, getSurveys,
  type SurveyRow, type SurveyStatus, type SurveysPayload,
} from '@/lib/admin-api'
import TableFrame, { TH } from '@/components/admin/TableFrame'
import PanelTabs from '@/components/admin/PanelTabs'
import SurveyForm from './SurveyForm'
import { MAKER_ROLES, audienceLabel, giftHref } from './shared'

/**
 * Programme → **Surveys** (student maintenance S9, 2026-11-02; the SurveysAdmin board).
 *
 * ⚠ EVERY RULE IS THE SERVER'S (`apps/scholarship/surveys.py`): who may make one (super, organisation admin,
 * admin — `may_make`), who it is for (decided when read), the status (read from the dates), the lock at the
 * first answer, and the two emails (the hourly job, once per scholar, only while the organisation's
 * "Survey" email is on). This screen offers Close now / Delete only where the row's `can_close` /
 * `can_delete` say so, and draws the server's own counts ("N of M answered").
 * ⚠ ITS OWN CHUNK: the route carries only a loader (`lazySource`), so the first-load median is untouched.
 */
const K = 'admin.surveys'
const TABS: readonly SurveyStatus[] = ['open', 'scheduled', 'draft', 'closed']
const LINK = 'inline-flex min-h-11 items-center text-sm font-medium text-primary-600 hover:text-primary-800 hover:underline disabled:opacity-50'

type Editing = { row: SurveyRow | null } | null
type Banner = { ok: boolean; text: string } | null

export default function SurveysAdmin({ programme }: { programme?: string }) {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const r = isSuperRole(role) ? 'super' : (role?.role ?? '')
  const allowed = MAKER_ROLES.includes(r)
  const [data, setData] = useState<SurveysPayload | null>(null)
  const [failed, setFailed] = useState<'' | 'load' | 'programme_required'>('')
  const [tab, setTab] = useState<SurveyStatus>('open')
  const [editing, setEditing] = useState<Editing>(null)
  const [banner, setBanner] = useState<Banner>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    if (!token || !allowed) return
    try {
      setData(await getSurveys(programme, { token })); setFailed('')
    } catch (err) {
      setFailed((err as { code?: string })?.code === 'programme_required' ? 'programme_required' : 'load')
    }
  }, [token, allowed, programme])
  useEffect(() => { void load() }, [load])

  if (role && !allowed) return <p className="text-critical-600">{t('apiErrors.superAdminRequired')}</p>

  const act = async (row: SurveyRow, action: 'close' | 'delete') => {
    if (!token || !window.confirm(t(`${K}.confirm.${action}`, { title: row.title }))) return
    setBusyId(row.id); setBanner(null)
    try {
      if (action === 'close') await closeSurvey(row.id, { token })
      else await deleteSurvey(row.id, { token })
      setBanner({ ok: true, text: t(`${K}.done.${action === 'close' ? 'closed' : 'deleted'}`) })
    } catch {
      setBanner({ ok: false, text: t(`${K}.error.generic`) })
    } finally {
      setBusyId(null)
      void load()
    }
  }

  const rows = (data?.surveys ?? []).filter((s) => s.status === tab)

  return (
    <div className="space-y-5" data-testid="surveys-admin">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ground-900">{t(`${K}.title`)}</h1>
          <p className="text-sm text-ground-600">{t(`${K}.intro`)}</p>
        </div>
        {data && !editing && (
          <button type="button" onClick={() => { setEditing({ row: null }); setBanner(null) }}
            data-testid="survey-new"
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
        <SurveyForm row={editing.row} audiences={data.audiences} emailOn={data.email_switch_on}
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
            data-testid="surveys-empty">{t(`${K}.empty.${tab}`)}</div>
        ) : (
          <TableFrame minWidth={820} label={t(`${K}.title`)} phoneRows>
            <table className="w-full text-sm">
              <thead className="border-b bg-ground-50">
                <tr>
                  {['survey', 'for', 'dates', 'answered'].map((c) => (
                    <th key={c} className={TH}>{t(`${K}.col.${c}`)}</th>
                  ))}
                  <th className={TH}><span className="sr-only">{t(`${K}.col.actions`)}</span></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((s) => {
                  const by = s.author.name || s.author.email
                  return (
                    <tr key={s.id} data-testid={`survey-row-${s.id}`}>
                      <td className="px-4 py-3">
                        <span className="font-medium text-ground-900 break-words">{s.title}</span>
                        <span className="block text-xs text-ground-500">
                          {[t(s.questions.length === 1 ? `${K}.oneQuestion` : `${K}.questions`, { count: String(s.questions.length) }),
                            by ? (s.author.role ? t(`${K}.byRole`, { name: by, role: t(`admin.role.${s.author.role}`) })
                              : t(`${K}.by`, { name: by })) : '',
                            s.locked ? t(`${K}.locked`) : ''].filter(Boolean).join(' · ')}
                        </span>
                      </td>
                      <td className="px-4 py-3" data-label={t(`${K}.col.for`)}>{audienceLabel(t, s)}</td>
                      <td className="whitespace-nowrap px-4 py-3" data-label={t(`${K}.col.dates`)}>{formatDate(s.opens_at)} – {formatDate(s.closes_at)}</td>
                      <td className="whitespace-nowrap px-4 py-3 tabular-nums" data-label={t(`${K}.col.answered`)} data-testid={`survey-answered-${s.id}`}>
                        {s.status === 'draft' ? '—'
                          : t(`${K}.answeredOf`, { n: String(s.answered_count), count: String(s.audience_count) })}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className="flex gap-4">
                          {s.status !== 'draft' && (
                            <Link href={giftHref(`/admin/programme/surveys/${s.id}`, programme)} className={LINK}
                              data-testid={`survey-results-${s.id}`}>{t(`${K}.action.results`)}</Link>
                          )}
                          <button type="button" className={LINK} disabled={busyId === s.id || !!editing}
                            data-testid={`survey-edit-${s.id}`}
                            onClick={() => { setEditing({ row: s }); setBanner(null) }}>{t(`${K}.action.edit`)}</button>
                          {s.can_close && (
                            <button type="button" className={LINK} disabled={busyId === s.id}
                              data-testid={`survey-close-${s.id}`} onClick={() => act(s, 'close')}>{t(`${K}.action.close`)}</button>
                          )}
                          {s.can_delete && (
                            <button type="button" className={LINK} disabled={busyId === s.id}
                              data-testid={`survey-delete-${s.id}`} onClick={() => act(s, 'delete')}>{t(`${K}.action.delete`)}</button>
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

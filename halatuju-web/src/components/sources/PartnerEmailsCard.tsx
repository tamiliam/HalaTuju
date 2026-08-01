'use client'

import { useEffect, useState } from 'react'
import {
  getPartnerEmails, updatePartnerEmail,
  type PartnerEmailTemplate, type PartnerEmailsPayload,
} from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'
import { PARTNER_EMAIL_KINDS, nobodyReachable, reach, unreachable } from '@/lib/partnerComms'
import PartnerTemplateEditor from './PartnerTemplateEditor'
import { Toggle } from './shared'

// The Partner-emails card, above the Organisations table on the Sources page.
//
// ONE switch per email, not per organisation (owner ruling, 2026-07-26): on means every qualifying
// partner receives it. The "who qualifies" panel is the honest half — today that is 0 of 9, and the
// card says so rather than looking as though switching an email on would do something.

export default function PartnerEmailsCard({ token, t }: {
  token: string | null
  t: (key: string, params?: Record<string, string>) => string
}) {
  const [data, setData] = useState<PartnerEmailsPayload | null>(null)
  const [openKind, setOpenKind] = useState<string | null>(null)
  const [busyKind, setBusyKind] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showWho, setShowWho] = useState(false)

  useEffect(() => {
    if (!token) return
    getPartnerEmails({ token })
      .then(setData)
      .catch(() => setError(t('admin.sources.emails.loadError')))
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) {
    // A partner-emails hiccup must never take the Organisations table with it.
    return error ? (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 mb-6 text-sm text-red-600">{error}</div>
    ) : null
  }

  const replace = (updated: PartnerEmailTemplate) =>
    setData({ ...data, templates: data.templates.map((x) => (x.kind === updated.kind ? updated : x)) })

  const toggle = async (tpl: PartnerEmailTemplate) => {
    setBusyKind(tpl.kind); setError(null)
    // Optimistic, then reconciled from the response — the same pattern the Active toggle uses.
    replace({ ...tpl, enabled: !tpl.enabled })
    try {
      const updated = await updatePartnerEmail(tpl.kind, { enabled: !tpl.enabled }, { token: token! })
      replace(updated)
    } catch {
      replace(tpl)
      setError(t('admin.actionFailed'))
    }
    setBusyKind(null)
  }

  const ordered = PARTNER_EMAIL_KINDS
    .map((k) => data.templates.find((x) => x.kind === k))
    .filter((x): x is PartnerEmailTemplate => !!x)
  const { reachable, partners } = reach(data.organisations)
  const cannotReachAnyone = nobodyReachable(data.organisations)
  const needAddress = unreachable(data.organisations)

  return (
    <div className="bg-white rounded-xl shadow-sm border overflow-hidden mb-6">
      <div className="px-4 sm:px-5 py-4 border-b">
        <h2 className="font-semibold text-gray-900">{t('admin.sources.emails.title')}</h2>
        <p className="text-sm text-gray-500 mt-0.5">{t('admin.sources.emails.subtitle')}</p>
      </div>

      {!data.comms_enabled && (
        <p className="flex items-baseline gap-2.5 px-4 sm:px-5 py-2.5 bg-amber-50 border-b border-amber-200 text-sm text-amber-700">
          <span aria-hidden>◆</span>
          <span>
            <b className="font-semibold">{t('admin.sources.emails.flagOffTitle')}</b>{' '}
            {t('admin.sources.emails.flagOffBody')}
          </span>
        </p>
      )}

      {data.comms_enabled && cannotReachAnyone && (
        <p className="flex items-baseline gap-2.5 px-4 sm:px-5 py-2.5 bg-amber-50 border-b border-amber-200 text-sm text-amber-700">
          <span aria-hidden>◆</span>
          <span>
            <b className="font-semibold">{t('admin.sources.emails.nobodyTitle')}</b>{' '}
            {t('admin.sources.emails.nobodyBody')}
          </span>
        </p>
      )}

      {error && (
        <div className="mx-4 sm:mx-5 mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <ul className="divide-y">
        {ordered.map((tpl) => {
          const open = openKind === tpl.kind
          return (
            <li key={tpl.kind} className={open ? 'bg-blue-50/40' : undefined}>
              <div className="grid grid-cols-[44px_minmax(0,1fr)] sm:grid-cols-[44px_minmax(0,1fr)_auto] gap-x-3.5 items-start px-4 sm:px-5 py-3.5">
                <Toggle on={tpl.enabled} disabled={busyKind === tpl.kind}
                  onClick={() => toggle(tpl)}
                  label={t(`admin.sources.emails.kind.${tpl.kind}`)} />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="font-semibold text-gray-900">
                      {t(`admin.sources.emails.kind.${tpl.kind}`)}
                    </span>
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500 whitespace-nowrap">
                      {t(`admin.sources.emails.when.${tpl.kind}`)}
                    </span>
                    {/* Every other row on this card goes to the partner ORGANISATION. The one
                        that goes to the STUDENT has to say so here — the card is titled "Partner
                        emails", so a reader would otherwise reasonably assume the partner gets it. */}
                    {tpl.to_student && (
                      <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 whitespace-nowrap">
                        {t('admin.sources.emails.toStudent')}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-sm text-gray-500">
                    {t(`admin.sources.emails.desc.${tpl.kind}`)}
                  </p>
                  {/* The amber banner above says partner emails are switched off platform-wide.
                      That is true of every row except this one, and leaving it unsaid would mean
                      the banner reads as covering a message that is in fact still sending. */}
                  {tpl.to_student && !data.comms_enabled && (
                    <p className="mt-1 text-xs text-amber-700">
                      {t('admin.sources.emails.studentUnaffected')}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-gray-400">
                    {tpl.last_sent_at
                      ? t('admin.sources.emails.lastSent', {
                          date: formatDate(tpl.last_sent_at),
                          count: String(tpl.last_sent_orgs),
                        })
                      : t('admin.sources.emails.neverSent')}
                  </p>
                </div>
                <div className="col-start-2 sm:col-start-3 mt-2 sm:mt-0 self-center">
                  <button type="button" aria-expanded={open}
                    onClick={() => setOpenKind(open ? null : tpl.kind)}
                    className="rounded-lg border border-gray-200 px-3 py-1.5 text-[13px] font-medium text-blue-600 hover:bg-blue-50">
                    {t('admin.sources.emails.wording')}{' '}
                    <span aria-hidden className={`inline-block text-[10px] transition-transform ${open ? 'rotate-180' : ''}`}>▾</span>
                  </button>
                </div>
              </div>

              {open && (
                <PartnerTemplateEditor
                  template={tpl} token={token} t={t}
                  onCancel={() => setOpenKind(null)}
                  onSaved={(updated) => { replace(updated); setOpenKind(null) }}
                />
              )}
            </li>
          )
        })}
      </ul>

      <div className="border-t bg-gray-50">
        <button type="button" onClick={() => setShowWho((v) => !v)}
          aria-expanded={showWho}
          className="flex w-full items-baseline gap-2 px-4 sm:px-5 py-3 text-left text-sm text-gray-700 hover:text-gray-900">
          <span aria-hidden className={`text-[10px] transition-transform ${showWho ? 'rotate-90' : ''}`}>▸</span>
          <span>
            <b className="font-semibold">{t('admin.sources.emails.whoQualifies')}</b>{' '}
            {t('admin.sources.emails.reach', { reachable: String(reachable), partners: String(partners) })}
          </span>
        </button>
        {showWho && (
          <div className="px-4 sm:px-5 pb-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide text-gray-400">
                  <th className="border-b py-1.5 font-medium">{t('admin.sources.colOrganisation')}</th>
                  <th className="border-b py-1.5 font-medium text-right w-20">{t('admin.sources.colStudents')}</th>
                  <th className="border-b py-1.5 font-medium w-56">{t('admin.sources.colEmail')}</th>
                </tr>
              </thead>
              <tbody>
                {data.organisations.map((o) => (
                  <tr key={o.id}>
                    <td className="border-b py-1.5">
                      {o.name} <span className="font-mono text-[11px] text-gray-400">{o.code}</span>
                    </td>
                    <td className="border-b py-1.5 text-right tabular-nums text-gray-500">{o.students}</td>
                    <td className="border-b py-1.5">
                      {o.is_house_org ? (
                        <span className="text-xs text-gray-400">{t('admin.sources.emails.houseOrg')}</span>
                      ) : o.qualifies ? (
                        <span className="text-xs text-green-700">{t('admin.sources.emails.hasEmail')}</span>
                      ) : (
                        <span className="text-xs text-amber-700">{t('admin.sources.emails.noEmail')}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2.5 text-xs text-gray-400">{t('admin.sources.emails.recipientNote')}</p>
            {needAddress.length > 0 && (
              <p className="mt-1 text-xs text-gray-400">
                {t('admin.sources.emails.needAddress', { count: String(needAddress.length) })}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

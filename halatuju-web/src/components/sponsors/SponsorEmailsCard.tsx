'use client'

import { useEffect, useState } from 'react'
import {
  getSponsorEmails, updateSponsorEmail,
  type SponsorEmailTemplate, type SponsorEmailsPayload,
} from '@/lib/admin-api'
import { formatDate } from '@/lib/formatDate'
import { ALREADY_LIVE, errorKey, ordered, sendsToday, switchedOn } from '@/lib/sponsorComms'
import TemplateEditor from '@/components/emails/TemplateEditor'
import { Toggle } from '@/components/sources/shared'

// The Emails panel behind the second badge on /admin/sponsors (S3, 2026-07-28).
//
// What it is FOR: until this existed, a sponsor was vetted and approved without being told — the
// review endpoint flipped a field and returned. Nine emails, one switch each, wording editable
// here, and the whole family dark behind a platform flag as well.
//
// Two honesty rules the panel must not break:
//   * a switched-on template that cannot send says so (the platform gate banner), and
//   * three of the nine are ALREADY reaching sponsors through their pre-S3 hardcoded sender, so
//     an "off" switch on those rows would be a lie. They carry a "sending today" note instead.

export default function SponsorEmailsCard({ token, t }: {
  token: string | null
  t: (key: string, params?: Record<string, string>) => string
}) {
  const [data, setData] = useState<SponsorEmailsPayload | null>(null)
  const [openKind, setOpenKind] = useState<string | null>(null)
  const [busyKind, setBusyKind] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    getSponsorEmails({ token })
      .then(setData)
      .catch(() => setError(t('admin.sponsors.emails.loadError')))
  }, [token]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!data) {
    return error ? (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">{error}</div>
    ) : null
  }

  const replace = (updated: SponsorEmailTemplate) =>
    setData({ ...data, templates: data.templates.map((x) => (x.kind === updated.kind ? updated : x)) })

  const toggle = async (tpl: SponsorEmailTemplate) => {
    setBusyKind(tpl.kind); setError(null)
    replace({ ...tpl, enabled: !tpl.enabled })      // optimistic, reconciled from the response
    try {
      replace(await updateSponsorEmail(tpl.kind, { enabled: !tpl.enabled }, { token: token! }))
    } catch {
      replace(tpl)
      setError(t('admin.actionFailed'))
    }
    setBusyKind(null)
  }

  const rows = ordered(data.templates)
  const notSeeded = data.seeded < data.expected

  return (
    <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
      <div className="px-4 sm:px-5 py-4 border-b">
        <h2 className="font-semibold text-gray-900">{t('admin.sponsors.emails.title')}</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          {t('admin.sponsors.emails.subtitle', {
            on: String(switchedOn(data.templates)),
            total: String(data.seeded),
            sponsors: String(data.sponsor_count),
          })}
        </p>
      </div>

      {/* The platform gate, stated rather than implied. A switch that saves but cannot send is
          exactly the "dark by default lives only in a comment" failure (L380). */}
      {!data.comms_enabled && (
        <p className="flex items-baseline gap-2.5 px-4 sm:px-5 py-2.5 bg-amber-50 border-b border-amber-200 text-sm text-amber-700">
          <span aria-hidden>◆</span>
          <span>
            <b className="font-semibold">{t('admin.sponsors.emails.flagOffTitle')}</b>{' '}
            {t('admin.sponsors.emails.flagOffBody')}
          </span>
        </p>
      )}

      {notSeeded && (
        <p className="flex items-baseline gap-2.5 px-4 sm:px-5 py-2.5 bg-amber-50 border-b border-amber-200 text-sm text-amber-700">
          <span aria-hidden>◆</span>
          <span>{t('admin.sponsors.emails.notSeeded', {
            seeded: String(data.seeded), expected: String(data.expected),
          })}</span>
        </p>
      )}

      {error && (
        <div className="mx-4 sm:mx-5 mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-600">
          {error}
        </div>
      )}

      <ul className="divide-y">
        {rows.map((tpl) => {
          const open = openKind === tpl.kind
          const live = sendsToday(tpl.kind, tpl.enabled, data.comms_enabled)
          return (
            <li key={tpl.kind} className={open ? 'bg-blue-50/40' : undefined}>
              <div className="grid grid-cols-[44px_minmax(0,1fr)] sm:grid-cols-[44px_minmax(0,1fr)_auto] gap-x-3.5 items-start px-4 sm:px-5 py-3.5">
                <Toggle on={tpl.enabled} disabled={busyKind === tpl.kind}
                  onClick={() => toggle(tpl)}
                  label={t(`admin.sponsors.emails.kind.${tpl.kind}`)} />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="font-semibold text-gray-900">
                      {t(`admin.sponsors.emails.kind.${tpl.kind}`)}
                    </span>
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500 whitespace-nowrap">
                      {t(`admin.sponsors.emails.when.${tpl.kind}`)}
                    </span>
                    {/* An "off" switch on an email that is demonstrably going out would be a lie. */}
                    {ALREADY_LIVE.includes(tpl.kind) && !tpl.enabled && (
                      <span className="rounded-full bg-green-100 px-2 py-0.5 text-[11px] font-semibold text-green-700 whitespace-nowrap">
                        {t('admin.sponsors.emails.alreadyLive')}
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-sm text-gray-500">
                    {t(`admin.sponsors.emails.desc.${tpl.kind}`)}
                  </p>
                  <p className="mt-1 text-xs text-gray-400">
                    {tpl.last_sent_at
                      ? t('admin.sponsors.emails.lastSent', {
                          date: formatDate(tpl.last_sent_at),
                          count: String(tpl.last_sent_count),
                        })
                      : live
                        ? t('admin.sponsors.emails.neverSentYet')
                        : t('admin.sponsors.emails.neverSent')}
                  </p>
                </div>
                <div className="col-start-2 sm:col-start-3 mt-2 sm:mt-0 self-center">
                  <button type="button"
                    onClick={() => setOpenKind(open ? null : tpl.kind)}
                    className="text-sm font-medium text-blue-600 hover:text-blue-800">
                    {open ? t('admin.sources.cancel') : t('admin.sponsors.emails.edit')}
                  </button>
                </div>
              </div>
              {open && (
                <TemplateEditor<SponsorEmailTemplate>
                  template={tpl}
                  prefix="admin.sponsors.emails"
                  onSave={(kind, patch) => updateSponsorEmail(kind, patch, { token: token! })}
                  errorKey={errorKey}
                  onSaved={(updated) => { replace(updated); setOpenKind(null) }}
                  onCancel={() => setOpenKind(null)}
                  t={t}
                />
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

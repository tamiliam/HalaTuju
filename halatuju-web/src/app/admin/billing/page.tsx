'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { getBillingUsage, type BillingUsagePayload, type BillingOrgBlock } from '@/lib/admin-api'
import {
  orderedServices, formatBytes, formatCount, formatMonth,
  PAUSED_SERVICES, FREE_SERVICE_KEYS,
} from '@/lib/billingUsage'

// Billing & usage v1 (Sprint 13a) — the super/org_admin usage readout. Ships DARK behind
// BILLING_USAGE_ENABLED: a 404 from the API means the feature is off, so we show the "coming
// soon" shell (the Administration hub card is gated by the same probe). Units + token counts
// ONLY — there are NO prices in v1. super sees every organisation plus the platform (NULL-org)
// reconciliation section; org_admin sees only its own organisation (fenced server-side).

function serviceLabel(t: (k: string) => string, service: string): string {
  const known = ['gemini', 'vision_ocr', 'openai', 'email', 'whatsapp']
  return known.includes(service) ? t(`admin.billing.service.${service}`) : service
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border shadow-sm p-4">
      <p className="text-xs font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-400">{sub}</p>}
    </div>
  )
}

function OrgCard({ block, t }: { block: BillingOrgBlock; t: (k: string) => string }) {
  const rows = orderedServices(block)
  const find = (s: string) => rows.find((r) => r.service === s)
  const gemini = find('gemini')
  const vision = find('vision_ocr')
  const email = find('email')
  const whatsapp = find('whatsapp')

  return (
    <section className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-lg font-semibold text-gray-900">
          {block.is_platform ? t('admin.billing.platform') : block.organisation}
        </h2>
        {block.is_platform && (
          <span className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700">
            {t('admin.billing.platformBadge')}
          </span>
        )}
      </div>
      {block.is_platform && (
        <p className="text-sm text-gray-500 -mt-2 mb-3">{t('admin.billing.platformSub')}</p>
      )}

      {/* Stat tiles */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-5">
        <Tile label={t('admin.billing.service.gemini')} value={formatCount(gemini?.events ?? 0)}
          sub={t('admin.billing.tokensLine')
            .replace('{in}', formatCount(gemini?.input_tokens ?? 0))
            .replace('{out}', formatCount(gemini?.output_tokens ?? 0))} />
        <Tile label={t('admin.billing.service.vision_ocr')} value={formatCount(vision?.events ?? 0)} />
        <Tile label={t('admin.billing.service.email')} value={formatCount(email?.quantity ?? 0)} />
        <Tile label={t('admin.billing.service.whatsapp')} value={formatCount(whatsapp?.quantity ?? 0)} />
        <Tile label={t('admin.billing.service.storage')} value={formatBytes(block.storage_bytes)} />
      </div>

      {/* Breakdown table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-sm bg-white rounded-xl border shadow-sm">
          <thead>
            <tr className="border-b text-gray-600">
              <th className="text-left px-4 py-2 font-medium">{t('admin.billing.col.service')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('admin.billing.col.calls')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('admin.billing.col.tokensIn')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('admin.billing.col.tokensOut')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-4 text-center text-gray-400">{t('admin.billing.noUsage')}</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.service} className="border-b last:border-0">
                <td className="px-4 py-2 text-gray-900">{serviceLabel(t, r.service)}</td>
                <td className="px-4 py-2 text-right text-gray-700">{formatCount(r.events)}</td>
                <td className="px-4 py-2 text-right text-gray-500">{r.input_tokens ? formatCount(r.input_tokens) : '—'}</td>
                <td className="px-4 py-2 text-right text-gray-500">{r.output_tokens ? formatCount(r.output_tokens) : '—'}</td>
              </tr>
            ))}
            {/* Document storage — a live snapshot, not a metered call. */}
            <tr className="border-b last:border-0 bg-gray-50/50">
              <td className="px-4 py-2 text-gray-900">{t('admin.billing.service.storage')}</td>
              <td className="px-4 py-2 text-right text-gray-700" colSpan={3}>{formatBytes(block.storage_bytes)}</td>
            </tr>
            {/* Paused services — shown greyed so the reader knows they exist and cost nothing now. */}
            {PAUSED_SERVICES.map((s) => (
              <tr key={s} className="text-gray-300">
                <td className="px-4 py-2">
                  {t(`admin.billing.service.${s}`)}{' '}
                  <span className="text-[10px] uppercase">{t('admin.billing.paused')}</span>
                </td>
                <td className="px-4 py-2 text-right">0</td>
                <td className="px-4 py-2 text-right">—</td>
                <td className="px-4 py-2 text-right">—</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function AdminBillingPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const isSuper = !!(role?.is_super_admin || role?.role === 'super')
  const isOrgAdmin = role?.role === 'org_admin'

  const [data, setData] = useState<BillingUsagePayload | null>(null)
  const [month, setMonth] = useState('')
  const [loading, setLoading] = useState(true)
  const [dark, setDark] = useState(false)

  const load = useCallback((m?: string) => {
    if (!token) return
    setLoading(true)
    getBillingUsage({ token, month: m })
      .then((d) => { setData(d); setMonth(d.month); setDark(false) })
      .catch((e) => {
        if (/404/.test(String(e))) setDark(true)   // dark ship (flag off)
      })
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => { load() }, [load])

  if (role && !isSuper && !isOrgAdmin) {
    return <p className="text-red-600 p-6">{t('apiErrors.superAdminRequired')}</p>
  }
  if (loading && !data) return <p className="p-6 text-gray-500">{t('admin.billing.loading')}</p>
  if (dark) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-xl font-bold text-gray-900">{t('admin.billing.title')}</h1>
        <p className="mt-3 text-gray-500">{t('admin.billing.comingSoon')}</p>
      </div>
    )
  }
  if (!data) return null

  return (
    <div className="p-4 sm:p-6 max-w-5xl">
      <h1 className="text-xl font-bold text-gray-900">{t('admin.billing.title')}</h1>
      <p className="mt-1 text-sm text-gray-500">
        {isSuper ? t('admin.billing.subtitleSuper') : t('admin.billing.subtitleOrg')}
      </p>

      {/* Month picker */}
      <div className="mt-4 flex items-center gap-2">
        <label className="text-sm text-gray-600">{t('admin.billing.month')}</label>
        <select
          className="border rounded-lg px-3 py-1.5 text-sm bg-white"
          value={month}
          onChange={(e) => { setMonth(e.target.value); load(e.target.value) }}
        >
          {(data.months.length ? data.months : [data.month]).map((m) => (
            <option key={m} value={m}>{formatMonth(m)}</option>
          ))}
        </select>
      </div>

      <div className="mt-6">
        {data.organisations.length === 0 && (
          <p className="text-gray-400">{t('admin.billing.noUsage')}</p>
        )}
        {data.organisations.map((b) => (
          <OrgCard key={b.organisation_id ?? 'platform'} block={b} t={t} />
        ))}
      </div>

      {/* Non-metered free services footnote. */}
      <p className="mt-2 text-xs text-gray-400">
        {t('admin.billing.freeNote')}{' '}
        {FREE_SERVICE_KEYS.map((k) => t(`admin.billing.free.${k}`)).join(' · ')}
      </p>
    </div>
  )
}

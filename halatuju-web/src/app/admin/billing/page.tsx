'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import TableFrame from '@/components/admin/TableFrame'
import { canAccess, effectiveRole } from '@/lib/navigation'
import { getBillingUsage, type BillingUsagePayload, type BillingOrgBlock } from '@/lib/admin-api'
import {
  orderedServices, formatBytes, formatCount, formatMonth,
  PAUSED_SERVICES, FREE_SERVICE_KEYS,
  orderedModels, jobsByModel, fixedJobs, secondProviderJobs,
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
    <div className="bg-ground-0 rounded-xl border shadow-sm p-4">
      <p className="text-xs font-medium text-ground-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ground-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-ground-400">{sub}</p>}
    </div>
  )
}

/** ⚠ `t` takes VARIABLES now. The per-model lines say "412 calls · last used 10/09/2026", and a
 *  count and a date belong in the sentence rather than glued on around it — the same reason the
 *  interview window copy interpolates its own numbers. */
function OrgCard({ block, t }: {
  block: BillingOrgBlock
  t: (k: string, vars?: Record<string, string>) => string
}) {
  const rows = orderedServices(block)
  const find = (s: string) => rows.find((r) => r.service === s)
  const gemini = find('gemini')
  const vision = find('vision_ocr')
  const email = find('email')
  const whatsapp = find('whatsapp')

  return (
    <section className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-lg font-semibold text-ground-900">
          {block.is_platform ? t('admin.billing.platform') : block.organisation}
        </h2>
        {block.is_platform && (
          <span className="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-category-1-surface text-category-1-ink">
            {t('admin.billing.platformBadge')}
          </span>
        )}
      </div>
      {block.is_platform && (
        <p className="text-sm text-ground-500 -mt-2 mb-3">{t('admin.billing.platformSub')}</p>
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
        {/* ⚠ On the PLATFORM block this is the WHOLE bucket, organisations included — every
            other figure in that block is exclusive (work billed to nobody), so without this
            note the page reads as if the two storage lines add up. They are the same bytes. */}
        <Tile label={t('admin.billing.service.storage')} value={formatBytes(block.storage_bytes)}
          sub={block.is_platform ? t('admin.billing.storageAllNote') : undefined} />
      </div>

      {/* Breakdown table */}
      <TableFrame className="mt-4" minWidth={720} label={t('admin.billing.title')}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-ground-600">
              <th className="text-left px-4 py-2 font-medium">{t('admin.billing.col.service')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('admin.billing.col.calls')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('admin.billing.col.tokensIn')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('admin.billing.col.tokensOut')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={4} className="px-4 py-4 text-center text-ground-400">{t('admin.billing.noUsage')}</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.service} className="border-b last:border-0">
                <td className="px-4 py-2 text-ground-900">
                  {serviceLabel(t, r.service)}
                  {/* ⚠ WHICH AI VERSION DID THE WORK. The model was written on every AI call from
                      the start and nothing read it back (owner, 2026-09-11). Rendered UNDER the
                      service rather than as a column, because only two of the five services have
                      one — a column would be mostly dashes, which reads as data we failed to
                      fetch rather than as a service that has no model. */}
                  {orderedModels(r).map((m) => (
                    <span key={m.model} className="mt-0.5 block text-[11px] text-ground-500">
                      {m.model}
                      <span className="text-ground-400">
                        {' · '}{t('admin.billing.modelCalls', { n: formatCount(m.events) })}
                        {m.last_seen ? ` · ${t('admin.billing.modelLastUsed', { date: m.last_seen })}` : ''}
                      </span>
                    </span>
                  ))}
                </td>
                <td className="px-4 py-2 text-right text-ground-700">{formatCount(r.events)}</td>
                <td className="px-4 py-2 text-right text-ground-500">{r.input_tokens ? formatCount(r.input_tokens) : '—'}</td>
                <td className="px-4 py-2 text-right text-ground-500">{r.output_tokens ? formatCount(r.output_tokens) : '—'}</td>
              </tr>
            ))}
            {/* Document storage — a live snapshot, not a metered call. */}
            <tr className="border-b last:border-0 bg-ground-50/50">
              <td className="px-4 py-2 text-ground-900">
                {t('admin.billing.service.storage')}
                {block.is_platform && (
                  <span className="text-ground-500"> — {t('admin.billing.storageAllNote')}</span>
                )}
              </td>
              <td className="px-4 py-2 text-right text-ground-700" colSpan={3}>{formatBytes(block.storage_bytes)}</td>
            </tr>
            {/* Paused services — shown greyed so the reader knows they exist and cost nothing now. */}
            {PAUSED_SERVICES.map((s) => (
              <tr key={s} className="text-ground-300">
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
      </TableFrame>
    </section>
  )
}

export default function AdminBillingPage() {
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const isSuper = effectiveRole(role) === 'super'
  const mayView = canAccess('/admin/billing', effectiveRole(role))

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

  if (role && !mayView) {
    return <p className="text-critical-600 p-6">{t('apiErrors.superAdminRequired')}</p>
  }
  if (loading && !data) return <p className="p-6 text-ground-500">{t('admin.billing.loading')}</p>
  if (dark) {
    return (
      <div>
        <h1 className="text-xl font-bold text-ground-900">{t('admin.billing.title')}</h1>
        <p className="mt-3 text-ground-500">{t('admin.billing.comingSoon')}</p>
      </div>
    )
  }
  if (!data) return null

  return (
    <div>
      <h1 className="text-xl font-bold text-ground-900">{t('admin.billing.title')}</h1>
      <p className="mt-1 text-sm text-ground-500">
        {isSuper ? t('admin.billing.subtitleSuper') : t('admin.billing.subtitleOrg')}
      </p>

      {/* Month picker */}
      <div className="mt-4 flex items-center gap-2">
        <label className="text-sm text-ground-600">{t('admin.billing.month')}</label>
        <select
          className="border rounded-lg px-3 py-1.5 text-sm bg-ground-0"
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
          <p className="text-ground-400">{t('admin.billing.noUsage')}</p>
        )}
        {data.organisations.map((b) => (
          <OrgCard key={b.organisation_id ?? 'platform'} block={b} t={t} />
        ))}
      </div>

      {/* ── The upgrade checklist. SUPER-ONLY, and absent from an org_admin payload entirely,
             so this renders for nobody else even if the component were reused. Which model a job
             is SET TO is a platform fact a tenant cannot change (owner, 2026-09-11); their own
             usage split by model, above, is theirs and stays. ── */}
      {data.ai_jobs && data.ai_jobs.length > 0 && (
        <div className="mt-8" data-testid="ai-jobs">
          <h2 className="text-sm font-semibold text-ground-900">{t('admin.billing.ai.title')}</h2>
          <p className="mt-1 text-xs text-ground-500">{t('admin.billing.ai.sub')}</p>

          {/* Grouped BY MODEL, not listed job by job: the question an upgrade asks is "if this
              version is replaced, what do I have to touch?", and that is one group. */}
          <div className="mt-3 space-y-3">
            {jobsByModel(data.ai_jobs).map((g) => (
              <div key={g.model} className="rounded-xl border bg-ground-0 p-4 shadow-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-mono text-sm font-semibold text-ground-900">{g.model}</span>
                  <span className="text-xs text-ground-400">
                    {t('admin.billing.ai.jobCount', { n: String(g.jobs.length) })}
                  </span>
                </div>
                <ul className="mt-2 space-y-1">
                  {g.jobs.map((j) => (
                    <li key={j.key} className="flex flex-wrap items-baseline gap-x-2 text-xs">
                      <span className="text-ground-700">{j.label}</span>
                      {/* WHERE the model comes from — a setting you can move, a cascade, or a
                          literal that needs a deploy. Without this the reader cannot tell which
                          rows they can actually change. */}
                      <span className="font-mono text-[11px] text-ground-400">{j.source_name}</span>
                      {j.fixed && (
                        <span className="rounded bg-caution-100 px-1.5 py-0.5 text-[10px] font-semibold text-caution-700">
                          {t('admin.billing.ai.needsDeploy')}
                        </span>
                      )}
                      {j.fallback_provider && (
                        <span className="rounded bg-info-100 px-1.5 py-0.5 text-[10px] font-semibold text-info-700">
                          {t('admin.billing.ai.secondProvider', { model: j.fallback_model })}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* ⚠ THE FALLBACKS ARE NAMED SEPARATELY, and none of them has ever run on production.
              A cascade drops to the next model only when the one above fails, so these are the
              versions that would carry the platform on a bad day — an upgrade that skips them
              leaves an old model one outage away from live. */}
          <p className="mt-3 text-xs text-ground-400">
            {t('admin.billing.ai.reachable')}{' '}
            <span className="font-mono">{(data.ai_models_in_use || []).join(' · ')}</span>
          </p>
          {(fixedJobs(data.ai_jobs).length > 0 || secondProviderJobs(data.ai_jobs).length > 0) && (
            <p className="mt-1 text-xs text-ground-400">{t('admin.billing.ai.walkPastNote')}</p>
          )}
        </div>
      )}

      {/* Non-metered free services footnote. */}
      <p className="mt-2 text-xs text-ground-400">
        {t('admin.billing.freeNote')}{' '}
        {FREE_SERVICE_KEYS.map((k) => t(`admin.billing.free.${k}`)).join(' · ')}
      </p>
    </div>
  )
}

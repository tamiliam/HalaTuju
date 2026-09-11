'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import TableFrame from '@/components/admin/TableFrame'
import { canAccess, effectiveRole } from '@/lib/navigation'
import {
  getBillingUsage, getBillingCosts, setBillingAdjustment, recordBuildHours,
  type BillingUsagePayload, type BillingOrgBlock, type BillingCostsPayload,
  type BillingCharge, type UnbilledRequest,
} from '@/lib/admin-api'
import {
  orderedServices, formatBytes, formatCount, formatMonth,
  PAUSED_SERVICES, FREE_SERVICE_KEYS,
  orderedModels, jobsByModel, fixedJobs, secondProviderJobs,
} from '@/lib/billingUsage'
import {
  formatMyr, formatPct, formatHours, orderedCostSources, costCaveats, unbilledByOrg,
  isCostWarning,
} from '@/lib/billingCosts'

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

/**
 * What the platform PAID this month, and how honest that figure is.
 *
 * ⚠ The health warnings are not decoration and must not be collapsed into the total. The cost
 * module's own words: **a total that mixes measured and hand-typed figures without saying so is
 * not an audit.** Three things can make this number less true than it looks — a held invoice we
 * cannot yet state in ringgit (the total is then a FLOOR), a source somebody read off a PDF, and
 * a provider whose billing window is not the calendar month. Each says so in its own words.
 */
function CostSection({ costs, t }: {
  costs: BillingCostsPayload['costs']
  t: (k: string, vars?: Record<string, string>) => string
}) {
  const caveats = costCaveats(costs)
  const sources = orderedCostSources(costs)

  return (
    <div className="mt-8" data-testid="cost-section">
      <h2 className="text-sm font-semibold text-ground-900">{t('admin.billing.cost.title')}</h2>
      <p className="mt-1 text-xs text-ground-500">{t('admin.billing.cost.sub')}</p>

      <div className="mt-3 grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Tile label={t('admin.billing.cost.total')} value={formatMyr(costs.total_myr)}
          sub={costs.is_complete ? undefined : t('admin.billing.cost.floor')} />
        <Tile label={t('admin.billing.cost.attributable')} value={formatMyr(costs.attributable_myr)}
          sub={t('admin.billing.cost.attributableSub')} />
        <Tile label={t('admin.billing.cost.platform')} value={formatMyr(costs.platform_myr)}
          sub={t('admin.billing.cost.platformSub')} />
        {/* ⚠ ITS OWN TILE, not folded into "driven by us". This is what it costs to DELIVER
            HOURS — Claude — and it is recovered by the hourly rate, not by the platform fee.
            Folding it in would mark it up as infrastructure and take the same ringgit twice. */}
        {Number(costs.development_myr) > 0 && (
          <Tile label={t('admin.billing.cost.development')}
            value={formatMyr(costs.development_myr)}
            sub={t('admin.billing.cost.developmentSub')} />
        )}
        <Tile label={t('admin.billing.cost.tax')} value={formatMyr(costs.tax_myr)} />
      </div>

      {caveats.length > 0 && (
        <ul className="mt-3 space-y-1" data-testid="cost-caveats">
          {/* ⚠ Only a real problem gets warning styling. `extracted` says where a figure came
              from — a parse of the provider's own PDF that refuses unless it reconciles to the
              printed total — and dressing that as a caution would train the reader to ignore
              `entered`, which is the one that IS a caution. */}
          {caveats.map((c, i) => (
            <li key={`${c.kind}-${i}`}
              className={`rounded-lg px-3 py-2 text-xs ${isCostWarning(c.kind)
                ? 'bg-caution-100 text-caution-700' : 'bg-ground-50 text-ground-600'}`}>
              {t(`admin.billing.cost.caveat.${c.kind}`)}{c.detail ? ` — ${c.detail}` : ''}
            </li>
          ))}
        </ul>
      )}

      <TableFrame className="mt-4" minWidth={520} label={t('admin.billing.cost.title')}>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-ground-600">
              <th className="text-left px-4 py-2 font-medium">{t('admin.billing.cost.col.source')}</th>
              <th className="text-right px-4 py-2 font-medium">{t('admin.billing.cost.col.amount')}</th>
            </tr>
          </thead>
          <tbody>
            {sources.length === 0 && (
              <tr><td colSpan={2} className="px-4 py-4 text-center text-ground-400">
                {t('admin.billing.cost.none')}
              </td></tr>
            )}
            {sources.map((s) => (
              <tr key={s.source} className="border-b last:border-0">
                <td className="px-4 py-2 text-ground-900">
                  {t(`admin.billing.cost.source.${s.source}`)}
                  {/* WHERE the figure came from. Three states, and they are genuinely three:
                      measured (a billing API), extracted (the provider's own PDF, parsed and
                      reconciled to its printed total), and typed by hand — which the owner's
                      standing instruction says should never appear again. */}
                  {costs.entered_sources.includes(s.source) && (
                    <span className="ml-2 rounded bg-caution-100 px-1.5 py-0.5 text-[10px] uppercase text-caution-700">
                      {t('admin.billing.cost.byHand')}
                    </span>
                  )}
                  {costs.extracted_sources?.includes(s.source) && (
                    <span className="ml-2 rounded bg-ground-100 px-1.5 py-0.5 text-[10px] uppercase text-ground-500">
                      {t('admin.billing.cost.fromInvoice')}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-ground-700">{formatMyr(s.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableFrame>
    </div>
  )
}

/** One tenant's bill: every line shown, THEN the discount. The owner's July rule — shown in
 *  full, charged nothing — only works if the subtotal survives to the screen. */
function ChargeCard({ charge, month, t, onDiscount, busy }: {
  charge: BillingCharge
  month: string
  t: (k: string, vars?: Record<string, string>) => string
  onDiscount: (orgId: number, pct: string, reason: string) => void
  busy: boolean
}) {
  const [open, setOpen] = useState(false)
  const [pct, setPct] = useState('100')
  const [reason, setReason] = useState('')

  return (
    <div className="rounded-xl border bg-ground-0 p-4 shadow-sm"
      data-testid={`charge-${charge.organisation_id}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ground-900">{charge.organisation}</h3>
        <span className="text-2xl font-semibold text-ground-900">{formatMyr(charge.charged_myr)}</span>
      </div>

      <dl className="mt-3 space-y-1 text-sm">
        {charge.lines.map((ln) => (
          <div key={ln.category} className="flex justify-between gap-4">
            <dt className="text-ground-600">
              {t(`admin.billing.charge.line.${ln.category}`)}
              {ln.hours ? (
                <>
                  <span className="text-ground-400">
                    {' · '}{t('admin.billing.charge.workedAt', {
                      hours: formatHours(ln.hours),
                      rate: formatMyr(ln.rate_myr),
                      margin: formatPct(ln.margin_pct),
                    })}
                  </span>
                  {/* ⚠ WHAT THE TOOLS COST US, beside what the hours are charged at. Shown,
                      never added — the hourly rate already recovers it, and adding it would
                      take the same ringgit twice. It exists so "is the rate enough?" is a
                      figure on a screen rather than a feeling. */}
                  {ln.tool_cost_myr && Number(ln.tool_cost_myr) > 0 && (
                    <span className="block text-[11px] text-ground-400">
                      {t('admin.billing.charge.toolCost', { cost: formatMyr(ln.tool_cost_myr) })}
                    </span>
                  )}
                </>
              ) : (
                /* ⚠ WHAT WE PAID, BESIDE WHAT WE CHARGE. A single marked-up figure hides the
                   markup, and the markup is the thing the reader is here to check. */
                <span className="text-ground-400">
                  {' · '}{t('admin.billing.charge.costPlus', {
                    cost: formatMyr(ln.cost_myr),
                    margin: formatPct(ln.margin_pct),
                  })}
                </span>
              )}
              {/* The tenant's share of a platform-wide cost, and the rule behind it. With one
                  tenant this reads 100% — which is exactly when it is worth writing down. */}
              {ln.share_pct && (
                <span className="block text-[11px] text-ground-400">
                  {t('admin.billing.charge.share', { pct: formatPct(ln.share_pct) })}
                  {ln.share_rule ? ` — ${ln.share_rule}` : ''}
                </span>
              )}
            </dt>
            <dd className="tabular-nums text-ground-900">{formatMyr(ln.amount_myr)}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-4 border-t pt-1">
          <dt className="text-ground-600">{t('admin.billing.charge.subtotal')}</dt>
          <dd className="tabular-nums text-ground-900">{formatMyr(charge.subtotal_myr)}</dd>
        </div>
        {/* ⚠ The discount is its own LINE, never a quietly smaller total. A waiver you cannot see
            is indistinguishable from a bug that produced zero. */}
        {Number(charge.discount_pct) > 0 && (
          <div className="flex justify-between gap-4" data-testid="discount-line">
            <dt className="text-ground-600">
              {t('admin.billing.charge.discount', { pct: formatPct(charge.discount_pct) })}
              {charge.discount_reason && (
                <span className="block text-xs text-ground-400">{charge.discount_reason}</span>
              )}
            </dt>
            <dd className="tabular-nums text-ground-900">−{formatMyr(charge.discount_myr)}</dd>
          </div>
        )}
        <div className="flex justify-between gap-4 border-t pt-1 font-semibold">
          <dt className="text-ground-900">{t('admin.billing.charge.charged')}</dt>
          <dd className="tabular-nums text-ground-900">{formatMyr(charge.charged_myr)}</dd>
        </div>
      </dl>

      {/* ⚠ Every category we could NOT price, with its reason. Never rendered as RM0.00 —
          a line the reader can see is missing gets fixed; a zero gets believed. */}
      {charge.blocked.length > 0 && (
        <ul className="mt-3 space-y-1" data-testid={`blocked-${charge.organisation_id}`}>
          {charge.blocked.map((b) => (
            <li key={b.category} className="rounded-lg bg-ground-50 px-3 py-2 text-xs text-ground-600">
              <span className="font-medium text-ground-700">
                {t(`admin.billing.charge.line.${b.category}`)}
              </span>
              {' — '}{b.reason}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3">
        <button type="button" className="text-xs text-ground-500 underline"
          onClick={() => setOpen((v) => !v)}>
          {t('admin.billing.charge.setDiscount', { month: formatMonth(month) })}
        </button>
        {open && (
          <div className="mt-2 grid gap-2 sm:grid-cols-[6rem_1fr_auto] sm:items-end">
            <label className="block">
              <span className="block text-[11px] text-ground-500">{t('admin.billing.charge.pct')}</span>
              <input type="number" min="0" max="100" step="0.01" inputMode="decimal"
                className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
                value={pct} onChange={(e) => setPct(e.target.value)}
                aria-label={t('admin.billing.charge.pct')} />
            </label>
            <label className="block">
              <span className="block text-[11px] text-ground-500">{t('admin.billing.charge.reason')}</span>
              <input type="text"
                className="mt-0.5 w-full rounded-lg border bg-ground-0 px-3 py-1.5 text-sm"
                value={reason} onChange={(e) => setReason(e.target.value)}
                aria-label={t('admin.billing.charge.reason')} />
            </label>
            <button type="button"
              /* The reason is required here as well as on the server, so the refusal is a
                 disabled button rather than a round-trip and an error message. */
              disabled={busy || reason.trim() === ''}
              /* Grey when there is nothing to apply — the same rule as the rates screen's Save.
                 A disabled control looks like a different kind of thing, not a dimmer one. */
              className="rounded-lg px-3 py-1.5 text-sm font-medium bg-primary-600 text-white
                disabled:bg-ground-200 disabled:text-ground-400 disabled:cursor-not-allowed"
              onClick={() => onDiscount(charge.organisation_id, pct.trim(), reason.trim())}>
              {t('admin.billing.charge.apply')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

/** Finished request work that has never reached an invoice.
 *
 * ⚠ It is REPORTED, not auto-billed. A request carries no completion date — only `updated_at`,
 * which any later edit moves — so which MONTH the work belongs to is a human call, and getting it
 * wrong would bill it under the wrong month's terms. Recording it writes an `OrgBuildHours` row
 * whose `basis` names the request, which is what makes the choice reviewable afterwards. */
function UnbilledSection({ payload, t, onRecord, busy }: {
  payload: BillingCostsPayload
  t: (k: string, vars?: Record<string, string>) => string
  onRecord: (row: UnbilledRequest) => void
  busy: boolean
}) {
  const groups = unbilledByOrg(payload)
  if (groups.length === 0) return null

  return (
    <div className="mt-8" data-testid="unbilled-requests">
      <h2 className="text-sm font-semibold text-ground-900">{t('admin.billing.unbilled.title')}</h2>
      <p className="mt-1 text-xs text-ground-500">{t('admin.billing.unbilled.sub')}</p>
      <div className="mt-3 space-y-3">
        {groups.map((g) => (
          <div key={g.organisation_id} className="rounded-xl border bg-ground-0 p-4 shadow-sm">
            <h3 className="text-sm font-semibold text-ground-900">{g.organisation}</h3>
            <ul className="mt-2 space-y-1">
              {g.rows.map((r) => (
                <li key={r.request_id} className="flex flex-wrap items-baseline justify-between gap-2 text-xs">
                  <span className="text-ground-700">
                    #{r.request_id} {r.title}
                    {/* ⚠ The month these hours go to, and how firm it is. Recording files them
                        HERE, not under the month being viewed — the owner's correction. */}
                    <span className="block text-[11px] text-ground-400">
                      {t('admin.billing.unbilled.worked', {
                        month: formatMonth(r.worked_month),
                        date: r.worked_on,
                        basis: r.worked_basis,
                      })}
                    </span>
                  </span>
                  <span className="flex items-baseline gap-3">
                    <span className="tabular-nums text-ground-900">{formatHours(r.hours)}</span>
                    <button type="button" disabled={busy}
                      className="text-ground-500 underline disabled:opacity-40"
                      onClick={() => onRecord(r)}>
                      {t('admin.billing.unbilled.record')}
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
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
  // The COST side. SUPER-ONLY and fetched separately, because it is a different endpoint with a
  // different fence: what the platform pays and what margin sits on it is a commercial
  // disclosure, and an org_admin gets a 403 from it. A failure here must NEVER darken the usage
  // screen an org_admin can legitimately see, so it lands in its own state.
  const [costs, setCosts] = useState<BillingCostsPayload | null>(null)
  const [busy, setBusy] = useState(false)
  const [costError, setCostError] = useState('')

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

  const loadCosts = useCallback((m?: string) => {
    if (!token || !isSuper) return
    getBillingCosts({ token, month: m })
      .then((d) => { setCosts(d); setCostError('') })
      .catch((e) => { setCosts(null); setCostError(String(e)) })
  }, [token, isSuper])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadCosts() }, [loadCosts])

  const pickMonth = useCallback((m: string) => {
    setMonth(m)
    load(m)
    loadCosts(m)
  }, [load, loadCosts])

  const applyDiscount = useCallback((orgId: number, pct: string, reason: string) => {
    if (!token) return
    setBusy(true)
    setBillingAdjustment(
      { organisation_id: orgId, period_month: month, discount_pct: pct, reason }, { token })
      // Re-read: a discount changes the subtotal line, the discount line and the charged total
      // at once. Patching one of the three would leave the card disagreeing with itself.
      .then(() => loadCosts(month))
      .catch((e) => setCostError(String(e)))
      .finally(() => setBusy(false))
  }, [token, month, loadCosts])

  const recordRequestHours = useCallback((row: UnbilledRequest) => {
    if (!token) return
    setBusy(true)
    recordBuildHours(row.organisation_id, {
      // ⚠ THE MONTH WE WORKED, not the month being viewed and not the month it was raised
      // (owner, 2026-09-11). Using the viewed month would file every request under whatever
      // page the reader happened to be on.
      period_month: row.worked_month,
      module: row.module,
      hours: row.hours ?? '0',
      // `basis` is required by the model and is the point of it: an hours figure with no stated
      // reconstruction is not auditable. Written by the code so it always names its source AND
      // how the month was decided — 'scheduled' is firm, 'last touched' is a fallback.
      basis: `Quoted on request #${row.request_id} (${row.title}). Worked ${row.worked_on} `
        + `(${row.worked_basis}), so recorded against ${row.worked_month}.`,
    }, { token })
      .then(() => loadCosts(month))
      .catch((e) => setCostError(String(e)))
      .finally(() => setBusy(false))
  }, [token, month, loadCosts])

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
          onChange={(e) => pickMonth(e.target.value)}
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

      {/* ── What it COST, and what each tenant is charged. SUPER-ONLY (the endpoint 403s an
             org_admin). The ledger, the BigQuery sync and this reconciliation were all built in
             July 2026 and starved: nothing fed the ledger after June and no screen ever read it,
             so real invoices reached nobody. This is that gap closed. ── */}
      {costError && (
        <p className="mt-6 text-sm text-critical-600" role="alert" data-testid="cost-error">
          {costError}
        </p>
      )}
      {costs && <CostSection costs={costs.costs} t={t} />}
      {costs && costs.charges.length > 0 && (
        <div className="mt-8" data-testid="charges">
          <h2 className="text-sm font-semibold text-ground-900">{t('admin.billing.charge.title')}</h2>
          <p className="mt-1 text-xs text-ground-500">{t('admin.billing.charge.sub')}</p>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {costs.charges.map((c) => (
              <ChargeCard key={c.organisation_id} charge={c} month={month} t={t}
                onDiscount={applyDiscount} busy={busy} />
            ))}
          </div>
        </div>
      )}
      {costs && (
        <UnbilledSection payload={costs} t={t}
          onRecord={recordRequestHours} busy={busy} />
      )}

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

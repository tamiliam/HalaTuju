'use client'

/** Finished request work that has never reached an invoice.
 *
 * Moved VERBATIM out of `src/app/admin/billing/page.tsx` on 2026-10-29 (moves only, plus the
 * planned-against-actual change this sprint): that page sits in the oversize ledger at 714 lines
 * against a 734-line allowance, and the standard asks for a SPLIT rather than for prose to be
 * trimmed until the number passes.
 *
 * ⚠ It is REPORTED, not auto-billed. A request carries no completion date — only `updated_at`,
 * which any later edit moves — so which MONTH the work belongs to is a human call, and getting it
 * wrong would bill it under the wrong month's terms. Recording it writes an `OrgBuildHours` row
 * whose `basis` names the request, which is what makes the choice reviewable afterwards. */

import type { BillingCostsPayload, UnbilledRequest } from '@/lib/admin-api/billing'
import { formatMonth } from '@/lib/billingUsage'
import { canRecordUnbilled, formatHours, unbilledByOrg } from '@/lib/billingCosts'

export function UnbilledSection({ payload, t, onRecord, busy }: {
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
                  {/* ⚠ THE PUBLISHED ACTUAL, AND THE PLAN BESIDE IT. The owner read this panel on
                      2026-10-29 and found it proposing 7h for #30 and 8h for #31 — the plans —
                      while the closing reports had told BrightPath 4 and 5. Pressing Record filed
                      the wrong number and the invoice billed it. `hours` is now the published
                      figure; where none exists there is NO number and NO button, because the
                      remedy is to record the actual, not to click past a blank. */}
                  <span className="flex items-baseline gap-3">
                    {!canRecordUnbilled(r) ? (
                      <span className="text-caution-700">
                        {t('admin.billing.unbilled.noActual')}
                      </span>
                    ) : (
                      <>
                        <span className="tabular-nums text-ground-900">
                          {formatHours(r.hours)}
                          {r.quoted_hours && r.quoted_hours !== r.hours && (
                            <span className="ml-2 text-[11px] font-normal text-ground-400">
                              {t('admin.billing.unbilled.quoted',
                                { hours: formatHours(r.quoted_hours) })}
                            </span>
                          )}
                        </span>
                        <button type="button" disabled={busy}
                          className="text-ground-500 underline disabled:opacity-40"
                          onClick={() => onRecord(r)}>
                          {t('admin.billing.unbilled.record')}
                        </button>
                      </>
                    )}
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

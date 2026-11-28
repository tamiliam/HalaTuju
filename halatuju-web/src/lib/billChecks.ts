/**
 * THE OPENED BILL'S "CHECKS" PANEL DATA (chip Sprint 2) — what the bill says beside what the application says.
 *
 * Built ONLY from the application detail the cockpit has already loaded (no new request). Names and
 * addresses live here and in the panel, never in the drawer row (owner rule, 2026-11-26).
 */
import type { AdminApplicantDocument, AdminScholarshipDetail } from '@/lib/admin-api'
import { utilityBillValues } from '@/lib/cockpitDocFacts'

export interface BillChecks {
  holder: string
  billAddress: string
  /** The application's names: the student, the family list and every read parent IC. */
  appNames: string[]
  appAddress: string
  /** 'MMM YYYY' read off the bill; '' when undated. */
  billMonth: string
  /** Plain values: amount, period, arrears (already formatted), Reasonable word key. */
  amount: string
  period: string
  arrears: string
  reasonable: string
  nameNote: string
  reasonableDetail: string
}

export function isBill(d: AdminApplicantDocument): boolean {
  return d.doc_type === 'water_bill' || d.doc_type === 'electricity_bill'
}

export function billChecksFor(d: AdminApplicantDocument, app: AdminScholarshipDetail): BillChecks | undefined {
  const c = d.utility_check
  if (!isBill(d) || !c) return undefined
  const names = [app.name, ...(app.guardians ?? []).map((g) => g.name ?? '')]
  for (const doc of app.documents ?? []) {
    if (doc.doc_type !== 'parent_ic') continue
    const n = (doc.vision_fields?.fields as Record<string, unknown> | undefined)?.name
    if (typeof n === 'string') names.push(n)
  }
  const seen = new Set<string>()
  const appNames = names.map((n) => (n || '').trim()).filter((n) => {
    const k = n.toLowerCase()
    if (!n || seen.has(k)) return false
    seen.add(k)
    return true
  })
  const vals = utilityBillValues(d)
  const pick = (key: string) => vals.find((v) => v.labelKey === key)
  return {
    holder: (c.name || '').trim(),
    billAddress: (c.address || '').trim(),
    appNames,
    appAddress: [app.address, app.postal_code, app.city].map((s) => (s || '').trim()).filter(Boolean).join(', '),
    billMonth: (c.bill_month || '').trim(),
    amount: pick('amount')?.value ?? '',
    period: pick('period')?.value ?? '',
    arrears: pick('arrears')?.value ?? '',
    reasonable: c.reasonable_status || '',
    nameNote: c.name_note || '',
    reasonableDetail: c.reasonable_detail || '',
  }
}

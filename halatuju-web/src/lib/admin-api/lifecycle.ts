/**
 * Post-award: the bursary countersignature and witness, the award amount, the disbursement
 * tranches, the maintenance sub-state, and manual closure.
 *
 * ⚠ FOUR SPANS of the old `admin-api.ts` (1192-1213, 1594, 1614-1631, 1883-1952). The single
 * line 1594 is the section banner that belongs to the bursary calls below it; the helper it
 * used to sit above (`adminBursaryPost`) is shared and now lives in `./client`.
 */
import type { BursaryAgreement } from '@/lib/api'

import { adminBursaryPost, adminMutate } from './client'
import type { ApiOptions } from './client'
import type { AdminScholarshipDetail } from './applications'

export type MaintenanceSubstate = 'on_track' | 'probation' | 'on_hold' | 'ready_to_close'
export type ClosureReason = 'graduated' | 'completed' | 'withdrawn' | 'lapsed' | 'terminated'

/** Post-award S4: one disbursement tranche. Admin-facing — funder link by id only,
 *  never a sponsor identity (anonymity holds). */
export interface AdminDisbursement {
  id: number
  sequence: number
  amount: string
  status: 'scheduled' | 'due' | 'released' | 'withheld' | 'returned'
  label: string
  scheduled_for: string | null
  released_at: string | null
  actioned_by: string
  reference: string
  note: string
  sponsorship_id: number | null
  created_at: string
}

export type DisbursementAction = 'release' | 'withhold' | 'return' | 'mark_due'

// ── Conditional Bursary Award Agreement (admin actions) ─────────────────────
/** The Foundation countersignature on a student's bursary agreement. SUPER-ONLY
 *  (the backend gates it). Returns the updated agreement (Foundation now signed). */
export async function adminCountersignBursary(applicationId: number, options?: ApiOptions): Promise<BursaryAgreement> {
  return adminBursaryPost(
    `/api/v1/admin/scholarship/applications/${applicationId}/bursary-agreement/countersign/`, {}, options)
}

/** The partner organisation's (non-blocking) witness attestation. The backend
 *  allows the referring-org admin or a super; anyone else gets a 403 (surfaced
 *  via err.status === 403). `witnessName` is the optional named signatory. */
export async function adminWitnessBursary(
  applicationId: number, witnessName?: string, options?: ApiOptions,
): Promise<BursaryAgreement> {
  return adminBursaryPost(
    `/api/v1/admin/scholarship/applications/${applicationId}/bursary-agreement/witness/`,
    witnessName ? { witness_name: witnessName } : {}, options)
}

/** Set (or clear with null) the recommended assistance amount the reviewer proposes. */
export async function setAwardAmount(
  id: number,
  amount: number | null,
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/award-amount/`,
    'POST',
    { amount },
    options,
  )
}

// ── Post-award S4: disbursement/tranche ledger ──
export async function scheduleTranche(
  id: number,
  payload: { amount: number | string; sequence?: number; label?: string; scheduled_for?: string | null },
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/disbursements/`,
    'POST',
    payload,
    options,
  )
}

export async function actOnDisbursement(
  disbursementId: number,
  action: DisbursementAction,
  payload?: { note?: string },
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/disbursements/${disbursementId}/${action}/`,
    'POST',
    payload ?? {},
    options,
  )
}

// ── Post-award S5: maintenance sub-state ──
export async function setMaintenanceSubstate(
  id: number,
  substate: MaintenanceSubstate,
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/maintenance/`,
    'POST',
    { substate },
    options,
  )
}

// ── Post-award S6: manual closure ──
export async function closeApplication(
  id: number,
  closureReason: ClosureReason,
  options?: ApiOptions,
): Promise<AdminScholarshipDetail> {
  return adminMutate<AdminScholarshipDetail>(
    `/api/v1/admin/scholarship/applications/${id}/close/`,
    'POST',
    { closure_reason: closureReason },
    options,
  )
}


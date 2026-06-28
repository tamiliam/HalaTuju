/**
 * Post-award S4 — pure display/logic helpers for the disbursement (tranche) ledger.
 *
 * Kept framework-free so the node-env jest suite can unit-test the round-trip
 * (the frontend jest runs in node — no DOM/RTL; testable logic lives in lib/*).
 */
import type { AdminDisbursement, DisbursementAction } from './admin-api'

/** The application statuses where a tranche may be scheduled/acted on (funded). */
export const FUNDED_STATUSES = ['active', 'maintenance'] as const

export function isFunded(status: string | null | undefined): boolean {
  return !!status && (FUNDED_STATUSES as readonly string[]).includes(status)
}

/** A pill tone per tranche status (maps to the cockpit's existing tone classes). */
export function disbursementTone(status: AdminDisbursement['status']): string {
  switch (status) {
    case 'released':
      return 'green'
    case 'due':
      return 'amber'
    case 'withheld':
      return 'red'
    case 'returned':
      return 'grey'
    default:
      return 'blue' // scheduled
  }
}

/** The i18n key suffix for a status label (admin.disbursement.status.*). */
export function statusKey(status: AdminDisbursement['status']): string {
  return `admin.disbursement.status.${status}`
}

/** Which actions are valid from a given status (drives which buttons render). */
export function actionsFor(status: AdminDisbursement['status']): DisbursementAction[] {
  switch (status) {
    case 'scheduled':
      return ['release', 'withhold', 'mark_due']
    case 'due':
      return ['release', 'withhold']
    case 'released':
      return ['return']
    default:
      return [] // withheld / returned are terminal in the S4 ledger
  }
}

/** The next tranche sequence number for a fresh schedule (max existing + 1). */
export function nextSequence(rows: readonly AdminDisbursement[]): number {
  return rows.reduce((max, d) => Math.max(max, d.sequence), 0) + 1
}

/** Total money actually released (paid out), as a number for display. */
export function totalReleased(rows: readonly AdminDisbursement[]): number {
  return rows
    .filter((d) => d.status === 'released')
    .reduce((sum, d) => sum + (parseFloat(d.amount) || 0), 0)
}

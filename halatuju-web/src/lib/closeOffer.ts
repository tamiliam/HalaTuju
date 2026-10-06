/**
 * Which Close card the officer cockpit offers, and with which reasons (TD-352, 2026-10-06).
 *
 * Owner ruling (option A): a stalled application is released by an officer closing it by hand.
 * The api (`closure.close_application`) closes from EVERY in-play status, with a reason that fits
 * the stage. This is the web's copy of that reasons-by-stage table, so the card never offers a
 * reason the api would refuse with `reason_not_allowed`. The api's other refusal,
 * `sponsorship_open` (a live offer or paid money, before a funded state), is mirrored only where it
 * is certain: an `awarded` case always holds its offer, so no card is offered there. Elsewhere the
 * admin detail does not carry the sponsorship, so the server answers and the card shows why.
 *
 * drift-test: halatuju-web/src/lib/__tests__/closeOfferDrift.test.ts
 */
import type { ClosureReason } from '@/lib/admin-api/lifecycle'

/** Before a funder has committed. A close here frees the student and emails her. */
export const PRE_AWARD_STATUSES = [
  'submitted', 'shortlisted', 'profile_complete', 'interviewing', 'interviewed', 'recommended',
] as const
/** A funder has committed (awarded) or the student is funded (active / maintenance). */
export const POST_AWARD_STATUSES = ['awarded', 'active', 'maintenance'] as const

export const PRE_AWARD_REASONS: readonly ClosureReason[] = ['stalled', 'withdrawn']
export const POST_AWARD_REASONS: readonly ClosureReason[] = [
  'graduated', 'completed', 'withdrawn', 'lapsed', 'terminated', 'stalled',
]

export interface CloseOffer {
  show: boolean
  preAward: boolean
  reasons: readonly ClosureReason[]
}

/**
 * `orgSuper` — the viewer is a super or an org_admin. The api closes a PRE-award case for those two
 * only (`AdminCloseApplicationView`, the org-reject gate), so for anyone else the card is not
 * offered there at all rather than showing a button that answers 403.
 */
export function closeOffer(status: string, orgSuper: boolean): CloseOffer {
  if ((PRE_AWARD_STATUSES as readonly string[]).includes(status)) {
    return orgSuper
      ? { show: true, preAward: true, reasons: PRE_AWARD_REASONS }
      : { show: false, preAward: true, reasons: [] }
  }
  // `awarded` always holds the sponsor's offer, so the api refuses every close there
  // (`sponsorship_open`) and no admin door releases it today (TD-366, an owner decision). The card is
  // not offered rather than show a button that always refuses (TD-363).
  if (status === 'awarded') return { show: false, preAward: false, reasons: [] }
  if ((POST_AWARD_STATUSES as readonly string[]).includes(status)) {
    return { show: true, preAward: false, reasons: POST_AWARD_REASONS }
  }
  return { show: false, preAward: false, reasons: [] }
}

/**
 * The api's refusal codes and the `admin.closure.error.*` sentence each one shows.
 * `reason_not_allowed` shares "Choose a valid closure reason." — the dropdown never offers a
 * refused reason, so it is reached only by a stale tab, and every en.json key ships on most routes.
 */
const ERROR_KEY = new Map([
  ['bad_reason', 'bad_reason'], ['reason_not_allowed', 'bad_reason'],
  ['not_closeable', 'not_closeable'], ['sponsorship_open', 'sponsorship_open'],
])

/** The message key for a failed close: its sentence when the code is known, else generic. */
export function closeErrorKey(code: string | undefined): string {
  return `admin.closure.error.${ERROR_KEY.get(code ?? '') ?? 'generic'}`
}

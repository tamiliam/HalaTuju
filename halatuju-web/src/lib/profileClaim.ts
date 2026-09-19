/**
 * TD-254 — what the browser is allowed to know about claiming a profile.
 *
 * **THE BROWSER KNOWS NO POLICY.** Whether a claim may proceed, which contact may be
 * challenged and how often, are all decided by `halatuju_api/apps/courses/profile_claim.py`.
 * This file does exactly one thing: turn a refusal CODE the server sent into the i18n key of
 * the sentence a seventeen-year-old should read. Nothing here decides anything.
 *
 * ⚠ **AND IT NEVER LEARNS WHO THE HOLDER IS.** The whole reason TD-254 was rated HIGH is that
 * the old endpoint answered somebody else's IC with that person's NAME. The `exists` response
 * now carries `channels` and nothing else — there is deliberately no `name` in any type here.
 *
 * The refusal vocabulary is the SERVER'S (`REFUSAL_CODES` in that module); this map is kept in
 * step by a test that reads the Python file, so a code added there and not given copy here
 * fails the build rather than reaching a student as a blank panel.
 * drift-test: halatuju-web/src/lib/__tests__/profileClaimCodes.test.ts
 */

/** A challenge channel, as a bare TYPE. Never an address or a number. */
export type ClaimChannel = 'phone' | 'email'

/** Every refusal code the server can send, to the copy it should read as. */
export const CLAIM_REFUSAL_COPY: Record<string, string> = {
  // Nothing on that profile is verified, so there is no door — this is the 90% case
  // (674 profiles hold an IC; 70 have a verified contact) and it routes to a human.
  no_verified_contact: 'authGate.claim.refusal.noContact',
  // The caller already IS somebody. Two real records cannot be merged from a modal.
  caller_has_verified_nric: 'authGate.claim.refusal.cannotMerge',
  caller_has_application: 'authGate.claim.refusal.cannotMerge',
  already_claimed: 'authGate.claim.refusal.cannotMerge',
  caller_is_staff: 'authGate.claim.refusal.cannotMerge',
  // The request does not make sense for this IC — including a client still posting the
  // removed `confirm: true`, which is the old takeover door and now answers here.
  channel_unavailable: 'authGate.claim.refusal.unavailable',
  not_claimable: 'authGate.claim.refusal.unavailable',
  confirm_removed: 'authGate.claim.refusal.unavailable',
  // Transport
  unconfigured: 'authGate.claim.refusal.sendFailed',
  send_failed: 'authGate.claim.refusal.sendFailed',
  rate_limited: 'authGate.claim.refusal.tooMany',
  // The code the student typed
  code_incorrect: 'authGate.claim.refusal.codeIncorrect',
  code_expired: 'authGate.claim.refusal.codeExpired',
  no_pending_code: 'authGate.claim.refusal.codeExpired',
  code_required: 'authGate.claim.refusal.codeExpired',
  too_many_attempts: 'authGate.claim.refusal.tooManyAttempts',
}

/** The message key for a refusal — falling back to the generic one for a code this build has
 *  never heard of, so an older browser against a newer server still says something useful. */
export function claimRefusalKey(code: string | undefined): string {
  return (code && CLAIM_REFUSAL_COPY[code]) || 'authGate.claimError'
}

/** Which "we can send you a code" sentence fits the channels on offer. */
export function claimHelpKey(channels: ClaimChannel[]): string {
  if (channels.length > 1) return 'authGate.claim.helpBoth'
  if (channels[0] === 'phone') return 'authGate.claim.helpPhone'
  return 'authGate.claim.helpEmail'
}

/** The button that sends the code down a given channel. */
export function claimChannelKey(channel: ClaimChannel): string {
  return channel === 'phone' ? 'authGate.claim.channelPhone' : 'authGate.claim.channelEmail'
}

/** The line above the code box, naming the channel the code went down — never the address. */
export function claimCodeHelpKey(channel: ClaimChannel): string {
  return channel === 'phone'
    ? 'authGate.claim.codeHelpPhone'
    : 'authGate.claim.codeHelpEmail'
}

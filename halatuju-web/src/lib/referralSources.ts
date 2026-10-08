/**
 * "Who referred you?" — the choices, their labels, and the submit refusal (per-gift referral
 * sources, Sprint 2, 2026-10-08). A LEAF: no imports, so the apply page, the admin list, the
 * cockpit and the gift Configuration card can all use it without carrying anything else.
 *
 * Owner's rulings: a gift's apply form lists ITS switched-on sources (served by the public intake,
 * the server's names as labels), then the three fixed choices ALWAYS, in this order. Legacy
 * `pushparani` / `govind` are gone (moved to `other`). A code the gift does not offer is REFUSED
 * by the server (`referral_source_not_offered`); the form re-reads the list and asks again.
 *
 * ⚠ The fixed three are a CONSTANT the server also holds (`gift_sources.FIXED_CODES`) — a mirror,
 * so it is guarded, not trusted. drift-test: halatuju-web/src/lib/__tests__/referralSources.test.ts
 */

/** On every form, after the gift's own sources. Labels: `scholarship.apply.org.<code>`. */
export const FIXED_REFERRAL_CODES = ['halatuju', 'social', 'other'] as const

/** One source as the public intake serves it: code and name, nothing else. */
export interface ReferralSource { code: string; name: string }

export interface ReferralOption { code: string; label: string }

type T = (key: string) => string

const isFixed = (code: string) => (FIXED_REFERRAL_CODES as readonly string[]).includes(code)

/**
 * The apply form's options: the gift's served sources (server name as label), then the fixed three
 * (i18n labels). A served code that collides with a fixed one is dropped — the fixed one, with its
 * own label, stands. `null`/absent sources (an older api, a failed intake) → the fixed three only.
 */
export function referralOptions(sources: ReferralSource[] | null | undefined, t: T): ReferralOption[] {
  const seen = new Set<string>()
  const own = (sources ?? []).filter((s) => {
    if (!s.code || isFixed(s.code) || seen.has(s.code)) return false
    seen.add(s.code)
    return true
  }).map((s) => ({ code: s.code, label: s.name || s.code }))
  return [...own, ...FIXED_REFERRAL_CODES.map((code) => ({ code, label: t(`scholarship.apply.org.${code}`) }))]
}

/**
 * A stored code's full name for an ADMIN surface (a tooltip, a filter): the fixed three from i18n,
 * a source from the server's names, else the code itself — never a raw message key.
 */
export function referralLabel(code: string | null | undefined, t: T, names?: Record<string, string>): string {
  if (!code) return ''
  if (isFixed(code)) return t(`scholarship.apply.org.${code}`)
  return names?.[code] || code
}

/** The submit was refused because the code is not offered for this gift (`ApplicationListCreateView`). */
export function isReferralNotOffered(err: unknown): boolean {
  return (err as { bodyCode?: string } | null)?.bodyCode === 'referral_source_not_offered'
}

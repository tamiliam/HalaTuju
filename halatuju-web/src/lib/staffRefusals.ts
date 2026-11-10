/**
 * Sprint M1a review: the `has_scholars` refusal in the reader's language.
 *
 * Remove from Mentors (`stop`), Delete and, since owner ruling O18, Revoke (Suspend) are REFUSED with 409
 * `has_scholars` while the person still mentors anyone; nothing is ended. The 409 carries `scholars_now`
 * (the count), which `adminMutate` keeps on the error's `body`. Each caller passes its own message key
 * (the Mentors table's or the person / Team tables' one); any other error gives `null`, so the caller
 * keeps its own handling.
 */
type T = (k: string, vars?: Record<string, string>) => string

export const HAS_SCHOLARS = 'has_scholars'

export function scholarsRefusal(err: unknown, t: T, key = 'admin.person.revokeHasScholars'): string | null {
  const e = err as { code?: string; body?: { scholars_now?: unknown } } | null
  if (e?.code !== HAS_SCHOLARS) return null
  const n = e.body?.scholars_now
  return t(key, { n: typeof n === 'number' ? String(n) : '' })
}

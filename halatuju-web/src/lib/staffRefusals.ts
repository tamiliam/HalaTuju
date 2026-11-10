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

/**
 * Sprint M1b: every refusal a Remove, Suspend or Delete can meet, in the reader's words — the greyed
 * button's tip (owner O17) and the Remove sheet's error. `admin.refusal.<code>`; a code that waits on a
 * count (`COUNTED`) reads it from the row or the 409's body and says it ("Reassign their 4 open cases
 * first"), with `.one` / `.many`, or `.some` when no count came. An unknown code gives `null`, so the
 * caller keeps the server's own sentence.
 */
export const COUNTED: Record<string, string> = {
  has_open_cases: 'open_cases',
  run_in_progress: 'runs_in_progress',
  has_scholars: 'scholars_now',
}

const PLAIN = new Set([
  'last_table', 'mentors_only', 'lead_fixed', 'qc_sees_all', 'not_arrived', 'self', 'last_org_admin',
  'sole_org_admin', 'has_unfinished_work', 'staff_mentor',
  // 409 on an Erase whose person gained work on record since the list was read: the list reloads.
  'has_work',
])

export function refusalWords(code: string | null | undefined, t: T,
                             counts: Record<string, unknown> = {}): string | null {
  if (!code) return null
  if (PLAIN.has(code)) return t(`admin.refusal.${code}`)
  const field = COUNTED[code]
  if (!field) return null
  const n = counts[field]
  if (typeof n !== 'number' || n < 1) return t(`admin.refusal.${code}.some`)
  return t(`admin.refusal.${code}.${n === 1 ? 'one' : 'many'}`, { n: String(n) })
}

/** A thrown refusal (`adminMutate` keeps `code` and the whole `body`) in the reader's words, or `null`. */
export function refusalOf(err: unknown, t: T): string | null {
  const e = err as { code?: string; body?: Record<string, unknown> } | null
  return refusalWords(e?.code, t, e?.body ?? {})
}

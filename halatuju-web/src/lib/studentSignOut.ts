/**
 * THE student sign-out — one small eager helper (Mobile M2 review), used by the header's menus and
 * by the header's own fallback when the menus' chunk cannot load.
 *
 *   1. wipe every `halatuju_` key she holds (grades, profile, the bursary hint; `clearAll` keeps the
 *      admin and sponsor sessions, which are other people's);
 *   2. end the Supabase session — and if the server could not be reached (`{ error }`, or a throw),
 *      forget it on this device anyway (`dropStudentSession`): auth-js keeps the stored session on a
 *      failed sign-out, and the next person on a shared phone would be signed in as her;
 *   3. wipe again — anything written while the sign-out was in flight goes too;
 *   4. start again from Home with a full load, so no screen keeps her data in memory.
 *
 * Kept OUT of `lib/supabase.ts` on purpose: that module rides on every route (the console's too),
 * and this is only needed where a student can sign out.
 */
import { clearAll } from '@/lib/storage'
import { getSupabase, signOut } from '@/lib/supabase'
import { defaultStorageKey } from '@/lib/supabaseAuthClient'

/**
 * End the student session ON THIS DEVICE without the server. auth-js 2.95's `signOut` asks the
 * server first and, on a network or 5xx error, returns `{ error }` WITHOUT removing the stored
 * session; it has no public "forget locally" call. So: stop its refresh timer (it could write the
 * session back), then remove the student client's own keys — its session, PKCE verifier and user
 * copy, all named from `defaultStorageKey` (the same function the client is built with). The admin
 * and sponsor clients store under their own keys and are untouched.
 */
export function dropStudentSession(): void {
  try { void getSupabase().auth.stopAutoRefresh() } catch { /* no client (no credentials): nothing runs */ }
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  if (!url) return
  const key = defaultStorageKey(url)
  for (const k of [key, `${key}-code-verifier`, `${key}-user`]) {
    try { localStorage.removeItem(k) } catch { /* storage unavailable */ }
  }
}

export async function signOutStudent(
  /** Where to go afterwards — a full load. Injectable for tests (jsdom cannot navigate). */
  go: (url: string) => void = (url) => { window.location.href = url },
): Promise<void> {
  clearAll()
  try {
    const { error } = await signOut()
    if (error) dropStudentSession()
  } catch {
    dropStudentSession()
  }
  clearAll()
  go('/')
}

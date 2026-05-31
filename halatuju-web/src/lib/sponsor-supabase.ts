import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let _sponsorSupabase: SupabaseClient | null = null

/**
 * Separate Supabase client for sponsor auth (mirrors the admin client pattern).
 * Its own storage key keeps the sponsor session isolated from the student and
 * admin sessions — a sponsor signs in with email/password or Google and never
 * touches the student anonymous-session / NRIC machinery.
 */
export function getSponsorSupabase(): SupabaseClient {
  if (!_sponsorSupabase) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    if (!url || !key) {
      throw new Error('Supabase credentials not configured')
    }
    _sponsorSupabase = createClient(url, key, {
      auth: {
        storageKey: 'halatuju_sponsor_session',
      },
    })
  }
  return _sponsorSupabase
}

export async function sponsorSignInWithPassword(email: string, password: string) {
  const { data, error } = await getSponsorSupabase().auth.signInWithPassword({ email, password })
  return { data, error }
}

export async function sponsorSignUpWithPassword(
  email: string,
  password: string,
  fullName?: string,
) {
  const { data, error } = await getSponsorSupabase().auth.signUp({
    email,
    password,
    options: {
      // Stash the name so it survives an email-confirmation gap (no session yet).
      data: fullName ? { full_name: fullName } : undefined,
      emailRedirectTo: `${window.location.origin}/sponsor/login`,
    },
  })
  return { data, error }
}

export async function sponsorSignInWithGoogle() {
  const { data, error } = await getSponsorSupabase().auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/sponsor/auth/callback`,
    },
  })
  return { data, error }
}

export async function sponsorResetPassword(email: string) {
  const { error } = await getSponsorSupabase().auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/sponsor/login`,
  })
  return { error }
}

export async function sponsorSignOut() {
  const { error } = await getSponsorSupabase().auth.signOut()
  return { error }
}

export async function getSponsorSession() {
  const { data: { session }, error } = await getSponsorSupabase().auth.getSession()
  return { session, error }
}

import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import { getTurnstileToken } from '@/lib/turnstile'

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
        // PKCE so this OAuth session can't be read off the URL hash by the
        // globally-mounted student client (which would leak sponsor → student).
        flowType: 'pkce',
      },
    })
  }
  return _sponsorSupabase
}

export async function sponsorSignInWithPassword(email: string, password: string) {
  const captchaToken = await getTurnstileToken('sponsor_signin')
  const { data, error } = await getSponsorSupabase().auth.signInWithPassword({
    email,
    password,
    options: captchaToken ? { captchaToken } : undefined,
  })
  return { data, error }
}

export async function sponsorSignUpWithPassword(
  email: string,
  password: string,
  fullName?: string,
) {
  const captchaToken = await getTurnstileToken('sponsor_signup')
  const { data, error } = await getSponsorSupabase().auth.signUp({
    email,
    password,
    options: {
      // Stash the name so it survives an email-confirmation gap (no session yet).
      data: fullName ? { full_name: fullName } : undefined,
      // Confirmation lands on a dedicated handler that logs the sponsor in when it can
      // (same browser) and otherwise sends them to sign in with a friendly notice —
      // never the raw PKCE error a cross-device click used to produce.
      emailRedirectTo: `${window.location.origin}/sponsor/auth/confirm`,
      ...(captchaToken ? { captchaToken } : {}),
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
  const captchaToken = await getTurnstileToken('sponsor_reset')
  const { error } = await getSponsorSupabase().auth.resetPasswordForEmail(email, {
    // Land on the set-a-new-password page (was /sponsor/login, which had no form to
    // actually change the password — the reset dead-ended).
    redirectTo: `${window.location.origin}/sponsor/auth/reset`,
    ...(captchaToken ? { captchaToken } : {}),
  })
  return { error }
}

export async function sponsorSignOut() {
  // scope: 'local' — end only the sponsor session, not the user's student/admin
  // sessions (same Supabase identity across the three isolated clients).
  const { error } = await getSponsorSupabase().auth.signOut({ scope: 'local' })
  return { error }
}

export async function getSponsorSession() {
  const { data: { session }, error } = await getSponsorSupabase().auth.getSession()
  return { session, error }
}

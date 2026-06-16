import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import { getTurnstileToken } from '@/lib/turnstile'

let _adminSupabase: SupabaseClient | null = null

/**
 * Separate Supabase client for admin auth.
 * Uses a different storage key so admin and student sessions don't conflict.
 */
export function getAdminSupabase(): SupabaseClient {
  if (!_adminSupabase) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    if (!url || !key) {
      throw new Error('Supabase credentials not configured')
    }
    _adminSupabase = createClient(url, key, {
      auth: {
        storageKey: 'halatuju_admin_session',
        // PKCE so this OAuth session can't be read off the URL hash by the
        // globally-mounted student client (which would leak admin → student).
        flowType: 'pkce',
      },
    })
  }
  return _adminSupabase
}

export async function adminSignInWithPassword(email: string, password: string) {
  const captchaToken = await getTurnstileToken('admin_signin')
  const { data, error } = await getAdminSupabase().auth.signInWithPassword({
    email,
    password,
    options: captchaToken ? { captchaToken } : undefined,
  })
  return { data, error }
}

export async function adminSignInWithGoogle() {
  const { data, error } = await getAdminSupabase().auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/admin/auth/callback`,
    },
  })
  return { data, error }
}

export async function adminResetPassword(email: string) {
  const captchaToken = await getTurnstileToken('admin_reset')
  const { error } = await getAdminSupabase().auth.resetPasswordForEmail(email, {
    // Land on the set-password page where the recovery session lets them choose a password.
    redirectTo: `${window.location.origin}/admin/set-password`,
    ...(captchaToken ? { captchaToken } : {}),
  })
  return { error }
}

/** Set a new password on the CURRENT session (used by the set-password page after the user
 *  arrives via an invite or password-reset email link). */
export async function adminUpdatePassword(password: string) {
  const { data, error } = await getAdminSupabase().auth.updateUser({ password })
  return { data, error }
}

export async function adminSignOut() {
  // scope: 'local' — end only the admin session, not the user's student/sponsor
  // sessions (same Supabase identity across the three isolated clients).
  const { error } = await getAdminSupabase().auth.signOut({ scope: 'local' })
  return { error }
}

export async function getAdminSession() {
  const { data: { session }, error } = await getAdminSupabase().auth.getSession()
  return { session, error }
}

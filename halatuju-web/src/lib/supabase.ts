import { createAuthOnlyClient, type AuthOnlyClient } from '@/lib/supabaseAuthClient'

let _supabase: AuthOnlyClient | null = null

// Lazy-initialised browser client (avoids build-time env var errors). Auth-only: see
// lib/supabaseAuthClient.ts (TD-300) — it keeps the default storage key every student is signed
// in under.
export function getSupabase(): AuthOnlyClient {
  if (!_supabase) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
    if (!url || !key) {
      throw new Error('Supabase credentials not configured')
    }
    // flowType: 'pkce' — OAuth returns a `?code=` that can only be exchanged with
    // the code-verifier stored under THIS client's storage key. The default
    // ('implicit') returns the session in the URL hash, which any mounted client
    // (this student client is mounted globally, incl. on /admin/* + /sponsor/*
    // callbacks) would happily read — leaking the admin/sponsor Google session into
    // the student session. PKCE closes that bleed.
    _supabase = createAuthOnlyClient(url, key, { flowType: 'pkce' })
  }
  return _supabase
}

// Auth helper functions
export async function signInWithPhone(_phone: string) {
  // Phone/OTP login is not yet implemented
  return {
    data: null,
    error: { message: 'Phone login is coming soon. Please use Google sign-in for now.' },
  }
}

export async function verifyOTP(phone: string, token: string) {
  const { data, error } = await getSupabase().auth.verifyOtp({
    phone,
    token,
    type: 'sms',
  })
  return { data, error }
}

export async function signInWithGoogle() {
  const { data, error } = await getSupabase().auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  })
  return { data, error }
}

export async function signOut() {
  // scope: 'local' — only end THIS (student) session. The default 'global' revokes
  // every session for the user server-side, which would log out the admin/sponsor
  // sessions too (same Supabase identity across the three isolated clients).
  const { error } = await getSupabase().auth.signOut({ scope: 'local' })
  return { error }
}

export async function getSession() {
  const { data: { session }, error } = await getSupabase().auth.getSession()
  return { session, error }
}

export async function getUser() {
  const { data: { user }, error } = await getSupabase().auth.getUser()
  return { user, error }
}

// `signInAnonymously` was removed in the 2026-11-19 captcha repair: the AuthProvider no longer
// mints an anonymous session on page load, and nothing else called it (see auth-context.tsx).

export async function linkIdentity(provider: 'google') {
  const { data, error } = await getSupabase().auth.linkIdentity({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/callback`,
    },
  })
  return { data, error }
}
